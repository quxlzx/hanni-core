"""Secrets must never reach a log sink or a report."""
from __future__ import annotations
import io
import logging
from hanni.config.secrets import load_secrets
from hanni.logs import JsonFormatter, RedactionFilter, TextFormatter, redact_text, register_secret, setup_logging
from tests.helpers import TEST_OPTIONAL_SECRET, TEST_SECRET, TEST_SECRET_SPECS, TOKEN_SHAPED, TempDirTestCase

class RedactTextTests(TempDirTestCase):

    def test_registered_value_is_replaced_by_name(self) -> None:
        register_secret('HANNI_TEST_SECRET', TEST_SECRET)
        self.assertEqual(redact_text(f'secret is {TEST_SECRET} ok'), 'secret is [REDACTED:HANNI_TEST_SECRET] ok')

    def test_short_values_are_not_registered(self) -> None:
        register_secret('TINY', 'abc')
        self.assertEqual(redact_text('abc is fine'), 'abc is fine')

    def test_three_segment_token_shape(self) -> None:
        self.assertNotIn(TOKEN_SHAPED, redact_text(f'token was {TOKEN_SHAPED}'))
        self.assertIn('[REDACTED:token]', redact_text(f'token was {TOKEN_SHAPED}'))

    def test_bearer_and_key_value_shapes(self) -> None:
        self.assertEqual(redact_text('Authorization: Bearer abc.def-123'), 'Authorization: Bearer [REDACTED]')
        self.assertEqual(redact_text('password=hunter22 api_key: \'xyz\' token="qq"'), 'password=[REDACTED] api_key: \'[REDACTED]\' token="[REDACTED]"')

    def test_loaded_secrets_are_registered(self) -> None:
        load_secrets(env={'HANNI_TEST_SECRET': TEST_SECRET, 'HANNI_TEST_OPTIONAL': TEST_OPTIONAL_SECRET}, dotenv_path=None, specs=TEST_SECRET_SPECS)
        text = redact_text(f'required {TEST_SECRET} optional {TEST_OPTIONAL_SECRET}')
        self.assertNotIn(TEST_SECRET, text)
        self.assertNotIn(TEST_OPTIONAL_SECRET, text)
        self.assertIn('[REDACTED:HANNI_TEST_SECRET]', text)

class LoggingSinkTests(TempDirTestCase):

    def _capture(self, formatter: logging.Formatter) -> tuple[logging.Logger, io.StringIO]:
        buffer = io.StringIO()
        handler = logging.StreamHandler(buffer)
        handler.setFormatter(formatter)
        handler.addFilter(RedactionFilter())
        logger = logging.getLogger(f'hanni.test.{id(buffer)}')
        logger.propagate = False
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        return (logger, buffer)

    def test_message_args_and_extra_are_scrubbed_in_json(self) -> None:
        register_secret('HANNI_TEST_SECRET', TEST_SECRET)
        logger, buffer = self._capture(JsonFormatter(node_id='t'))
        logger.info('value %s and %s', TEST_SECRET, TOKEN_SHAPED, extra={'api_secret': TEST_SECRET, 'nested': {'k': [TEST_SECRET]}})
        out = buffer.getvalue()
        self.assertNotIn(TEST_SECRET, out)
        self.assertNotIn(TOKEN_SHAPED, out)
        self.assertIn('[REDACTED:HANNI_TEST_SECRET]', out)

    def test_exception_text_is_scrubbed_in_text_format(self) -> None:
        register_secret('HANNI_TEST_SECRET', TEST_SECRET)
        logger, buffer = self._capture(TextFormatter())
        try:
            raise RuntimeError(f'connect failed with {TEST_SECRET}')
        except RuntimeError:
            logger.exception('boom')
        self.assertNotIn(TEST_SECRET, buffer.getvalue())
        self.assertIn('[REDACTED:HANNI_TEST_SECRET]', buffer.getvalue())

    def test_setup_logging_file_sink_never_contains_secret(self) -> None:
        register_secret('HANNI_TEST_SECRET', TEST_SECRET)
        setup_logging(node_id='t', level='DEBUG', log_dir=self.data_dir / 'logs', stream=io.StringIO())
        self.addCleanup(setup_logging, node_id='t', log_dir=None, stream=io.StringIO())
        logging.getLogger('hanni.test.file').warning('secret is %s token=%s', TEST_SECRET, TOKEN_SHAPED)
        for handler in logging.getLogger().handlers:
            handler.flush()
        content = (self.data_dir / 'logs' / 'hanni.jsonl').read_text(encoding='utf-8')
        self.assertIn('secret is [REDACTED:HANNI_TEST_SECRET]', content)
        self.assertNotIn(TEST_SECRET, content)
        self.assertNotIn(TOKEN_SHAPED, content)
