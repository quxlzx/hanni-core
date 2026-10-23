"""Health check (Milestone 0 exit criterion).

Reports whether configuration loads, declared secrets are present (by name
only), data/log directories are writable, and whether the emergency stop is
tripped. Every rendered form of the report is passed through redaction.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

import hanni
from hanni.config.loader import CONFIG_FILES, load_config, resolve_config_dir, resolve_data_dir
from hanni.config.schema import ConfigError
from hanni.config.secrets import SECRET_SPECS, InvalidSecretError, MissingSecretError, SecretSpec, load_secrets
from hanni.core.identity import local_machine_name
from hanni.core.shutdown import FileStopStateStore
from hanni.core.state import RuntimeMode
from hanni.logs.redaction import redact_text, redact_value

MIN_PYTHON = (3, 12)
Status = Literal["ok", "warn", "fail"]


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: Status
    detail: str


@dataclass(frozen=True, slots=True)
class HealthReport:
    node_id: str  # machine label (HANNI_NODE_ID or the hostname)
    version: str
    python_version: str
    mode: RuntimeMode
    checks: tuple[CheckResult, ...]

    @property
    def ok(self) -> bool:
        return all(check.status != "fail" for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return redact_value(
            {
                "node_id": self.node_id,
                "version": self.version,
                "python": self.python_version,
                "mode": self.mode.value,
                "ok": self.ok,
                "checks": [{"name": c.name, "status": c.status, "detail": c.detail} for c in self.checks],
            }
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def render_text(self) -> str:
        lines = [f"H.A.N.N.I. health - node={self.node_id} version={self.version} python={self.python_version}"]
        for check in self.checks:
            lines.append(f"  [{check.status.upper():<4}] {check.name}: {check.detail}")
        verdict = "HEALTHY" if self.ok else "UNHEALTHY"
        lines.append(f"Overall: {verdict} (mode={self.mode.value})")
        return redact_text("\n".join(lines))


def run_health_check(
    *,
    config_dir: Path | None = None,
    data_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
    dotenv_path: Path | None = Path(".env"),
    node_id: str | None = None,
    secret_specs: tuple[SecretSpec, ...] = SECRET_SPECS,
) -> HealthReport:
    config_dir = resolve_config_dir(config_dir, env)
    data_dir = resolve_data_dir(data_dir, env)
    checks: list[CheckResult] = []

    py = sys.version_info
    py_text = f"{py.major}.{py.minor}.{py.micro}"
    checks.append(
        CheckResult("python", "ok" if (py.major, py.minor) >= MIN_PYTHON else "fail", f"{py_text} (>= {MIN_PYTHON[0]}.{MIN_PYTHON[1]} required)")
    )

    loaded_config = None
    try:
        loaded_config = load_config(config_dir, data_dir=data_dir, env=env)
        checks.append(CheckResult("config", "ok", f"loaded {', '.join(CONFIG_FILES)} from {config_dir.resolve()}"))
    except ConfigError as exc:
        checks.append(CheckResult("config", "fail", str(exc)))

    required = sorted(s.name for s in secret_specs if s.required)
    if dotenv_path is not None:
        if dotenv_path.is_file():
            checks.append(CheckResult("dotenv", "ok", f"{dotenv_path} found"))
        elif required:
            checks.append(CheckResult("dotenv", "warn", f"no {dotenv_path} file; required secrets must come from the environment (see .env.example)"))
        else:
            checks.append(CheckResult("dotenv", "ok", f"no {dotenv_path} file (none needed: V1 requires no secrets)"))

    try:
        secrets = load_secrets(env=env, dotenv_path=dotenv_path, specs=secret_specs)
        detail = f"required present: {', '.join(required)}" if required else "none required (V1 needs no secrets)"
        checks.append(CheckResult("secrets", "ok", detail))
        optional_missing = [s for s in secret_specs if not s.required and not secrets.has(s.name)]
        if optional_missing:
            detail = ", ".join(f"{s.name} (needed from Milestone {s.needed_from_milestone})" for s in optional_missing)
            checks.append(CheckResult("secrets-optional", "warn", f"not set: {detail}"))
    except MissingSecretError as exc:
        checks.append(CheckResult("secrets", "fail", f"missing: {', '.join(exc.names)} - set it in the environment or .env (see .env.example)"))
    except InvalidSecretError as exc:
        checks.append(CheckResult("secrets", "fail", "; ".join(f"{name} {problem}" for name, problem in exc.problems.items())))

    checks.append(_writable("data-dir", data_dir))
    checks.append(_writable("log-dir", data_dir / "logs"))

    if loaded_config is not None and loaded_config.hanni.memory.enabled:
        try:
            from hanni.memory import MemoryStore
            memory_path = data_dir / loaded_config.hanni.memory.database_file
            store = MemoryStore(memory_path, max_item_chars=loaded_config.hanni.memory.max_item_chars)
            checks.append(CheckResult("durable-memory", "ok", f"SQLite ready: {memory_path.resolve()} ({store.count()} memories)"))
        except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
            checks.append(CheckResult("durable-memory", "fail", f"SQLite unavailable: {exc}"))

    record = FileStopStateStore.for_data_dir(data_dir).load()
    if record is None:
        mode = RuntimeMode.NORMAL
        checks.append(CheckResult("emergency-stop", "ok", "not tripped"))
    else:
        mode = RuntimeMode.SAFE_MODE
        checks.append(
            CheckResult(
                "emergency-stop",
                "warn",
                f"TRIPPED at {record.tripped_at.isoformat()} via {record.source.value} by {record.requested_by} "
                f"(reason: {record.reason}); resume with `{hanni.COMMAND_NAME} resume`",
            )
        )

    return HealthReport(
        node_id=node_id or local_machine_name(env),
        version=hanni.__version__,
        python_version=py_text,
        mode=mode,
        checks=tuple(checks),
    )


def _writable(name: str, directory: Path) -> CheckResult:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return CheckResult(name, "ok", f"writable: {directory.resolve()}")
    except OSError as exc:
        return CheckResult(name, "fail", f"not writable: {directory} ({exc})")
