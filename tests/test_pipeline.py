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

    def test_audit_versions_only_change_with_content_and_preserve_revisited_states(self):
        self.save(self.record)
        first=self.store.db.execute('SELECT record_version,record_changed_at FROM records').fetchone()
        self.save(self.record)
        same=self.store.db.execute('SELECT record_version,record_changed_at FROM records').fetchone()
        self.assertEqual(tuple(first),tuple(same))
        self.save(replace(self.record,status='Complete'))
        self.save(self.record)
        versions=self.store.db.execute('SELECT version,payload FROM record_versions ORDER BY version').fetchall()
        self.assertEqual([r['version'] for r in versions],[1,2,3])
        self.assertEqual([json.loads(r['payload'])['status'] for r in versions],['','Complete',''])
        row=dict(zip(*self.store.table('prestamos')))
        self.assertEqual(row['record_version'],3)
        self.assertTrue(row['record_changed_at'])

    def test_catalog_changes_labels_without_rewriting_raw_data(self):
        record=replace(self.record,item_material_type='BOOK')
        self.save(record)
        table=self.store.table('prestamos',{'material_types':{'BOOK':'Libro'}})
        row=dict(zip(*table))
        self.assertEqual(row['item_material_type_code'],'BOOK')
        self.assertEqual(row['item_material_type_name'],'Libro')
        self.assertEqual(row['item_material_type_mapping_status'],'mapped')
        self.assertEqual(row['user_id'],'')
        self.assertEqual(row['source_user_id'],'000123')
        self.assertEqual(row['user_match_status'],'pending')
        row=dict(zip(*self.store.table('prestamos',{'material_types':{}})))
        self.assertEqual(row['item_material_type_name'],'Sin clasificar')
        self.assertEqual(self.store.records('prestamos')[0].item_material_type,'BOOK')
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM record_versions').fetchone()[0],1)

    def test_date_parts_can_be_omitted_without_losing_base_date_or_time(self):
        self.save(replace(self.record,loan_time='14:30:00'))
        settings={'include_date_parts':False}
        table=self.store.table('prestamos',settings)
        row=dict(zip(*table))
        self.assertEqual(row['loan_date'],'2026-10-06')
        self.assertEqual(row['loan_time'],'14:30:00')
        for field in ('loan_hour','loan_month_name','loan_month_number'):
            self.assertNotIn(field,row)
        self.assertEqual(len(table[0]),len(table[1]))

    def test_attendance_is_independent_of_cancellation_and_unrecorded_is_not_no(self):
        from alma_libcal.models import report_headers
        for status in ('Confirmed','Cancelled by Admin'):
            for raw,label,indicator in [('in','Sí',1),('out','Sí',1),('no','No',0),('-','-',''),('','-',''),('new-code','Desconocido','')]:
                record=Record('reservas','B1','2026-10-06',status=status,booking_check_in_status=raw)
                row=dict(zip(report_headers('reservas'),record.report_values()))
                self.assertEqual(row['booking_attendance_status'],label)
                self.assertEqual(row['booking_attendance_indicator'],indicator)
                self.assertEqual(row['source_booking_attendance_status'],raw)

    def test_module_classification_keeps_renewals_separate(self):
        from alma_libcal.models import report_headers
        for indicator,desk,expected in [('Y','Huancayo autopréstamo','Uso interno'),
                                        ('N','Huancayo AUTOPRÉSTAMO','Préstamo regular por autopréstamo'),
                                        ('N','Cusco módulo 1','Préstamo regular por bibliotecario')]:
            record=replace(self.record,in_house_loan_indicator=indicator,loan_desk_description=desk)
            row=dict(zip(report_headers('prestamos'),record.report_values()))
            self.assertEqual(row['loan_type'],expected)
        renewal=Record('renovaciones','L1:2026-10-06','2026-10-06',quantity=2)
        row=dict(zip(report_headers('renovaciones'),renewal.report_values()))
        self.assertEqual(row['renewal_type'],'Renovación')
        self.assertEqual(row['renewal_quantity'],2)

    def test_legacy_storage_migration_marks_baseline_without_inventing_past_versions(self):
        import sqlite3
        path=self.directory/'legacy.sqlite3'
        db=sqlite3.connect(path)
        db.execute('CREATE TABLE records(dataset TEXT,record_id TEXT,activity_date TEXT,payload TEXT,PRIMARY KEY(dataset,record_id))')
        old={'dataset':'prestamos','record_id':'L1','activity_date':'2026-10-06','user_id':'000123','resource_id':'R1'}
        db.execute('INSERT INTO records VALUES(?,?,?,?)',('prestamos','L1','2026-10-06',json.dumps(old)))
        db.commit();db.close()
        store=Store(path)
        try:
            run=store.start_run('prestamos','extract',self.interval)
            store.save('prestamos',self.interval,Batch([self.record]),run)
            baseline=store.db.execute('SELECT version,observation_type FROM record_versions').fetchall()
            self.assertEqual([tuple(r) for r in baseline],[(1,'baseline')])
            run=store.start_run('prestamos','extract',self.interval)
            store.save('prestamos',self.interval,Batch([replace(self.record,status='Complete')]),run)
            self.assertEqual(store.db.execute('SELECT record_version FROM records').fetchone()[0],2)
        finally:store.close()

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
        self.assertEqual(row["user_email"], "one@example.invalid")
        self.assertEqual(row["booking_participant_2_email"], "two@example.invalid")
        self.assertEqual(row["booking_participant_3_email"], "three@example.invalid")
        self.assertEqual(row["source_booking_status"], "Cancelled by Admin")
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
        common = 'record_id source_system record_version record_changed_at loan_id source_user_id source_user_email user_id user_email user_full_name user_first_name user_last_name user_type user_modality user_campus_name user_program_name user_department_name user_business_unit_name user_match_status item_id item_mms_id item_barcode item_material_type_code item_material_type_name item_material_type_mapping_status item_policy_name item_title'.split()
        loan_headers = common + 'loan_type loan_channel loan_date loan_time in_house_loan_indicator loan_campus_code loan_campus_name loan_library_code loan_desk_code loan_desk_name loan_desk_description loan_status loan_month_name loan_month_number loan_hour'.split()
        renewal_headers = common + 'renewal_type renewal_date renewal_campus_code renewal_campus_name renewal_quantity loan_status loan_campus_code loan_campus_name report_campus_code report_campus_name report_campus_source renewal_month_name renewal_month_number'.split()
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

    def test_renewal_report_campus_falls_back_without_changing_original_or_key(self):
        record = Record('renovaciones', 'L1:2026-10-06', '2026-10-06', loan_id='L1',
                        loan_origin_campus_code='CUS', loan_origin_campus='Cusco')
        self.save(record)
        row = dict(zip(*self.store.table('renovaciones')))
        self.assertEqual(row['renewal_campus_code'], '')
        self.assertEqual(row['renewal_campus_name'], '')
        self.assertEqual(row['loan_campus_code'], 'CUS')
        self.assertEqual(row['report_campus_name'], 'Cusco')
        self.assertEqual(row['report_campus_source'], 'loan')
        self.assertEqual(self.store.records('renovaciones')[0].record_id, 'L1:2026-10-06')
        for code, name in [('HYO','Huancayo'),('HYO','')]:
            changed = replace(record, site_id=code, site=name)
            output = dict(zip(self.store.table('renovaciones')[0], changed.report_values()))
            self.assertEqual(output['report_campus_code'], 'HYO')
            self.assertEqual(output['report_campus_name'], name)
            self.assertEqual(output['report_campus_source'], 'renewal')

    def test_booking_report_transforms_cross_midnight_and_keeps_canonical_identity_empty(self):
        record = Record('reservas','B1','2026-10-06',source_user_email='000123@example.invalid',
                        source_user_name='Manual name', source_user_lastname='Manual surname',
                        starts_at='2026-10-06T23:30:00-05:00',ends_at='2026-10-07T01:00:00-05:00',
                        status='Cancelled by Admin',booking_account='login123')
        self.save(record)
        row = dict(zip(*self.store.table('reservas')))
        self.assertEqual(row['booking_duration_hours'],1.5)
        self.assertNotIn('booking_duration_minutes',row)
        self.assertEqual(row['booking_hour'],23)
        self.assertEqual(row['booking_month_number'],10)
        self.assertEqual(row['booking_month_name'],'Octubre')
        self.assertEqual(row['booking_attendance_status'],'-')
        self.assertEqual(row['source_booking_status'],'Cancelled by Admin')
        self.assertEqual(row['user_first_name'],'')
        self.assertEqual(row['user_last_name'],'')
        self.assertEqual(row['source_user_first_name'],'Manual name')
        self.assertEqual(row['booking_account_email'],'')
        self.assertEqual(row['booking_account'],'login123')
        changed = replace(record,status='Confirmed',booking_account='000123@example.invalid')
        row = dict(zip(self.store.table('reservas')[0],changed.report_values()))
        self.assertEqual(row['booking_attendance_status'],'-')
        self.assertEqual(row['booking_account_email'],'000123@example.invalid')
        changed = replace(record,status='Tentative')
        row = dict(zip(self.store.table('reservas')[0],changed.report_values()))
        self.assertEqual(row['booking_attendance_status'],'-')

    def test_loan_report_uses_validated_hour_and_month_without_rewriting_source_time(self):
        from alma_libcal.errors import SourceError
        headers=self.store.table('prestamos')[0]
        for value in ('14','14:25:59'):
            row=dict(zip(headers,replace(self.record,loan_time=value).report_values()))
            self.assertEqual(row['loan_hour'],14)
            self.assertEqual(row['loan_time'],value)
            self.assertEqual(row['loan_month_number'],10)
        with self.assertRaises(SourceError):
            replace(self.record,loan_time='25:00').report_values()

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

    def test_unicode_payload_limit_matches_transport_serialization(self):
        config=demo_config(self.directory)
        config.raw['google']={'spreadsheet_id':'test_spreadsheet'}
        session=Session()
        with self.assertRaisesRegex(PublicationError,'tamaño'):
            SheetsPublisher(config,session).publish({'prestamos':[['title'],['á'*300_000]]})
        self.assertEqual([call[0] for call in session.calls],['GET'])
