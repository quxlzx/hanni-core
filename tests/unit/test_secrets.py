from __future__ import annotations
from hanni.config.secrets import SECRET_SPECS, InvalidSecretError, MissingSecretError, Secret, load_secrets, read_environment
from tests.helpers import TEST_ENV, TEST_OPTIONAL_SECRET, TEST_SECRET, TEST_SECRET_SPECS, TempDirTestCase
DOTENV_SECRET = 'd0tenv-' + 'z' * 40

class SecretTests(TempDirTestCase):

    def test_secret_never_prints(self) -> None:
        secret = Secret(TEST_SECRET)
        self.assertNotIn(TEST_SECRET, repr(secret))
        self.assertNotIn(TEST_SECRET, str(secret))
        self.assertNotIn(TEST_SECRET, f'{secret!r} {secret}')
        self.assertEqual(secret.reveal(), TEST_SECRET)
        self.assertEqual(secret, Secret(TEST_SECRET))
        self.assertNotEqual(secret, Secret('other-' + 'y' * 40))
        with self.assertRaises(TypeError):
            hash(secret)
        with self.assertRaises(ValueError):
            Secret('')

    def test_v1_declares_no_secrets(self) -> None:
        """D-0010: nothing is required, so loading with an empty environment succeeds."""
        self.assertEqual(SECRET_SPECS, ())
        self.assertEqual(load_secrets(env={}, dotenv_path=None).present_names, ())

    def test_missing_required_lists_names_only(self) -> None:
        with self.assertRaises(MissingSecretError) as ctx:
            load_secrets(env={'HANNI_TEST_OPTIONAL': TEST_OPTIONAL_SECRET}, dotenv_path=None, specs=TEST_SECRET_SPECS)
        self.assertEqual(ctx.exception.names, ('HANNI_TEST_SECRET',))
        self.assertNotIn(TEST_OPTIONAL_SECRET, str(ctx.exception))

    def test_optional_secret_may_be_absent(self) -> None:
        secrets = load_secrets(env=TEST_ENV, dotenv_path=None, specs=TEST_SECRET_SPECS)
        self.assertTrue(secrets.has('HANNI_TEST_SECRET'))
        self.assertFalse(secrets.has('HANNI_TEST_OPTIONAL'))
        self.assertEqual(secrets.present_names, ('HANNI_TEST_SECRET',))

    def test_invalid_values_are_rejected_without_echoing_them(self) -> None:
        with self.assertRaises(InvalidSecretError) as ctx:
            load_secrets(env={'HANNI_TEST_SECRET': 'tooshort'}, dotenv_path=None, specs=TEST_SECRET_SPECS)
        self.assertIn('HANNI_TEST_SECRET', str(ctx.exception))
        self.assertNotIn('tooshort', str(ctx.exception))
        with self.assertRaises(InvalidSecretError):
            load_secrets(env={**TEST_ENV, 'HANNI_TEST_OPTIONAL': 'tiny'}, dotenv_path=None, specs=TEST_SECRET_SPECS)

    def test_blank_values_count_as_missing(self) -> None:
        with self.assertRaises(MissingSecretError):
            load_secrets(env={'HANNI_TEST_SECRET': '   '}, dotenv_path=None, specs=TEST_SECRET_SPECS)

    def test_dotenv_is_read_but_real_environment_wins(self) -> None:
        dotenv = self.tmp / '.env'
        dotenv.write_text(f'HANNI_TEST_SECRET={DOTENV_SECRET}\nHANNI_TEST_OPTIONAL={TEST_OPTIONAL_SECRET}\n', encoding='utf-8')
        merged = read_environment(env={'HANNI_TEST_SECRET': TEST_SECRET}, dotenv_path=dotenv)
        self.assertEqual(merged['HANNI_TEST_SECRET'], TEST_SECRET)
        self.assertEqual(merged['HANNI_TEST_OPTIONAL'], TEST_OPTIONAL_SECRET)
        secrets = load_secrets(env={}, dotenv_path=dotenv, specs=TEST_SECRET_SPECS)
        self.assertEqual(secrets.get('HANNI_TEST_SECRET').reveal(), DOTENV_SECRET)

    def test_secrets_repr_shows_names_only(self) -> None:
        secrets = load_secrets(env=TEST_ENV, dotenv_path=None, specs=TEST_SECRET_SPECS)
        self.assertNotIn(TEST_SECRET, repr(secrets))
        self.assertIn('HANNI_TEST_SECRET', repr(secrets))
