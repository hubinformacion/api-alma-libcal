import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from alma_libcal.connectors.sheets import FilePublisher, SheetsPublisher
from alma_libcal.demo import demo_config, run_demo
from alma_libcal.errors import PilotError, PublicationError, SourceError
from alma_libcal.models import Batch, Interval, Record
from alma_libcal.service import extract, publish
from alma_libcal.storage import Store, exclusive_lock


class Source:
    def __init__(self, result):
        self.result = result

    def fetch(self, interval):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class CapturePublisher:
    def __init__(self, error=None):
        self.tables = None
        self.error = error

    def publish(self, tables):
        if self.error:
            raise self.error
        self.tables = tables


class Response:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        return self.payload


class Session:
    def __init__(self, fail=False, metadata=None):
        self.calls = []
        self.fail = fail
        self.metadata = metadata or {"sheets": [{"properties": {"sheetId": 0, "title": "prestamos", "gridProperties": {"rowCount": 100, "columnCount": 20}}}]}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if method == "GET":
            return Response(self.metadata)
        return Response({}, 503 if self.fail else 200)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = Store(self.directory / "pilot.sqlite3")
        self.addCleanup(self.store.close)
        self.interval = Interval(date(2026, 10, 6), date(2026, 10, 6))
        self.record = Record("prestamos", "L1", "2026-10-06", user_id="000123", resource_id="R1")
        self.report = lambda message: None

    def save(self, record):
        run_id = self.store.start_run(record.dataset, "extract", self.interval)
        self.store.save(record.dataset, self.interval, Batch([record]), run_id)

    def test_repeated_extraction_upserts_and_keeps_leading_zeros(self):
        self.save(self.record)
        self.save(replace(self.record, status="Complete"))
        self.assertEqual(self.store.count("prestamos"), 1)
        self.assertEqual(self.store.records("prestamos")[0].status, "Complete")
        self.assertEqual(self.store.records("prestamos")[0].user_id, "000123")

    def test_cancelled_booking_updates_without_duplicate(self):
        booking = Record("reservas", "B1", "2026-10-06", status="Confirmed")
        self.save(booking)
        self.save(replace(booking, status="Cancelled"))
        self.assertEqual(self.store.count("reservas"), 1)
        self.assertEqual(self.store.records("reservas")[0].status, "Cancelled")

    def test_participant_emails_survive_storage_and_publication_without_extra_bookings(self):
        booking = Record("reservas", "B1", "2026-10-06", source_user_email="one@example.invalid",
                         booking_form_id="8253", booking_form_answer_1="two@example.invalid",
                         booking_form_answer_2="three@example.invalid")
        self.save(booking)
        self.save(replace(booking, status="Cancelled by Admin"))
        self.assertEqual(self.store.count("reservas"), 1)
        publisher = CapturePublisher()
        self.assertTrue(publish(self.store, publisher, ["reservas"], self.interval, self.report))
        table = publisher.tables["reservas"]
        row = dict(zip(table[0], table[1]))
        self.assertEqual(row["source_user_email"], "one@example.invalid")
        self.assertEqual(row["booking_form_answer_1"], "two@example.invalid")
        self.assertEqual(row["booking_form_answer_2"], "three@example.invalid")
        self.assertEqual(row["status"], "Cancelled by Admin")

    def test_old_payloads_load_with_empty_new_contact_fields(self):
        self.save(self.record)
        payload = dict(self.store.db.execute("SELECT payload FROM records").fetchone())["payload"]
        old = json.loads(payload)
        for key in ("source_user_email", "booking_form_id", "booking_form_answer_1", "booking_form_answer_2"):
            old.pop(key)
        with self.store.db:
            self.store.db.execute("UPDATE records SET payload=?", (json.dumps(old),))
        self.assertEqual(self.store.records("prestamos")[0].source_user_email, "")
        self.assertEqual(self.store.records("prestamos")[0].booking_form_answer_1, "")

    def test_renewal_quantity_updates_instead_of_accumulating(self):
        renewal = Record("renovaciones", "L1:2026-10-06", "2026-10-06", quantity=2)
        self.save(renewal)
        self.save(replace(renewal, quantity=3))
        self.assertEqual(self.store.count("renovaciones"), 1)
        self.assertEqual(self.store.records("renovaciones")[0].quantity, 3)

    def test_retrospective_overlap_preserves_existing_records(self):
        self.save(self.record)
        old = replace(self.record, record_id="OLD", activity_date="2026-01-02")
        historical = Interval(date(2026, 1, 1), date(2026, 10, 6))
        run_id = self.store.start_run("prestamos", "extract", historical)
        self.store.save("prestamos", historical, Batch([old, self.record]), run_id)
        self.assertEqual(self.store.count("prestamos"), 2)
        self.save(self.record)
        self.assertEqual(self.store.count("prestamos"), 2)

    def test_failed_extraction_preserves_previous_snapshot_and_other_source(self):
        self.save(self.record)
        revisions = self.store.revisions(["prestamos"])
        successful, failed = extract(self.store, {"prestamos": Source(SourceError("unavailable")),
            "reservas": Source(Batch([Record("reservas", "B1", "2026-10-06")]))}, self.interval, self.report)
        self.assertEqual(successful, ["reservas"])
        self.assertEqual(failed, ["prestamos"])
        self.assertEqual(self.store.revisions(["prestamos"]), revisions)
        capture = CapturePublisher()
        self.assertTrue(publish(self.store, capture, successful, self.interval, self.report))
        self.assertNotIn("prestamos", capture.tables)
        self.assertIn("reservas", capture.tables)
        control = capture.tables["control"]
        loan_control = dict(zip(control[0], control[1]))
        self.assertEqual(loan_control["last_extraction_status"], "extraction_failed")

    def test_invalid_duplicate_batch_cannot_partially_save(self):
        self.save(self.record)
        invalid = Batch([replace(self.record, status="wrong"), self.record])
        successful, failed = extract(self.store, {"prestamos": Source(invalid)}, self.interval, self.report)
        self.assertEqual(successful, [])
        self.assertEqual(failed, ["prestamos"])
        self.assertEqual(self.store.records("prestamos")[0].status, "")

    def test_failed_publication_remains_pending_and_retries_without_extraction(self):
        self.save(self.record)
        self.assertFalse(publish(self.store, CapturePublisher(PublicationError("offline")), ["prestamos"], self.interval, self.report))
        control = self.store.control()
        state = dict(zip(control[0], control[1]))
        self.assertEqual(state["pending"], "sí")
        self.assertEqual(state["last_status"], "publication_failed")
        capture = CapturePublisher()
        self.assertTrue(publish(self.store, capture, ["prestamos"], self.interval, self.report))
        state = dict(zip(self.store.control()[0], self.store.control()[1]))
        self.assertEqual(state["pending"], "no")
        self.assertEqual(capture.tables["prestamos"][1][2], "000123")

    def test_missing_user_is_flagged_without_inventing_identity(self):
        self.save(replace(self.record, user_id=""))
        table = self.store.table("prestamos")
        row = dict(zip(table[0], table[1]))
        self.assertEqual(row["user_id"], "")
        self.assertEqual(row["user_id_missing"], "sí")

    def test_valid_empty_batch_creates_headers_and_preserves_history(self):
        self.save(self.record)
        run_id = self.store.start_run("prestamos", "extract", self.interval)
        self.store.save("prestamos", self.interval, Batch([]), run_id)
        self.assertEqual(self.store.count("prestamos"), 1)
        run_id = self.store.start_run("reservas", "extract", self.interval)
        self.store.save("reservas", self.interval, Batch([]), run_id)
        self.assertEqual(len(self.store.table("reservas")), 1)

    def test_publication_keeps_previous_extraction_failure_visible(self):
        self.save(self.record)
        extract(self.store, {"prestamos": Source(SourceError("unavailable"))}, self.interval, self.report)
        publish(self.store, CapturePublisher(), ["prestamos"], self.interval, self.report)
        state = dict(zip(self.store.control()[0], self.store.control()[1]))
        self.assertEqual(state["last_status"], "published")
        self.assertEqual(state["last_extraction_status"], "extraction_failed")

    def test_lock_rejects_parallel_execution(self):
        path = self.directory / "lock-test.sqlite3"
        with exclusive_lock(path):
            with self.assertRaises(PilotError):
                with exclusive_lock(path):
                    pass

    def test_google_atomic_batch_preserves_text_and_does_not_touch_other_tabs(self):
        config = demo_config(self.directory)
        config.raw["google"] = {"spreadsheet_id": "test_spreadsheet"}
        session = Session()
        self.save(replace(self.record, resource_name="=IMPORTXML(secret)"))
        SheetsPublisher(config, session).publish({"prestamos": self.store.table("prestamos"), "control": self.store.control()})
        self.assertEqual([call[0] for call in session.calls], ["GET", "POST"])
        self.assertTrue(session.calls[1][1].endswith(":batchUpdate"))
        requests = session.calls[1][2]["json"]["requests"]
        self.assertEqual(requests[1]["updateCells"]["range"], {"sheetId": 0})
        cells = requests[2]["updateCells"]["rows"][1]["values"]
        self.assertEqual(cells[2]["userEnteredValue"], {"stringValue": "000123"})
        self.assertEqual(cells[4]["userEnteredValue"], {"stringValue": "=IMPORTXML(secret)"})
        self.assertEqual(cells[12]["userEnteredValue"], {"numberValue": 1})

    def test_google_failure_does_not_mark_snapshot_published(self):
        config = demo_config(self.directory)
        config.raw["google"] = {"spreadsheet_id": "test_spreadsheet"}
        self.save(self.record)
        session = Session(fail=True)
        self.assertFalse(publish(self.store, SheetsPublisher(config, session), ["prestamos"], self.interval, self.report))
        state = dict(zip(self.store.control()[0], self.store.control()[1]))
        self.assertEqual(state["published_revision"], 0)

    def test_oversize_publication_does_not_clear_google(self):
        config = demo_config(self.directory)
        config.raw["google"] = {"spreadsheet_id": "test_spreadsheet"}
        session = Session()
        with self.assertRaisesRegex(PublicationError, "tamaño"):
            SheetsPublisher(config, session).publish({"prestamos": [["header"], ["x" * 1_800_001]]})
        self.assertEqual([call[0] for call in session.calls], ["GET"])

    def test_demo_repeated_run_is_offline_and_deduplicated(self):
        directory = self.directory / "demo"
        self.assertEqual(run_demo(directory), 0)
        self.assertEqual(run_demo(directory), 0)
        output = json.loads((directory / "sheets.json").read_text())
        self.assertEqual(len(output["prestamos"]), 3)
        self.assertEqual(len(output["renovaciones"]), 2)
        self.assertEqual(len(output["reservas"]), 4)
