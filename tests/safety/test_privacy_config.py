"""The two-minute ephemeral limit is a ceiling enforced in code."""
from __future__ import annotations
from hanni.config.loader import load_config
from hanni.config.schema import MAX_EPHEMERAL_RETENTION_SECONDS, ConfigError
from tests.helpers import TempDirTestCase

class PrivacyConfigTests(TempDirTestCase):

    def test_defaults_are_exactly_two_minutes(self) -> None:
        retention = load_config(self.config_dir(), data_dir=self.data_dir, env={}).privacy.retention
        self.assertEqual(MAX_EPHEMERAL_RETENTION_SECONDS, 120)
        self.assertEqual((retention.raw_audio_seconds, retention.transcript_seconds, retention.screen_frames_seconds), (120, 120, 120))

    def test_retention_above_two_minutes_is_rejected(self) -> None:
        for key in ('raw_audio_seconds', 'transcript_seconds', 'screen_frames_seconds'):
            with self.subTest(key=key):
                cfg_dir = self.config_dir({'privacy.yaml': {'ephemeral_retention': {key: 121}}})
                with self.assertRaisesRegex(ConfigError, f'{key}: must be <= 120'):
                    load_config(cfg_dir, data_dir=self.data_dir, env={})

    def test_retention_may_be_shortened_but_not_zero(self) -> None:
        cfg = load_config(self.config_dir({'privacy.yaml': {'ephemeral_retention': {'transcript_seconds': 30}}}), data_dir=self.data_dir, env={})
        self.assertEqual(cfg.privacy.retention.transcript_seconds, 30)
        with self.assertRaisesRegex(ConfigError, 'must be >= 1'):
            load_config(self.config_dir({'privacy.yaml': {'ephemeral_retention': {'raw_audio_seconds': 0}}}), data_dir=self.data_dir, env={})

    def test_exclusion_patterns_must_compile(self) -> None:
        cfg_dir = self.config_dir({'privacy.yaml': {'screen_exclusions': {'window_title_patterns': ['(unclosed']}}})
        with self.assertRaisesRegex(ConfigError, 'invalid regular expression'):
            load_config(cfg_dir, data_dir=self.data_dir, env={})

    def test_default_exclusions_cover_password_managers(self) -> None:
        exclusions = load_config(self.config_dir(), data_dir=self.data_dir, env={}).privacy.screen_exclusions
        self.assertIn('1Password.exe', exclusions.process_names)
        self.assertTrue(any(('password' in p for p in exclusions.window_title_patterns)))
