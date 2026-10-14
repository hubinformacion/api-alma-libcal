import csv
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from alma_libcal.models import Record, report_headers
from scripts.prepare_institutional_check import ROOT
from scripts.prepare_institutional_profiles import PROBES, evidence_query, read_review, render_profiles


class InstitutionalProfileTests(unittest.TestCase):
    def review_file(self, directory, rows):
        path = Path(directory) / 'review.csv'
        with path.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=';')
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_only_ready_scoped_people_enter_and_changed_input_is_rejected(self):
        original = [{'request_id': 1, 'source_email': 'student@example.edu', 'activity_date': '2026-10-07',
                     'record_count': 2, 'source_datasets': 'prestamos'},
                    {'request_id': 2, 'source_email': 'unknown@example.edu', 'activity_date': '2026-10-07',
                     'record_count': 1, 'source_datasets': 'reservas'}]
        rows = [{**r, 'identity_status': 'matched_identity', 'person_id': '123', 'account_scope': 'institute',
                 'review_status': 'ready_for_profile' if r['request_id'] == 1 else 'scope_pending'} for r in original]
        with tempfile.TemporaryDirectory() as directory:
            path = self.review_file(directory, rows)
            selected = read_review(path, original)
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0]['record_count'], 2)
            self.assertEqual(read_review(path, original, {'student@example.edu'}), [])
            rows[0]['source_email'] = 'different@example.edu'
            self.review_file(directory, rows)
            with self.assertRaises(ValueError):
                read_review(path, original)

    def test_scope_guard_wraps_or_conditions_and_sample_limits_are_removed(self):
        source = ('-- sample.csv\nSELECT DISTINCT TOP (100) d.ID_PERSONA AS person_id\n'
                  'FROM dbo.DIM_DOCENTE AS d\nWHERE d.ID_PERSONA=@persona_id OR d.NUMERO_DOCUMENTO=@documento\n'
                  'ORDER BY d.ID_PERSONA;')
        sql = evidence_query(source, 'sample.csv', 'teacher', 'labor')
        self.assertIn("WHERE q.account_scope=N'labor' AND (", sql)
        self.assertIn('OR d.NUMERO_DOCUMENTO=identity_person.COD_DOCUMENTO)', sql)
        self.assertNotIn('TOP (100)', sql)
        self.assertNotIn('@persona_id', sql)

    def test_all_profile_sources_compile_and_keep_json_and_context(self):
        request = {'request_id': 1, 'source_email': "o'neil@example.edu", 'activity_date': '2026-10-07',
                   'record_count': 1, 'source_datasets': 'prestamos', 'person_id': '123', 'account_scope': 'institute'}
        sql = render_profiles([request], (ROOT / 'sql/institutional/09_extraer_perfiles.sql').read_text(),
                              ROOT / 'sql/institutional')
        for _, _, name, scope in PROBES:
            self.assertIn("N'" + name + "' AS profile_source", sql)
        self.assertIn("N'o''neil@example.edu'", sql)
        self.assertIn('INCLUDE_NULL_VALUES', sql)
        self.assertNotIn('TOP (100)', sql)
        self.assertNotIn('@documento', sql)
        self.assertNotIn('@persona_id', sql)

    def test_pending_display_keeps_identifiers_empty_and_does_not_rewrite_source(self):
        record = Record(dataset='prestamos', record_id='loan-1', activity_date='2026-10-07',
                        user_id='raw-id', source_user_email='unknown@example.edu')
        before = asdict(record)
        row = dict(zip(report_headers('prestamos'), record.report_values()))
        self.assertEqual(row['user_type'], 'Pendiente de revisión')
        self.assertEqual(row['user_campus_name'], 'Pendiente de revisión')
        self.assertEqual(row['user_match_status'], 'pending_review')
        self.assertEqual(row['user_id'], '')
        self.assertEqual(row['source_user_id'], 'raw-id')
        self.assertEqual(row['user_email'], 'unknown@example.edu')
        self.assertEqual(asdict(record), before)
