"""The native agent loop.

prompt -> model -> validated tool calls -> receipts -> repeat -> final answer.

Deliberately small: the intelligence lives in the model and the tool boundary;
this file only moves messages. Tool execution is a callback supplied by the
worker so the durable approval/receipt flow in hanni.hermes.state stays the
single enforcement point.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

from .compact import compact

THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S)


def strip_reasoning(text: str) -> str:
    return THINK_BLOCK.sub("", text or "").split("<think>", 1)[0].strip()


def run_loop(client, *, system_prompt: str, user_message: str,
             tool_specs: list[dict], execute: Callable[[str, dict], dict],
             max_iterations: int = 12, budget_seconds: float = 900.0,
             context_budget_tokens: int | None = 24000,
             on_event: Callable[[str], None] | None = None) -> dict:
    """Returns {'claims': str, 'interrupted': bool, 'iterations': int}."""
    started = time.monotonic()
    schemas = [spec["schema"] for spec in tool_specs]
    valid = {spec["name"] for spec in tool_specs}
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    interrupted = False
    iterations = 0
    final = ""
    for iteration in range(max_iterations):
        iterations = iteration + 1
        if time.monotonic() - started > budget_seconds:
            interrupted = True
            break
        if on_event:
            on_event(f"native loop: request {iterations}/{max_iterations}")
        if context_budget_tokens:
            messages = compact(messages, client, max_tokens=context_budget_tokens)
        reply = client.chat(messages, schemas or None)
        message = reply["message"]
        content = message.get("content") or ""
        reasoning = message.get("reasoning_content") or ""
        calls = message.get("tool_calls") or []
        if not calls:
            final = strip_reasoning(content) or strip_reasoning(reasoning)
            break
        # normalize an assistant turn that carries both prose and calls
        messages.append({"role": "assistant", "content": content, "tool_calls": calls})
        for call in calls:
            name = call.get("function", {}).get("name", "")
            raw_args = call.get("function", {}).get("arguments") or "{}"
            try:
                arguments = json.loads(raw_args)
            except json.JSONDecodeError:
                receipt = {"ok": False, "error": "Tool arguments were not valid JSON; execution blocked."}
            else:
                if name not in valid:
                    receipt = {"ok": False, "error": "Capability outside task scope; no broader authority granted."}
                else:
                    receipt = execute(name, arguments, call.get("id") or f"{name}-{iteration}")
            # a discovery receipt may swap the menu for subsequent turns
            replacement = (receipt.get("data") or {}).get("replacement_menu") if isinstance(receipt, dict) else None
            if replacement:
                schemas = replacement
                valid = {s["function"]["name"] for s in replacement}
            messages.append({"role": "tool", "tool_call_id": call.get("id", name),
                             "content": json.dumps({"untrusted_observation": receipt})})
    else:
        interrupted = True
    if not final:
        # Budget exhausted: force one claim-only turn so the human always
        # gets an answer summarizing what was learned or why it stalled.
        if context_budget_tokens:
            try:
                messages = compact(messages, client, max_tokens=context_budget_tokens)
            except Exception:
                pass
        messages.append({"role": "user", "content":
            "Your tool budget is exhausted. Answer now in plain text: what you "
            "learned, or why you could not finish. Do not call any tools."})
        try:
            reply = client.chat(messages, None)
            m = reply["message"]
            final = strip_reasoning(m.get("content") or "") or strip_reasoning(m.get("reasoning_content") or "")
        except Exception:
            pass
    return {"claims": final, "interrupted": interrupted, "iterations": iterations}
