"""Single-PC invariants (docs/DECISIONS.md D-0009, D-0010).

These run against the repository's shipped ``config/`` directory, not a temp
copy, so they pin exactly what the owner sees on the laptop.
"""
from __future__ import annotations
import importlib.util
from urllib.parse import urlsplit
import hanni.core.identity
import hanni.core.state
from hanni.config.loader import load_config
from hanni.core.health import run_health_check
from tests.helpers import DEFAULT_CONFIG_DIR, TempDirTestCase
LOOPBACK_HOSTS = {'127.0.0.1', 'localhost', '::1'}

class SinglePcTests(TempDirTestCase):

    def test_shipped_config_is_healthy_with_no_secrets_and_no_dotenv(self) -> None:
        """Milestone 0 exit criterion: the laptop needs nothing beyond the repository itself."""
        report = run_health_check(config_dir=DEFAULT_CONFIG_DIR, data_dir=self.data_dir, env={}, dotenv_path=self.tmp / 'absent.env')
        self.assertTrue(report.ok, report.render_text())
        statuses = {c.name: c.status for c in report.checks}
        self.assertEqual(statuses['dotenv'], 'ok')
        self.assertEqual(statuses['secrets'], 'ok')

    def test_every_shipped_model_endpoint_is_local(self) -> None:
        cfg = load_config(DEFAULT_CONFIG_DIR, data_dir=self.data_dir, env={})
        for model in cfg.models.models:
            with self.subTest(model=model.id):
                self.assertIn(urlsplit(model.endpoint).hostname, LOOPBACK_HOSTS, model.endpoint)

    def test_shipped_models_follow_the_single_assistant_contract(self) -> None:
        cfg = load_config(DEFAULT_CONFIG_DIR, data_dir=self.data_dir, env={})
        self.assertEqual(len(cfg.models.models), 1)
        supervisor = cfg.models.supervisor
        self.assertEqual(supervisor.role, 'supervisor')
        self.assertTrue(supervisor.endpoint.startswith('http://127.0.0.1:'))
        self.assertTrue(supervisor.keep_loaded)
        self.assertEqual(supervisor.backend, 'llama.cpp')
        self.assertEqual(supervisor.hf_repo, 'lmstudio-community/Qwen3.5-4B-GGUF')
        self.assertEqual(supervisor.quantization, 'Q4_K_M')
        self.assertEqual(supervisor.context_length, 16384)
        self.assertEqual(supervisor.gpu_selection, 'smallest_8gb')
        self.assertFalse(supervisor.thinking_enabled)

    def test_two_pc_and_discord_modules_do_not_exist(self) -> None:
        for name in ('hanni.discord', 'hanni.networking', 'hanni.database', 'hanni_node', 'hanni.cli_support'):
            with self.subTest(module=name):
                self.assertIsNone(importlib.util.find_spec(name))
        self.assertFalse(hasattr(hanni.core.state, 'NodeRole'))
        self.assertFalse(hasattr(hanni.core.identity, 'resolve_discord_actor'))
