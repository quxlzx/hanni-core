"""Native model provider.

Reads the resident model from ``config/models.yaml`` (the same file the
dashboard's model controls use) and speaks the OpenAI-compatible
``/chat/completions`` protocol that both Strata and llama-server expose.

Secrets come only from the environment: ``HANNI_MODEL_API_KEY`` (default
``local`` for unauthenticated llama-server endpoints).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = Path("config/models.yaml")


def normalize_endpoint(value: str) -> str:
    from urllib.parse import urlsplit
    endpoint = value.strip().rstrip("/")
    if any(ord(character) < 32 for character in endpoint):
        raise ValueError('Model endpoint cannot contain control characters.')
    parsed = urlsplit(endpoint)
    try:
        parsed.port
    except ValueError:
        raise ValueError('Model endpoint contains an invalid port.') from None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Model endpoint must be an http(s) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use HANNI_MODEL_API_KEY for credentials; endpoint URLs cannot contain credentials, queries or fragments.")
    if endpoint.endswith("/chat/completions"):
        endpoint = endpoint.removesuffix("/chat/completions")
    if not urlsplit(endpoint).path:
        endpoint += "/v1"
    return endpoint


def load_model(config_path: Path | None = None, model_id: str | None = None, *, output_settings=True) -> dict:
    path = Path(config_path or os.environ.get("HANNI_MODEL_CONFIG", DEFAULT_CONFIG))
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    models = doc.get("models") or []
    if not models:
        raise ValueError(f"no models defined in {path}")
    def selected(entry):
        if not output_settings:
            return entry
        from .output_settings import OutputSettings
        return OutputSettings(os.environ.get('HANNI_MODEL_STATE')).apply(entry)
    wanted = model_id or os.environ.get("HANNI_MODEL_ID")
    for entry in models:
        if wanted and entry.get("id") == wanted:
            return selected(entry)
    if wanted:
        raise ValueError(f"Model {wanted!r} is not defined in {path}.")
    # fall back to the supervisor role, then the first entry
    for entry in models:
        if entry.get("role") == "supervisor":
            return selected(entry)
    return selected(models[0])


class NativeClient:
    """Minimal OpenAI-compatible chat client with tool support."""

    def __init__(self, model_cfg: dict, *, timeout: float | None = None, api_key: str | None = None):
        self.endpoint = normalize_endpoint(str(model_cfg["endpoint"]))
        self.api_model = str(model_cfg.get("api_model") or model_cfg["id"]).strip()
        if api_key is not None:
            self.api_key = api_key.strip()
        elif model_cfg.get('api_key_ref'):
            from .model_settings import stored_api_key
            self.api_key = stored_api_key(model_cfg['api_key_ref'])
        else:
            self.api_key = ('local' if model_cfg.get('source') == 'local' else os.environ.get("HANNI_MODEL_API_KEY", "local")).strip()
        from hanni.logs.redaction import register_secret
        if self.api_key != 'local':
            register_secret('model-api', self.api_key)
        self.max_tokens = int(model_cfg.get("native_max_tokens", 1500))
        self.temperature = float(model_cfg.get("native_temperature", 0.6))
        self.reasoning_budget = model_cfg.get("native_reasoning_budget")
        self.timeout = timeout
        self.config = model_cfg
        self.image_resolver = None
        self._image_support_checked = False
        state_root = os.environ.get('HANNI_MODEL_STATE')
        self.reasoning_effort = model_cfg.get('native_reasoning_effort')
        if state_root and model_cfg.get('use_reasoning_preferences', True):
            from .reasoning_settings import ReasoningSettings
            setting = ReasoningSettings(state_root).values(model_cfg)
            self.reasoning_effort = setting['effort']
            self.reasoning_budget = setting['budget']

    def status(self) -> dict:
        import httpx
        result = {"ready": False, "state": "unreachable", "id": self.config["id"],
                  "api_model": self.api_model, "file": self.config.get("model_file") or self.api_model,
                  "context": self.config.get("context_length"), "context_verified": False,
                  "quantization": self.config.get("quantization") or "Not reported",
                  "reasoning_budget_supported": False, "reasoning_disable_supported": False}
        result['image_input_supported'] = False if self.config.get('source') == 'local' else None
        try:
            with httpx.Client(timeout=3, trust_env=False) as client:
                response = client.get(self.endpoint + "/models", headers={"Authorization": f"Bearer {self.api_key}"})
                response.raise_for_status()
                models = response.json().get("data", [])
            present = any(m.get("id") == self.api_model or self.api_model in m.get("aliases", []) for m in models)
            result.update(ready=present, state="ready" if present else "model-not-found")
            if not present:
                result["detail"] = f"Configured model {self.api_model!r} is not advertised by the server."
            if present:
                advertised = next(m for m in models if m.get('id') == self.api_model or self.api_model in m.get('aliases', []))
                modalities = (advertised.get('architecture') or {}).get('input_modalities')
                if isinstance(modalities, list):
                    result['image_input_supported'] = 'image' in modalities
                levels = advertised.get('reasoning_effort_levels') or self.config.get('reasoning_effort_levels') or []
                result['reasoning_levels'] = [level for level in levels if level in {'low', 'medium', 'high'}]
                result['reasoning_disable_supported'] = 'none' in levels
                limit = advertised.get('context_length') or advertised.get('context_window')
                if type(limit) is int and limit > 0:
                    result.update(context=limit, context_verified=True)
                if self.config.get('source') == 'local':
                    try:
                        with httpx.Client(timeout=3, trust_env=False) as client:
                            props = client.get(self.endpoint.removesuffix('/v1') + '/props', headers={'Authorization': f'Bearer {self.api_key}'})
                            props.raise_for_status()
                            metadata = props.json()
                            vision = (metadata.get('modalities') or {}).get('vision')
                            if type(vision) is bool:
                                result['image_input_supported'] = vision
                            result['reasoning_budget_supported'] = True
                            result['reasoning_disable_supported'] = True
                            limit = metadata.get('default_generation_settings', {}).get('n_ctx')
                            if metadata.get('chat_template_caps', {}).get('supports_reasoning_effort') is True:
                                result['reasoning_levels'] = ['low', 'medium', 'high']
                        if type(limit) is int and limit > 0:
                            result.update(context=limit, context_verified=True)
                    except (httpx.HTTPError, ValueError, AttributeError, TypeError):
                        pass
        except httpx.HTTPStatusError as exc:
            result.update(state="loading" if exc.response.status_code == 503 else "http-error",
                          detail=f"Model server returned HTTP {exc.response.status_code}.")
        except (httpx.RequestError, ValueError, AttributeError, TypeError):
            result["detail"] = "Model server could not be reached or returned invalid model metadata."
        return result

    def _payload(self, messages, tools):
        if any(isinstance(message.get('content'), list) and any(part.get('type') == 'hanni_image'
               for part in message['content'] if isinstance(part, dict)) for message in messages):
            if not callable(self.image_resolver):
                raise ValueError('Image attachments cannot be resolved in this session.')
            if not self._image_support_checked:
                status = self.status()
                if not status.get('ready'):
                    raise ValueError('Connect the selected model before sending images.')
                if status.get('image_input_supported') is False:
                    raise ValueError('The selected model does not accept images. Choose an image-capable model in Models, then send again.')
                self._image_support_checked = True
            messages = [{**message, 'content': [self.image_resolver(part) if isinstance(part, dict) and part.get('type') == 'hanni_image' else part
                        for part in message['content']]} if isinstance(message.get('content'), list) else message for message in messages]
        payload: dict[str, Any] = {
            "model": self.api_model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if self.reasoning_effort:
            payload['reasoning_effort'] = self.reasoning_effort
            if self.reasoning_effort == 'none' and self.config.get('source') == 'local':
                payload['chat_template_kwargs'] = {'enable_thinking': False}
        if self.reasoning_budget is not None and self.config.get('source') != 'api':
            # honored by llama-server (--reasoning-budget) builds
            payload["reasoning_budget_tokens"] = int(self.reasoning_budget)
        return payload

    def chat_stream(self, messages, tools=None, *, on_delta):
        import httpx
        from .streaming import read_chat_stream
        payload = {**self._payload(messages, tools), 'stream': True,
                   'stream_options': {'include_usage': True}}
        timeout = self.timeout or float(os.environ.get('HANNI_MODEL_TIMEOUT', '180'))
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            with client.stream('POST', f'{self.endpoint}/chat/completions', json=payload,
                               headers={'Authorization': f'Bearer {self.api_key}'}) as response:
                if response.status_code in (400, 422, 501):
                    response.read()
                    try:
                        error = response.json().get('error') or {}
                    except (ValueError, AttributeError):
                        error = {}
                    unsupported = response.status_code == 501 or (isinstance(error, dict) and (
                        error.get('param') in {'stream', 'stream_options'} or
                        ('stream' in str(error.get('message', '')).lower() and
                         any(word in str(error.get('message', '')).lower() for word in ('unsupported', 'not support', 'unknown', 'unrecognized')))))
                    if unsupported:
                        result = self.chat(messages, tools)
                        on_delta(result['message'])
                        return result
                if response.status_code == 404:
                    raise RuntimeError(f'Model {self.api_model!r} was not found at the configured endpoint.')
                response.raise_for_status()
                # Some compatible providers ignore stream=True and return JSON.
                if 'application/json' in response.headers.get('content-type', ''):
                    response.read()
                    data = response.json()
                    choice = (data.get('choices') or [])[0]
                    result = {'message': choice.get('message') or {}, 'finish': choice.get('finish_reason'),
                              'usage': data.get('usage') or {}, 'timings': data.get('timings') or {}}
                    on_delta(result['message'])
                    return result
                return read_chat_stream(response, on_delta)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        return self._complete(self._payload(messages, tools))

    def chat_json(self, messages, schema):
        """Bounded structured review; never grant tools or switch providers."""
        import httpx
        payload = self._payload(messages, None)
        if self.config.get('source') == 'local':
            payload['response_format'] = {'type': 'json_object', 'schema': schema}
            payload['chat_template_kwargs'] = {'enable_thinking': False}
            payload['reasoning_effort'] = 'none'
        else:
            payload['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'learning_review', 'strict': True, 'schema': schema}}
        try:
            return self._complete(payload, attempts=1)
        except httpx.HTTPStatusError as exc:
            try: error = exc.response.json().get('error', {})
            except (ValueError, AttributeError): error = {}
            message = str(error.get('message', '')).lower() if isinstance(error, dict) else ''
            unsupported = (exc.response.status_code in {400, 422, 501} and isinstance(error, dict) and (
                error.get('param') == 'response_format' or
                any(key in message for key in ('response_format', 'json_schema')) and
                any(word in message for word in ('unsupported', 'not support', 'unknown', 'unrecognized'))))
            if not unsupported: raise
            # Explicit rejection only: one ordinary JSON-prompt completion on
            # this same provider. Output still passes the full review validator.
            return self._complete(self._payload(messages, None), attempts=1)

    def _complete(self, payload, *, attempts=2):
        import httpx
        timeout = self.timeout or float(os.environ.get("HANNI_MODEL_TIMEOUT", "180"))
        data: dict = {}
        # a single retry on read timeout: shared single-slot brains queue behind
        # interactive traffic; transient starvation should not fail the task
        for attempt in range(1, attempts + 1):
            try:
                with httpx.Client(timeout=timeout, trust_env=False) as client:
                    response = client.post(
                        f"{self.endpoint}/chat/completions",
                        json=payload,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                    if response.status_code == 404:
                        raise RuntimeError(f"Model {self.api_model!r} was not found at the configured endpoint. Check --brain-model and the server's /v1/models response.")
                    response.raise_for_status()
                    data = response.json()
                break
            except httpx.ReadTimeout:
                if attempt == attempts:
                    raise
        if not isinstance(data, dict) or not isinstance(data.get("choices"), list) or not data["choices"]:
            raise ValueError("Model server returned no completion choices.")
        choice = data["choices"][0]
        return {"message": choice.get("message") or {}, "finish": choice.get("finish_reason"),
                "usage": data.get("usage") or {}, 'timings': data.get('timings') or {}}
