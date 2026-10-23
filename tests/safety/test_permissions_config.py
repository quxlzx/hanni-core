"""The permission model's hard boundaries cannot be loosened through configuration."""
from __future__ import annotations
from hanni.config.loader import load_config
from hanni.config.schema import ConfigError
from tests.helpers import DELETE, TempDirTestCase

class PermissionsConfigTests(TempDirTestCase):

    def test_defaults_are_high_autonomy_with_level_3_confirmation(self) -> None:
        cfg = load_config(self.config_dir(), data_dir=self.data_dir, env={})
        self.assertEqual(cfg.permissions.owner.max_auto_approve_level, 2)
        self.assertFalse(cfg.permissions.levels[3].auto_approve_allowed)
        self.assertTrue(cfg.permissions.profiles['everyone_else'].chat_only)
        self.assertEqual(cfg.permissions.profiles['everyone_else'].max_auto_approve_level, -1)

    def test_profile_cannot_auto_approve_level_3(self) -> None:
        cfg_dir = self.config_dir({'permissions.yaml': {'profiles': {'owner': {'max_auto_approve_level': 3}}}})
        with self.assertRaisesRegex(ConfigError, 'may not exceed 2'):
            load_config(cfg_dir, data_dir=self.data_dir, env={})

    def test_level_3_cannot_be_marked_auto_approvable(self) -> None:
        levels = [{'level': 0, 'name': 'a', 'auto_approve_allowed': True}, {'level': 1, 'name': 'b', 'auto_approve_allowed': True}, {'level': 2, 'name': 'c', 'auto_approve_allowed': True}, {'level': 3, 'name': 'd', 'auto_approve_allowed': True}]
        with self.assertRaisesRegex(ConfigError, 'level 3 can never be auto-approved'):
            load_config(self.config_dir({'permissions.yaml': {'levels': levels}}), data_dir=self.data_dir, env={})

    def test_levels_must_be_exactly_0_to_3(self) -> None:
        levels = [{'level': 0, 'name': 'a', 'auto_approve_allowed': True}, {'level': 3, 'name': 'd', 'auto_approve_allowed': False}]
        with self.assertRaisesRegex(ConfigError, 'exactly levels 0..3'):
            load_config(self.config_dir({'permissions.yaml': {'levels': levels}}), data_dir=self.data_dir, env={})

    def test_owner_and_everyone_else_profiles_are_required(self) -> None:
        cfg_dir = self.config_dir({'permissions.yaml': {'profiles': {'owner': DELETE}}})
        with self.assertRaisesRegex(ConfigError, 'missing required profile'):
            load_config(cfg_dir, data_dir=self.data_dir, env={})

    def test_secret_like_key_must_not_be_placed_in_yaml(self) -> None:
        cfg_dir = self.config_dir({'permissions.yaml': {'profiles': {'owner': {'api_token': 'abc'}}}})
        with self.assertRaisesRegex(ConfigError, 'secrets must not be stored in YAML'):
            load_config(cfg_dir, data_dir=self.data_dir, env={})
