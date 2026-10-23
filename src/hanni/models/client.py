"""Local OpenAI-compatible model client for llama.cpp.

Milestone 1 deliberately talks to a loopback-only llama.cpp server rather than
embedding llama.cpp into the H.A.N.N.I. process.  This keeps the model runtime
replaceable and lets the CLI, future voice loop, and later workers share the
same client boundary.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Mapping, Sequence

from hanni.config.schema import ModelSpec
from hanni.logs.redaction import redact_text


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A configured model endpoint cannot delegate requests to another source."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ModelProtocolError('Local model endpoint redirects are refused.')


class ModelClientError(RuntimeError):
    """Base class for local model client failures."""


class ModelUnavailableError(ModelClientError):
    """Raised when the configured local model endpoint cannot be reached."""


class ModelProtocolError(ModelClientError):
    """Raised when the local model server returns malformed data."""


class ModelIdentityError(ModelProtocolError):
    """The response names another model; replay cannot restore its identity."""


@dataclass(frozen=True, slots=True)
class ModelHealth:
    model_id: str
    endpoint: str
    ok: bool
    state: str
    detail: str
    latency_ms: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "endpoint": self.endpoint,
            "ok": self.ok,
            "state": self.state,
            "detail": self.detail,
            "latency_ms": self.latency_ms,
        }

    def render_text(self) -> str:
        timing = f" ({self.latency_ms:.0f} ms)" if self.latency_ms is not None else ""
        verdict = "HEALTHY" if self.ok else "UNHEALTHY"
        return f"{self.model_id}: {verdict} state={self.state} endpoint={self.endpoint}{timing} - {self.detail}"




@dataclass(frozen=True, slots=True)
class ModelToolCall:
    id: str
    name: str
    arguments: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ModelTurn:
    content: str
    tool_calls: tuple[ModelToolCall, ...] = ()
    usage: Mapping[str, int] = field(default_factory=dict)


class LlamaCppClient:
    """Small stdlib client for llama.cpp's OpenAI-compatible HTTP API."""

    def __init__(self, spec: ModelSpec, *, max_attempts: int = 3) -> None:
        if spec.backend != "llama.cpp":
            raise ValueError(f"model {spec.id!r} uses unsupported backend {spec.backend!r}")
        self.spec = spec
        self.max_attempts = max(1, max_attempts)
        # Per-client transport; do not mutate urllib's process-wide defaults.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def _open(self, request, *, timeout):
        """One scoped dependency seam, preserving original timeout/retry policy."""
        from hanni.core.response_stream import check_cancelled
        check_cancelled()
        return self._opener.open(request, timeout=timeout)

    @property
    def health_url(self) -> str:
        return f"{self.spec.endpoint.rstrip('/')}/health"

    @property
    def chat_url(self) -> str:
        return f"{self.spec.endpoint.rstrip('/')}/chat/completions"

    def health(self) -> ModelHealth:
        started = time.perf_counter()
        request = urllib.request.Request(self.health_url, method="GET", headers={"Accept": "application/json"})
        try:
            with self._open(request, timeout=self.spec.health_timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
            elapsed = (time.perf_counter() - started) * 1000
            try:
                payload = json.loads(raw or "{}")
            except json.JSONDecodeError:
                return ModelHealth(self.spec.id, self.spec.endpoint, False, "protocol-error", "health response was not JSON", elapsed)
            state = str(payload.get("status", "unknown"))
            ok = state == "ok"
            detail = "llama.cpp model is ready" if ok else redact_text(f"health status={state!r}")
            return ModelHealth(self.spec.id, self.spec.endpoint, ok, "ready" if ok else state, detail, elapsed)
        except urllib.error.HTTPError as exc:
            elapsed = (time.perf_counter() - started) * 1000
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 503:
                return ModelHealth(self.spec.id, self.spec.endpoint, False, "loading", _http_error_detail(exc.code, body), elapsed)
            return ModelHealth(self.spec.id, self.spec.endpoint, False, "http-error", _http_error_detail(exc.code, body), elapsed)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return ModelHealth(self.spec.id, self.spec.endpoint, False, "unreachable", _network_error_detail(exc), elapsed)
        except ModelProtocolError:
            elapsed = (time.perf_counter() - started) * 1000
            return ModelHealth(self.spec.id, self.spec.endpoint, False, "protocol-error", "local model endpoint redirect was refused", elapsed)

    def ensure_loaded(self):
        from hanni.models.manager import current
        manager = current(self.spec)
        if manager: manager.ensure_loaded(self.spec.id)

    def stream_chat(self, messages, **kwargs):
        from hanni.models.manager import inference_lease
        from hanni.core.responsiveness import phase, mark
        performance = kwargs.pop('performance', None)
        if performance is None:
            performance = getattr(self, '_inference_performance', None)
        started = time.perf_counter()
        first = True
        lease = inference_lease(self.spec)
        with phase('local_admission'):
            lease.__enter__()
        try:
            stream = self._stream_chat(messages, performance=performance, **kwargs)
            try:
                for part in stream:
                    from hanni.core.response_stream import check_cancelled
                    check_cancelled()
                    if first:
                        mark('first_model_content')
                    if first and performance is not None:
                        performance['ttft_ms'] = (time.perf_counter() - started) * 1000
                    first = False
                    yield part
            finally:
                close = getattr(stream, 'close', None)
                if callable(close):
                    close()
        finally:
            lease.__exit__(None, None, None)

    def _stream_chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        response_format: Mapping[str, object] | None = None,
        usage: dict | None = None,
        performance: dict | None = None,
    ) -> Iterator[str]:
        """Yield assistant text chunks from a streaming chat completion.

        Retries are only attempted before any text has been yielded. Once a
        visible partial response exists, retrying would duplicate text and is
        therefore surfaced as an error instead.
        """

        payload = {
            "model": self.spec.api_model,
            "messages": [dict(message) for message in messages],
            "stream": True,
            "max_tokens": max_tokens if max_tokens is not None else self.spec.max_tokens,
            "temperature": temperature if temperature is not None else self.spec.temperature,
            "top_p": top_p if top_p is not None else self.spec.top_p,
            # Qwen3 defaults to a thinking mode. For the low-latency voice-first
            # assistant path, M1 starts with thinking disabled; later milestones
            # may opt in per task.
            "chat_template_kwargs": {"enable_thinking": self.spec.thinking_enabled},
        }
        if response_format is not None:
            payload["response_format"] = dict(response_format)
            # Decisions are machine-readable, not a reasoning transcript.
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        if usage is not None:
            payload['stream_options'] = {'include_usage': True}
        body = json.dumps(payload).encode("utf-8")
        last_error: BaseException | None = None

        for attempt in range(1, self.max_attempts + 1):
            yielded = False
            request = urllib.request.Request(
                self.chat_url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            )
            try:
                with self._open(request, timeout=self.spec.request_timeout_seconds) as response:
                    for chunk in _iter_sse_content(response, usage=usage, performance=performance,
                                                   expected_model=self.spec.api_model):
                        yielded = True
                        yield chunk
                return
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ModelProtocolError) as exc:
                last_error = exc
                if yielded or isinstance(exc, ModelIdentityError) or attempt >= self.max_attempts:
                    break
                time.sleep(min(0.20 * (2 ** (attempt - 1)), 1.0))

        if isinstance(last_error, urllib.error.HTTPError):
            try:
                body_text = last_error.read().decode("utf-8", errors="replace")
            except Exception:
                body_text = ""
            raise ModelUnavailableError(_http_error_detail(last_error.code, body_text)) from last_error
        if isinstance(last_error, ModelProtocolError):
            raise last_error
        raise ModelUnavailableError(_network_error_detail(last_error)) from last_error

    def complete_with_tools(
        self,
        messages: Sequence[Mapping[str, object]],
        *,
        tools: Sequence[Mapping[str, object]],
        max_tokens: int | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
    ) -> ModelTurn:
        """Run one non-streaming OpenAI-compatible tool-calling turn.

        llama.cpp exposes tool calls through the normal ``chat/completions``
        shape. Keeping this boundary in the model client means the rest of
        HANNI is independent of Qwen-specific response details.
        """
        payload: dict[str, object] = {
            "model": self.spec.api_model,
            "messages": [dict(message) for message in messages],
            "stream": False,
            "max_tokens": max_tokens if max_tokens is not None else self.spec.max_tokens,
            "temperature": temperature if temperature is not None else self.spec.temperature,
            "top_p": top_p if top_p is not None else self.spec.top_p,
            "chat_template_kwargs": {"enable_thinking": False},
            "tools": [dict(tool) for tool in tools],
            "tool_choice": "auto",
            "parallel_tool_calls": False,
        }
        body = json.dumps(payload).encode("utf-8")
        last_error: BaseException | None = None
        for attempt in range(1, self.max_attempts + 1):
            request = urllib.request.Request(
                self.chat_url, data=body, method="POST",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            try:
                with self._open(request, timeout=self.spec.request_timeout_seconds) as response:
                    raw = response.read().decode("utf-8", errors="replace")
                turn = _parse_tool_turn(raw, expected_model=self.spec.api_model)
                performance = getattr(self, '_inference_performance', None)
                if performance is not None:
                    from hanni.models.performance import server_rates
                    performance.update(server_rates(json.loads(raw)))
                return turn
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ModelProtocolError) as exc:
                last_error = exc
                if isinstance(exc, ModelIdentityError) or attempt >= self.max_attempts:
                    break
                time.sleep(min(0.20 * (2 ** (attempt - 1)), 1.0))
        if isinstance(last_error, urllib.error.HTTPError):
            try:
                body_text = last_error.read().decode("utf-8", errors="replace")
            except Exception:
                body_text = ""
            raise ModelUnavailableError(_http_error_detail(last_error.code, body_text)) from last_error
        if isinstance(last_error, ModelProtocolError):
            raise last_error
        raise ModelUnavailableError(_network_error_detail(last_error)) from last_error

    def chat(self, messages: Sequence[Mapping[str, str]], **kwargs: object) -> str:
        return "".join(self.stream_chat(messages, **kwargs))



