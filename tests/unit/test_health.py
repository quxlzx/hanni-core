from __future__ import annotations
import json
from hanni.core.health import run_health_check
from hanni.core.shutdown import LocalStopControls
from hanni.core.state import RuntimeMode
from tests.helpers import TEST_ENV, TEST_OPTIONAL_SECRET, TEST_SECRET, TEST_SECRET_SPECS, TempDirTestCase

class HealthCheckTests(TempDirTestCase):

    def _run(self, env: dict[str, str] | None=None, *, config=None, secret_specs=()):
        return run_health_check(config_dir=self.config_dir(config), data_dir=self.data_dir, env=env or {}, dotenv_path=None, node_id='test-machine', secret_specs=secret_specs)

    def _statuses(self, report) -> dict[str, str]:
        return {c.name: c.status for c in report.checks}

    def test_healthy_with_no_secrets_and_no_environment(self) -> None:
        """Milestone 0 exit criterion under D-0010: nothing to configure beyond the YAML files."""
        report = self._run()
        self.assertTrue(report.ok)
        self.assertIs(report.mode, RuntimeMode.NORMAL)
        statuses = self._statuses(report)
        self.assertEqual(statuses['config'], 'ok')
        self.assertEqual(statuses['secrets'], 'ok')
        self.assertEqual(statuses['emergency-stop'], 'ok')
        self.assertEqual(statuses['data-dir'], 'ok')
        self.assertNotIn('secrets-optional', statuses)
        self.assertTrue((self.data_dir / 'logs').is_dir())
        self.assertEqual(report.node_id, 'test-machine')

    def test_optional_secret_warning_names_the_milestone(self) -> None:
        report = self._run(TEST_ENV, secret_specs=TEST_SECRET_SPECS)
        self.assertTrue(report.ok)
        optional = next((c for c in report.checks if c.name == 'secrets-optional'))
        self.assertEqual(optional.status, 'warn')
        self.assertIn('HANNI_TEST_OPTIONAL', optional.detail)
        self.assertIn('Milestone 1', optional.detail)

    def test_missing_required_secret_fails_by_name_only(self) -> None:
        report = self._run({'HANNI_TEST_OPTIONAL': TEST_OPTIONAL_SECRET}, secret_specs=TEST_SECRET_SPECS)
        self.assertFalse(report.ok)
        secrets = next((c for c in report.checks if c.name == 'secrets'))
        self.assertEqual(secrets.status, 'fail')
        self.assertIn('HANNI_TEST_SECRET', secrets.detail)
        self.assertNotIn(TEST_OPTIONAL_SECRET, report.render_text())

    def test_report_never_contains_secret_values(self) -> None:
        report = self._run({**TEST_ENV, 'HANNI_TEST_OPTIONAL': TEST_OPTIONAL_SECRET}, secret_specs=TEST_SECRET_SPECS)
        for rendered in (report.render_text(), report.to_json(), json.dumps(report.to_dict())):
            self.assertNotIn(TEST_SECRET, rendered)
            self.assertNotIn(TEST_OPTIONAL_SECRET, rendered)

    def test_broken_config_is_reported_not_raised(self) -> None:
        report = self._run(config={'privacy.yaml': {'ephemeral_retention': {'transcript_seconds': 999}}})
        self.assertFalse(report.ok)
        config = next((c for c in report.checks if c.name == 'config'))
        self.assertEqual(config.status, 'fail')
        self.assertIn('transcript_seconds', config.detail)

    def test_tripped_stop_reports_safe_mode(self) -> None:
        LocalStopControls(self.data_dir, machine_name='X').trip('test')
        report = self._run()
        self.assertIs(report.mode, RuntimeMode.SAFE_MODE)
        self.assertTrue(report.ok)
        stop = next((c for c in report.checks if c.name == 'emergency-stop'))
        self.assertEqual(stop.status, 'warn')
        self.assertIn('hanni resume', stop.detail)

    def test_dotenv_presence_reported(self) -> None:
        dotenv = self.tmp / '.env'
        report = run_health_check(config_dir=self.config_dir(), data_dir=self.data_dir, env={}, dotenv_path=dotenv)
        self.assertEqual(self._statuses(report)['dotenv'], 'ok')
        report = run_health_check(config_dir=self.config_dir(), data_dir=self.data_dir, env=TEST_ENV, dotenv_path=dotenv, secret_specs=TEST_SECRET_SPECS)
        self.assertEqual(self._statuses(report)['dotenv'], 'warn')
        self.assertTrue(report.ok)
        dotenv.write_text('', encoding='utf-8')
        report = run_health_check(config_dir=self.config_dir(), data_dir=self.data_dir, env=TEST_ENV, dotenv_path=dotenv, secret_specs=TEST_SECRET_SPECS)
        self.assertEqual(self._statuses(report)['dotenv'], 'ok')
