import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape

from alma_libcal.connectors.alma import AlmaConnector, date_filter, parse_page
from alma_libcal.connectors.libcal import LibCalConnector
from alma_libcal.demo import DemoHTTP, demo_config, fixture
from alma_libcal.errors import ConfigError, SourceError
from alma_libcal.models import Interval, local_date, quantity


def xml_page(rows="", finished="true", token="", *, encoded=False):
    rowset = '<rowset xmlns="urn:schemas-microsoft-com:xml-analysis:rowset">' + rows + '</rowset>'
    if encoded:
        rowset = escape(rowset)
    return (f"<report><QueryResult><IsFinished>{finished}</IsFinished><ResumptionToken>{token}</ResumptionToken>"
            f"<ResultXml>{rowset}</ResultXml></QueryResult></report>").encode()


class QueueHTTP:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result

    def json(self, method, url, **kwargs):
        return self.request(method, url, **kwargs)


class ConnectorTests(unittest.TestCase):
    def test_real_alma_column_maps_retain_item_and_desk_attributes(self):
        import tomllib
        example = Path(__file__).resolve().parents[1] / 'config.example.toml'
        config = tomllib.loads(example.read_text())
        for dataset, barcode_column, mms_column in [('prestamos','Column9','Column16'),('renovaciones','Column4','Column9')]:
            fields = config['alma'][dataset]['fields']
            row = {fields['loan_id']:'L1',fields['activity_date']:'2026-10-07',
                   fields['user_id']:'000123',barcode_column:'000045',mms_column:'990000000123456789',
                   fields['item_material_type']:'Libro',fields['item_policy']:'Domicilio'}
            if dataset == 'renovaciones': row[fields['quantity']] = '2.0'
            else:
                for key in ('loan_time','loan_library_code','loan_desk_code','loan_desk_name','loan_desk_description'):
                    row[fields[key]] = key + '-original'
            record = AlmaConnector(self.config, QueueHTTP([]), dataset).normalize(row, fields)
            self.assertEqual(record.loan_id, 'L1')
            self.assertEqual(record.item_barcode, '000045')
            self.assertEqual(record.item_mms_id, '990000000123456789')
            self.assertEqual(record.item_material_type, 'Libro')
            self.assertEqual(record.item_policy, 'Domicilio')
            if dataset == 'prestamos':
                self.assertEqual(record.loan_time, 'loan_time-original')
                self.assertEqual(record.loan_desk_description, 'loan_desk_description-original')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = demo_config(Path(self.temp.name))
        self.interval = Interval(date(2026, 10, 6), date(2026, 10, 6))
        clock = patch("alma_libcal.connectors.libcal.current_date", return_value=self.interval.start)
        clock.start()
        self.addCleanup(clock.stop)
        env = patch.dict(os.environ, {"DEMO_ALMA_KEY": "private-test-key", "DEMO_LIBCAL_ID": "private-test-id", "DEMO_LIBCAL_SECRET": "private-test-secret"})
        env.start()
        self.addCleanup(env.stop)

    def test_alma_follows_token_and_keeps_missing_user(self):
        http = QueueHTTP([fixture("alma_loans_page1.xml").encode(), fixture("alma_loans_page2.xml").encode()])
        batch = AlmaConnector(self.config, http, "prestamos").fetch(self.interval)
        self.assertEqual(len(batch.records), 2)
        self.assertEqual(batch.records[0].user_id, "000123")
        self.assertEqual(batch.records[1].user_id, "")
        second_params = http.calls[1][2]["params"]
        self.assertNotIn("path", second_params)
        self.assertNotIn("filter", second_params)
        self.assertEqual(second_params["token"], "demo-shared-token")
        self.assertTrue(http.calls[0][2]["retry"])
        self.assertFalse(http.calls[1][2]["retry"])
        self.assertTrue(batch.source_updated_at)

    def test_alma_same_token_is_valid_across_multiple_pages(self):
        row1 = '<Row><Column1>L1</Column1><Column2>2026-10-06</Column2></Row>'
        row2 = row1.replace("L1", "L2")
        http = QueueHTTP([xml_page(row1, "false", "same-token"), xml_page(row2, "false"), xml_page()])
        batch = AlmaConnector(self.config, http, "prestamos").fetch(self.interval)
        self.assertEqual(len(batch.records), 2)
        self.assertEqual(http.calls[1][2]["params"]["token"], http.calls[2][2]["params"]["token"])

    def test_alma_renewals_preserve_daily_quantity(self):
        batch = AlmaConnector(self.config, DemoHTTP(), "renovaciones").fetch(self.interval)
        self.assertEqual(batch.records[0].quantity, 2)
        self.assertEqual(batch.records[0].record_id, "LOAN-001:2026-10-06")

    def test_alma_renewal_of_older_loan_is_included(self):
        row = '<Row><Column1>OLD-LOAN</Column1><Column2>2026-10-06</Column2><Column10>1</Column10></Row>'
        batch = AlmaConnector(self.config, QueueHTTP([xml_page(row)]), "renovaciones").fetch(self.interval)
        self.assertEqual(batch.records[0].record_id, "OLD-LOAN:2026-10-06")

    def test_alma_repeated_page_fails(self):
        response = fixture("alma_loans_page1.xml").encode()
        with self.assertRaisesRegex(SourceError, "repitió"):
            AlmaConnector(self.config, QueueHTTP([response, response]), "prestamos").fetch(self.interval)

    def test_alma_missing_token_fails(self):
        row = '<Row><Column1>L1</Column1><Column2>2026-10-06</Column2></Row>'
        with self.assertRaisesRegex(SourceError, "token"):
            AlmaConnector(self.config, QueueHTTP([xml_page(row, "false")]), "prestamos").fetch(self.interval)

    def test_alma_duplicate_keys_fail_instead_of_losing_counts(self):
        row = '<Row><Column1>L1</Column1><Column2>2026-10-06</Column2></Row>'
        with self.assertRaisesRegex(SourceError, "duplicadas"):
            AlmaConnector(self.config, QueueHTTP([xml_page(row + row)]), "prestamos").fetch(self.interval)

    def test_alma_max_pages_fails_without_silent_truncation(self):
        self.config.raw["alma"]["max_pages"] = 1
        with self.assertRaisesRegex(SourceError, "max_pages"):
            AlmaConnector(self.config, QueueHTTP([fixture("alma_loans_page1.xml").encode()]), "prestamos").fetch(self.interval)

    def test_xml_empty_report_and_encoded_rowset(self):
        self.assertEqual(parse_page(xml_page())[0], [])
        rows, finished, _ = parse_page(xml_page('<Row><Column1>000123</Column1></Row>', encoded=True))
        self.assertEqual(rows[0]["Column1"], "000123")
        self.assertTrue(finished)

    def test_xml_malformed_error_and_entity_declarations_fail(self):
        for xml in (b"<bad", b"<report><errorList/></report>", b'<!DOCTYPE report [<!ENTITY secret "hidden">]><report/>',
                    b"<report><QueryResult><IsFinished>true</IsFinished></QueryResult></report>"):
            with self.subTest(xml=xml), self.assertRaises(SourceError):
                parse_page(xml)

    def test_alma_schema_inspection_does_not_expose_values(self):
        raw = xml_page('<Row><Column1>private-user</Column1></Row>')
        result = AlmaConnector(self.config, QueueHTTP([raw]), "prestamos").inspect(self.interval)
        self.assertEqual(result, [{"column": "Column1", "heading": "", "type": ""}])
        self.assertNotIn("private-user", repr(result))

    def test_alma_inspection_without_filter_and_bad_catalog_prefix(self):
        http = QueueHTTP([xml_page()])
        AlmaConnector(self.config, http, "prestamos").inspect(self.interval, without_filter=True)
        self.assertNotIn("filter", http.calls[0][2]["params"])
        self.config.raw["alma"]["prestamos"]["report_path"] = "/Shared Folders/Pilot/Loans"
        with self.assertRaisesRegex(ConfigError, "/shared/"):
            AlmaConnector(self.config, QueueHTTP([]), "prestamos").inspect(self.interval)

    def test_alma_http_500_suggests_safe_path_and_filter_diagnostics(self):
        http = QueueHTTP([SourceError("La API respondió HTTP 500; revisa acceso y configuración.")])
        with self.assertRaisesRegex(SourceError, "without-filter") as caught:
            AlmaConnector(self.config, http, "prestamos").inspect(self.interval)
        self.assertNotIn("private-test-key", str(caught.exception))

    def test_internal_use_without_user_is_not_an_identity_error(self):
        fields = {"loan_id": "id", "activity_date": "date", "in_house_loan_indicator": "internal"}
        connector = AlmaConnector(self.config, QueueHTTP([]), "prestamos")
        record = connector.normalize({"id": "L1", "date": "2026-10-06", "internal": "Y"}, fields)
        from alma_libcal.models import HEADERS
        values = dict(zip(HEADERS, record.values()))
        self.assertEqual(values["usage_type"], "Uso interno")
        self.assertEqual(values["user_id"], "")
        self.assertEqual(values["user_id_missing"], "no aplica")
        unknown = connector.normalize({"id": "L2", "date": "2026-10-06"}, fields)
        self.assertEqual(dict(zip(HEADERS, unknown.values()))["user_id_missing"], "sí")

    def test_existing_internal_use_formula_does_not_create_a_fictitious_user(self):
        fields = {"loan_id": "id", "activity_date": "date", "user_id": "user", "in_house_loan_indicator": "internal"}
        connector = AlmaConnector(self.config, QueueHTTP([]), "prestamos")
        row = {"id": "L1", "date": "2026-10-06", "internal": "Y", "user": "Uso interno"}
        self.assertEqual(connector.normalize(row, fields).user_id, "")
        self.assertEqual(connector.normalize({**row, "internal": "N", "user": "000123"}, fields).user_id, "000123")
        self.assertEqual(connector.normalize({**row, "user": "000123"}, fields).user_id, "000123")

    def test_renewals_on_same_day_in_different_campuses_remain_distinct(self):
        fields = {"loan_id": "id", "activity_date": "date", "quantity": "count", "site_id": "campus"}
        connector = AlmaConnector(self.config, QueueHTTP([]), "renovaciones")
        row = {"id": "L1", "date": "2026-10-06", "count": "1", "campus": "CUS"}
        first = connector.normalize(row, fields)
        second = connector.normalize({**row, "campus": "HYO"}, fields)
        self.assertNotEqual(first.record_id, second.record_id)
        self.assertEqual(first.site_id, "CUS")

    def test_libcal_discovery_uses_category_endpoint_for_location_ids(self):
        http = QueueHTTP([{"access_token": "test"}, [{"lid": 20114, "categories": []}]])
        LibCalConnector(self.config, http).discover(locations=[20114, 20109])
        self.assertTrue(http.calls[1][1].endswith("/space/categories/20114,20109"))

    def test_libcal_probe_counts_all_pages_without_exposing_users_or_answers(self):
        rows = [{"lid": 20114, "cid": 100, "fromDate": "2026-10-06T10:00:00-05:00", "status": "Confirmed",
                 "email": "private-user", "q43": "private-answer"}]
        http = QueueHTTP([{"access_token": "private-token"}, rows, []])
        summary = LibCalConnector(self.config, http).check_bookings(self.interval.start, 20114, 100)
        self.assertEqual(summary["rows"], 1)
        self.assertIn("q43", summary["fields"])
        self.assertNotIn("private", repr(summary))
        self.assertEqual(http.calls[-1][2]["params"]["page"], 2)
        self.assertEqual(http.calls[1][2]["params"]["days"], 0)

    def test_libcal_rejects_past_dates_before_network(self):
        http = QueueHTTP([])
        with patch("alma_libcal.connectors.libcal.current_date", return_value=date(2026, 10, 7)):
            with self.assertRaisesRegex(ConfigError, "histórico"):
                LibCalConnector(self.config, http).fetch(self.interval)
            with self.assertRaisesRegex(ConfigError, "pasadas"):
                LibCalConnector(self.config, http).check_bookings(self.interval.start, 20114)
        self.assertEqual(http.calls, [])

    def test_libcal_allows_same_group_at_several_campuses(self):
        self.config.raw["libcal"]["categories"] = [
            {"id": "101", "name": "Computadoras y laptops", "location_id": "20114"},
            {"id": "104", "name": "Computadoras y laptops", "location_id": "20109"}]
        http = QueueHTTP([{"access_token": "test"}, [], []])
        self.assertEqual(LibCalConnector(self.config, http).fetch(self.interval).records, [])

    def test_date_filter_escapes_column_and_uses_requested_interval(self):
        expression = date_filter('"Dates"."A & B"', self.interval)
        self.assertIn("A &amp; B", expression)
        self.assertIn("2026-10-06", expression)

    def test_libcal_all_categories_cancelled_and_missing_checkin(self):
        batch = LibCalConnector(self.config, DemoHTTP()).fetch(self.interval)
        self.assertEqual(len(batch.records), 3)
        self.assertEqual({record.category for record in batch.records}, {"Computadoras y laptops", "Espacios grupales", "Kindle"})
        self.assertEqual(batch.records[1].status, "Cancelled")
        self.assertEqual(batch.records[1].check_in, "")

    def test_libcal_offset_uses_actual_server_page_size(self):
        rows = json.loads(fixture("libcal_bookings.json"))
        first = rows[0]
        second = {**first, "bookId": "SECOND"}
        http = QueueHTTP([{"access_token": "test"}, [first], [second], [], [], []])
        batch = LibCalConnector(self.config, http).fetch(self.interval)
        self.assertEqual(len(batch.records), 2)
        self.assertEqual(http.calls[2][2]["params"]["offset"], "1")
        self.assertEqual(http.calls[3][2]["params"]["offset"], "2")

    def test_libcal_page_pagination_and_wrapped_results(self):
        settings = self.config.raw["libcal"]
        settings["pagination"] = "page"
        settings["response_path"] = "data.bookings"
        settings["query"].pop("offset")
        settings["query"]["page"] = "{page}"
        first = json.loads(fixture("libcal_bookings.json"))[0]
        wrap = lambda rows: {"data": {"bookings": rows}}
        http = QueueHTTP([{"access_token": "test"}, wrap([first]), wrap([]), wrap([]), wrap([])])
        batch = LibCalConnector(self.config, http).fetch(self.interval)
        self.assertEqual(len(batch.records), 1)
        self.assertEqual(http.calls[2][2]["params"]["page"], "2")

    def test_libcal_incomplete_last_category_aborts_whole_batch(self):
        rows = json.loads(fixture("libcal_bookings.json"))
        http = QueueHTTP([{"access_token": "test"}, [rows[0]], [], [rows[1]], [], SourceError("third category unavailable")])
        with self.assertRaises(SourceError):
            LibCalConnector(self.config, http).fetch(self.interval)

    def test_libcal_repeated_page_is_not_silently_complete(self):
        first = json.loads(fixture("libcal_bookings.json"))[0]
        http = QueueHTTP([{"access_token": "test"}, [first], [first]])
        with self.assertRaisesRegex(SourceError, "repitió"):
            LibCalConnector(self.config, http).fetch(self.interval)

    def test_libcal_malformed_and_error_responses_fail(self):
        for response in ({"unexpected": []}, {"error": "private detail"}, ["not a row"]):
            with self.subTest(response=response), self.assertRaises(SourceError):
                LibCalConnector(self.config, QueueHTTP([{"access_token": "test"}, response])).fetch(self.interval)

    def test_libcal_nested_user_field_and_leading_zeros(self):
        first = json.loads(fixture("libcal_bookings.json"))[0]
        first["answers"] = [{"value": "000009"}]
        fields = {**self.config.raw["libcal"]["fields"], "user_id": "answers.0.value"}
        record = LibCalConnector(self.config, DemoHTTP()).normalize(first, fields, {"id": "101", "name": "Computadoras y laptops"})
        self.assertEqual(record.user_id, "000009")

    def test_libcal_email_prefix_is_only_a_source_identifier_and_keeps_zeros(self):
        self.config.raw['libcal']['user_id_from_email']=True
        row=json.loads(fixture('libcal_bookings.json'))[0]
        fields={**self.config.raw['libcal']['fields'],'source_user_email':'email',
                'source_user_name':'firstName','source_user_lastname':'lastName','booking_account':'account','user_id':''}
        row.update(email='000123@example.invalid',firstName='Manual',lastName='Entry',account='login123')
        category={'id':'101','name':'Computadoras y laptops'}
        connector=LibCalConnector(self.config,DemoHTTP())
        record=connector.normalize(row,fields,category)
        self.assertEqual(record.user_id,'000123')
        self.assertEqual(record.source_user_name,'Manual')
        self.assertEqual(record.user_name,'')
        self.assertEqual(record.booking_account,'login123')
        for email in ('not-an-email','@example.invalid','id@','a@b@c'):
            self.assertEqual(connector.normalize({**row,'email':email},fields,category).user_id,'')
        fields['user_id']='institutionalId'
        self.assertEqual(connector.normalize({**row,'institutionalId':'000456'},fields,category).user_id,'000456')

    def test_updated_renewal_map_preserves_both_campuses_and_report_fallback(self):
        import tomllib
        config=tomllib.loads((Path(__file__).resolve().parents[1]/'config.example.toml').read_text())
        fields=config['alma']['renovaciones']['fields']
        row={'Column1':'000123','Column2':'CUS','Column3':'Cusco','Column4':'000045','Column5':'I1',
             'Column6':'L1','Column7':'Active','Column8':'Libro','Column9':'990000123456789',
             'Column10':'Title','Column11':'Domicilio','Column12':'000123@example.invalid',
             'Column15':'2026-10-07','Column16':'2.0'}
        record=AlmaConnector(self.config,DemoHTTP(),'renovaciones').normalize(row,fields)
        from alma_libcal.models import report_headers
        result=dict(zip(report_headers('renovaciones'),record.report_values()))
        self.assertEqual(result['loan_id'],'L1')
        self.assertEqual(result['item_barcode'],'000045')
        self.assertEqual(result['renewal_quantity'],2)
        self.assertEqual(result['renewal_campus_code'],'')
        self.assertEqual(result['report_campus_code'],'CUS')
        self.assertEqual(result['report_campus_source'],'loan')

    def test_booking_date_month_hour_and_duration_use_local_start_across_year_boundary(self):
        from alma_libcal.models import report_headers
        row=json.loads(fixture('libcal_bookings.json'))[0]
        fields=self.config.raw['libcal']['fields']
        row[fields['starts_at']]='2027-01-01T04:30:00Z'
        row[fields['ends_at']]='2027-01-01T05:30:00Z'
        record=LibCalConnector(self.config,DemoHTTP()).normalize(row,fields,{'id':'101','name':'Computadoras y laptops'})
        result=dict(zip(report_headers('reservas'),record.report_values()))
        self.assertEqual(result['booking_date'],'2026-12-31')
        self.assertEqual(result['booking_month_number'],12)
        self.assertEqual(result['booking_month_name'],'Diciembre')
        self.assertEqual(result['booking_hour'],23)
        self.assertEqual(result['booking_duration_hours'],1)

    def test_libcal_category_mismatch_fails(self):
        first = json.loads(fixture("libcal_bookings.json"))[0]
        fields = {**self.config.raw["libcal"]["fields"], "category_id": "cid"}
        with self.assertRaisesRegex(SourceError, "otra categoría"):
            LibCalConnector(self.config, DemoHTTP()).normalize(first, fields, {"id": "102", "name": "Espacios grupales"})

    def test_group_participant_emails_use_question_ids_not_response_order(self):
        self.config.raw["libcal"]["forms"] = {
            "8253": {"report_fields": {"booking_form_answer_1": "q25459", "booking_form_answer_2": "q25460"}}}
        fields = {**self.config.raw["libcal"]["fields"], "source_user_email": "email"}
        row = {**json.loads(fixture("libcal_bookings.json"))[0],
               "q25460": "third@example.invalid", "q25458": "not-an-email",
               "email": "requester@example.invalid", "q25459": "second@example.invalid"}
        connector = LibCalConnector(self.config, DemoHTTP())
        category = {"id": "102", "name": "Espacios grupales", "form_id": "8253"}
        record = connector.normalize(row, fields, category)
        self.assertEqual(record.source_user_email, "requester@example.invalid")
        self.assertEqual(record.booking_form_answer_1, "second@example.invalid")
        self.assertEqual(record.booking_form_answer_2, "third@example.invalid")
        self.assertEqual(record.booking_form_id, "8253")
        # The same response cannot populate participant columns for another form.
        computer = connector.normalize(row, fields, {"id": "101", "name": "Computadoras y laptops", "form_id": "8254"})
        self.assertEqual(computer.booking_form_answer_1, "")
        self.assertEqual(computer.booking_form_answer_2, "")
        del row["q25460"]
        self.assertEqual(connector.normalize(row, fields, category).booking_form_answer_2, "")

    def test_booking_additional_answers_and_attendance_are_preserved_by_explicit_field(self):
        from alma_libcal.models import report_headers
        fields={**self.config.raw['libcal']['fields'],'booking_check_in_status':'check_in_status',
                'booking_phone':'q25458','booking_terms_accepted':'q25536','source_booking_row_id':'id',
                'source_booking_category_name':'category_name'}
        row={**json.loads(fixture('libcal_bookings.json'))[0],'check_in_status':'in',
             'q25458':'012345678','q25536':'Acepto','id':123,'category_name':'Computadoras',
             'status':'Cancelled by Admin'}
        record=LibCalConnector(self.config,DemoHTTP()).normalize(row,fields,{'id':'101','name':'Computadoras y laptops','form_id':'0'})
        result=dict(zip(report_headers('reservas'),record.report_values()))
        self.assertEqual(result['booking_phone'],'012345678')
        self.assertEqual(result['source_booking_terms_response'],'Acepto')
        self.assertEqual(result['booking_terms_accepted'],1)
        self.assertEqual(result['booking_attendance_status'],'Sí')
        self.assertEqual(result['booking_status'],'Cancelado')
        self.assertEqual(result['source_booking_row_id'],'123')
        self.assertEqual(result['booking_category_code'],'101')
        self.assertEqual(result['source_booking_category_name'],'Computadoras')

    def test_alma_email_is_preserved_without_becoming_user_id(self):
        fields = {"loan_id": "id", "activity_date": "date", "source_user_email": "email"}
        record = AlmaConnector(self.config, QueueHTTP([]), "prestamos").normalize(
            {"id": "L1", "date": "2026-10-06", "email": "Reader@example.invalid"}, fields)
        self.assertEqual(record.source_user_email, "Reader@example.invalid")
        self.assertEqual(record.user_id, "")

    def test_seat_booking_preserves_position_and_contact_with_no_category_form(self):
        fields = {**self.config.raw["libcal"]["fields"], "source_user_email": "email",
                  "seat_id": "seat_id", "seat_name": "seat_name"}
        row = {**json.loads(fixture("libcal_bookings.json"))[0], "eid": 172123,
               "seat_id": 123, "seat_name": "Puesto 01", "itemName": "Dispositivos",
               "email": "reader@example.invalid", "q25458": "phone", "q25536": "Acepto"}
        category = {"id": "42375", "name": "Computadoras y laptops", "form_id": "0"}
        record = LibCalConnector(self.config, DemoHTTP()).normalize(row, fields, category)
        self.assertEqual(record.resource_id, "172123")
        self.assertEqual(record.resource_name, "Dispositivos")
        self.assertEqual(record.seat_id, "123")
        self.assertEqual(record.seat_name, "Puesto 01")
        self.assertEqual(record.source_user_email, "reader@example.invalid")
        self.assertEqual(record.booking_form_id, "")
        self.assertEqual(record.booking_form_answer_1, "")

    def test_libcal_location_ids_are_preserved_and_wrong_campus_is_rejected(self):
        first = json.loads(fixture("libcal_bookings.json"))[0]
        first["lid"] = 20114
        fields = {**self.config.raw["libcal"]["fields"], "site_id": "lid"}
        connector = LibCalConnector(self.config, DemoHTTP())
        category = {"id": "101", "name": "Computadoras y laptops", "location_id": "20114"}
        self.assertEqual(connector.normalize(first, fields, category).site_id, "20114")
        with self.assertRaisesRegex(SourceError, "otro campus"):
            connector.normalize(first, fields, {**category, "location_id": "20109"})

    def test_libcal_timezone_and_end_before_start(self):
        first = json.loads(fixture("libcal_bookings.json"))[0]
        first["fromDate"] = "2026-10-07T01:00:00Z"
        first["toDate"] = "2026-10-07T02:00:00Z"
        connector = LibCalConnector(self.config, DemoHTTP())
        category = {"id": "101", "name": "Computadoras y laptops"}
        record = connector.normalize(first, self.config.raw["libcal"]["fields"], category)
        self.assertEqual(record.activity_date, "2026-10-06")
        first["toDate"] = "2026-10-07T00:00:00Z"
        with self.assertRaises(SourceError):
            connector.normalize(first, self.config.raw["libcal"]["fields"], category)

    def test_placeholder_configuration_fails_without_network(self):
        self.config.raw["libcal"]["fields"]["user_id"] = "REPLACE_USER_CODE_FIELD"
        http = QueueHTTP([])
        with self.assertRaises(ConfigError):
            LibCalConnector(self.config, http).fetch(self.interval)
        self.assertEqual(http.calls, [])

    def test_missing_secret_fails_without_network(self):
        with patch.dict(os.environ, {"DEMO_ALMA_KEY": ""}), self.assertRaises(ConfigError):
            AlmaConnector(self.config, QueueHTTP([]), "prestamos").fetch(self.interval)

    def test_quantity_and_dates_validate(self):
        self.assertEqual(quantity("2.0"), 2)
        for value in ("-1", "1.5", "NaN", "Infinity", "not-a-number"):
            with self.subTest(value=value), self.assertRaises(SourceError):
                quantity(value)
        self.assertEqual(local_date("2026-10-07T01:00:00Z", "America/Lima"), "2026-10-06")
        with self.assertRaises(SourceError):
            local_date("06/10/2026", "America/Lima")
