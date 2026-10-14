import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from alma_libcal.config import load_config, service_accounts
from alma_libcal.errors import ConfigError
from alma_libcal.models import Record, report_headers


class ServiceAccountTests(unittest.TestCase):
    def test_service_profile_does_not_inherit_a_person_or_modify_stored_data(self):
        record = Record(dataset='reservas', record_id='booking-1', activity_date='2026-10-08',
                        site='Campus Cusco',
                        source_user_email=' AREA@example.edu ', user_id='source-account',
                        source_user_name='Source name', verified_user_id='person-1',
                        verified_user_email='person@example.edu', user_name='Person', user_full_name='Person name',
                        user_type='Docente', user_program='Program', user_department='Department',
                        user_business_unit='Unit', user_modality='Modality')
        original = asdict(record)
        settings = {'service_accounts': {'area@example.edu': {'user_type': 'Administrativo', 'user_campus': 'Virtual'}}}
        row = dict(zip(report_headers('reservas'), record.report_values(settings)))
        self.assertEqual(row['user_type'], 'Administrativo')
        self.assertEqual(row['user_campus_name'], 'Virtual')
        self.assertEqual(row['booking_campus_name'], 'Cusco')
        self.assertEqual(row['user_match_status'], 'configured_service_account')
        self.assertEqual(row['source_user_id'], 'source-account')
        self.assertEqual(row['source_user_first_name'], 'Source name')
        for field in ['user_id', 'user_full_name', 'user_first_name', 'user_program_name',
                      'user_department_name', 'user_business_unit_name', 'user_modality']:
            self.assertEqual(row[field], '')
        self.assertEqual(asdict(record), original)

    def test_exceptions_do_not_classify_other_accounts_or_internal_loans(self):
        settings = {'service_accounts': {'area@example.edu': {'user_type': 'Administrativo', 'user_campus': 'Virtual'}}}
        for email, internal in [('other@example.edu', ''), ('area@example.edu', 'Y')]:
            record = Record(dataset='prestamos', record_id='loan-1', activity_date='2026-10-06',
                            source_user_email=email, in_house_loan_indicator=internal)
            row = dict(zip(report_headers('prestamos'), record.report_values(settings)))
            self.assertEqual(row['user_type'], '')
            self.assertEqual(row['user_match_status'], 'not_applicable' if internal else 'pending')

    def test_config_normalizes_service_email(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text('[reporting.service_accounts." AREA@example.edu "]\n'
                            'user_type="Administrativo"\nuser_campus="Virtual"\n')
            settings = load_config(path).raw['reporting']['service_accounts']
            self.assertEqual(set(settings), {'area@example.edu'})

    def test_email_list_assigns_administrative_virtual_profiles(self):
        settings = service_accounts([' AREA@example.edu ', 'other-area@example.edu'])
        self.assertEqual(set(settings), {'area@example.edu', 'other-area@example.edu'})
        self.assertTrue(all(profile == {'user_type': 'Administrativo', 'user_campus': 'Virtual'}
                            for profile in settings.values()))

    def test_service_config_rejects_identity_fabrication_or_ambiguous_keys(self):
        profile = {'user_type': 'Administrativo', 'user_campus': 'Virtual'}
        for value in [[123], ['area@example.edu', 'AREA@example.edu'],
                      {'area@example.edu': {**profile, 'verified_user_id': 'person-1'}},
                      {'area@example.edu': {'user_type': 'Estudiante', 'user_campus': 'Virtual'}},
                      {'area@example.edu': profile, 'AREA@example.edu': profile}]:
            with self.assertRaises(ConfigError):
                service_accounts(value)
