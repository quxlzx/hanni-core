from __future__ import annotations
from hanni.config.loader import load_config
from hanni.config.schema import ConfigError
from tests.helpers import TempDirTestCase

class ConfigLoaderTests(TempDirTestCase):

    def test_repository_defaults_load(self) -> None:
        cfg = load_config(self.config_dir(), data_dir=self.data_dir, env={})
        self.assertEqual(cfg.hanni.name, 'H.A.N.N.I.')
        self.assertEqual(cfg.hanni.logging.level, 'INFO')
        self.assertEqual(cfg.hanni.user.timezone, 'America/New_York')
        self.assertEqual(cfg.hanni.recovery.max_attempts, 3)
        self.assertEqual(cfg.models.supervisor.id, 'supervisor')
        self.assertEqual(len(cfg.models.models), 1)
        self.assertEqual({m.role for m in cfg.models.models}, {'supervisor'})
        self.assertTrue(cfg.models.supervisor.keep_loaded)
        self.assertEqual(cfg.models.supervisor.hf_repo, 'lmstudio-community/Qwen3.5-4B-GGUF')
        self.assertEqual(cfg.models.supervisor.quantization, 'Q4_K_M')
        self.assertEqual(cfg.models.supervisor.context_length, 16384)
        self.assertEqual(cfg.models.supervisor.gpu_selection, 'smallest_8gb')
        self.assertTrue(cfg.hanni.mcp.enabled)
        self.assertTrue(cfg.hanni.mcp.read_only)
        self.assertEqual(cfg.hanni.mcp.max_tools_per_turn, 8)
        self.assertTrue(cfg.hanni.memory.enabled)
        self.assertEqual(cfg.hanni.memory.database_file, 'memory.sqlite3')
        self.assertEqual(cfg.paths.log_dir, self.data_dir / 'logs')

    def test_missing_file_names_the_file(self) -> None:
        cfg_dir = self.config_dir()
        (cfg_dir / 'privacy.yaml').unlink()
        with self.assertRaisesRegex(ConfigError, 'privacy.yaml: file not found'):
            load_config(cfg_dir, data_dir=self.data_dir, env={})

    def test_invalid_yaml_syntax(self) -> None:
        cfg_dir = self.config_dir()
        (cfg_dir / 'hanni.yaml').write_text('hanni: [unclosed', encoding='utf-8')
        with self.assertRaisesRegex(ConfigError, 'invalid YAML'):
            load_config(cfg_dir, data_dir=self.data_dir, env={})

    def test_unknown_key_is_rejected(self) -> None:
        cfg_dir = self.config_dir({'hanni.yaml': {'logging': {'levl': 'INFO'}}})
        with self.assertRaisesRegex(ConfigError, 'unknown key\\(s\\) levl'):
            load_config(cfg_dir, data_dir=self.data_dir, env={})

    def test_wrong_type_is_rejected(self) -> None:
        cfg_dir = self.config_dir({'hanni.yaml': {'recovery': {'max_attempts': 'three'}}})
        with self.assertRaisesRegex(ConfigError, 'max_attempts: expected an integer'):
            load_config(cfg_dir, data_dir=self.data_dir, env={})

    def test_bool_is_not_accepted_as_integer(self) -> None:
        cfg_dir = self.config_dir({'hanni.yaml': {'recovery': {'max_attempts': True}}})
        with self.assertRaises(ConfigError):
            load_config(cfg_dir, data_dir=self.data_dir, env={})

    def test_secret_like_value_in_yaml_is_rejected(self) -> None:
        cfg_dir = self.config_dir({'models.yaml': {'api_key': 'sk-live-123'}})
        with self.assertRaisesRegex(ConfigError, 'models.yaml.api_key: secrets must not be stored in YAML'):
            load_config(cfg_dir, data_dir=self.data_dir, env={})

    def test_env_log_level_override(self) -> None:
        cfg = load_config(self.config_dir(), data_dir=self.data_dir, env={'HANNI_LOG_LEVEL': 'debug'})
        self.assertEqual(cfg.hanni.logging.level, 'DEBUG')
        self.assertEqual(cfg.hanni.user.timezone, 'America/New_York')
        self.assertEqual(cfg.hanni.memory.database_file, 'memory.sqlite3')
        with self.assertRaisesRegex(ConfigError, 'HANNI_LOG_LEVEL'):
            load_config(self.config_dir(), data_dir=self.data_dir, env={'HANNI_LOG_LEVEL': 'loud'})

    def test_workflow_limits_survive_log_override(self) -> None:
        directory = self.config_dir({'hanni.yaml': {'workflows': {'max_steps': 3, 'max_invocations': 4, 'enabled': False, 'default_mode': 'background', 'max_retries': 0}}})
        config = load_config(directory, data_dir=self.data_dir, env={'HANNI_LOG_LEVEL': 'DEBUG'})
        self.assertEqual(config.hanni.workflows.max_steps, 3)
        self.assertEqual(config.hanni.workflows.max_invocations, 4)
        self.assertEqual(config.hanni.workflows.max_retries, 0)
        self.assertFalse(config.hanni.workflows.enabled)
        self.assertEqual(config.hanni.workflows.default_mode, 'background')

    def test_workflow_limits_cannot_widen_hard_caps(self) -> None:
        for values in ({'max_retries': 2}, {'max_parallel_reads': 5}, {'max_duration_seconds': 3601}, {'max_steps': True}, {'step_timeout_seconds': float('nan')}, {'lease_seconds': 0}, {'default_mode': 'unrestricted'}, {'authority': 'owner'}):
            with self.subTest(values=values):
                directory = self.config_dir({'hanni.yaml': {'workflows': values}})
                with self.assertRaises(ConfigError):
                    load_config(directory, data_dir=self.data_dir, env={})

    def test_owner_timezone_must_be_iana(self) -> None:
        with self.assertRaisesRegex(ConfigError, 'IANA timezone'):
            load_config(self.config_dir({'hanni.yaml': {'user': {'timezone': 'Not/A_Zone'}}}), data_dir=self.data_dir, env={})

    def test_env_dirs_are_honoured(self) -> None:
        cfg_dir = self.config_dir()
        cfg = load_config(None, env={'HANNI_CONFIG_DIR': str(cfg_dir), 'HANNI_DATA_DIR': str(self.tmp / 'elsewhere')})
        self.assertEqual(cfg.paths.config_dir, cfg_dir)
        self.assertEqual(cfg.paths.data_dir, self.tmp / 'elsewhere')

    def test_models_require_exactly_one_supervisor(self) -> None:
        models = [{'id': 'a', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': 'a.gguf', 'endpoint': 'http://127.0.0.1:1/v1'}, {'id': 'b', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': 'b.gguf', 'endpoint': 'http://127.0.0.1:2/v1'}]
        with self.assertRaisesRegex(ConfigError, 'exactly one configured model'):
            load_config(self.config_dir({'models.yaml': {'models': models}}), data_dir=self.data_dir, env={})

    def test_models_reject_bad_endpoint_and_legacy_node_key(self) -> None:
        base = {'id': 's', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': 's.gguf'}
        with self.assertRaisesRegex(ConfigError, 'endpoint: must be a valid'):
            load_config(self.config_dir({'models.yaml': {'models': [dict(base, endpoint='localhost:8080')]}}), data_dir=self.data_dir, env={})
        with self.assertRaisesRegex(ConfigError, 'unknown key\\(s\\) node'):
            load_config(self.config_dir({'models.yaml': {'models': [dict(base, endpoint='http://127.0.0.1:1/v1', node='core')]}}), data_dir=self.data_dir, env={})

    def test_models_reject_non_loopback_endpoint(self) -> None:
        base = {'id': 's', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': 's.gguf'}
        with self.assertRaisesRegex(ConfigError, 'loopback-only'):
            load_config(self.config_dir({'models.yaml': {'models': [dict(base, endpoint='https://api.example.com/v1')]}}), data_dir=self.data_dir, env={})

    def test_supervisor_generation_settings_are_typed(self) -> None:
        cfg = load_config(self.config_dir(), data_dir=self.data_dir, env={})
        supervisor = cfg.models.supervisor
        self.assertEqual(supervisor.api_model, 'supervisor')
        self.assertEqual(supervisor.hf_repo, 'lmstudio-community/Qwen3.5-4B-GGUF')
        self.assertEqual(supervisor.model_file, 'Qwen3.5-4B-Q4_K_M.gguf')
        self.assertTrue(supervisor.jinja_enabled)
        self.assertEqual(supervisor.quantization, 'Q4_K_M')
        self.assertEqual(supervisor.context_length, 16384)
        self.assertFalse(supervisor.thinking_enabled)
        self.assertGreater(supervisor.request_timeout_seconds, 0)

    def test_duplicate_model_ids_rejected(self) -> None:
        spec = {'id': 'dup', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': 's.gguf', 'endpoint': 'http://127.0.0.1:1/v1'}
        with self.assertRaisesRegex(ConfigError, 'model ids must be unique'):
            load_config(self.config_dir({'models.yaml': {'models': [spec, dict(spec)]}}), data_dir=self.data_dir, env={})

    def test_multi_gpu_model_settings_are_validated(self) -> None:
        base = {'id': 's', 'role': 'supervisor', 'backend': 'llama.cpp', 'model_file': 's.gguf', 'endpoint': 'http://127.0.0.1:1/v1'}
        with self.assertRaisesRegex(ConfigError, 'split_mode: must be one of'):
            load_config(self.config_dir({'models.yaml': {'models': [dict(base, split_mode='magic')]}}), data_dir=self.data_dir, env={})
        with self.assertRaisesRegex(ConfigError, 'at least one value'):
            load_config(self.config_dir({'models.yaml': {'models': [dict(base, tensor_split=[0, 0])]}}), data_dir=self.data_dir, env={})
        with self.assertRaisesRegex(ConfigError, 'expected 2 values'):
            load_config(self.config_dir({'models.yaml': {'models': [dict(base, tensor_split=[1], device_name_hints=['GPU A', 'GPU B'])]}}), data_dir=self.data_dir, env={})

    def test_memory_config_rejects_paths_outside_data_dir(self) -> None:
        with self.assertRaisesRegex(ConfigError, 'database_file'):
            load_config(self.config_dir({'hanni.yaml': {'memory': {'database_file': '../memory.sqlite3'}}}), data_dir=self.data_dir, env={})

class SpeechConfigTests(TempDirTestCase):

    def test_repository_speech_defaults(self) -> None:
        speech = load_config(self.config_dir(), data_dir=self.data_dir, env={}).hanni.speech
        self.assertEqual(speech.sample_rate, 16000)
        self.assertEqual(speech.channels, 1)
        self.assertEqual(speech.block_samples, 512)
        self.assertEqual(speech.input_device, 'default')
        self.assertEqual(speech.stt.model, 'small.en')
        self.assertEqual(speech.stt.device, 'cpu')
        self.assertEqual(speech.stt.compute_type, 'int8')
        self.assertEqual(speech.vad.threshold, 0.5)
        self.assertIn('hanni', speech.relevance.wake_names)
        self.assertIn('ani', speech.relevance.wake_names)
        self.assertIn('honey', speech.relevance.wake_names)
        self.assertEqual(speech.relevance.engagement_seconds, 0.0)
        self.assertIn('umm', speech.relevance.filler_words)
        self.assertIn("we're done", speech.relevance.disengage_phrases)
        self.assertTrue(speech.tts.enabled)
        self.assertEqual(speech.tts.backend, 'kokoro')
        self.assertEqual(speech.tts.voice, 'hanni')
        self.assertFalse(speech.tts.sapi_fallback)
        self.assertEqual(speech.tts.rate, 1)
        self.assertEqual(speech.tts.volume, 100)

    def test_invalid_speech_settings_are_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, 'channels: must be <= 1'):
            load_config(self.config_dir({'hanni.yaml': {'speech': {'channels': 2}}}), data_dir=self.data_dir, env={})
        with self.assertRaisesRegex(ConfigError, 'threshold: must be <= 0.99'):
            load_config(self.config_dir({'hanni.yaml': {'speech': {'vad': {'threshold': 1.0}}}}), data_dir=self.data_dir, env={})
        with self.assertRaisesRegex(ConfigError, 'device: must be one of'):
            load_config(self.config_dir({'hanni.yaml': {'speech': {'stt': {'device': 'cloud'}}}}), data_dir=self.data_dir, env={})
        with self.assertRaisesRegex(ConfigError, 'engagement_seconds: must be >= 0.0'):
            load_config(self.config_dir({'hanni.yaml': {'speech': {'relevance': {'engagement_seconds': -1}}}}), data_dir=self.data_dir, env={})
        with self.assertRaisesRegex(ConfigError, 'at least one wake name'):
            load_config(self.config_dir({'hanni.yaml': {'speech': {'relevance': {'wake_names': []}}}}), data_dir=self.data_dir, env={})
        with self.assertRaisesRegex(ConfigError, 'rate: must be <= 10'):
            load_config(self.config_dir({'hanni.yaml': {'speech': {'tts': {'rate': 11}}}}), data_dir=self.data_dir, env={})
        with self.assertRaisesRegex(ConfigError, 'backend: must be one of'):
            load_config(self.config_dir({'hanni.yaml': {'speech': {'tts': {'backend': 'cloud'}}}}), data_dir=self.data_dir, env={})
