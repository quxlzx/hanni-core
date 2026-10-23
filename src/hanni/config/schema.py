"""Typed configuration schemas for H.A.N.N.I.

All non-secret configuration lives in YAML files under ``config/``; secrets never
appear here (see :mod:`hanni.config.secrets`). Parsing is strict: unknown keys,
wrong types, and values outside the limits fixed by the Master Spec are rejected
with a :class:`ConfigError` that names the file and key.

These remain lightweight stdlib dataclasses with explicit validation. Runtime
model settings added in Milestone 1 are validated here as well; H.A.N.N.I. does
not need a validation-framework migration simply to add the local LLM client.
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# ---- Limits fixed by the specifications (not configurable) --------------------------------
MAX_EPHEMERAL_RETENTION_SECONDS = 120  # Master Spec §15; V1 plan §8-9
DANGEROUS_LEVEL = 3  # Master Spec §20 / D-0004: Level 3 always requires explicit confirmation
MAX_AUTO_APPROVE_LEVEL = 2  # High Autonomy Owner Mode may auto-approve at most Level 2
NO_TOOL_ACCESS = -1  # profile value meaning "no tool access at all"
MAX_RECOVERY_ATTEMPTS = 10

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LOG_FORMATS = ("text", "json")
MODEL_ROLES = frozenset({"supervisor"})
MODEL_SPLIT_MODES = ("none", "layer", "row", "tensor")
REQUIRED_PROFILES = ("owner", "everyone_else")


class ConfigError(ValueError):
    """Raised when configuration is missing, malformed, or violates a fixed limit."""


_MISSING = object()


class _Section:
    """Reads and type-checks keys from a YAML mapping, producing precise error messages."""

    def __init__(self, data: Any, *, where: str) -> None:
        if not isinstance(data, Mapping):
            raise ConfigError(f"{where}: expected a mapping, got {type(data).__name__}")
        self._data = data
        self.where = where

    def allow_only(self, *allowed: str) -> None:
        unknown = sorted(str(k) for k in self._data if k not in allowed)
        if unknown:
            raise ConfigError(f"{self.where}: unknown key(s) {', '.join(unknown)}; allowed: {', '.join(allowed)}")

    def section(self, key: str) -> "_Section":
        if key not in self._data:
            raise ConfigError(f"{self.where}: missing required section '{key}'")
        return _Section(self._data[key], where=f"{self.where}.{key}")

    def _raw(self, key: str, default: Any) -> Any:
        if key in self._data and self._data[key] is not None:
            return self._data[key]
        if default is _MISSING:
            raise ConfigError(f"{self.where}: missing required key '{key}'")
        return default

    def get_str(self, key: str, *, default: Any = _MISSING, choices: Sequence[str] | None = None) -> str:
        value = self._raw(key, default)
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{self.where}.{key}: expected a non-empty string, got {value!r}")
        if choices is not None and value not in choices:
            raise ConfigError(f"{self.where}.{key}: must be one of {', '.join(choices)}; got {value!r}")
        return value

    def get_int(self, key: str, *, default: Any = _MISSING, minimum: int | None = None, maximum: int | None = None) -> int:
        value = self._raw(key, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{self.where}.{key}: expected an integer, got {value!r}")
        if minimum is not None and value < minimum:
            raise ConfigError(f"{self.where}.{key}: must be >= {minimum}, got {value}")
        if maximum is not None and value > maximum:
            raise ConfigError(f"{self.where}.{key}: must be <= {maximum}, got {value}")
        return value

    def get_bool(self, key: str, *, default: Any = _MISSING) -> bool:
        value = self._raw(key, default)
        if not isinstance(value, bool):
            raise ConfigError(f"{self.where}.{key}: expected true/false, got {value!r}")
        return value

    def get_float(self, key: str, *, default: Any = _MISSING, minimum: float | None = None, maximum: float | None = None) -> float:
        value = self._raw(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{self.where}.{key}: expected a number, got {value!r}")
        number = float(value)
        if minimum is not None and number < minimum:
            raise ConfigError(f"{self.where}.{key}: must be >= {minimum}, got {number}")
        if maximum is not None and number > maximum:
            raise ConfigError(f"{self.where}.{key}: must be <= {maximum}, got {number}")
        return number

    def get_str_list(self, key: str, *, default: Sequence[str] = ()) -> tuple[str, ...]:
        value = self._raw(key, list(default))
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            raise ConfigError(f"{self.where}.{key}: expected a list of non-empty strings")
        return tuple(value)

    def get_number_list(
        self, key: str, *, default: Sequence[float] = (), minimum: float | None = None
    ) -> tuple[float, ...]:
        value = self._raw(key, list(default))
        if not isinstance(value, list):
            raise ConfigError(f"{self.where}.{key}: expected a list of numbers")
        numbers: list[float] = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ConfigError(f"{self.where}.{key}: expected a list of numbers")
            number = float(item)
            if minimum is not None and number < minimum:
                raise ConfigError(f"{self.where}.{key}: every value must be >= {minimum}")
            numbers.append(number)
        return tuple(numbers)

    def get_sections(self, key: str) -> list["_Section"]:
        value = self._raw(key, _MISSING)
        if not isinstance(value, list):
            raise ConfigError(f"{self.where}.{key}: expected a list")
        return [_Section(item, where=f"{self.where}.{key}[{i}]") for i, item in enumerate(value)]


# ---- hanni.yaml ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    level: str = "INFO"
    console_format: str = "text"
    file_enabled: bool = True
    file_format: str = "json"
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5


@dataclass(frozen=True, slots=True)
class RecoveryConfig:
    max_attempts: int = 3  # total attempts per operation, first attempt included (D-0003)


@dataclass(frozen=True, slots=True)
class VadConfig:
    threshold: float = 0.5
    min_silence_ms: int = 500
    speech_pad_ms: int = 100
    pre_roll_ms: int = 250
    max_utterance_seconds: float = 30.0


@dataclass(frozen=True, slots=True)
class SttConfig:
    model: str = "small.en"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "en"
    beam_size: int = 1


@dataclass(frozen=True, slots=True)
class TtsConfig:
    enabled: bool = True
    backend: str = "windows_sapi"
    voice: str = "default"
    rate: int = 0
    volume: int = 100
    chunk_chars: int = 260
    timeout_seconds: int = 120
    model_dir: str = "voice"  # relative to HANNI's data directory
    speed: float = 0.97
    language: str = "en-gb"
    cpu_threads: int = 4
    sapi_fallback: bool = True
    pitch_semitones: float = 0.0


@dataclass(frozen=True, slots=True)
class BargeInConfig:
    enabled: bool = True
    interrupt_phrases: tuple[str, ...] = ("stop", "wait", "hold on", "quiet", "cancel", "no", "no wait", "hanni stop", "honey stop", "ani stop")
    echo_suppression: bool = True
    echo_min_words: int = 3
    echo_overlap_ratio: float = 0.72
    poll_ms: int = 50


@dataclass(frozen=True, slots=True)
class RelevanceConfig:
    wake_names: tuple[str, ...] = ("hanni", "ani", "hani", "hanny", "hannie")
    # 0 means stay active until an explicit disengage phrase is spoken.
    engagement_seconds: float = 0.0
    disengage_phrases: tuple[str, ...] = (
        "that's all", "that is all", "that'll be all", "that will be all",
        "we're done", "we are done", "go quiet", "you can go quiet",
        "stop responding", "stand by", "standby", "never mind", "nevermind",
        "never mind hanni", "thanks hanni that's all", "thank you hanni that's all",
    )
    filler_words: tuple[str, ...] = (
        "um", "umm", "ummm", "uh", "uhh", "uhhh", "hm", "hmm", "hmmm",
        "mm", "mmm", "erm", "er", "err", "ah",
    )
    acknowledgement_words: tuple[str, ...] = (
        "thanks", "thank you", "yeah", "yep", "okay", "ok", "alright", "got it", "cool",
    )


@dataclass(frozen=True, slots=True)
class SpeechConfig:
    sample_rate: int = 16_000
    channels: int = 1
    block_samples: int = 512
    input_device: str = "default"
    vad: VadConfig = VadConfig()
    stt: SttConfig = SttConfig()
    tts: TtsConfig = TtsConfig()
    barge_in: BargeInConfig = BargeInConfig()
    relevance: RelevanceConfig = RelevanceConfig()


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    enabled: bool = True
    database_file: str = "memory.sqlite3"
    max_item_chars: int = 1200
    search_limit: int = 8
    extraction_enabled: bool = True
    retrieval_enabled: bool = True
    max_context_chars: int = 4000
    min_relevance_score: int = 25
    context_enabled: bool = False
    max_context_tokens: int = 4000


@dataclass(frozen=True, slots=True)
class LayaConfig:
    """Requested rollout configuration; it is not evidence that a model is active."""
    advisory_enabled: bool = False
    retrieval_enabled: bool = False
    transport: str = 'local'
    url: str = 'http://127.0.0.1:8766/v1/advisory/evaluate'
    allow_stored_memories: bool = False
    allow_remote_text: bool = False
    allow_remote_memories: bool = False
    timeout_seconds: float = 1.5
    max_queue: int = 8
    cache_seconds: int = 30




@dataclass(frozen=True, slots=True)
class McpConfig:
    enabled: bool = True
    read_only: bool = True
    allowed_actions: tuple[str, ...] = ("google_calendar.create",)
    max_tools_per_turn: int = 8
    max_tool_rounds: int = 3
    tool_result_chars: int = 12000


@dataclass(frozen=True, slots=True)
class UserConfig:
    timezone: str = "UTC"


@dataclass(frozen=True, slots=True)
class PersonalityConfig:
    enabled: bool = True
    style: str = "hanni"
    intensity: float = 0.65


@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    """Bounded workflow admission; no model-generated authority overrides."""

    enabled: bool = True
    default_mode: str = "assisted"
    max_steps: int = 16
    max_parallel_reads: int = 2
    max_active_workflows: int = 2
    max_retries: int = 1
    step_timeout_seconds: int = 30
    max_duration_seconds: int = 600
    planning_timeout_seconds: int = 120
    max_plan_attempts: int = 2
    approval_ttl_seconds: int = 300
    max_goal_chars: int = 4000
    max_payload_bytes: int = 65536
    max_result_bytes: int = 65536
    max_artifact_bytes: int = 5242880
    max_invocations: int = 32
    max_workflows: int = 500
    retention_days: int = 30
    lease_seconds: int = 10


@dataclass(frozen=True, slots=True)
class ModelRoutingConfig:
    """Conservative measurable model-policy thresholds, not model authority."""
    policy: str = 'balanced'
    max_fallbacks: int = 2
    max_queue_seconds: float = 5.0
    minimum_samples: int = 20
    minimum_accuracy_lower_bound: float = .7


@dataclass(frozen=True, slots=True)
class HanniConfig:
    name: str = "H.A.N.N.I."
    user: UserConfig = UserConfig()
    logging: LoggingConfig = LoggingConfig()
    recovery: RecoveryConfig = RecoveryConfig()
    speech: SpeechConfig = SpeechConfig()
    memory: MemoryConfig = MemoryConfig()
    laya: LayaConfig = LayaConfig()
    mcp: McpConfig = McpConfig()
    personality: PersonalityConfig = PersonalityConfig()
    workflows: WorkflowConfig = WorkflowConfig()
    model_routing: ModelRoutingConfig = ModelRoutingConfig()


def parse_hanni(data: Any, *, where: str = "hanni.yaml") -> HanniConfig:
    root = _Section(data, where=where)
    root.allow_only("hanni", "user", "logging", "recovery", "speech", "memory", "laya", "mcp", "personality", "workflows", "model_routing")
    identity = root.section("hanni")
    identity.allow_only("name")
    user = UserConfig()
    if "user" in root._data:
        section = root.section("user")
        section.allow_only("timezone")
        timezone_name = section.get_str("timezone", default="UTC")
        try:
            ZoneInfo(timezone_name)
        except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
            raise ConfigError(f"{section.where}.timezone: use an IANA timezone such as America/Chicago") from exc
        user = UserConfig(timezone=timezone_name)
    logging_cfg = LoggingConfig()
    if "logging" in root._data:
        section = root.section("logging")
        section.allow_only("level", "console_format", "file_enabled", "file_format", "max_bytes", "backup_count")
        logging_cfg = LoggingConfig(
            level=section.get_str("level", default="INFO").upper(),
            console_format=section.get_str("console_format", default="text", choices=LOG_FORMATS),
            file_enabled=section.get_bool("file_enabled", default=True),
            file_format=section.get_str("file_format", default="json", choices=LOG_FORMATS),
            max_bytes=section.get_int("max_bytes", default=10 * 1024 * 1024, minimum=64 * 1024),
            backup_count=section.get_int("backup_count", default=5, minimum=0, maximum=100),
        )
        if logging_cfg.level not in LOG_LEVELS:
            raise ConfigError(f"{where}.logging.level: must be one of {', '.join(LOG_LEVELS)}; got {logging_cfg.level!r}")
    recovery = RecoveryConfig()
    if "recovery" in root._data:
        section = root.section("recovery")
        section.allow_only("max_attempts")
        recovery = RecoveryConfig(max_attempts=section.get_int("max_attempts", default=3, minimum=1, maximum=MAX_RECOVERY_ATTEMPTS))

    speech = SpeechConfig()
    if "speech" in root._data:
        section = root.section("speech")
        section.allow_only("sample_rate", "channels", "block_samples", "input_device", "vad", "stt", "tts", "barge_in", "relevance")
        sample_rate = section.get_int("sample_rate", default=16_000, minimum=8_000, maximum=48_000)
        channels = section.get_int("channels", default=1, minimum=1, maximum=1)
        block_samples = section.get_int("block_samples", default=512, minimum=128, maximum=4096)
        input_device = section.get_str("input_device", default="default")

        vad = VadConfig()
        if "vad" in section._data:
            vad_section = section.section("vad")
            vad_section.allow_only("threshold", "min_silence_ms", "speech_pad_ms", "pre_roll_ms", "max_utterance_seconds")
            vad = VadConfig(
                threshold=vad_section.get_float("threshold", default=0.5, minimum=0.01, maximum=0.99),
                min_silence_ms=vad_section.get_int("min_silence_ms", default=500, minimum=50, maximum=5000),
                speech_pad_ms=vad_section.get_int("speech_pad_ms", default=100, minimum=0, maximum=1000),
                pre_roll_ms=vad_section.get_int("pre_roll_ms", default=250, minimum=0, maximum=2000),
                max_utterance_seconds=vad_section.get_float("max_utterance_seconds", default=30.0, minimum=1.0, maximum=120.0),
            )

        stt = SttConfig()
        if "stt" in section._data:
            stt_section = section.section("stt")
            stt_section.allow_only("model", "device", "compute_type", "language", "beam_size")
            stt = SttConfig(
                model=stt_section.get_str("model", default="small.en"),
                device=stt_section.get_str("device", default="cpu", choices=("cpu", "cuda", "auto")),
                compute_type=stt_section.get_str("compute_type", default="int8"),
                language=stt_section.get_str("language", default="en"),
                beam_size=stt_section.get_int("beam_size", default=1, minimum=1, maximum=10),
            )
        tts = TtsConfig()
        if "tts" in section._data:
            tts_section = section.section("tts")
            tts_section.allow_only("enabled", "backend", "voice", "rate", "volume", "chunk_chars", "timeout_seconds",
                                   "model_dir", "speed", "language", "cpu_threads", "sapi_fallback", "pitch_semitones")
            tts = TtsConfig(
                enabled=tts_section.get_bool("enabled", default=True),
                backend=tts_section.get_str("backend", default="windows_sapi", choices=("windows_sapi", "kokoro", "windows_australian")),
                voice=tts_section.get_str("voice", default="default"),
                rate=tts_section.get_int("rate", default=0, minimum=-10, maximum=10),
                volume=tts_section.get_int("volume", default=100, minimum=0, maximum=100),
                chunk_chars=tts_section.get_int("chunk_chars", default=260, minimum=40, maximum=2000),
                timeout_seconds=tts_section.get_int("timeout_seconds", default=120, minimum=1, maximum=600),
                model_dir=tts_section.get_str("model_dir", default="voice"),
                speed=tts_section.get_float("speed", default=0.97, minimum=0.5, maximum=2.0),
                language=tts_section.get_str("language", default="en-gb", choices=("en-us", "en-gb", "en-au")),
                cpu_threads=tts_section.get_int("cpu_threads", default=4, minimum=1, maximum=16),
                sapi_fallback=tts_section.get_bool("sapi_fallback", default=True),
                pitch_semitones=tts_section.get_float("pitch_semitones", default=0.0, minimum=-4, maximum=4),
            )

        barge_in = BargeInConfig()
        if "barge_in" in section._data:
            barge_section = section.section("barge_in")
            barge_section.allow_only("enabled", "interrupt_phrases", "echo_suppression", "echo_min_words", "echo_overlap_ratio", "poll_ms")
            barge_in = BargeInConfig(
                enabled=barge_section.get_bool("enabled", default=True),
                interrupt_phrases=tuple(p.strip().lower() for p in barge_section.get_str_list("interrupt_phrases", default=BargeInConfig().interrupt_phrases)),
                echo_suppression=barge_section.get_bool("echo_suppression", default=True),
                echo_min_words=barge_section.get_int("echo_min_words", default=3, minimum=2, maximum=20),
                echo_overlap_ratio=barge_section.get_float("echo_overlap_ratio", default=0.72, minimum=0.5, maximum=1.0),
                poll_ms=barge_section.get_int("poll_ms", default=50, minimum=10, maximum=500),
            )

        relevance = RelevanceConfig()
        if "relevance" in section._data:
            relevance_section = section.section("relevance")
            relevance_section.allow_only("wake_names", "engagement_seconds", "disengage_phrases", "filler_words", "acknowledgement_words")
            wake_names = tuple(name.strip().lower() for name in relevance_section.get_str_list("wake_names", default=RelevanceConfig().wake_names))
            if not wake_names:
                raise ConfigError(f"{relevance_section.where}.wake_names: at least one wake name is required")
            relevance = RelevanceConfig(
                wake_names=wake_names,
                engagement_seconds=relevance_section.get_float("engagement_seconds", default=0.0, minimum=0.0, maximum=300.0),
                disengage_phrases=tuple(
                    phrase.strip().lower()
                    for phrase in relevance_section.get_str_list("disengage_phrases", default=RelevanceConfig().disengage_phrases)
                ),
                filler_words=tuple(
                    word.strip().lower()
                    for word in relevance_section.get_str_list("filler_words", default=RelevanceConfig().filler_words)
                ),
                acknowledgement_words=tuple(
                    word.strip().lower()
                    for word in relevance_section.get_str_list("acknowledgement_words", default=RelevanceConfig().acknowledgement_words)
                ),
            )

        speech = SpeechConfig(
            sample_rate=sample_rate,
            channels=channels,
            block_samples=block_samples,
            input_device=input_device,
            vad=vad,
            stt=stt,
            tts=tts,
            barge_in=barge_in,
            relevance=relevance,
        )

    memory = MemoryConfig()
    if "memory" in root._data:
        section = root.section("memory")
        section.allow_only("enabled", "database_file", "max_item_chars", "search_limit", "extraction_enabled", "retrieval_enabled", "max_context_chars", "min_relevance_score", "context_enabled", "max_context_tokens")
        database_file = section.get_str("database_file", default="memory.sqlite3")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", database_file) or database_file in {".", ".."}:
            raise ConfigError(f"{section.where}.database_file: must be a simple file name inside the data directory")
        memory = MemoryConfig(
            enabled=section.get_bool("enabled", default=True),
            database_file=database_file,
            max_item_chars=section.get_int("max_item_chars", default=1200, minimum=64, maximum=10000),
            search_limit=section.get_int("search_limit", default=8, minimum=1, maximum=50),
            extraction_enabled=section.get_bool("extraction_enabled", default=True),
            retrieval_enabled=section.get_bool("retrieval_enabled", default=True),
            max_context_chars=section.get_int("max_context_chars", default=4000, minimum=512, maximum=16000),
            min_relevance_score=section.get_int("min_relevance_score", default=25, minimum=1, maximum=100),
            context_enabled=section.get_bool('context_enabled', default=False),
            max_context_tokens=section.get_int('max_context_tokens', default=4000, minimum=128, maximum=4000),
        )

    laya = LayaConfig()
    if 'laya' in root._data:
        section = root.section('laya')
        section.allow_only(*LayaConfig.__dataclass_fields__)
        laya = LayaConfig(
            advisory_enabled=section.get_bool('advisory_enabled', default=False),
            retrieval_enabled=section.get_bool('retrieval_enabled', default=False),
            transport=section.get_str('transport', default='local', choices=('local', 'remote-ssh')),
            url=section.get_str('url', default=laya.url),
            allow_stored_memories=section.get_bool('allow_stored_memories', default=False),
            allow_remote_text=section.get_bool('allow_remote_text', default=False),
            allow_remote_memories=section.get_bool('allow_remote_memories', default=False),
            timeout_seconds=section.get_float('timeout_seconds', default=1.5, minimum=0.05, maximum=3.),
            max_queue=section.get_int('max_queue', default=8, minimum=1, maximum=32),
            cache_seconds=section.get_int('cache_seconds', default=30, minimum=1, maximum=60),
        )
        from urllib.parse import urlsplit
        endpoint = urlsplit(laya.url)
        if endpoint.scheme != 'http' or endpoint.hostname not in {'127.0.0.1', 'localhost'} or endpoint.path != '/v1/advisory/evaluate' or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ConfigError('laya.url must be authenticated loopback HTTP /v1/advisory/evaluate')
        if laya.retrieval_enabled and not laya.advisory_enabled:
            raise ConfigError('laya.retrieval_enabled requires explicitly enabled advisory mode')

    mcp = McpConfig()
    if "mcp" in root._data:
        section = root.section("mcp")
        section.allow_only("enabled", "read_only", "allowed_actions", "max_tools_per_turn", "max_tool_rounds", "tool_result_chars")
        mcp = McpConfig(
            enabled=section.get_bool("enabled", default=True),
            read_only=section.get_bool("read_only", default=True),
            allowed_actions=section.get_str_list("allowed_actions", default=("google_calendar.create",)),
            max_tools_per_turn=section.get_int("max_tools_per_turn", default=8, minimum=1, maximum=8),
            max_tool_rounds=section.get_int("max_tool_rounds", default=3, minimum=1, maximum=8),
            tool_result_chars=section.get_int("tool_result_chars", default=12000, minimum=1000, maximum=50000),
        )

    personality = PersonalityConfig()
    if "personality" in root._data:
        section = root.section("personality")
        section.allow_only("enabled", "style", "intensity")
        personality = PersonalityConfig(
            enabled=section.get_bool("enabled", default=True),
            style=section.get_str("style", default="hanni", choices=("hanni", "neutral")),
            intensity=section.get_float("intensity", default=0.65, minimum=0.0, maximum=1.0),
        )

    workflows = WorkflowConfig()
    if "workflows" in root._data:
        section = root.section("workflows")
        bounds = {
            "max_steps": (1, 32), "max_parallel_reads": (1, 4),
            "max_active_workflows": (1, 4), "max_retries": (0, 1),
            "step_timeout_seconds": (1, 300), "max_duration_seconds": (1, 3600),
            "planning_timeout_seconds": (1, 300), "max_plan_attempts": (1, 2),
            "approval_ttl_seconds": (1, 3600), "max_goal_chars": (64, 8000),
            "max_payload_bytes": (1024, 131072), "max_result_bytes": (1024, 131072),
            "max_artifact_bytes": (1024, 10485760), "max_invocations": (1, 64),
            "max_workflows": (1, 1000), "retention_days": (1, 90),
            "lease_seconds": (2, 60),
        }
        section.allow_only("enabled", "default_mode", *bounds)
        values = {key: section.get_int(key, default=getattr(workflows, key), minimum=low, maximum=high)
                  for key, (low, high) in bounds.items()}
        workflows = WorkflowConfig(
            enabled=section.get_bool("enabled", default=True),
            default_mode=section.get_str("default_mode", default="assisted", choices=("assisted", "supervised", "background")),
            **values,
        )

    model_routing = ModelRoutingConfig()
    if 'model_routing' in root._data:
        section = root.section('model_routing')
        section.allow_only(*ModelRoutingConfig.__dataclass_fields__)
        queue = section.get_float('max_queue_seconds', default=5., minimum=.1, maximum=30.)
        quality = section.get_float('minimum_accuracy_lower_bound', default=.7, minimum=.5, maximum=.99)
        if not math.isfinite(queue) or not math.isfinite(quality):
            raise ConfigError('model_routing thresholds must be finite.')
        model_routing = ModelRoutingConfig(
            policy=section.get_str('policy', default='balanced', choices=('balanced', 'fast', 'quality')),
            max_fallbacks=section.get_int('max_fallbacks', default=2, minimum=0, maximum=2),
            max_queue_seconds=queue,
            minimum_samples=section.get_int('minimum_samples', default=20, minimum=20, maximum=1000),
            minimum_accuracy_lower_bound=quality,
        )
    return HanniConfig(
        name=identity.get_str("name", default="H.A.N.N.I."),
        user=user,
        logging=logging_cfg,
        recovery=recovery,
        speech=speech,
        memory=memory,
        laya=laya,
        mcp=mcp,
        personality=personality,
        workflows=workflows,
        model_routing=model_routing,
    )



# ---- models.yaml --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModelSpec:
    id: str
    role: str
    backend: str
    model_file: str
    endpoint: str
    keep_loaded: bool
    context_length: int | None
    api_model: str
    hf_repo: str | None
    quantization: str | None
    gpu_layers: int
    split_mode: str | None
    tensor_split: tuple[float, ...]
    device_name_hints: tuple[str, ...]
    max_tokens: int
    temperature: float
    top_p: float
    thinking_enabled: bool
    request_timeout_seconds: int
    health_timeout_seconds: int
    jinja_enabled: bool = True
    parallel: int = 1
    kv_key_type: str = 'q8_0'
    kv_value_type: str = 'q8_0'
    mmap: bool = True
    no_host: bool = False
    idle_unload_seconds: int = 600
    minimum_residency_seconds: int = 120
    retry_cooldown_seconds: int = 60
    ram_budget_mb: int = 0
    vram_budget_mb: int = 0
    fallback_device_name_hints: tuple[str, ...] = ()
    fallback_gpu_layers: int = 0
    gpu_selection: str = 'configured'
    gpu_preference: int = 0
    vision_projector: str | None = None


@dataclass(frozen=True, slots=True)
class ModelsConfig:
    models: tuple[ModelSpec, ...]
    idle_unload_seconds: int
    ram_reserve_mb: int = 3072
    vram_reserve_mb: int = 1024
    critical_ram_percent: float = 90.

    @property
    def supervisor(self) -> ModelSpec:
        return next(m for m in self.models if m.role == "supervisor")

    def by_id(self, model_id: str) -> ModelSpec:
        for model in self.models:
            if model.id == model_id:
                return model
        raise KeyError(model_id)


def parse_models(data: Any, *, where: str = "models.yaml") -> ModelsConfig:
    root = _Section(data, where=where)
    root.allow_only("models", "idle_unload_seconds", "ram_reserve_mb", "vram_reserve_mb", "critical_ram_percent")
    specs: list[ModelSpec] = []
    for section in root.get_sections("models"):
        section.allow_only(
            "id", "role", "backend", "model_file", "endpoint", "keep_loaded", "context_length",
            "api_model", "hf_repo", "quantization", "gpu_layers", "split_mode", "tensor_split",
            "device_name_hints", "max_tokens", "temperature", "top_p", "thinking_enabled",
            "request_timeout_seconds", "health_timeout_seconds", "jinja_enabled",
            "parallel", "kv_key_type", "kv_value_type", "mmap", "no_host", "idle_unload_seconds",
            "minimum_residency_seconds", "retry_cooldown_seconds", "ram_budget_mb", "vram_budget_mb",
            "fallback_device_name_hints", "fallback_gpu_layers",
            "gpu_selection", "gpu_preference",
            "vision_projector",
        )
        endpoint = section.get_str("endpoint").rstrip("/")
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ConfigError(f"{section.where}.endpoint: must be a valid http:// or https:// URL")
        if parsed.hostname.lower() not in {"127.0.0.1", "localhost", "::1"}:
            raise ConfigError(
                f"{section.where}.endpoint: V1 model endpoints must be loopback-only; got host {parsed.hostname!r}"
            )
        context_length = None
        if "context_length" in section._data:
            context_length = section.get_int("context_length", minimum=512)
        hf_repo = section.get_str("hf_repo") if "hf_repo" in section._data else None
        quantization = section.get_str("quantization") if "quantization" in section._data else None
        split_mode = section.get_str("split_mode", choices=MODEL_SPLIT_MODES) if "split_mode" in section._data else None
        tensor_split = section.get_number_list("tensor_split", minimum=0.0) if "tensor_split" in section._data else ()
        device_name_hints = section.get_str_list("device_name_hints") if "device_name_hints" in section._data else ()
        gpu_selection = section.get_str('gpu_selection', default='configured', choices=['configured', 'most_vram', 'smallest_8gb'])
        if gpu_selection in {'most_vram', 'smallest_8gb'} and (device_name_hints or tensor_split or split_mode or section._data.get('fallback_device_name_hints')):
            raise ConfigError(f'{section.where}: automatic GPU selection chooses one GPU; remove manual device/split settings')
        if tensor_split and not any(value > 0 for value in tensor_split):
            raise ConfigError(f"{section.where}.tensor_split: at least one value must be greater than zero")
        if tensor_split and device_name_hints and len(tensor_split) != len(device_name_hints):
            raise ConfigError(
                f"{section.where}.tensor_split: expected {len(device_name_hints)} values to match device_name_hints"
            )
        specs.append(
            ModelSpec(
                id=section.get_str("id"),
                role=section.get_str("role", choices=sorted(MODEL_ROLES)),
                backend=section.get_str("backend"),
                model_file=section.get_str("model_file"),
                endpoint=endpoint,
                keep_loaded=section.get_bool("keep_loaded", default=False),
                context_length=context_length,
                api_model=section.get_str("api_model", default=section.get_str("id")),
                hf_repo=hf_repo,
                quantization=quantization,
                gpu_layers=section.get_int("gpu_layers", default=99, minimum=0, maximum=999),
                split_mode=split_mode,
                tensor_split=tensor_split,
                device_name_hints=device_name_hints,
                max_tokens=section.get_int("max_tokens", default=1024, minimum=1, maximum=32768),
                temperature=section.get_float("temperature", default=0.6, minimum=0.0, maximum=2.0),
                top_p=section.get_float("top_p", default=0.95, minimum=0.0, maximum=1.0),
                thinking_enabled=section.get_bool("thinking_enabled", default=False),
                jinja_enabled=section.get_bool("jinja_enabled", default=True),
                request_timeout_seconds=section.get_int("request_timeout_seconds", default=180, minimum=1, maximum=3600),
                health_timeout_seconds=section.get_int("health_timeout_seconds", default=3, minimum=1, maximum=60),
                parallel=section.get_int('parallel', default=1, minimum=1, maximum=8),
                kv_key_type=section.get_str('kv_key_type', default='q8_0', choices=['f16','q8_0','q4_0']),
                kv_value_type=section.get_str('kv_value_type', default='q8_0', choices=['f16','q8_0','q4_0']),
                mmap=section.get_bool('mmap', default=True),
                no_host=section.get_bool('no_host', default=False),
                idle_unload_seconds=section.get_int('idle_unload_seconds', default=600, minimum=1),
                minimum_residency_seconds=section.get_int('minimum_residency_seconds', default=120, minimum=0),
                retry_cooldown_seconds=section.get_int('retry_cooldown_seconds', default=60, minimum=1),
                ram_budget_mb=section.get_int('ram_budget_mb', default=0, minimum=0),
                vram_budget_mb=section.get_int('vram_budget_mb', default=0, minimum=0),
                fallback_device_name_hints=section.get_str_list('fallback_device_name_hints') if 'fallback_device_name_hints' in section._data else (),
                fallback_gpu_layers=section.get_int('fallback_gpu_layers', default=0, minimum=0, maximum=999),
                gpu_selection=gpu_selection,
                gpu_preference=section.get_int('gpu_preference', default=0, minimum=0),
                vision_projector=section.get_str('vision_projector') if 'vision_projector' in section._data else None,
            )
        )
    ids = [m.id for m in specs]
    for spec in specs:
        projector = spec.vision_projector
        if projector and (Path(projector).name != projector or '/' in projector or '\\' in projector
                          or not projector.lower().endswith('.gguf')):
            raise ConfigError(f'{where}.models: vision_projector must be a GGUF filename in the configured model cache')
    if len(ids) != len(set(ids)):
        raise ConfigError(f"{where}.models: model ids must be unique")
    if len(specs) != 1:
        raise ConfigError(f"{where}.models: HANNI assistant mode requires exactly one configured model (found {len(specs)})")
    supervisors = [m for m in specs if m.role == "supervisor"]
    if len(supervisors) != 1:
        raise ConfigError(f"{where}.models: exactly one model must have role 'supervisor' (found {len(supervisors)})")
    return ModelsConfig(models=tuple(specs), idle_unload_seconds=root.get_int("idle_unload_seconds", default=600, minimum=0),
                        ram_reserve_mb=root.get_int('ram_reserve_mb', default=3072, minimum=0),
                        vram_reserve_mb=root.get_int('vram_reserve_mb', default=1024, minimum=0),
                        critical_ram_percent=root.get_float('critical_ram_percent', default=90., minimum=50., maximum=99.))


# ---- permissions.yaml ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PermissionLevel:
    level: int
    name: str
    description: str
    auto_approve_allowed: bool


@dataclass(frozen=True, slots=True)
class PermissionProfile:
    name: str
    max_auto_approve_level: int  # NO_TOOL_ACCESS (-1) .. MAX_AUTO_APPROVE_LEVEL (2)
    chat_only: bool


@dataclass(frozen=True, slots=True)
class PermissionsConfig:
    levels: tuple[PermissionLevel, ...]
    profiles: Mapping[str, PermissionProfile]

    @property
    def owner(self) -> PermissionProfile:
        return self.profiles["owner"]


def parse_permissions(data: Any, *, where: str = "permissions.yaml") -> PermissionsConfig:
    root = _Section(data, where=where)
    root.allow_only("levels", "profiles")
    levels: list[PermissionLevel] = []
    for section in root.get_sections("levels"):
        section.allow_only("level", "name", "description", "auto_approve_allowed")
        level = PermissionLevel(
            level=section.get_int("level", minimum=0, maximum=DANGEROUS_LEVEL),
            name=section.get_str("name"),
            description=section.get_str("description", default="-"),
            auto_approve_allowed=section.get_bool("auto_approve_allowed"),
        )
        if level.level == DANGEROUS_LEVEL and level.auto_approve_allowed:
            raise ConfigError(f"{section.where}: level {DANGEROUS_LEVEL} can never be auto-approved (Master Spec §20)")
        levels.append(level)
    if sorted(l.level for l in levels) != list(range(DANGEROUS_LEVEL + 1)):
        raise ConfigError(f"{where}.levels: must define exactly levels 0..{DANGEROUS_LEVEL}, each once")

    profiles_section = root.section("profiles")
    profiles: dict[str, PermissionProfile] = {}
    for name in profiles_section._data:
        section = profiles_section.section(str(name))
        section.allow_only("max_auto_approve_level", "chat_only")
        profile = PermissionProfile(
            name=str(name),
            max_auto_approve_level=section.get_int("max_auto_approve_level", minimum=NO_TOOL_ACCESS, maximum=DANGEROUS_LEVEL),
            chat_only=section.get_bool("chat_only", default=False),
        )
        if profile.max_auto_approve_level > MAX_AUTO_APPROVE_LEVEL:
            raise ConfigError(
                f"{section.where}.max_auto_approve_level: may not exceed {MAX_AUTO_APPROVE_LEVEL}; "
                f"level {DANGEROUS_LEVEL} always requires explicit confirmation"
            )
        profiles[profile.name] = profile
    missing = [p for p in REQUIRED_PROFILES if p not in profiles]
    if missing:
        raise ConfigError(f"{where}.profiles: missing required profile(s) {', '.join(missing)}")
    return PermissionsConfig(levels=tuple(sorted(levels, key=lambda l: l.level)), profiles=profiles)


# ---- privacy.yaml -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EphemeralRetention:
    raw_audio_seconds: int = MAX_EPHEMERAL_RETENTION_SECONDS
    transcript_seconds: int = MAX_EPHEMERAL_RETENTION_SECONDS
    screen_frames_seconds: int = MAX_EPHEMERAL_RETENTION_SECONDS


@dataclass(frozen=True, slots=True)
class ScreenExclusions:
    process_names: tuple[str, ...] = ()
    window_title_patterns: tuple[str, ...] = ()
    url_patterns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PrivacyConfig:
    retention: EphemeralRetention = EphemeralRetention()
    screen_exclusions: ScreenExclusions = ScreenExclusions()


def parse_privacy(data: Any, *, where: str = "privacy.yaml") -> PrivacyConfig:
    root = _Section(data, where=where)
    root.allow_only("ephemeral_retention", "screen_exclusions")
    retention_section = root.section("ephemeral_retention")
    retention_section.allow_only("raw_audio_seconds", "transcript_seconds", "screen_frames_seconds")
    kwargs = {
        key: retention_section.get_int(key, default=MAX_EPHEMERAL_RETENTION_SECONDS, minimum=1, maximum=MAX_EPHEMERAL_RETENTION_SECONDS)
        for key in ("raw_audio_seconds", "transcript_seconds", "screen_frames_seconds")
    }
    exclusions = ScreenExclusions()
    if "screen_exclusions" in root._data:
        section = root.section("screen_exclusions")
        section.allow_only("process_names", "window_title_patterns", "url_patterns")
        exclusions = ScreenExclusions(
            process_names=section.get_str_list("process_names"),
            window_title_patterns=section.get_str_list("window_title_patterns"),
            url_patterns=section.get_str_list("url_patterns"),
        )
        for key in ("window_title_patterns", "url_patterns"):
            for pattern in getattr(exclusions, key):
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise ConfigError(f"{section.where}.{key}: invalid regular expression {pattern!r}: {exc}") from exc
    return PrivacyConfig(retention=EphemeralRetention(**kwargs), screen_exclusions=exclusions)


# ---- Aggregate ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Paths:
    config_dir: Path
    data_dir: Path

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"


@dataclass(frozen=True, slots=True)
class AppConfig:
    hanni: HanniConfig
    models: ModelsConfig
    permissions: PermissionsConfig
    privacy: PrivacyConfig
    paths: Paths
