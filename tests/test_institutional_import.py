import csv
import json
import tempfile
import unittest
from collections import defaultdict
from datetime import date
from pathlib import Path

from alma_libcal.errors import PilotError
from alma_libcal.institutional import import_users, resolve_profile
from alma_libcal.models import Batch, Interval, Record, report_headers
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
        result = self.resolve()
        self.assertEqual(result['fields']['user_match_status'], 'partial_profile')
        self.assertEqual(result['fields']['user_type'], 'Estudiante')
        self.assertEqual(result['fields']['user_program'], 'Carrera A')

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

    def test_admin_academic_fields_do_not_count_as_missing_but_campus_does(self):
        self.context['account_scope'] = 'labor'
        self.evidence['employment'] = [dict(work_email=self.context['source_email'],
            employment_start='2023-01-01', source_teacher_flag=0,
            source_division='UCCI', source_branch='104')]
        self.settings['labor_business_units'] = {'UCCI': 'Universidad Continental'}
        result = self.resolve()
        self.assertEqual(result['fields']['user_match_status'], 'partial_profile')
        self.assertEqual(result['reasons'], ['missing_or_ambiguous_user_campus'])
        for field in ['user_program', 'user_department', 'user_modality']:
            self.assertEqual(result['fields'][field], 'No aplica')
        self.settings['labor_campuses'] = {'UCCI:104': 'Campus de prueba'}
        result = self.resolve()
        self.assertEqual(result['fields']['user_match_status'], 'matched_profile')
        self.assertEqual(result['reasons'], [])

    def test_report_admin_rule_preserves_campus_and_source_data(self):
        for role in ['Administrativo', 'Docente', 'Estudiante', '']:
            record = Record('reservas', 'B1', '2026-10-06', user_type=role,
                user_match_status='partial_profile', user_program='Programa',
                user_department='Facultad', user_modality='Modalidad', user_campus='Campus',
                site='Campus Cusco')
            row = dict(zip(report_headers('reservas'), record.report_values()))
            self.assertEqual(row['user_program_name'], 'No aplica' if role == 'Administrativo' else 'Programa')
            self.assertEqual(row['user_department_name'], 'No aplica' if role == 'Administrativo' else 'Facultad')
            self.assertEqual(row['user_modality'], 'No aplica' if role == 'Administrativo' else 'Modalidad')
            self.assertEqual(row['user_campus_name'], 'Campus')
            self.assertEqual(row['booking_campus_name'], 'Cusco')
            self.assertEqual(record.user_program, 'Programa')

    def test_formal_graduation_is_required_for_egresado(self):
        self.evidence['uc_student'] = [dict(source_status='ESTUDIANTES')]
        self.assertEqual(self.resolve()['fields']['user_type'], '')
        self.evidence['uc_student'][0]['graduation_date'] = '2020-12-01'
        self.assertEqual(self.resolve()['fields']['user_type'], 'Egresado')
        self.evidence['uc_student'][0]['graduation_date'] = '2027-01-01'
        self.assertEqual(self.resolve()['fields']['user_type'], '')

    def test_study_end_does_not_backdate_egresado_before_formal_graduation(self):
        self.context['activity_date'] = '2020-12-15'
        self.settings['university_period_by_date'] = {'2020-12-15': '202020', '2021-01-02': '202110'}
        self.evidence['uc_student'] = [dict(student_id=5, program_id=1,
            study_end='2020-12-01', graduation_date='2021-01-01',
            title_date='2024-07-01', source_status='TITULADO')]
        self.evidence['uc_enrollment'] = [dict(self.enrollment, period_name='202010',
            enrollment_date='2020-03-08', source_activity_date='2020-03-08'),
            dict(self.enrollment, period_name='202020', enrollment_date=None,
                 source_activity_date='2020-12-01', source_status_name='ESTUDIOS CONCLUIDOS',
                 enrollment_status_name='ESTUDIOS CONCLUIDOS', enrolled_credits=None)]
        before = self.resolve()
        self.assertEqual(before['fields']['user_type'], '')
        self.assertEqual(before['fields']['user_match_status'], 'pending_review')
        self.context['activity_date'] = '2021-01-02'
        after = self.resolve()
        self.assertEqual(after['fields']['user_type'], 'Egresado')
        self.assertEqual(after['academic_selection']['date'], '2020-12-01')
        self.assertTrue(all(p['status_date'] == '2021-01-01' for p in after['academic_evidence']))
        self.assertEqual(self.evidence['uc_enrollment'][0]['enrollment_date'], '2020-03-08')

    def graduate_university(self):
        self.evidence['uc_student'] = [dict(student_id=5, program_id=1,
            study_start='2020-03-01', study_end='2020-12-01', graduation_date='2021-01-01')]
        self.evidence['uc_enrollment'] = [dict(self.enrollment, period_name='202010',
            enrollment_date='2020-03-01', source_activity_date='2020-03-01'),
            dict(self.enrollment, enrollment_date=None, source_activity_date='2026-09-01',
                 source_status_name='BACHILLER', enrollment_status_name='BACHILLER', enrolled_credits=None)]

    def test_current_period_degree_update_is_not_a_new_enrollment(self):
        self.graduate_university()
        self.evidence['edc_enrollment'] = [dict(enrollment_date='2019-01-01')]
        self.evidence['psg_enrollment'] = [dict(enrollment_date='2018-01-01', study_end=None)]
        result = self.resolve()
        self.assertEqual(result['fields']['user_type'], 'Egresado')
        self.assertEqual(result['fields']['user_modality'], 'Presencial')
        self.assertTrue(any(r['original_status'] == 'BACHILLER' for r in result['academic_evidence']))

    def test_late_titling_does_not_outrank_newer_continua(self):
        self.graduate_university()
        self.evidence['uc_student'][0]['title_date'] = '2026-09-01'
        self.evidence['edc_enrollment'] = [dict(enrollment_date='2025-01-01', source_active_status=1)]
        self.evidence['edc_profile'] = [dict(source_start_date='2025-01-01',
            source_emission_date='2025-12-01', source_funnel_status='MATRICULADO')]
        result = self.resolve()
        self.assertEqual(result['fields']['user_match_status'], 'partial_profile')
        self.assertEqual(result['fields']['user_type'], 'Egresado')
        self.assertEqual(result['fields']['user_program'], 'Carrera A')
        self.assertEqual(result['academic_selection']['date'], '2020-12-01')
        self.assertTrue(result['academic_selection']['later_study_unresolved'])
        self.assertIn('newer_academic_study_requires_validation', result['reasons'])

    def test_newer_undated_psg_requires_review_and_future_only_study_does_not(self):
        self.graduate_university()
        self.evidence['psg_enrollment'] = [dict(source_active_status=1, source_status_id=2)]
        self.assertEqual(self.resolve()['fields']['user_type'], 'Egresado')
        self.assertEqual(self.resolve()['fields']['user_match_status'], 'partial_profile')
        self.evidence['psg_enrollment'][0]['study_start'] = '2027-01-01'
        self.assertEqual(self.resolve()['fields']['user_type'], 'Egresado')

    def test_other_career_after_graduation_does_not_inherit_egresado(self):
        self.graduate_university()
        self.evidence['uc_enrollment'].append(dict(self.enrollment, period_name='202510',
            student_id=6, program_id=2, enrollment_date='2025-03-01', source_activity_date='2025-03-01'))
        result = self.resolve()
        self.assertEqual(result['fields']['user_type'], 'Egresado')
        self.assertEqual(result['fields']['user_program'], 'Carrera A')
        self.assertEqual(result['fields']['user_match_status'], 'partial_profile')

    def test_equal_study_dates_do_not_use_titling_dates_to_choose_a_career(self):
        self.graduate_university()
        self.evidence['uc_student'].append(dict(self.evidence['uc_student'][0],
            student_id=6, program_id=2, title_date='2026-01-01'))
        history = [dict(row, student_id=6, program_id=2, program_name='Carrera B')
                   for row in self.evidence['uc_enrollment']]
        history[-1]['source_activity_date'] = '2026-09-15'
        self.evidence['uc_enrollment'].extend(history)
        result = self.resolve()
        self.assertEqual(result['fields']['user_type'], 'Egresado')
        self.assertEqual(result['fields']['user_program'], '')
        self.assertEqual(result['fields']['user_campus'], 'Campus A')

    def test_later_completion_wins_over_later_start_in_two_graduated_careers(self):
        self.graduate_university()
        first = self.evidence['uc_student'][0]
        first.update(study_end='2025-12-01', graduation_date='2026-01-01')
        self.evidence['uc_student'].append(dict(student_id=6, program_id=2,
            study_start='2022-01-01', study_end='2024-12-01', graduation_date='2025-01-01'))
        self.evidence['uc_enrollment'].append(dict(self.enrollment, student_id=6, program_id=2,
            program_name='Carrera B', period_name='202210', enrollment_date='2022-01-01',
            source_activity_date='2022-01-01'))
        result = self.resolve()
        self.assertEqual(result['fields']['user_program'], 'Carrera A')
        self.assertEqual(result['academic_selection']['date'], '2025-12-01')
        self.assertEqual(result['academic_selection']['date_basis'], ['study_end'])

    def test_unknown_completion_does_not_displace_known_program_end(self):
        self.graduate_university()
        self.evidence['uc_student'].append(dict(student_id=6, program_id=2,
            study_start='2022-01-01', graduation_date='2026-01-01'))
        self.evidence['uc_enrollment'].append(dict(self.enrollment, student_id=6, program_id=2,
            program_name='Carrera B', period_name='202210', enrollment_date='2022-01-01',
            source_activity_date='2022-01-01'))
        result = self.resolve()
        self.assertEqual(result['fields']['user_program'], 'Carrera A')
        self.assertTrue(result['academic_selection']['other_completion_dates_missing'])
        self.assertEqual(result['fields']['user_match_status'], 'partial_profile')

    def institute_graduate(self):
        self.context['account_scope'] = 'institute'
        self.evidence['ic_enrollment'] = [dict(student_id=3, program_id=1, program_name='Programa IC',
            modality_name='REGULAR', source_status_id=4,
            section_start='2021-03-01', section_end='2021-08-01')]
        self.evidence['ic_graduation'] = [dict(program_id=1, program_name='Programa IC',
            source_graduation_certificate_status=1, source_graduation_certificate_date='2021-11-05')]

    def test_dated_issued_ic_certificate_proves_graduation_and_retains_missing_campus(self):
        self.institute_graduate()
        result = self.resolve()
        self.assertEqual(result['fields']['user_type'], 'Egresado')
        self.assertEqual(result['fields']['user_program'], 'Programa IC')
        self.assertEqual(result['fields']['user_campus'], '')
        self.assertEqual(result['fields']['user_match_status'], 'partial_profile')
        self.assertEqual(result['academic_evidence'][0]['original_status'], '1')

    def test_late_ic_certificate_is_not_evidence_of_a_more_recent_study(self):
        self.institute_graduate()
        self.evidence['ic_graduation'][0]['source_graduation_certificate_date'] = '2026-09-01'
        self.evidence['ic_enrollment'].append(dict(program_id=2, student_id=4,
            source_status_id=4, section_start='2025-01-01', section_end='2025-06-01'))
        result = self.resolve()
        self.assertEqual(result['fields']['user_type'], 'Egresado')
        self.assertEqual(result['fields']['user_program'], 'Programa IC')
        self.assertEqual(result['academic_selection']['date'], '2021-08-01')
        self.assertTrue(result['academic_selection']['later_study_unresolved'])
        self.evidence['ic_enrollment'] = self.evidence['ic_enrollment'][1:]
        result = self.resolve()
        self.assertEqual(result['fields']['user_type'], 'Egresado')
        self.assertEqual(result['academic_selection']['date'], '')
        self.assertIn('completion_date_not_available', result['reasons'])

    def test_ic_certificate_requires_confirmed_status_and_historical_date(self):
        self.institute_graduate()
        certificate = self.evidence['ic_graduation'][0]
        for status, issued in [(0, '2021-11-05'), (1, '2027-11-05'), (1, ''), (1, 'bad-date')]:
            certificate.update(source_graduation_certificate_status=status,
                               source_graduation_certificate_date=issued)
            self.assertEqual(self.resolve()['fields']['user_type'], '')

    def test_current_ic_enrollment_precedes_old_graduation(self):
        self.institute_graduate()
        self.evidence['ic_enrollment'].append(dict(program_id=2, student_id=4, program_name='Nuevo IC',
            source_status_id=4, section_start='2026-09-01', section_end='2027-01-01'))
        self.assertEqual(self.resolve()['fields']['user_type'], 'Estudiante')
        self.assertEqual(self.resolve()['fields']['user_program'], 'Nuevo IC')
        self.evidence['ic_enrollment'][-1]['section_end'] = '2026-10-01'
        result = self.resolve()
        self.assertEqual(result['fields']['user_type'], 'Egresado')
        self.assertEqual(result['fields']['user_program'], 'Programa IC')
        self.assertIn('institute_newer_study_requires_validation', result['reasons'])

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

    def test_graduation_audit_identifies_completion_date_and_keeps_raw_operations(self):
        self.rows.append(dict(self.identity, profile_source='uc_student', profile_data=json.dumps(
            dict(person_id=1, student_id=5, program_id=1, study_end='2020-12-01',
                 graduation_date='2021-01-01'))))
        self.run_import()
        with (self.root / 'reports/usuarios_revision.csv').open(encoding='utf-8-sig', newline='') as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row['selected_academic_date'], '2020-12-01')
        self.assertEqual(row['selected_academic_date_basis'], 'study_end')
        self.assertEqual(row['academic_selection_policy'], 'latest_known_completion')
        self.assertEqual(self.store.records('prestamos')[0].user_type, '')
        self.assertEqual(self.run_import()['changed_profiles'], 0)

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