def _parse_tool_turn(raw: str, *, expected_model=None) -> ModelTurn:
    try:
        payload = json.loads(raw or "{}")
        _check_response_model(payload, expected_model)
        choices = payload.get("choices") or []
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        calls: list[ModelToolCall] = []
        for index, item in enumerate(message.get("tool_calls") or []):
            function = item.get("function") or {}
            name = function.get("name")
            raw_arguments = function.get("arguments", "{}")
            if not isinstance(name, str) or not name:
                raise ValueError("tool call has no function name")
            if isinstance(raw_arguments, str):
                arguments = json.loads(raw_arguments or "{}")
            elif isinstance(raw_arguments, Mapping):
                arguments = dict(raw_arguments)
            else:
                raise ValueError("tool call arguments are not an object")
            if not isinstance(arguments, dict):
                raise ValueError("tool call arguments are not a JSON object")
            call_id = item.get("id") or f"call_{index}"
            calls.append(ModelToolCall(str(call_id), name, arguments))
        if not isinstance(content, str):
            content = str(content)
        usage = payload.get('usage') or {}
        return ModelTurn(content=content, tool_calls=tuple(calls),
                         usage={key: value for key, value in usage.items() if isinstance(value, int) and not isinstance(value, bool)})
    except (AttributeError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ModelProtocolError("malformed tool-calling response from local model") from exc


def _check_response_model(payload, expected_model):
    if expected_model is not None and payload.get('model') is not None and payload['model'] != expected_model:
        raise ModelIdentityError('The local response names a different configured model.')


def _iter_sse_content(response: Iterable[bytes], *, usage=None, performance=None, expected_model=None) -> Iterator[str]:
    """Parse llama.cpp/OpenAI-style SSE and yield only assistant content."""
    saw_done = False
    for raw_line in response:
        from hanni.core.response_stream import check_cancelled
        check_cancelled()
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or line.startswith(":"):
            continue
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            saw_done = True
            break
        try:
            payload = json.loads(data)
            _check_response_model(payload, expected_model)
            if performance is not None:
                from hanni.models.performance import server_rates
                performance.update(server_rates(payload))
            if usage is not None and isinstance(payload.get('usage'), dict):
                usage.update({key:value for key,value in payload['usage'].items()
                              if key in {'prompt_tokens','completion_tokens','total_tokens'} and type(value) is int and value>=0})
            choices = payload.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
        except (AttributeError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ModelProtocolError("malformed streaming response from local model") from exc
        if isinstance(content, str) and content:
            yield content
    # llama.cpp normally emits [DONE], but closing the response cleanly without
    # it is still a valid end for compatibility with older local builds.
    _ = saw_done


def _http_error_detail(code: int, body: str) -> str:
    message = redact_text(body).strip().replace("\n", " ")
    if len(message) > 300:
        message = message[:297] + "..."
    return f"local model HTTP {code}" + (f": {message}" if message else "")


def _network_error_detail(exc: BaseException | None) -> str:
    if exc is None:
        return "local model request failed"
    reason = getattr(exc, "reason", exc)
    return redact_text(f"local model unavailable: {reason}")
