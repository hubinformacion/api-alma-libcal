import csv
import json
import tempfile
import unittest
from collections import defaultdict
from datetime import date
from pathlib import Path

from alma_libcal.errors import PilotError
from alma_libcal.institutional import import_users, resolve_profile
from alma_libcal.models import Batch, Interval, Record
from alma_libcal.storage import Store


class ProfileResolutionTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(source_email='00123456@example.edu', activity_date='2026-10-06',
                            account_scope='university', person_id='7')
        self.evidence = defaultdict(list, identity=[dict(source_identifier='00123456',
                                                        full_name='NOMBRE COMPLETO SIN COMAS')])
        self.settings = {'university_period_by_date': {'2026-10-06': '202620'}}
        self.enrollment = dict(period_id=355, period_name='202620', student_id=5,
                               program_id=1, program_name='Carrera A', campus_name='Campus A',
                               faculty_name='Facultad', modality_name='Presencial',
                               source_activity_date='2026-08-10', enrollment_date='2026-08-09',
                               source_status_name='ACTIVO', enrollment_status_name='ACTIVO',
                               enrolled_credits=20)

    def resolve(self):
        return resolve_profile(self.context, self.evidence, self.settings)

    def test_current_period_uses_code_not_surrogate_and_preserves_identifier(self):
        self.evidence['uc_enrollment'] = [self.enrollment]
        result = self.resolve()['fields']
        self.assertEqual(result['user_type'], 'Estudiante')
        self.assertEqual(result['verified_user_id'], '00123456')
        self.assertEqual(result['user_name'], '')
        self.assertEqual(result['user_full_name'], 'NOMBRE COMPLETO SIN COMAS')

    def test_future_enrollment_and_period_do_not_replace_current(self):
        self.evidence['uc_enrollment'] = [self.enrollment,
            dict(self.enrollment, period_name='202710', program_name='Futuro'),
            dict(self.enrollment, source_activity_date='2026-10-10', program_name='Futuro')]
        self.assertEqual(self.resolve()['fields']['user_program'], 'Carrera A')

    def test_no_confirmed_period_and_conflicting_status_remain_pending(self):
        self.evidence['uc_enrollment'] = [self.enrollment]
        self.settings = {}
        self.assertEqual(self.resolve()['fields']['user_match_status'], 'pending_review')
        self.settings = {'university_period_by_date': {'2026-10-06': '202620'}}
        self.evidence['uc_enrollment'].append(dict(self.enrollment, source_status_name='NO MATRICULADO'))
        self.assertEqual(self.resolve()['fields']['user_match_status'], 'pending_review')

    def test_two_current_careers_keep_common_campus_and_do_not_choose_program(self):
        self.evidence['uc_enrollment'] = [self.enrollment,
            dict(self.enrollment, student_id=6, program_id=2, program_name='Carrera B')]
        fields = self.resolve()['fields']
        self.assertEqual(fields['user_type'], 'Estudiante')
        self.assertEqual(fields['user_campus'], 'Campus A')
        self.assertEqual(fields['user_program'], '')
        self.assertEqual(fields['user_match_status'], 'partial_profile')

    def test_newer_continua_is_not_inferred_from_funnel_status(self):
        self.evidence['uc_enrollment'] = [self.enrollment]
        self.evidence['edc_profile'] = [dict(source_start_date='2026-09-01',
                                          source_funnel_status='MATRICULADO')]
        self.assertEqual(self.resolve()['fields']['user_match_status'], 'pending_review')

    def test_institute_is_scoped_and_requires_dated_enrollment(self):
        self.context['account_scope'] = 'institute'
        self.evidence['uc_enrollment'] = [self.enrollment]
        self.assertEqual(self.resolve()['fields']['user_type'], '')
        self.evidence['ic_enrollment'] = [dict(source_status_id=4, section_start='2026-08-01',
                                              section_end='2026-12-01', program_name='IC')]
        self.assertEqual(self.resolve()['fields']['user_type'], 'Estudiante')
        self.assertEqual(self.resolve()['fields']['user_business_unit'], 'Instituto Continental')
        self.evidence['ic_enrollment'][0]['section_end'] = 'invalid'
        self.assertEqual(self.resolve()['fields']['user_type'], '')

    def test_teacher_precedes_admin_but_old_teacher_is_not_current(self):
        self.context['account_scope'] = 'labor'
        self.evidence['employment'] = [dict(work_email=self.context['source_email'],
            employment_start='2023-01-01', employment_end='2024-01-01', source_teacher_flag=0)]
        self.evidence['teacher'] = [dict(work_email=self.context['source_email'], teacher_id=10,
                                       teacher_start='2026-01-01')]
        self.evidence['teaching_program'] = [dict(period_name='202620', period_id=355,
            teacher_id=10, source_teacher_type='JEFE DE PRACTICA HYFLEX', program_name='Carrera')]
        self.assertEqual(self.resolve()['fields']['user_type'], 'Docente')
        self.evidence['teacher'][0]['teacher_end'] = '2025-01-01'
        self.assertEqual(self.resolve()['fields']['user_type'], 'Administrativo')
        self.evidence['employment'][0]['source_division'] = 'UCCI'
        self.settings['labor_business_units'] = {'UCCI': 'Universidad Continental'}
        self.assertEqual(self.resolve()['fields']['user_business_unit'], 'Universidad Continental')
        self.evidence['employment'][0]['employment_withdrawal'] = '2025-01-01'
        self.assertEqual(self.resolve()['fields']['user_type'], '')

    def test_formal_graduation_is_required_for_egresado(self):
        self.evidence['uc_student'] = [dict(source_status='ESTUDIANTES')]
        self.assertEqual(self.resolve()['fields']['user_type'], '')
        self.evidence['uc_student'][0]['graduation_date'] = '2020-12-01'
        self.assertEqual(self.resolve()['fields']['user_type'], 'Egresado')
        self.evidence['uc_student'][0]['graduation_date'] = '2027-01-01'
        self.assertEqual(self.resolve()['fields']['user_type'], '')

    def test_tm_identifier_remains_alphanumeric(self):
        self.evidence['identity'][0]['source_identifier'] = 'TM000123'
        self.assertEqual(self.resolve()['fields']['verified_user_id'], 'TM000123')


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'db.sqlite3')
        self.addCleanup(self.store.close)
        self.record = Record('prestamos', 'L1', '2026-10-06', source_user_email='test@example.edu')
        interval = Interval(date(2026, 10, 6), date(2026, 10, 6))
        run = self.store.start_run('prestamos', 'extract', interval)
        self.store.save('prestamos', interval, Batch([self.record]), run)
        self.review = dict(request_id='1', source_email='test@example.edu', activity_date='2026-10-06',
                           record_count='1', source_datasets='prestamos', person_id='1',
                           account_scope='university', identity_status='matched_identity',
                           review_status='ready_for_profile')
        self.identity = dict(self.review, profile_source='identity', profile_data=json.dumps(
            dict(person_id=1, source_identifier='00123', full_name='Nombre Institucional')))
        self.rows = [self.identity]
        self.settings = {'university_period_by_date': {'2026-10-06': '202620'}}

    def write(self, path, rows):
        with path.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=';')
            writer.writeheader()
            writer.writerows(rows)

    def run_import(self):
        evidence, review = self.root / '09.csv', self.root / '08.csv'
        self.write(evidence, self.rows)
        self.write(review, [self.review])
        return import_users(self.store, evidence, review, self.settings, output=self.root / 'reports')

    def test_import_is_overlay_idempotent_and_versions_changed_profiles(self):
        raw_before = tuple(self.store.db.execute('SELECT payload,record_version FROM records').fetchone())
        revision = self.store.revisions(['prestamos'])['prestamos']
        self.assertEqual(self.run_import()['changed_profiles'], 1)
        self.assertEqual(self.store.revisions(['prestamos'])['prestamos'], revision + 1)
        table = self.store.table('prestamos')
        row = dict(zip(table[0], table[1]))
        self.assertEqual(row['user_id'], '00123')
        self.assertEqual(row['user_full_name'], 'Nombre Institucional')
        self.assertEqual(row['user_type'], 'Pendiente de revisión')
        self.assertEqual(tuple(self.store.db.execute('SELECT payload,record_version FROM records').fetchone()), raw_before)
        self.assertEqual(self.run_import()['changed_profiles'], 0)
        self.assertEqual(self.store.revisions(['prestamos'])['prestamos'], revision + 1)
        self.identity['profile_data'] = json.dumps(dict(person_id=1, source_identifier='00123', full_name='Nombre Corregido'))
        self.assertEqual(self.run_import()['changed_profiles'], 1)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM institutional_profile_versions').fetchone()[0], 2)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM record_versions').fetchone()[0], 1)

    def test_wrong_person_bad_json_and_cross_scope_reject_entire_batch(self):
        for replacement in (dict(profile_data='{broken'),
                            dict(profile_data=json.dumps(dict(person_id=2))),
                            dict(profile_source='employment')):
            self.rows = [dict(self.identity, **replacement)]
            with self.assertRaises(PilotError):
                self.run_import()
            self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM institutional_profiles').fetchone()[0], 0)

    def test_stale_counts_and_missing_identity_are_rejected(self):
        self.review['record_count'] = '2'
        with self.assertRaises(PilotError):
            self.run_import()
        self.review['record_count'] = '1'
        self.rows = [dict(self.identity, profile_source='uc_student')]
        with self.assertRaises(PilotError):
            self.run_import()

    def test_orphan_evidence_after_scope_review_rejects_import(self):
        self.run_import()
        self.review.update(review_status='scope_pending', account_scope='unresolved')
        # A second request would ordinarily supply evidence; an orphaned evidence row must reject.
        with self.assertRaises(PilotError):
            self.run_import()
