"""Model registry helpers for HANNI's single resident assistant model."""
from __future__ import annotations

from hanni.config.schema import AppConfig, ModelSpec
from hanni.models.client import LlamaCppClient


def model_spec(config: AppConfig, model_id: str | None = None) -> ModelSpec:
    """Return the configured assistant model.

    HANNI now ships with exactly one resident model. ``model_id`` remains as a
    narrow diagnostic override so existing CLI callers fail clearly rather than
    silently selecting a retired router/planner profile.
    """
    if model_id is None:
        return config.models.supervisor
    return config.models.by_id(model_id)


def create_client(config: AppConfig, model_id: str | None = None) -> LlamaCppClient:
    spec = model_spec(config, model_id)
    if spec.backend == "llama.cpp":
        client = LlamaCppClient(spec, max_attempts=config.hanni.recovery.max_attempts)
        from hanni.models.adaptive import current
        engine = current(config)
        return engine.wrap_client(client) if engine is not None else client
    raise ValueError(f"unsupported model backend: {spec.backend}")
