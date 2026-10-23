"""Shared test helpers. Tests are ``unittest`` cases, which pytest also collects."""
from __future__ import annotations
import copy
import tempfile
import unittest
from pathlib import Path
from typing import Any
import yaml
from hanni.config.loader import CONFIG_FILES
from hanni.config.secrets import SecretSpec, validate_min_length
from hanni.logs import redaction
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_DIR = REPO_ROOT / 'config'
TEST_SECRET = 't3st-' + 'x' * 44
TEST_OPTIONAL_SECRET = '0pt-' + 'y' * 40
TOKEN_SHAPED = 'MTIzNDU2Nzg5MDEyMzQ1Njc4OTA.GhIjKl.' + 'm' * 38
TEST_SECRET_SPECS = (SecretSpec(name='HANNI_TEST_SECRET', description='test-only required secret', required=True, needed_from_milestone=0, validate=validate_min_length(32)), SecretSpec(name='HANNI_TEST_OPTIONAL', description='test-only optional secret', required=False, needed_from_milestone=1, validate=validate_min_length(8)))
TEST_ENV = {'HANNI_TEST_SECRET': TEST_SECRET}
DELETE = object()

def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if value is DELETE:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result

def write_config_dir(target: Path, overrides: dict[str, dict[str, Any]] | None=None) -> Path:
    """Copy the repository's default config into ``target``, applying per-file overrides."""
    target.mkdir(parents=True, exist_ok=True)
    for name in CONFIG_FILES:
        data = yaml.safe_load((DEFAULT_CONFIG_DIR / name).read_text(encoding='utf-8')) or {}
        if overrides and name in overrides:
            data = deep_merge(data, overrides[name])
        (target / name).write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    return target

class FakeGoogleAccess:
    """Stand-in for a connected Google account with write capability.

    Since the google-access gate landed, write tools are only exposed when
    a real account with '<service>.write' is connected. Tests that exercise
    the write path must present such an account explicitly.
    """
    def resolve_account(self, account, service):
        return account or "default"

    def has_capability(self, account, capability):
        return True


class TempDirTestCase(unittest.TestCase):
    """Provides ``self.tmp`` and resets the redaction registry around each test."""

    def setUp(self) -> None:
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        redaction.clear_registry()
        self.addCleanup(redaction.clear_registry)

    def config_dir(self, overrides: dict[str, dict[str, Any]] | None=None) -> Path:
        return write_config_dir(self.tmp / 'config', overrides)

    @property
    def data_dir(self) -> Path:
        return self.tmp / 'data'
