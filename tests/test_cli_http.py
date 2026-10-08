import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from alma_libcal.cli import main
from alma_libcal.errors import SourceError
from alma_libcal.http import HTTPClient
from alma_libcal.config import load_config, load_env
from alma_libcal.errors import ConfigError


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.body


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request)
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return Response(result)


class HTTPTests(unittest.TestCase):
    def test_http_error_does_not_expose_keys_url_or_response(self):
        private_url = "https://example.invalid/?apikey=private-key"
        error = HTTPError(private_url, 403, "private-key", {}, io.BytesIO(b"private-user"))
        http = HTTPClient(opener=Opener([error]))
        with self.assertRaises(SourceError) as caught:
            http.request("GET", private_url)
        self.assertNotIn("private", str(caught.exception))
        self.assertIn("403", str(caught.exception))

    def test_rate_limit_retries_and_urlencodes_filter_once(self):
        url = "https://example.invalid"
        error = HTTPError(url, 429, "rate limited", {"Retry-After": "2"}, io.BytesIO())
        opener = Opener([error, b"ok"])
        delays = []
        http = HTTPClient(opener=opener, sleep=delays.append)
        self.assertEqual(http.request("GET", url, params={"filter": "<expr>A & B</expr>"}), b"ok")
        self.assertEqual(delays, [2])
        self.assertIn("%3Cexpr%3E", opener.calls[0].full_url)
        self.assertNotIn("%253C", opener.calls[0].full_url)

    def test_stateful_cursor_request_is_not_retried(self):
        opener = Opener([URLError("private-token"), b"would skip a page"])
        http = HTTPClient(opener=opener, sleep=lambda delay: None)
        with self.assertRaises(SourceError):
            http.request("GET", "https://example.invalid", retry=False)
        self.assertEqual(len(opener.calls), 1)

    def test_network_failure_retries_and_redacts_details(self):
        opener = Opener([URLError("private-key")] * 3)
        http = HTTPClient(opener=opener, sleep=lambda delay: None)
        with self.assertRaises(SourceError) as caught:
            http.request("GET", "https://example.invalid")
        self.assertEqual(len(opener.calls), 3)
        self.assertNotIn("private-key", str(caught.exception))

    def test_json_invalid_response_and_http_scheme_are_rejected(self):
        with self.assertRaises(SourceError):
            HTTPClient(opener=Opener([b"not-json"])).json("GET", "https://example.invalid")
        with self.assertRaises(SourceError):
            HTTPClient(opener=Opener([])).request("GET", "http://example.invalid")


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        original_umask = os.umask(0o077)
        self.addCleanup(os.umask, original_umask)

    def invoke(self, arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(arguments)
        return code, output.getvalue()

    def config(self):
        path = self.directory / "config.toml"
        path.write_text('[project]\ntimezone="America/Lima"\nstart_date="2026-10-06"\ndatabase="data/pilot.sqlite3"\n')
        return path

    def test_demo_cli_creates_only_offline_artifacts(self):
        output_path = self.directory / "demo"
        code, output = self.invoke(["demo", "--directory", str(output_path)])
        self.assertEqual(code, 0)
        self.assertIn("no se publicó en Google", output)
        self.assertTrue((output_path / "sheets.json").exists())
        self.assertEqual((output_path / "pilot.sqlite3").stat().st_mode & 0o777, 0o600)

    def test_missing_config_returns_safe_actionable_error(self):
        code, output = self.invoke(["--config", str(self.directory / "missing.toml"), "sync"])
        self.assertEqual(code, 1)
        self.assertIn("configuración", output)

    def test_status_uses_paths_relative_to_config(self):
        config = self.config()
        code, output = self.invoke(["--config", str(config), "status"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)[0]["last_status"], "not_run")
        self.assertTrue((self.directory / "data" / "pilot.sqlite3").exists())

    def test_env_is_loaded_beside_config_and_preserves_exported_variables(self):
        config = self.config()
        (self.directory / ".env").write_text('TEST_ENV_KEY="value with # and $literal"\nTEST_ENV_OVERRIDE=from-file\n')
        with patch.dict(os.environ, {"TEST_ENV_OVERRIDE": "exported"}):
            os.environ.pop("TEST_ENV_KEY", None)
            load_config(config)
            self.assertEqual(os.environ["TEST_ENV_KEY"], "value with # and $literal")
            self.assertEqual(os.environ["TEST_ENV_OVERRIDE"], "exported")

    def test_sheet_column_configuration_rejects_unknown_or_unkeyed_exports(self):
        config=self.config()
        original=config.read_text()
        for columns in ('["loan_type"]','["record_id", "unknown"]','["record_id", "record_id"]'):
            config.write_text(original+'\n[reporting.sheet_columns]\nprestamos='+columns+'\n')
            with self.assertRaises(ConfigError):load_config(config)
        config.write_text(original+'\n[reporting]\nsheet_layout="full"\n[reporting.sheet_columns]\nprestamos=["record_id", "loan_type"]\n')
        self.assertEqual(load_config(config).raw['reporting']['sheet_layout'],'full')

    def test_invalid_env_redacts_secret_and_applies_no_partial_values(self):
        path = self.directory / ".env"
        path.write_text('TEST_PARTIAL_SECRET=private-secret\nINVALID LINE private-secret\n')
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigError) as caught:
                load_env(path)
            self.assertNotIn("private-secret", str(caught.exception))
            self.assertNotIn("TEST_PARTIAL_SECRET", os.environ)

    def test_reversed_dates_and_empty_publish_fail(self):
        config = self.config()
        code, output = self.invoke(["--config", str(config), "sync", "--from", "2026-10-07", "--to", "2026-10-06"])
        self.assertEqual(code, 1)
        self.assertIn("fecha", output)
        code, output = self.invoke(["--config", str(config), "publish"])
        self.assertEqual(code, 1)
        self.assertIn("Sin extracción completa", output)

    def test_missing_source_configuration_records_failure_without_google(self):
        config = self.config()
        code, output = self.invoke(["--config", str(config), "sync", "--only", "prestamos", "--extract-only"])
        self.assertEqual(code, 1)
        self.assertIn("alma.base_url", output)
        code, output = self.invoke(["--config", str(config), "status"])
        self.assertEqual(json.loads(output)[0]["last_extraction_status"], "extraction_failed")
