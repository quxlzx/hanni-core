"""Load and validate the YAML configuration files.

Policy enforced here, before any parsing:
* every file must exist and be a YAML mapping;
* no key that looks like a secret (token, password, api_key, ...) may carry a
  string value - secrets come from the environment only.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

from hanni.config.schema import (
    AppConfig,
    ConfigError,
    HanniConfig,
    LoggingConfig,
    Paths,
    parse_hanni,
    parse_models,
    parse_permissions,
    parse_privacy,
)

CONFIG_FILES = ("hanni.yaml", "models.yaml", "permissions.yaml", "privacy.yaml")
DEFAULT_CONFIG_DIR = Path("config")
DEFAULT_DATA_DIR = Path("data")

_SECRET_LIKE_KEY = re.compile(r"(?i)(token|secret|password|passwd|api[_-]?key|private[_-]?key)")


def resolve_config_dir(explicit: Path | None = None, env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    return Path(explicit or env.get("HANNI_CONFIG_DIR") or DEFAULT_CONFIG_DIR)


def resolve_data_dir(explicit: Path | None = None, env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    return Path(explicit or env.get("HANNI_DATA_DIR") or DEFAULT_DATA_DIR)


def load_yaml_mapping(path: Path) -> Mapping[str, Any]:
    if not path.is_file():
        raise ConfigError(f"{path}: file not found")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    if data is None:
        data = {}
    if not isinstance(data, Mapping):
        raise ConfigError(f"{path}: top level must be a mapping")
    _reject_secret_like_values(data, where=path.name)
    return data


def _reject_secret_like_values(node: Any, *, where: str) -> None:
    if isinstance(node, Mapping):
        for key, value in node.items():
            if isinstance(key, str) and _SECRET_LIKE_KEY.search(key) and isinstance(value, str) and value.strip():
                raise ConfigError(f"{where}.{key}: secrets must not be stored in YAML; use the environment / .env")
            _reject_secret_like_values(value, where=f"{where}.{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _reject_secret_like_values(item, where=f"{where}[{index}]")


def load_config(
    config_dir: Path | None = None,
    *,
    data_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> AppConfig:
    """Load all four config files. Raises :class:`ConfigError` naming the file and key on failure."""
    env = os.environ if env is None else env
    config_dir = resolve_config_dir(config_dir, env)
    data_dir = resolve_data_dir(data_dir, env)

    hanni = parse_hanni(load_yaml_mapping(config_dir / "hanni.yaml"))
    override = env.get("HANNI_LOG_LEVEL")
    if override:
        level = override.strip().upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ConfigError(f"HANNI_LOG_LEVEL: invalid level {override!r}")
        hanni = HanniConfig(
            name=hanni.name,
            user=hanni.user,
            logging=LoggingConfig(
                level=level,
                console_format=hanni.logging.console_format,
                file_enabled=hanni.logging.file_enabled,
                file_format=hanni.logging.file_format,
                max_bytes=hanni.logging.max_bytes,
                backup_count=hanni.logging.backup_count,
            ),
            recovery=hanni.recovery,
            speech=hanni.speech,
            memory=hanni.memory,
            laya=hanni.laya,
            mcp=hanni.mcp,
            personality=hanni.personality,
            workflows=hanni.workflows,
            model_routing=hanni.model_routing,
        )

    return AppConfig(
        hanni=hanni,
        models=parse_models(load_yaml_mapping(
            Path(env.get("HANNI_MODEL_CONFIG") or config_dir / "models.yaml"))),
        permissions=parse_permissions(load_yaml_mapping(config_dir / "permissions.yaml")),
        privacy=parse_privacy(load_yaml_mapping(config_dir / "privacy.yaml")),
        paths=Paths(config_dir=config_dir, data_dir=data_dir),
    )
