import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_institutional_check import ROOT, gather_requests, render_sql


class InstitutionalPreparationTests(unittest.TestCase):
    def test_groups_email_dates_and_excludes_internal_and_missing_email(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'pilot.sqlite3'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE records(dataset,record_id,activity_date,payload)')
                data = [
                    ('prestamos', 'a', '2026-10-06', {'source_user_email': ' STUDENT@example.edu '}),
                    ('renovaciones', 'b', '2026-10-06', {'source_user_email': 'student@example.edu'}),
                    ('reservas', 'c', '2026-10-07', {'source_user_email': 'student@example.edu'}),
                    ('prestamos', 'd', '2026-10-06', {'source_user_email': 'room@example.edu', 'in_house_loan_indicator': 'Y'}),
                    ('reservas', 'e', '2026-10-07', {'source_user_email': ''}),
                ]
                db.executemany('INSERT INTO records VALUES(?,?,?,?)',
                               [(ds, key, day, json.dumps(payload)) for ds, key, day, payload in data])
            before = path.read_bytes()
            requests, counts = gather_requests(path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(counts['total_records'], 5)
            self.assertEqual(counts['in_house_records'], 1)
            self.assertEqual(counts['missing_email_records'], 1)
            self.assertEqual(counts['eligible_records'], 3)
            self.assertEqual(counts['distinct_emails'], 1)
            self.assertEqual(len(requests), 2)
            self.assertEqual(requests[0]['record_count'], 2)
            self.assertEqual(requests[0]['source_datasets'], 'prestamos,renovaciones')

    def test_generated_sql_quotes_emails_and_uses_the_shared_identity_methods(self):
        requests = [{'request_id': 1, 'source_email': "o'neil@example.edu", 'activity_date': '2026-10-06',
                     'record_count': 1, 'source_datasets': 'reservas'}]
        sql = render_sql(requests, (ROOT / 'sql/institutional/08_validar_lote.sql').read_text(),
                         (ROOT / 'sql/institutional/07_validar_cuentas.sql').read_text())
        self.assertIn("N'o''neil@example.edu'", sql)
        self.assertNotIn('@documento_referencia', sql)
        self.assertNotIn('q.account_context', sql)
        self.assertNotIn('-- INSERT_REQUESTS_HERE', sql)
        self.assertNotIn('-- BEGIN_SHARED_MATCHES', sql)
        self.assertNotIn('-- END_SHARED_MATCHES', sql)
        self.assertIn('email_institute_code_candidate', sql)
