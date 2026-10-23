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


def load_model(config_path: Path | None = None, model_id: str | None = None) -> dict:
    path = Path(config_path or os.environ.get("HANNI_MODEL_CONFIG", DEFAULT_CONFIG))
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    models = doc.get("models") or []
    if not models:
        raise ValueError(f"no models defined in {path}")
    wanted = model_id or os.environ.get("HANNI_MODEL_ID")
    for entry in models:
        if wanted and entry.get("id") == wanted:
            return entry
    # fall back to the supervisor role, then the first entry
    for entry in models:
        if entry.get("role") == "supervisor":
            return entry
    return models[0]


class NativeClient:
    """Minimal OpenAI-compatible chat client with tool support."""

    def __init__(self, model_cfg: dict, *, timeout: float | None = None):
        self.endpoint = str(model_cfg["endpoint"]).strip().rstrip("/")
        self.api_model = str(model_cfg.get("api_model") or model_cfg["id"]).strip()
        self.api_key = os.environ.get("HANNI_MODEL_API_KEY", "local").strip()
        self.max_tokens = int(model_cfg.get("native_max_tokens", 1500))
        self.temperature = float(model_cfg.get("native_temperature", 0.6))
        self.reasoning_budget = model_cfg.get("native_reasoning_budget")
        self.timeout = timeout

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        import httpx

        payload: dict[str, Any] = {
            "model": self.api_model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if self.reasoning_budget is not None:
            # honored by llama-server (--reasoning-budget) builds
            payload["reasoning_budget_tokens"] = int(self.reasoning_budget)
        timeout = self.timeout or float(os.environ.get("HANNI_MODEL_TIMEOUT", "180"))
        data: dict = {}
        # a single retry on read timeout: shared single-slot brains queue behind
        # interactive traffic; transient starvation should not fail the task
        for attempt in (1, 2):
            try:
                with httpx.Client(timeout=timeout, trust_env=False) as client:
                    response = client.post(
                        f"{self.endpoint}/chat/completions",
                        json=payload,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                    )
                    response.raise_for_status()
                    data = response.json()
                break
            except httpx.ReadTimeout:
                if attempt == 2:
                    raise
        choice = (data.get("choices") or [{}])[0]
        return {"message": choice.get("message") or {}, "finish": choice.get("finish_reason"), "usage": data.get("usage") or {}}
