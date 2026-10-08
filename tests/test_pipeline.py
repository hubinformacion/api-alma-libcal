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
                         booking_form_answer_2="three@example.invalid", seat_id="000123", seat_name="Puesto 01")
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
        self.assertEqual(row["seat_id"], "000123")
        self.assertEqual(row["seat_name"], "Puesto 01")

    def test_old_payloads_load_with_empty_new_contact_fields(self):
        self.save(self.record)
        payload = dict(self.store.db.execute("SELECT payload FROM records").fetchone())["payload"]
        old = json.loads(payload)
        for key in ("source_user_email", "booking_form_id", "booking_form_answer_1", "booking_form_answer_2", "seat_id", "seat_name"):
            old.pop(key)
        with self.store.db:
            self.store.db.execute("UPDATE records SET payload=?", (json.dumps(old),))
        self.assertEqual(self.store.records("prestamos")[0].source_user_email, "")
        self.assertEqual(self.store.records("prestamos")[0].booking_form_answer_1, "")
        self.assertEqual(self.store.records("prestamos")[0].seat_id, "")

    def test_renewal_quantity_updates_instead_of_accumulating(self):
        renewal = Record("renovaciones", "L1:2026-10-06", "2026-10-06", quantity=2)
        self.save(renewal)
        self.save(replace(renewal, quantity=3))
        self.assertEqual(self.store.count("renovaciones"), 1)
        self.assertEqual(self.store.records("renovaciones")[0].quantity, 3)

    def test_alma_reports_use_exact_distinct_schemas_and_original_loan_id(self):
        loan_headers = 'loan_id source_user_id source_user_email item_id item_mms_id item_barcode item_material_type item_policy item_title loan_date loan_time in_house_loan_indicator loan_campus_code loan_campus loan_library_code loan_desk_code loan_desk_name loan_desk_description loan_status'.split()
        renewal_headers = 'loan_id source_user_id source_user_email item_id item_mms_id item_barcode item_material_type item_policy item_title renewal_date renewal_campus_code renewal_campus_name renewal_quantity loan_status'.split()
        renewal = Record('renovaciones', 'L1:2026-10-06:CUS', '2026-10-06', loan_id='L1', quantity=2,
                         user_id='000123', resource_id='I1', item_mms_id='990000000123456789',
                         item_barcode='000045', item_material_type='Libro', item_policy='Domicilio')
        self.save(renewal)
        self.save(replace(self.record, loan_id='L1', loan_time='14:05', loan_library_code='LIB',
                          loan_desk_code='DESK', loan_desk_name='Módulo 1', loan_desk_description='Cusco'))
        for dataset, expected in [('prestamos',loan_headers),('renovaciones',renewal_headers)]:
            self.assertEqual(self.store.table(dataset)[0], expected)
        row = dict(zip(*self.store.table('renovaciones')))
        self.assertEqual(row['loan_id'], 'L1')
        self.assertEqual(row['renewal_quantity'], 2)
        self.assertEqual(row['item_barcode'], '000045')
        self.assertEqual(row['item_mms_id'], '990000000123456789')
        loan = dict(zip(*self.store.table('prestamos')))
        self.assertEqual(loan['loan_time'], '14:05')
        self.assertEqual(loan['loan_desk_name'], 'Módulo 1')

    def test_legacy_renewal_id_is_recovered_without_inventing_missing_item_fields(self):
        self.save(Record('renovaciones', 'L1:2026-10-06:CUS', '2026-10-06', quantity=2))
        row = dict(zip(*self.store.table('renovaciones')))
        self.assertEqual(row['loan_id'], 'L1')
        self.assertEqual(row['item_barcode'], '')

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
        self.assertEqual(capture.tables["prestamos"][1][capture.tables["prestamos"][0].index("source_user_id")], "000123")

    def test_missing_user_is_flagged_without_inventing_identity(self):
        self.save(replace(self.record, user_id=""))
        table = self.store.table("prestamos")
        row = dict(zip(table[0], table[1]))
        self.assertEqual(row["source_user_id"], "")

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
        self.assertEqual(cells[self.store.table("prestamos")[0].index("source_user_id")]["userEnteredValue"], {"stringValue": "000123"})
        self.assertEqual(cells[self.store.table("prestamos")[0].index("item_title")]["userEnteredValue"], {"stringValue": "=IMPORTXML(secret)"})
        self.assertNotIn("quantity", self.store.table("prestamos")[0])

    def test_google_failure_does_not_mark_snapshot_published(self):
        config = demo_config(self.directory)
        config.raw["google"] = {"spreadsheet_id": "test_spreadsheet"}
        self.save(self.record)
        session = Session(fail=True)
        self.assertFalse(publish(self.store, SheetsPublisher(config, session), ["prestamos"], self.interval, self.report))
        state = dict(zip(self.store.control()[0], self.store.control()[1]))
        self.assertEqual(state["published_revision"], 0)

    def test_google_renewal_output_keeps_original_id_and_numeric_quantity(self):
        self.save(Record('renovaciones', 'L1:2026-10-06:CUS', '2026-10-06', loan_id='L1', quantity=2))
        config = demo_config(self.directory)
        config.raw['google'] = {'spreadsheet_id': 'test_spreadsheet'}
        session = Session()
        table = self.store.table('renovaciones')
        SheetsPublisher(config, session).publish({'renovaciones': table})
        requests = session.calls[1][2]['json']['requests']
        rows = next(r['updateCells']['rows'] for r in requests if 'rows' in r.get('updateCells', {}))
        cells = rows[1]['values']
        self.assertEqual(cells[table[0].index('loan_id')]['userEnteredValue'], {'stringValue': 'L1'})
        self.assertEqual(cells[table[0].index('renewal_quantity')]['userEnteredValue'], {'numberValue': 2})

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
