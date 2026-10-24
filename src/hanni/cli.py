"""``hanni`` command-line entry point for the single-model local assistant."""

from __future__ import annotations

import argparse
import json
import os
import queue
import sqlite3
import re
import sys
import time
import threading
from dataclasses import replace
from pathlib import Path
from typing import Mapping, Sequence

import hanni
from hanni.core.interaction import interaction
from hanni.config.loader import load_config, resolve_config_dir, resolve_data_dir
from hanni.config.schema import AppConfig, ConfigError, LoggingConfig
from hanni.core.health import run_health_check
from hanni.core.identity import Actor, local_machine_name
from hanni.core.orchestrator import TextSession
from hanni.core.response_style import sanitize_assistant_text
from hanni.core.shutdown import LocalStopControls, StopSource
from hanni.logs import correlation, get_logger, setup_logging
from hanni.models import ModelClientError, create_client, model_spec, snapshot_resources

LOG_LEVEL_CHOICES = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config-dir", type=Path, help="directory with HANNI YAML configuration")
    common.add_argument("--data-dir", type=Path, help="directory for local logs/state/memory")
    common.add_argument("--env-file", type=Path, default=Path(".env"), help="optional local environment file")
    common.add_argument("--log-level", choices=LOG_LEVEL_CHOICES)
    common.add_argument("--no-file-log", action="store_true")

    parser = argparse.ArgumentParser(
        prog=hanni.COMMAND_NAME,
        description="H.A.N.N.I. - local Windows assistant with one resident model and read-only MCP tools.",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    health = sub.add_parser("health", parents=[common], help="validate local configuration and state")
    health.add_argument("--json", action="store_true")
    status = sub.add_parser("status", parents=[common], help="show emergency-stop state")
    status.add_argument("--json", action="store_true")
    stop = sub.add_parser("stop", parents=[common], help="enter Safe Mode on this machine")
    stop.add_argument("--reason", default="terminal emergency stop")
    sub.add_parser("resume", parents=[common], help="clear Safe Mode locally")
    sub.add_parser("version", parents=[common], help="print version")

    eval_cmd = sub.add_parser("eval", help="run HANNI evaluation suites")
    eval_sub = eval_cmd.add_subparsers(dest="eval_command", required=True, metavar="SUITE")
    llm_eval = eval_sub.add_parser("llm-tools", parents=[common], help="benchmark the configured model with synthetic MCP results")
    llm_coverage = eval_sub.add_parser("llm-coverage", parents=[common], help="audit model-facing capabilities against LLM scenario coverage")
    llm_coverage.add_argument("--cases", type=Path, default=Path("evals/llm_tools/capability_coverage_v1.jsonl"))
    llm_coverage.add_argument("--json", type=Path, default=Path("evals/llm_tools/results/capability_coverage_audit.json"))
    llm_coverage.add_argument("--strict", action="store_true", help="fail on undercoverage or fixture/schema drift")
    artifact_check = eval_sub.add_parser("artifact-check", parents=[common], help="verify saved LLM benchmark identity and result counts")
    artifact_check.add_argument("report", type=Path)
    language_eval = eval_sub.add_parser("routing-language-v2", parents=[common], help="evaluate owner-style development routing without tool execution")
    language_eval.add_argument("--cases", type=Path, default=Path("evals/routing/language_generalization_v2.jsonl"))
    language_eval.add_argument("--json", type=Path, default=Path("evals/routing/results/language_generalization_v2.json"))
    language_eval.add_argument("--min-pass-rate", type=float, default=90.0)
    mutation_eval = eval_sub.add_parser("routing-mutations", parents=[common], help="probe development phrases with deterministic ASR-style mutations")
    mutation_eval.add_argument("--cases", type=Path, default=Path("evals/routing/language_generalization_v3.jsonl"))
    mutation_eval.add_argument("--json", type=Path, default=Path("evals/routing/results/language_v3_mutations.json"))
    mutation_eval.add_argument("--seed", type=int, default=17)
    mt_mutation_eval = eval_sub.add_parser("routing-multiturn-mutations", parents=[common], help="probe follow-up turns with deterministic mutations")
    mt_mutation_eval.add_argument("--cases", type=Path, default=Path("evals/routing/multiturn_v1.jsonl"))
    mt_mutation_eval.add_argument("--json", type=Path, default=Path("evals/routing/results/multiturn_mutations.json"))
    multiturn_eval = eval_sub.add_parser("routing-multiturn-v1", parents=[common], help="evaluate short multi-turn routing without tool execution")
    multiturn_eval.add_argument("--cases", type=Path, default=Path("evals/routing/multiturn_v1.jsonl"))
    multiturn_eval.add_argument("--json", type=Path, default=Path("evals/routing/results/multiturn_v1.json"))
    personality_eval = eval_sub.add_parser("personality-v1", parents=[common], help="compare neutral and HANNI style on synthetic evidence")
    personality_eval.add_argument("--cases", type=Path, default=Path("evals/personality/personality_v1.jsonl"))
    personality_eval.add_argument("--json", type=Path, default=Path("evals/personality/results/personality_ab.json"))
    personality_eval.add_argument("--limit", type=int, default=20)
    personality_v2 = eval_sub.add_parser("personality-v2", parents=[common], help="compare neutral and V2 style on synthetic evidence")
    personality_v2.add_argument("--cases", type=Path, default=Path("evals/personality/personality_v2.jsonl"))
    personality_v2.add_argument("--json", type=Path, default=Path("evals/personality/results/personality_v2_ab.json"))
    personality_v2.add_argument("--limit", type=int, default=50)
    routing_debug = eval_sub.add_parser("routing-debug", parents=[common], help="show deterministic routing decisions without executing tools")
    routing_debug.add_argument("query", nargs="+")
    llm_eval.add_argument("--family", help="run one scenario family")
    llm_eval.add_argument("--case", dest="case_id", help="run one scenario ID")
    llm_eval.add_argument("--json", type=Path, default=Path("data/llm-tool-eval.json"), metavar="PATH")
    llm_eval.add_argument("--cases", type=Path, default=Path("evals/llm_tools/cases.jsonl"), metavar="PATH")
    llm_eval.add_argument("--model", "--model-id", dest="model_id", default=None,
                          help="configured model ID for this eval only")
    llm_eval.add_argument("--endpoint", help="temporary loopback endpoint override")
    llm_eval.add_argument("--api-model", help="temporary API model-name override")
    llm_eval.add_argument("--audit", action="store_true", help="check routing and mocked-result coverage without running a model")
    llm_eval.add_argument("--trace", action="store_true", help="show observable routing, tool calls, mock results, and score for one case")
    llm_eval.add_argument("--rescore", type=Path, metavar="SAVED_REPORT",
                          help="re-grade saved observable model turns and original mock results without inference")
    llm_eval.add_argument("--resume", action="store_true", help="continue a matching JSON checkpoint")
    llm_compare = eval_sub.add_parser("compare", help="compare completed 150-case LLM tool reports")
    llm_compare.add_argument("first", type=Path)
    llm_compare.add_argument("second", type=Path)

    google = sub.add_parser("google", help="connect and manage Google access")
    google_sub = google.add_subparsers(dest="google_command", required=True, metavar="ACTION")
    google_login = google_sub.add_parser("login", parents=[common], help="connect a Google account in the browser")
    google_login.add_argument("--account", default="personal")
    google_login.add_argument("--scopes", nargs='+', help="service grants, e.g. calendar.read gmail.read drive.read docs.read tasks.read")
    google_login.add_argument("--email", help="optional expected address; otherwise choose in Google sign-in")
    google_login.add_argument("--client-secrets", type=Path, help="Google OAuth Desktop client JSON")
    google_login.add_argument("--calendar", action="append", dest="calendar_ids")
    google_login.add_argument("--replace", action="store_true")
    google_status = google_sub.add_parser("status", parents=[common], help="show connected Google accounts")
    google_status.add_argument("--verify", action="store_true", help="probe only services authorized for each account")
    google_status.add_argument("--json", action="store_true")
    google_accounts = google_sub.add_parser("accounts", parents=[common], help="list named Google connections without network access")
    google_accounts.add_argument("--json", action="store_true")
    google_accounts.set_defaults(verify=False)
    google_use = google_sub.add_parser("use", parents=[common], help="choose the default Google account")
    google_use.add_argument("account")
    google_use.add_argument("--service", choices=('calendar', 'gmail', 'drive', 'docs', 'tasks'))
    google_logout = google_sub.add_parser("logout", parents=[common], help="remove HANNI's local Google authorization")
    google_logout.add_argument("--account", default="personal")

    chat = sub.add_parser("chat", parents=[common], help="chat with the single local assistant model")
    chat.add_argument("prompt", nargs="*", metavar="PROMPT")
    chat.add_argument("--model-id", default=None)
    chat.add_argument("--max-tokens", type=int, default=None)
    chat.add_argument("--temperature", type=float, default=None)
    chat.add_argument("--top-p", type=float, default=None)

    mh = sub.add_parser("model-health", parents=[common], help="check the local llama.cpp endpoint")
    mh.add_argument("--model-id", default=None)
    mh.add_argument("--json", action="store_true")
    mi = sub.add_parser("model-info", parents=[common], help="show configured model/runtime metadata")
    mi.add_argument("--model-id", default=None)
    mi.add_argument("--json", action="store_true")
    resources = sub.add_parser("resources", parents=[common], help="show local CPU/RAM/GPU telemetry")
    resources.add_argument("--json", action="store_true")

    mics = sub.add_parser("mics", parents=[common], help="list microphone/input devices")
    mics.add_argument("--json", action="store_true")
    speech_info = sub.add_parser("speech-info", parents=[common], help="show local speech configuration")
    speech_info.add_argument("--json", action="store_true")
    tts_info = sub.add_parser("tts-info", parents=[common], help="show local TTS configuration")
    tts_info.add_argument("--json", action="store_true")
    voices = sub.add_parser("voices", parents=[common], help="list installed Windows SAPI voices")
    voices.add_argument("--json", action="store_true")
    speak = sub.add_parser("speak", parents=[common], help="speak TEXT with local TTS")
    speak.add_argument("text", nargs="+", metavar="TEXT")
    listen = sub.add_parser("listen", parents=[common], help="transcribe local microphone speech")
    listen.add_argument("--device", default=None)
    listen.add_argument("--once", action="store_true")
    relevance_info = sub.add_parser("relevance-info", parents=[common], help="show wake/engagement configuration")
    relevance_info.add_argument("--json", action="store_true")
    barge_info = sub.add_parser("barge-info", parents=[common], help="show interruption configuration")
    barge_info.add_argument("--json", action="store_true")

    tools = sub.add_parser("tools", parents=[common], help="list validated local capabilities")
    tools.add_argument("--json", action="store_true")
    tool_run = sub.add_parser("tool-run", aliases=["capability-call"], parents=[common], help="manually execute one validated capability")
    tool_run.add_argument("name")
    tool_run.add_argument("--args", default=None)
    tool_run.add_argument("--arg", action="append", default=[], metavar="KEY=VALUE")
    tool_run.add_argument("--confirm", action="store_true")
    tool_run.add_argument("--json", action="store_true")
    tool_audit = sub.add_parser("tool-audit", parents=[common], help="show recent local tool audit records")
    tool_audit.add_argument("--limit", type=int, default=20)
    tool_audit.add_argument("--json", action="store_true")
    capabilities = sub.add_parser("capabilities", parents=[common], help="show registered capability descriptors")
    capabilities.add_argument("--json", action="store_true")
    capability_search = sub.add_parser("capability-search", parents=[common], help="rank local capabilities without executing them")
    capability_search.add_argument("goal", nargs="+")
    capability_search.add_argument("--limit", type=int, default=None)
    capability_search.add_argument("--json", action="store_true")
    capability_get = sub.add_parser("capability-get", parents=[common], help="show one capability schema")
    capability_get.add_argument("name")
    capability_get.add_argument("--json", action="store_true")

    remember = sub.add_parser("remember", parents=[common], help="store one explicit durable memory locally")
    remember.add_argument("text", nargs="+", metavar="TEXT")
    remember.add_argument("--json", action="store_true")
    memories = sub.add_parser("memories", parents=[common], help="list recent durable memories")
    memories.add_argument("--limit", type=int, default=None)
    memories.add_argument("--json", action="store_true")
    memory_search = sub.add_parser("memory-search", parents=[common], help="search durable memories locally")
    memory_search.add_argument("query", nargs="+", metavar="QUERY")
    memory_search.add_argument("--limit", type=int, default=None)
    memory_search.add_argument("--json", action="store_true")
    memory_context = sub.add_parser("memory-context", parents=[common], help="inspect bounded memory context for a query")
    memory_context.add_argument("query", nargs="+", metavar="QUERY")
    memory_context.add_argument("--json", action="store_true")
    memory_info = sub.add_parser("memory-info", parents=[common], help="show local memory configuration")
    memory_info.add_argument("--json", action="store_true")
    memory_cleanup = sub.add_parser("memory-cleanup", parents=[common], help="verify SQLite integrity and checkpoint deletion residue")
    memory_cleanup.add_argument("--json", action="store_true")
    forget = sub.add_parser("forget", parents=[common], help="delete matching durable memory")
    forget.add_argument("query", nargs="+", metavar="QUERY")
    forget.add_argument("--all", action="store_true", dest="delete_all")
    forget.add_argument("--json", action="store_true")

    typed = sub.add_parser("text", aliases=["type"], parents=[common], help="keyboard HANNI session using the resident model + MCP")
    typed.add_argument("prompt", nargs="*", metavar="PROMPT")
    typed.add_argument("--model-id", default=None)
    typed.add_argument("--tts", action="store_true")
    attend = sub.add_parser("attend", parents=[common], help="always-listening local voice session using the resident model + MCP")
    attend.add_argument("--device", default=None)
    attend.add_argument("--once", action="store_true")
    attend.add_argument("--show-ignored", action="store_true")
    attend.add_argument("--model-id", default=None)
    attend.add_argument("--no-tts", action="store_true")
    return parser

def run(argv: Sequence[str] | None = None, *, shutdown_event=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "eval" and args.eval_command == "compare":
        from hanni.evals.comparison import run_cli
        return run_cli(args)
    env = os.environ
    config_dir = resolve_config_dir(args.config_dir, env)
    data_dir = resolve_data_dir(args.data_dir, env)
    node_id = local_machine_name(env)

    logging_cfg = _logging_config(config_dir, data_dir, env)
    setup_logging(
        node_id=node_id,
        level=args.log_level or logging_cfg.level,
        console_format=logging_cfg.console_format,
        log_dir=None if (args.no_file_log or not logging_cfg.file_enabled) else data_dir / "logs",
        file_format=logging_cfg.file_format,
        max_bytes=logging_cfg.max_bytes,
        backup_count=logging_cfg.backup_count,
    )
    log = get_logger("cli")

    with correlation():
        if args.command == "version":
            print(f"{hanni.COMMAND_NAME} {hanni.__version__}")
            return 0

        if args.command == "google":
            return _run_google(args, config_dir)

        if args.command == "eval" and args.eval_command == "llm-tools":
            from hanni.evals.llm_tools import run_cli
            return run_cli(args, config_dir=config_dir, data_dir=data_dir, env=env)
        if args.command == "eval" and args.eval_command == "llm-coverage":
            from hanni.evals.llm_coverage import main as run_coverage
            return run_coverage(["--cases", str(args.cases), "--json", str(args.json)]
                                + (["--strict"] if args.strict else []))
        if args.command == "eval" and args.eval_command == "artifact-check":
            from hanni.evals.artifact_integrity import main as check_artifact
            return check_artifact([str(args.report)])
        if args.command == "eval" and args.eval_command == "routing-language-v2":
            from hanni.evals.routing_language import main as run_language
            return run_language(["--cases", str(args.cases), "--config", str(config_dir),
                                 "--json", str(args.json), "--min-pass-rate", str(args.min_pass_rate)])
        if args.command == "eval" and args.eval_command == "routing-mutations":
            from hanni.evals.routing_mutations import main as run_mutations
            return run_mutations(["--cases", str(args.cases), "--json", str(args.json),
                                  "--seed", str(args.seed)])
        if args.command == "eval" and args.eval_command == "routing-multiturn-mutations":
            from hanni.evals.routing_mutations import multiturn_main
            return multiturn_main(["--cases", str(args.cases), "--json", str(args.json)])
        if args.command == "eval" and args.eval_command == "routing-multiturn-v1":
            from hanni.evals.routing_multiturn import main as run_multiturn
            return run_multiturn(["--cases", str(args.cases), "--config", str(config_dir), "--json", str(args.json)])
        if args.command == "eval" and args.eval_command == "personality-v1":
            from hanni.evals.personality import main as run_personality
            return run_personality(["--cases", str(args.cases), "--config", str(config_dir),
                                    "--json", str(args.json), "--limit", str(args.limit)])
        if args.command == "eval" and args.eval_command == "personality-v2":
            from hanni.evals.personality import main as run_personality
            return run_personality(["--cases", str(args.cases), "--config", str(config_dir),
                                    "--json", str(args.json), "--limit", str(args.limit), "--variant", "v2"])
        if args.command == "eval" and args.eval_command == "routing-debug":
            from hanni.evals.routing_debug import main as run_debug
            return run_debug(["--config", str(config_dir), *args.query])
        if args.command == "health":
            report = run_health_check(config_dir=config_dir, data_dir=data_dir, env=env, dotenv_path=args.env_file, node_id=node_id)
            print(report.to_json() if args.json else report.render_text())
            log.info("Health check finished", extra={"ok": report.ok, "mode": report.mode.value})
            return 0 if report.ok else 1

        if args.command == "mics":
            return _run_mics(args)

        if args.command in {"model-health", "model-info", "chat", "text", "type", "speech-info", "tts-info", "voices", "speak", "listen", "relevance-info", "barge-info", "tools", "tool-run", "capability-call", "tool-audit", "capabilities", "capability-search", "capability-get", "remember", "memories", "memory-search", "memory-context", "memory-info", "memory-cleanup", "forget", "attend"}:
            try:
                config = load_config(config_dir, data_dir=data_dir, env=env)
            except ConfigError as exc:
                print(f"Configuration error: {exc}", file=sys.stderr)
                return 2

            if args.command == "model-health":
                try:
                    client = create_client(config, args.model_id)
                except (KeyError, ValueError) as exc:
                    print(f"Model configuration error: {exc}", file=sys.stderr)
                    return 2
                report = client.health()
                print(json.dumps(report.to_dict(), indent=2) if args.json else report.render_text())
                return 0 if report.ok else 1

            if args.command == "model-info":
                try:
                    spec = model_spec(config, args.model_id)
                except KeyError as exc:
                    print(f"Unknown model id: {exc.args[0]}", file=sys.stderr)
                    return 2
                info = _model_info(spec)
                if args.json:
                    print(json.dumps(info, indent=2))
                else:
                    for key, value in info.items():
                        print(f"{key}: {value}")
                return 0

            if args.command == "speech-info":
                info = _speech_info(config.hanni.speech, config.privacy.retention)
                if args.json:
                    print(json.dumps(info, indent=2))
                else:
                    for key, value in info.items():
                        print(f"{key}: {value}")
                return 0

            if args.command == "tts-info":
                info = _tts_info(config.hanni.speech.tts)
                if args.json:
                    print(json.dumps(info, indent=2))
                else:
                    for key, value in info.items():
                        print(f"{key}: {value}")
                return 0

            if args.command == "voices":
                return _run_voices(args)

            if args.command == "speak":
                return _run_speak(args, config)

            if args.command == "relevance-info":
                info = _relevance_info(config.hanni.speech.relevance)
                if args.json:
                    print(json.dumps(info, indent=2))
                else:
                    for key, value in info.items():
                        print(f"{key}: {value}")
                return 0

            if args.command == "barge-info":
                info = _barge_info(config.hanni.speech.barge_in)
                if args.json:
                    print(json.dumps(info, indent=2))
                else:
                    for key, value in info.items():
                        print(f"{key}: {value}")
                return 0

            if args.command == "tools":
                return _run_tools(args, config, data_dir)

            if args.command in {"tool-run", "capability-call"}:
                return _run_tool(args, config, data_dir)

            if args.command == "tool-audit":
                return _run_tool_audit(args, config, data_dir)

            if args.command in {"capabilities", "capability-search", "capability-get"}:
                return _run_capability_diagnostics(args, config)

            if args.command in {"remember", "memories", "memory-search", "memory-context", "memory-info", "memory-cleanup", "forget"}:
                try:
                    return _run_memory_cli(args, config)
                except (sqlite3.Error, OSError, RuntimeError, ValueError) as exc:
                    print(f"Durable memory unavailable: {exc}", file=sys.stderr)
                    return 1

            if args.command == "listen":
                return _run_listen(args, config)

            if args.command in {"text", "type"}:
                return _run_typed(args, config, shutdown_event=shutdown_event)

            if args.command == "attend":
                return _run_attend(args, config, shutdown_event=shutdown_event)

            return _run_chat(args, config)

        if args.command == "resources":
            snapshot = snapshot_resources()
            print(snapshot.to_json() if args.json else snapshot.render_text())
            return 0

        controls = LocalStopControls(data_dir, machine_name=node_id)
        if args.command == "stop":
            record = controls.trip(args.reason)
            print(f"EMERGENCY STOP active on {node_id}: tripped {record.tripped_at.isoformat()} via {record.source.value} ({record.reason})")
            print(f"Safe Mode until `{hanni.COMMAND_NAME} resume` is run on this machine.")
            return 0
        if args.command == "resume":
            was_tripped = controls.record is not None
            controls.clear()
            print(f"{node_id}: {'emergency stop cleared; normal mode' if was_tripped else 'emergency stop was not tripped; nothing to do'}")
            return 0
        if args.command == "status":
            record = controls.record
            if args.json:
                print(json.dumps({"node_id": node_id, "mode": controls.mode.value, "record": record.to_dict() if record else None}, indent=2))
            elif record is None:
                print(f"{node_id}: mode={controls.mode.value} (emergency stop not tripped)")
            else:
                print(f"{node_id}: mode={controls.mode.value} - TRIPPED {record.tripped_at.isoformat()} via {record.source.value} by {record.requested_by}: {record.reason}")
            return 0

    return 2


def _run_mics(args: argparse.Namespace) -> int:
    try:
        from hanni.speech import MicrophoneError, SpeechDependencyError, list_input_devices
        devices = list_input_devices()
    except (SpeechDependencyError, MicrophoneError) as exc:
        print(f"Microphone error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([
            {
                "index": d.index,
                "name": d.name,
                "max_input_channels": d.max_input_channels,
                "default_samplerate": d.default_samplerate,
                "hostapi": d.hostapi,
            } for d in devices
        ], indent=2))
    elif not devices:
        print("No input devices found.")
    else:
        print("Local microphone/input devices:")
        for device in devices:
            print(f"  {device.render()}")
    return 0


def _run_google(args, config_dir: Path) -> int:
    from hanni.tools.google_access import GoogleAccessError
    from hanni.tools.google_auth import connect, dependency_error, logout, prepare_client_secrets, status
    try:
        if args.google_command == "login":
            print("HANNI Google Setup\n")
            missing = dependency_error()
            if missing:
                raise GoogleAccessError(missing)
            path = prepare_client_secrets(config_dir, explicit=args.client_secrets)
            print("Opening Google sign-in in your browser...\n")
            result = connect(args.account, args.email, path, calendar_ids=args.calendar_ids,
                             replace=args.replace, scopes=getattr(args, 'scopes', None))
            print("[OK] Google account connected")
            print('Authorized: ' + ', '.join(result['services']))
            print(f"Account: {result['email']}\n")
            print("HANNI can now access your permitted Google services.")
            return 0
        if args.google_command == 'use':
            from hanni.tools.google_access import WindowsTokenVault
            WindowsTokenVault().set_preference(args.account, args.service)
            print(f"Default {args.service or 'Google'} account: {args.account}")
            return 0
        if args.google_command in {"status", "accounts"}:
            rows = status(verify=args.verify)
            if args.json:
                print(json.dumps(rows, indent=2))
                return 0
            connected = [row for row in rows if row["connected"]]
            if not connected:
                print("Google connection: not configured\n\nRun:\nhanni google login")
                return 0
            print("Google connection: connected")
            for row in connected:
                print(f"\nAccount ({row['account']}):\n{row['email']}")
                for service, grant in row['services'].items():
                    mode = 'read/write' if grant['write'] else 'read-only' if grant['read'] else 'not authorized'
                    print(f"  {service}: {mode}" + (f" ({grant['api_status']})" if 'api_status' in grant else ''))
                print(f"  Token health: {row['token_health']}")
                print(f"  Last successful API check: {row['last_successful_api_check'] or 'not recorded'}")
                if row.get("error"):
                    print(f"\nConnection check: {row['error']}")
            return 0
        result = logout(args.account)
        if result["local_connection_removed"]:
            print("[OK] Removed HANNI's local Google authorization.")
        else:
            print(f"No local Google authorization was stored for {args.account}.")
        return 0
    except GoogleAccessError as exc:
        print(str(exc), file=sys.stderr)
    except Exception as exc:
        # Never expose auth library exception bodies, which can contain URLs or tokens.
        print(f"Google setup failed ({type(exc).__name__}). Check the client file, enabled APIs, and consent settings.", file=sys.stderr)
    return 1


def _run_listen(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        from hanni.speech import (
            MicrophoneCapture, MicrophoneError, SpeechDependencyError, SttError, create_pipeline,
        )
        microphone = None
        if args.device is not None:
            speech = config.hanni.speech
            microphone = MicrophoneCapture(
                sample_rate=speech.sample_rate,
                channels=speech.channels,
                block_samples=speech.block_samples,
                device=args.device,
            )
        pipeline = create_pipeline(config, microphone=microphone)
        print("H.A.N.N.I. microphone transcription is active. Speak naturally; Ctrl+C to stop.")
        if args.once:
            print("Waiting for one utterance...")
        for record in pipeline.run(once=args.once):
            language = f" [{record.language}]" if record.language else ""
            print(f"Heard{language}: {record.text}")
        return 0
    except (SpeechDependencyError, MicrophoneError, SttError, ValueError) as exc:
        print(f"Speech error: {exc}", file=sys.stderr)
        return 1


def _relevance_info(relevance) -> dict[str, object]:
    return {
        "wake_names": list(relevance.wake_names),
        "wake_match_scope": "anywhere_in_utterance",
        "engagement_mode": "until_disengaged" if relevance.engagement_seconds == 0 else "timed",
        "engagement_seconds": relevance.engagement_seconds,
        "disengage_phrases": list(relevance.disengage_phrases),
        "filler_words": list(relevance.filler_words),
        "acknowledgement_words": list(relevance.acknowledgement_words),
    }


def _is_voice_emergency_stop(text: str, wake_names: Sequence[str]) -> bool:
    normalized = " ".join(text.lower().replace("’", "'").split())
    if "stop everything" not in normalized:
        return False
    return any(re.search(rf"(?<![a-z]){re.escape(name.lower())}(?![a-z])", normalized) for name in wake_names)



def _is_text_emergency_stop(text: str, wake_names: Sequence[str]) -> bool:
    """Typed sessions are owner-local, so an explicit stop phrase can trip Safe Mode."""
    normalized = " ".join(text.lower().replace("’", "'").split()).strip()
    if normalized in {"/stop", "stop everything"}:
        return True
    return _is_voice_emergency_stop(text, wake_names)


def _memory_store(config: AppConfig):
    from hanni.memory import MemoryStore
    memory_cfg = config.hanni.memory
    return MemoryStore(config.paths.data_dir / memory_cfg.database_file, max_item_chars=memory_cfg.max_item_chars)


def _memory_context(config: AppConfig, goal: str) -> str:
    if not config.hanni.memory.enabled or not config.hanni.memory.retrieval_enabled:
        return ""
    from hanni.memory.integration import configured_retriever, ProjectSelectionRequired
    try:
        return configured_retriever(config, _memory_store(config)).retrieve(goal).text
    except ProjectSelectionRequired as exc:
        return json.dumps({'kind': 'project_selection_required', 'candidates': exc.candidates,
                           'uncertainty': 'No project has been selected or resumed.'})


def _memory_hints(config: AppConfig, goal: str) -> tuple[str, ...]:
    from hanni.memory.retrieval import MEMORY_DATA_POLICY
    context = _memory_context(config, goal)
    return (MEMORY_DATA_POLICY, context) if context else ()


def _wrap_memory_session(config: AppConfig, fallback_session, *, source: str, emergency_stop=None, registry=None):
    if not config.hanni.memory.enabled:
        return fallback_session
    from hanni.memory import MemoryAwareSession
    from hanni.memory.integration import configured_retriever
    from hanni.laya.runtime import advisory_for_config
    from hanni.laya.manager import start_shadow_from_env
    store = _memory_store(config)
    stop = emergency_stop or (registry.context.emergency_stop if registry is not None else None)
    guard = (lambda: not stop.is_tripped) if stop is not None else None
    advisory = advisory_for_config(config, admission_guard=guard)
    return MemoryAwareSession(
        fallback_session,
        store,
        source=source,
        search_limit=config.hanni.memory.search_limit,
        emergency_stop=emergency_stop,
        registry=registry,
        extraction_enabled=config.hanni.memory.extraction_enabled,
        retrieval_enabled=config.hanni.memory.retrieval_enabled,
        max_context_chars=config.hanni.memory.max_context_chars,
        min_relevance_score=config.hanni.memory.min_relevance_score,
        shadow_observer=start_shadow_from_env(),
        context_retriever=configured_retriever(config, store, emergency_stop=stop),
        advisory_observer=advisory if advisory.enabled else None,
    )


def _run_memory_cli(args: argparse.Namespace, config: AppConfig) -> int:
    if not config.hanni.memory.enabled:
        print("Durable memory is disabled in config/hanni.yaml.", file=sys.stderr)
        return 2
    from hanni.memory import SensitiveMemoryError
    store = _memory_store(config)
    limit = getattr(args, "limit", None) or config.hanni.memory.search_limit

    if args.command == "memory-info":
        from dataclasses import asdict
        from hanni.memory.store import SCHEMA_VERSION
        print(json.dumps({"schema_version": SCHEMA_VERSION, "records": store.count(),
                          "settings": asdict(config.hanni.memory), "raw_transcripts_stored": False,
                          "memory_grants_authority": False}, indent=2))
        return 0
    if args.command == "memory-context":
        context = _memory_context(config, " ".join(args.query))
        print(context or '{"kind": "untrusted_durable_memory", "memories": []}')
        return 0
    if args.command == "memory-cleanup":
        controls = LocalStopControls(config.paths.data_dir, machine_name=local_machine_name())
        if controls.record is not None:
            print("Safe Mode is active, so memory maintenance was not run.", file=sys.stderr)
            return 1
        print(json.dumps(store.cleanup(), indent=2))
        return 0

    if args.command == "remember":
        text = " ".join(args.text).strip()
        controls = LocalStopControls(config.paths.data_dir, machine_name=local_machine_name())
        if controls.record is not None:
            print("Safe Mode is active, so durable memory was not changed.", file=sys.stderr)
            return 1
        try:
            record, created = store.remember(text, source="owner_explicit:cli", confidence=1.0)
        except SensitiveMemoryError as exc:
            print(f"Memory privacy refusal: {exc}", file=sys.stderr)
            return 2
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"Memory error: {exc}", file=sys.stderr)
            return 1
        payload = {"created": created, "memory": record.to_dict()}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(("Remembered" if created else "Memory updated") + f": {record.content} [{record.id[:8]}]")
        return 0

    if args.command == "memories":
        records = store.list(limit=limit)
        if args.json:
            print(json.dumps([record.to_dict() for record in records], indent=2))
        elif not records:
            print("No durable memories stored.")
        else:
            for record in records:
                print(f"{record.id[:8]}  {record.memory_type:<10}  {record.content}")
        return 0

    if args.command == "memory-search":
        query = " ".join(args.query).strip()
        results = store.search(query, limit=limit)
        if args.json:
            print(json.dumps([{"score": item.score, **item.record.to_dict()} for item in results], indent=2))
        elif not results:
            print("No matching durable memories.")
        else:
            for item in results:
                print(f"{item.score:6.1f}  {item.record.id[:8]}  {item.record.content}")
        return 0

    if args.command == "forget":
        controls = LocalStopControls(config.paths.data_dir, machine_name=local_machine_name())
        if controls.record is not None:
            print("Safe Mode is active, so durable memory was not changed.", file=sys.stderr)
            return 1
        query = " ".join(args.query).strip()
        from hanni.memory.store import MemorySearchResult
        matches = (tuple(MemorySearchResult(record, 100) for record in store.find_all(query)) if args.delete_all
                   else store.search(query, limit=max(2, limit)))
        if not matches:
            print("No matching durable memories.")
            return 0
        if not args.delete_all and len(matches) > 1 and (matches[0].score < 80.0 or abs(matches[0].score - matches[1].score) < 5.0):
            print("Multiple memories match. Refusing an ambiguous deletion; narrow the query or rerun with --all.", file=sys.stderr)
            return 2
        records = tuple(item.record for item in matches) if args.delete_all else (matches[0].record,)
        try:
            if args.delete_all:
                records = store.forget(query, delete_all=True)
                deleted = len(records)
            else:
                deleted = store.delete_many(record.id for record in records)
        except (OSError, RuntimeError) as exc:
            print(f"Memory deletion error: {exc}", file=sys.stderr)
            return 1
        payload = {"deleted": deleted, "memories": [record.to_dict() for record in records]}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"Deleted and verified {deleted} durable memor{'y' if deleted == 1 else 'ies'}.")
        return 0

    return 2


def _dashboard_control(prompt, registry, wake_names):
    """Explicit browser owner controls, before any model inference."""
    if _is_text_emergency_stop(prompt, wake_names):
        registry.context.emergency_stop.trip(source=StopSource.OWNER_TEXT,
            requested_by=Actor.owner('browser'), reason='owner requested Safe Mode in browser')
        return 'Stopped. Safe Mode is active.'
    if prompt.lower() == '/status':
        return 'Safe Mode is active.' if registry.context.emergency_stop.record else 'Safe Mode is not active.'
    if prompt.lower() == '/resume':
        registry.context.emergency_stop.clear(Actor.owner('browser'))
        return 'Safe Mode cleared. Computer actions are enabled again.'
    if prompt.lower() in {'/exit', '/quit', 'exit', 'quit'}:
        return 'To exit HANNI, press Ctrl+C in the launcher terminal.'
    return None


def _run_typed(args: argparse.Namespace, config: AppConfig, *, shutdown_event=None) -> int:
    """Keyboard-only H.A.N.N.I. path using the resident model and MCP tools.

    This path intentionally never constructs the microphone, VAD, STT pipeline, or
    transcript pump. It is useful in quiet/public places and for repeatable testing.
    """
    try:
        try:
            client = create_client(config, args.model_id)
        except (KeyError, ValueError) as exc:
            print(f"Model configuration error: {exc}", file=sys.stderr)
            return 2

        health = client.health()
        if not health.ok:
            print(health.render_text(), file=sys.stderr)
            print(r"Start the selected local model server, then retry.", file=sys.stderr)
            return 1

        tts = None
        if args.tts:
            try:
                from hanni.speech import TtsError, create_tts
                if not config.hanni.speech.tts.enabled:
                    print("TTS is disabled in config/hanni.yaml.", file=sys.stderr)
                    return 2
                tts = create_tts(config.hanni.speech.tts, data_dir=config.paths.data_dir)
            except (TtsError, ValueError) as exc:
                print(f"TTS configuration error: {exc}", file=sys.stderr)
                return 2

        from hanni.tools import build_default_registry
        registry = build_default_registry(config, data_dir=config.paths.data_dir)
        from hanni.core.orchestrator import system_prompt_for
        base_session = TextSession(client, system_prompt=system_prompt_for(config.hanni.personality))
        session = _wrap_mcp_session(config, base_session, client=client, registry=registry)
        session = _wrap_memory_session(config, session, source="keyboard", registry=registry,
                                       emergency_stop=registry.context.emergency_stop)
        from hanni.dashboard.chat import attach, current_hub, keyboard_inputs
        session = attach(session, 'terminal')
        chat = current_hub()
        browser_inputs = keyboard_inputs(chat, stop_event=shutdown_event) if chat else None
        wake_names = config.hanni.speech.relevance.wake_names

        def handle(prompt: str) -> int:
            interaction.responding(True)
            try:
                return handle_inner(prompt)
            finally:
                interaction.responding(False)

        def handle_inner(prompt: str) -> int:
            clean = prompt.strip()
            if not clean:
                return 0
            workflow_message = _workflow_command(clean, config)
            if workflow_message is not None:
                if chat and chat.current:
                    chat.note(clean, workflow_message)
                print(f'H.A.N.N.I.> {workflow_message}')
                return 0
            if chat and chat.current:
                message = _dashboard_control(clean, registry, wake_names)
                if message is not None:
                    chat.note(clean, message)
                    print(f'H.A.N.N.I.> {message}')
                    return 0

            if _is_text_emergency_stop(clean, wake_names):
                registry.context.emergency_stop.trip(
                    source=StopSource.OWNER_TEXT,
                    requested_by=Actor.owner("keyboard"),
                    reason="owner typed stop everything",
                )
                message = "Stopped. Safe Mode is active."
                print(f"H.A.N.N.I.> {message}")
                if tts is not None:
                    try:
                        tts.speak(message)
                    except Exception:
                        pass
                return 0

            if clean.lower() == "/status":
                stop = registry.context.emergency_stop
                if stop.record is None:
                    print("H.A.N.N.I.> Safe Mode is not active.")
                else:
                    print("H.A.N.N.I.> Safe Mode is active. Computer actions are blocked until you run `hanni resume` or type `/resume` here.")
                return 0

            if clean.lower() == "/resume":
                stop = registry.context.emergency_stop
                was_tripped = stop.record is not None
                stop.clear(Actor.owner("keyboard"))
                if was_tripped:
                    print("H.A.N.N.I.> Safe Mode cleared. Computer actions are enabled again.")
                else:
                    print("H.A.N.N.I.> Safe Mode was not active.")
                return 0

            print("H.A.N.N.I.> ", end="", flush=True)
            parts: list[str] = []
            try:
                for chunk in session.stream_response(clean):
                    parts.append(chunk)
                    print(chunk, end="", flush=True)
                print()
            except (ModelClientError, ValueError) as exc:
                print()
                print(f"Local model error: {exc}", file=sys.stderr)
                return 1

            spoken = sanitize_assistant_text("".join(parts))
            if tts is not None and spoken:
                tts.speak(spoken)
            return 0

        try:
            if args.prompt:
                return handle(" ".join(args.prompt))

            print("H.A.N.N.I. keyboard mode. Microphone, VAD, and STT are not started.")
            print("Type normally; no wake word is required. /exit quits, /stop trips Safe Mode, /status shows Safe Mode, /resume clears it.")
            if registry.context.emergency_stop.record is not None:
                print("WARNING: Safe Mode is already active from a previous stop. Computer actions are blocked until `hanni resume` or `/resume`.")
            if config.hanni.memory.enabled:
                print("M9 local memory is enabled. Stable fact extraction and relevant recall follow config. Say/type 'remember that...', 'forget...', or 'what do you remember about...'.")

            while True:
                if shutdown_event is not None and shutdown_event.is_set():
                    return 0
                try:
                    if browser_inputs:
                        prompt, from_browser = next(browser_inputs)
                    else:
                        prompt, from_browser = input("You> ").strip(), False
                except (EOFError, StopIteration):
                    print()
                    return 0
                if shutdown_event is not None and shutdown_event.is_set():
                    return 0
                if not from_browser and prompt.lower() in {"/exit", "/quit", "exit", "quit"}:
                    return 0
                if not prompt:
                    continue
                code = handle(prompt)
                if code:
                    return code
        finally:
            if browser_inputs:
                browser_inputs.close()
            _close_interactive_session(session)
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as exc:
        print(f"Keyboard mode error: {exc}", file=sys.stderr)
        return 1


def _run_attend(args: argparse.Namespace, config: AppConfig, *, shutdown_event=None) -> int:
    """Live path: continuous STT + relevance + MCP tools + cancellable TTS."""
    try:
        from hanni.speech import (
            AttentiveTextBridge, BargeInClassifier, MicrophoneCapture, MicrophoneError,
            PUMP_FINISHED, PumpFailure, SpeechAttentionRouter, SpeechDependencyError,
            SpeechRelevanceClassifier, SttError, TranscriptPump, TtsError,
            create_pipeline, create_tts,
        )

        try:
            client = create_client(config, args.model_id)
        except (KeyError, ValueError) as exc:
            print(f"Model configuration error: {exc}", file=sys.stderr)
            return 2
        health = client.health()
        if not health.ok:
            print(health.render_text(), file=sys.stderr)
            print(r"Start the local model with .\scripts\start_llama.ps1, then retry.", file=sys.stderr)
            return 1

        tts = None
        if config.hanni.speech.tts.enabled and not args.no_tts:
            try:
                tts = create_tts(config.hanni.speech.tts, data_dir=config.paths.data_dir)
            except (TtsError, ValueError) as exc:
                print(f"TTS configuration error: {exc}", file=sys.stderr)
                return 2

        microphone = None
        if args.device is not None:
            speech = config.hanni.speech
            microphone = MicrophoneCapture(
                sample_rate=speech.sample_rate,
                channels=speech.channels,
                block_samples=speech.block_samples,
                device=args.device,
            )
        pipeline = create_pipeline(config, microphone=microphone)
        relevance = config.hanni.speech.relevance
        prepare_voice = getattr(tts, 'prepare', None)
        if callable(prepare_voice):
            prepare_voice()
        prepare = getattr(pipeline, 'prepare', None)
        if callable(prepare):
            print('Loading local speech recognition and wake-listening models...', flush=True)
            prepare()
        classifier = SpeechRelevanceClassifier(
            wake_names=relevance.wake_names,
            engagement_seconds=relevance.engagement_seconds,
            disengage_phrases=relevance.disengage_phrases,
            filler_words=relevance.filler_words,
            acknowledgement_words=relevance.acknowledgement_words,
        )
        from hanni.tools import build_default_registry
        registry = build_default_registry(config, data_dir=config.paths.data_dir)
        from hanni.core.orchestrator import system_prompt_for
        base_session = TextSession(client, system_prompt=system_prompt_for(config.hanni.personality))
        conversation_session = _wrap_mcp_session(config, base_session, client=client, registry=registry)
        conversation_session = _wrap_memory_session(config, conversation_session, source="voice", registry=registry,
                                                     emergency_stop=registry.context.emergency_stop)
        from hanni.dashboard.chat import attach, current_hub
        conversation_session = attach(conversation_session, 'voice')
        chat = current_hub()
        bridge = AttentiveTextBridge(SpeechAttentionRouter(classifier), conversation_session)
        barge_cfg = config.hanni.speech.barge_in
        barge = BargeInClassifier(
            interrupt_phrases=barge_cfg.interrupt_phrases,
            filler_words=relevance.filler_words,
            echo_min_words=barge_cfg.echo_min_words,
            echo_overlap_ratio=barge_cfg.echo_overlap_ratio,
        )
        from hanni.dashboard.voice import ManagedTranscriptPump, voice_control
        pump = ManagedTranscriptPump(
            lambda: TranscriptPump(create_pipeline(config, microphone=microphone)),
            initial=TranscriptPump(pipeline))
        response_gate = threading.Lock()
        pump.start()
        voice_control.bind(pump, classifier, registry, relevance.wake_names[0])
        pending = None
        stream_finished = False
        playback = None
        with interaction.condition:
            interaction.closed = False
            interaction.speaker = tts.start if tts is not None and hasattr(tts, 'start') else None

        print("H.A.N.N.I. is always listening locally. Say 'Hanni' to activate; Ctrl+C stops the process.")
        if tts is not None:
            if barge_cfg.enabled:
                print("Local voice + M5 barge-in are enabled. Speak while H.A.N.N.I. is talking to interrupt her.")
            else:
                print("Local voice is enabled; barge-in is disabled in config.")
        if relevance.engagement_seconds == 0:
            print("Once activated, H.A.N.N.I. stays active until a disengage phrase. Raw audio/transcripts still expire after 2 minutes.")
        print(f"Follow-up window: {relevance.engagement_seconds:g}s. Raw audio/transcripts still expire after 2 minutes.")

        try:
            while True:
                if shutdown_event is not None and shutdown_event.is_set():
                    return 0
                interaction.responding(False)
                item = pending
                pending = None
                from_browser = False
                if item is None:
                    browser_prompt = chat.take() if chat else None
                    if browser_prompt is not None:
                        message = _dashboard_control(browser_prompt, registry, relevance.wake_names)
                        if message is not None:
                            chat.note(browser_prompt, message)
                            print(f'H.A.N.N.I.> {message}')
                            continue
                        from hanni.speech.types import TranscriptRecord
                        from_browser = True
                        item = TranscriptRecord(text=browser_prompt, started_at=0.0, ended_at=0.0)
                    elif chat:
                        try:
                            item = pump.get(timeout=.1)
                        except queue.Empty:
                            continue
                    else:
                        try:
                            item = pump.get(timeout=.1)
                        except queue.Empty:
                            continue
                if item is PUMP_FINISHED:
                    return 0
                if shutdown_event is not None and shutdown_event.is_set():
                    return 0
                if isinstance(item, PumpFailure):
                    voice_control.audio_failure()
                    raise item.error
                record = item

                # Queued completion speech shares the established barge-in
                # classifier even while the foreground loop was waiting idle.
                with interaction.condition:
                    completion = interaction.completion_playback
                    completion_text = interaction.completion_text
                if not from_browser and barge_cfg.enabled and completion is not None and completion.active:
                    b = barge.classify(record.text, spoken_text=completion_text if barge_cfg.echo_suppression else '')
                    if not b.interrupt:
                        continue
                    completion.stop()
                    print('[H.A.N.N.I. interrupted]')
                    if not b.route_after_interrupt or not b.command_text:
                        continue
                    record = replace(record, text=b.command_text)

                # Deterministic owner-voice emergency stop. This does not ask the
                # LLM to interpret or authorize the phrase. The same persisted
                # stop state is checked again before every validated tool action.
                if _is_voice_emergency_stop(record.text, relevance.wake_names):
                    registry.context.emergency_stop.trip(
                        source=StopSource.OWNER_VOICE, requested_by=Actor.owner("voice"), reason="owner said stop everything"
                    )
                    print("[EMERGENCY STOP active — autonomous/tool actions are blocked]")
                    if tts is not None:
                        try:
                            tts.speak("Stopped. Safe Mode is active.")
                        except Exception:
                            pass
                    continue

                if from_browser:
                    from types import SimpleNamespace
                    decision = SimpleNamespace(disengaged=False, relevant=True, wake_word_detected=False)
                    response = conversation_session.stream_response(record.text)
                    voice_control.transcript_observed(record, False)
                else:
                    if not interaction.wake_enabled and not interaction.voice_engaged:
                        continue
                    routed, response = bridge.handle(record)
                    decision = routed.decision
                    if decision.relevant:
                        voice_control.transcript_observed(record, decision.wake_word_detected)
                if decision.disengaged:
                    print("[H.A.N.N.I. standby — still listening for wake name]")
                    continue
                if not decision.relevant:
                    if args.show_ignored:
                        if decision.filler_ignored:
                            label = "Ignored filler"
                        elif decision.acknowledgement_ignored:
                            label = "Ignored acknowledgement"
                        else:
                            label = "Ignored"
                        print(f"{label}: {record.text}")
                    continue

                marker = 'browser' if from_browser else "wake" if decision.wake_word_detected else "follow-up"
                interaction.responding(True)
                print(f"You [{marker}]> {record.text}")
                print("H.A.N.N.I.> ", end="", flush=True)
                from hanni.speech.response import deliver_response
                from hanni.core.responsiveness import TurnTimings, turn_scope
                first_response = [True]
                def show_sentence(chunk):
                    if first_response[0]:
                        voice_control.response_observed()
                        first_response[0] = False
                    print(chunk, end="", flush=True)
                try:
                    with turn_scope(TurnTimings(speech_ended_at=record.ended_at if not from_browser else None)) as response_timings:
                        delivered = deliver_response(
                            response, tts=tts if not from_browser else None, pump=pump,
                            barge=barge, barge_enabled=barge_cfg.enabled,
                            echo_suppression=barge_cfg.echo_suppression,
                            poll_seconds=barge_cfg.poll_ms / 1000.0,
                            shutdown_event=shutdown_event, on_text=show_sentence,
                            on_interrupt=voice_control.interruption_observed,
                            emergency=lambda text: _is_voice_emergency_stop(text, relevance.wake_names),
                            gate=response_gate, playback_timeout=config.hanni.speech.tts.timeout_seconds,
                            stop_active=lambda: registry.context.emergency_stop.is_tripped)
                        voice_control.response_timings_observed(response_timings.snapshot())
                    print()
                    pending = delivered.pending
                    if delivered.interrupted:
                        print("[H.A.N.N.I. interrupted]")
                    if delivered.stream_finished:
                        return 0
                except (ModelClientError, ValueError, TtsError) as exc:
                    print()
                    if isinstance(exc, TtsError):
                        voice_control.audio_failure()
                    print(f"Response error: {exc}. Still listening for your next request.", file=sys.stderr)
                    if args.once:
                        return 1
                    continue

                if args.once:
                    return 0
        finally:
            if playback is not None and playback.active:
                playback.stop()
            pump.stop()
            voice_control.unbind(pump)
            interaction.responding(False)
            interaction.close()
            _close_interactive_session(conversation_session)
    except (SpeechDependencyError, MicrophoneError, SttError, TtsError, ValueError) as exc:
        print(f"Speech error: {exc}", file=sys.stderr)
        return 1


def _run_tools(args: argparse.Namespace, config: AppConfig, data_dir: Path) -> int:
    from hanni.tools import build_default_registry
    registry = build_default_registry(config, data_dir=data_dir)
    rows = [
        {
            "name": d.name,
            "description": d.description,
            "permission_level": d.permission_level,
            "risk_level": d.risk_level,
            "timeout_seconds": d.timeout_seconds,
            "input": {k: ("/".join(t.__name__ for t in v) if isinstance(v, tuple) else v.__name__) for k, v in d.input_schema.items()},
        }
        for d in registry.definitions()
    ]
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print("Registered local tools:")
        for row in rows:
            print(f"  {row['name']:<20} level={row['permission_level']} risk={row['risk_level']}  {row['description']}")
    return 0



def _coerce_tool_arg_value(value: str):
    """Coerce a CLI KEY=VALUE token without making Windows users write JSON.

    JSON scalar spellings (numbers, true/false/null, arrays/objects) are parsed
    when unambiguous; everything else remains a string.
    """
    text = value.strip()
    if text == "":
        return ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return value
    # A bare JSON string would need quotes. Unquoted words fall through above.
    return parsed


def _parse_tool_payload(raw_json: str | None, key_values: Sequence[str]) -> dict[str, object]:
    """Parse tool arguments from legacy JSON and/or PowerShell-friendly KEY=VALUE.

    ``--arg`` values override duplicate keys from ``--args`` so a user can keep
    a JSON base payload and patch one value without fighting shell quoting.
    """
    payload: dict[str, object] = {}
    if raw_json is not None:
        try:
            decoded = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--args must be valid JSON ({exc})") from exc
        if not isinstance(decoded, dict):
            raise ValueError("--args must decode to a JSON object")
        payload.update(decoded)

    for item in key_values:
        if "=" not in item:
            raise ValueError(f"--arg must be KEY=VALUE, got {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("--arg key cannot be empty")
        payload[key] = _coerce_tool_arg_value(value)
    return payload

def _run_tool(args: argparse.Namespace, config: AppConfig, data_dir: Path) -> int:
    from hanni.tools import (
        ConfirmationRequired, ToolError, ToolPermissionError, ToolRequest,
        ToolValidationError, UnknownToolError, build_default_registry,
    )
    try:
        payload = _parse_tool_payload(args.args, args.arg)
    except ValueError as exc:
        print(f"Tool arguments are invalid: {exc}", file=sys.stderr)
        print("Tip for PowerShell: use --arg key=value instead of JSON, e.g. --arg limit=5", file=sys.stderr)
        return 2
    registry = build_default_registry(config, data_dir=data_dir)
    request = ToolRequest(args.name, payload, actor_profile="owner", confirmed=args.confirm, source="cli")
    try:
        if args.command == 'capability-call':
            result = registry.capabilities.invoke({'id': args.name, 'arguments': payload}, confirmed=args.confirm)
            print(json.dumps(result, indent=2) if args.json else result['message'])
            return 0 if result['ok'] else 3 if result['error']['code'] == 'CONFIRMATION_REQUIRED' else 1
        try:
            result = registry.capabilities.call(request)
        except ConfirmationRequired as exc:
            print(f"Confirmation required: {exc}", file=sys.stderr)
            print("Review the action, then rerun with --confirm if you intend to proceed.", file=sys.stderr)
            return 3
        except (UnknownToolError, ToolValidationError, ToolPermissionError, ToolError, OSError, ValueError, LookupError, PermissionError) as exc:
            print(f"Tool error: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.message)
            if result.data:
                print(json.dumps(result.data, indent=2))
        return 0 if result.ok else 1
    finally:
        _close_interactive_session(None, registry=registry)


def _run_tool_audit(args: argparse.Namespace, config: AppConfig, data_dir: Path) -> int:
    from hanni.tools import ToolAuditLog
    rows = ToolAuditLog(data_dir).tail(max(1, min(args.limit, 200)))
    if args.json:
        print(json.dumps(rows, indent=2))
    elif not rows:
        print("No tool audit records yet.")
    else:
        for row in rows:
            status = "OK" if row.get("ok") else "FAIL"
            print(f"{row.get('timestamp')} {status:<4} {row.get('tool')} source={row.get('source')} confirmed={row.get('confirmed')}")
    return 0


def _barge_info(barge) -> dict[str, object]:
    return {
        "enabled": barge.enabled,
        "interrupt_phrases": list(barge.interrupt_phrases),
        "echo_suppression": barge.echo_suppression,
        "echo_min_words": barge.echo_min_words,
        "echo_overlap_ratio": barge.echo_overlap_ratio,
        "poll_ms": barge.poll_ms,
    }

def _tts_info(tts) -> dict[str, object]:
    info = {
        "enabled": tts.enabled,
        "backend": tts.backend,
        "voice": tts.voice,
        "rate": tts.rate,
        "volume": tts.volume,
        "chunk_chars": tts.chunk_chars,
        "timeout_seconds": tts.timeout_seconds,
        "model_dir": tts.model_dir,
        "speed": tts.speed,
        "language": tts.language,
        "cpu_threads": tts.cpu_threads,
        "sapi_fallback": tts.sapi_fallback,
        "pitch_semitones": tts.pitch_semitones,
        "local_only": True,
    }
    if tts.backend == "windows_australian":
        from hanni.speech.australian import australian_voice
        info["australian_voice_installed"] = australian_voice() is not None
    return info


def _run_voices(args: argparse.Namespace) -> int:
    try:
        from hanni.speech import TtsError, list_windows_voices
        voices = list_windows_voices()
    except TtsError as exc:
        print(f"TTS error: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([
            {"name": v.name, "culture": v.culture, "gender": v.gender, "age": v.age}
            for v in voices
        ], indent=2))
    elif not voices:
        print("No Windows SAPI voices were found.")
    else:
        print("Installed local Windows voices:")
        for voice in voices:
            print(f"  {voice.render()}")
    return 0


def _run_speak(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        from hanni.speech import TtsError, create_tts
        tts_cfg = config.hanni.speech.tts
        if not tts_cfg.enabled:
            print("TTS is disabled in config/hanni.yaml.", file=sys.stderr)
            return 1
        engine = create_tts(tts_cfg, data_dir=config.paths.data_dir)
        engine.speak(sanitize_assistant_text(" ".join(args.text)))
        return 0
    except (TtsError, ValueError) as exc:
        print(f"TTS error: {exc}", file=sys.stderr)
        return 1


def _speech_info(speech, retention) -> dict[str, object]:
    return {
        "sample_rate": speech.sample_rate,
        "channels": speech.channels,
        "block_samples": speech.block_samples,
        "input_device": speech.input_device,
        "vad_threshold": speech.vad.threshold,
        "vad_min_silence_ms": speech.vad.min_silence_ms,
        "vad_speech_pad_ms": speech.vad.speech_pad_ms,
        "vad_pre_roll_ms": speech.vad.pre_roll_ms,
        "max_utterance_seconds": speech.vad.max_utterance_seconds,
        "stt_model": speech.stt.model,
        "stt_device": speech.stt.device,
        "stt_compute_type": speech.stt.compute_type,
        "stt_language": speech.stt.language,
        "stt_beam_size": speech.stt.beam_size,
        "tts_enabled": speech.tts.enabled,
        "tts_backend": speech.tts.backend,
        "tts_voice": speech.tts.voice,
        "tts_rate": speech.tts.rate,
        "tts_volume": speech.tts.volume,
        "barge_in_enabled": speech.barge_in.enabled,
        "barge_in_echo_suppression": speech.barge_in.echo_suppression,
        "wake_names": list(speech.relevance.wake_names),
        "engagement_mode": "until_disengaged" if speech.relevance.engagement_seconds == 0 else "timed",
        "engagement_seconds": speech.relevance.engagement_seconds,
        "raw_audio_retention_seconds": retention.raw_audio_seconds,
        "transcript_retention_seconds": retention.transcript_seconds,
    }



def _wrap_mcp_session(config: AppConfig, fallback_session, *, client, registry):
    """Attach adaptive pure inference and the original bounded MCP layer."""
    from hanni.models.adaptive import AdaptiveModelEngine, AdaptiveModelClient, current, install
    from hanni.models.client import LlamaCppClient
    routing_owner = None
    if isinstance(client, (LlamaCppClient, AdaptiveModelClient)):
        engine = current(config)
        if engine is None:
            from hanni.compute import ComputeRegistry, ComputeScheduler
            engine = AdaptiveModelEngine(config, compute_scheduler=ComputeScheduler(ComputeRegistry(config.paths.data_dir)))
            engine.owns_compute = True
            routing_owner = engine
            install(engine)
            # Remote exact-file fingerprints can take minutes for large
            # installations. They run in the shared background monitor; the
            # original local controller does not wait for remote discovery.
        engine.start_monitor()
        engine.controller_attached = True
        client = engine.wrap_client(client)
        if getattr(fallback_session, 'client', None) is not None:
            fallback_session.client = client
    from hanni.mcp.runtime import attach_controller
    if not config.hanni.mcp.enabled:
        attach_controller(config, registry)
        fallback_session.model_routing_owner = routing_owner
        return _with_hermes_session(config, fallback_session, registry, client)
    from hanni.mcp import McpHost, McpToolSession
    mcp_cfg = config.hanni.mcp
    host = McpHost(registry, read_only=mcp_cfg.read_only, max_tools=mcp_cfg.max_tools_per_turn,
                   allowed_actions=mcp_cfg.allowed_actions)
    attach_controller(config, registry, client=client, host=host)
    session = McpToolSession(
        fallback_session, client, host,
        max_rounds=mcp_cfg.max_tool_rounds,
        tool_result_chars=mcp_cfg.tool_result_chars,
    )
    session.model_routing_owner = routing_owner
    session.workflow_submit = lambda prompt: _workflow_command('/goal ' + prompt.removeprefix('/goal '), config)
    return _with_hermes_session(config, session, registry, client)


def _with_hermes_session(config, session, registry, client):
    from hanni.hermes.client import current as current_hermes
    control = current_hermes(config.paths.data_dir)
    if control is not None and control.client is not None:
        from hanni.hermes.session import HermesSession
        control.bind(registry)
        session = HermesSession(session, control, registry, client)
    return session


def _workflow_command(prompt, config):
    """Explicit goal submission through the same private workflow service."""
    if not (prompt.lower() == '/workflows' or prompt.lower().startswith('/goal ')):
        return None
    from hanni.mcp.runtime import workflow_hub
    hub = workflow_hub(config)
    if hub is None:
        return 'Start the HANNI dashboard backend to submit or inspect persistent workflows.'
    try:
        if prompt.lower() == '/workflows':
            result = hub.snapshot(limit=20)
            rows = result.get('items', [])
            if not result.get('available'):
                return result.get('reason') or 'Workflow history is unavailable.'
            return ('No saved workflows.' if not rows else '\n'.join(
                f"{row['workflow_id']}: {row['status']} ({row.get('counts', {}).get('verified', 0)}/{row.get('counts', {}).get('required', 0)} verified steps)"
                for row in rows))
        from uuid import uuid4
        result = hub.mutate({'id': str(uuid4()), 'operation': 'goal.submit', 'data': {
            'goal': prompt[6:].strip(), 'mode': config.hanni.workflows.default_mode}})
        return f"Goal saved as {result['workflow_id']}. Review its plan and approvals in Workflows. Execution has not been verified."
    except (ValueError, OSError, RuntimeError, sqlite3.Error):
        return 'The workflow request is unavailable or outside its limits. Inspect Workflows for the current saved state.'


def _run_capability_diagnostics(args, config):
    """Inspect the capability registry without invoking the retired worker stack."""
    from hanni.tools import build_default_registry
    from hanni.tools.capabilities import capability_catalog

    registry = build_default_registry(config, data_dir=config.paths.data_dir)
    try:
        if args.command == "capabilities":
            payload = [cap.to_dict() for cap in capability_catalog(registry)]
        elif args.command == "capability-search":
            limit = args.limit if args.limit is not None else config.hanni.mcp.max_tools_per_turn
            payload = registry.capabilities.search(" ".join(args.goal), limit=limit)
        else:
            payload = registry.capabilities.get(args.name)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, KeyError, sqlite3.Error, OSError, RuntimeError) as exc:
        print(f"Capability lookup failed: {exc}", file=sys.stderr)
        return 1


def _close_interactive_session(session, *, registry=None):
    def detach_before_close(value):
        if value is None:
            return
        from hanni.mcp.runtime import detach_controller
        try:
            detach_controller(value)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning('Workflow detach failed (%s).', type(exc).__name__)

    detach_before_close(registry)
    seen = set()
    services = {}
    from hanni.reliability.execution import ReliabilityService
    service = getattr(getattr(registry, 'context', None), 'reliability', None)
    if isinstance(service, ReliabilityService):
        services[id(service)] = service
    try:
        while session is not None and id(session) not in seen:
            seen.add(id(session))
            registries = (getattr(session, 'registry', None),
                          getattr(getattr(session, 'host', None), 'registry', None))
            for registry in registries:
                if registry is not None:
                    detach_before_close(registry)
                service = getattr(getattr(registry, 'context', None), 'reliability', None)
                if isinstance(service, ReliabilityService):
                    services[id(service)] = service
            close = getattr(session, 'close', None)
            if callable(close): close()
            routing = getattr(session, 'model_routing_owner', None)
            if routing is not None:
                routing.controller_attached = False
                routing.close()
                if getattr(routing, 'owns_compute', False):
                    routing.compute.close()
            session = getattr(session, 'fallback_session', None)
    finally:
        # Observational connections are released after the original session and
        # shadow observer close. Other live registries can lazily reopen their
        # shared service; no controller, approval or MCP connection is stopped.
        for service in services.values():
            service.close()


def _run_chat(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        client = create_client(config, args.model_id)
    except (KeyError, ValueError) as exc:
        print(f"Model configuration error: {exc}", file=sys.stderr)
        return 2

    health = client.health()
    if not health.ok:
        print(health.render_text(), file=sys.stderr)
        print("Start the local model with .\\scripts\\start_llama.ps1, then retry.", file=sys.stderr)
        return 1

    from hanni.tools import build_default_registry
    registry = build_default_registry(config, data_dir=config.paths.data_dir)
    from hanni.core.orchestrator import system_prompt_for
    base_session = TextSession(client, system_prompt=system_prompt_for(config.hanni.personality))
    session = _wrap_mcp_session(config, base_session, client=client, registry=registry)
    session = _wrap_memory_session(config, session, source="chat", registry=registry,
                                   emergency_stop=registry.context.emergency_stop)
    request_kwargs = {k: v for k, v in {
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "top_p": args.top_p,
    }.items() if v is not None}

    try:
        if args.prompt:
            return _stream_one(session, " ".join(args.prompt), request_kwargs, prefix="")

        print("H.A.N.N.I. local text chat. Type /exit to quit.")
        while True:
            try:
                prompt = input("You> ").strip()
            except EOFError:
                print()
                return 0
            if prompt.lower() in {"/exit", "/quit", "exit", "quit"}:
                return 0
            if not prompt:
                continue
            code = _stream_one(session, prompt, request_kwargs, prefix="H.A.N.N.I.> ")
            if code:
                return code
    finally:
        _close_interactive_session(session, registry=registry)


def _stream_one(session, prompt: str, kwargs: Mapping[str, object], *, prefix: str) -> int:
    if prefix:
        print(prefix, end="", flush=True)
    try:
        for chunk in session.stream_response(prompt, **kwargs):
            print(chunk, end="", flush=True)
        print()
        return 0
    except (ModelClientError, ValueError) as exc:
        if prefix:
            print()
        print(f"Local model error: {exc}", file=sys.stderr)
        return 1


def _model_info(spec) -> dict[str, object]:
    return {
        "id": spec.id,
        "role": spec.role,
        "backend": spec.backend,
        "endpoint": spec.endpoint,
        "api_model": spec.api_model,
        "model_file": spec.model_file,
        "hf_repo": spec.hf_repo,
        "quantization": spec.quantization,
        "context_length": spec.context_length,
        "gpu_layers": spec.gpu_layers,
        "split_mode": spec.split_mode,
        "tensor_split": list(spec.tensor_split),
        "device_name_hints": list(spec.device_name_hints),
        "max_tokens": spec.max_tokens,
        "temperature": spec.temperature,
        "top_p": spec.top_p,
        "thinking_enabled": spec.thinking_enabled,
        "jinja_enabled": spec.jinja_enabled,
    }


def _logging_config(config_dir: Path, data_dir: Path, env: Mapping[str, str]) -> LoggingConfig:
    """Best-effort: a broken config must not prevent ``health`` from reporting the problem."""
    try:
        return load_config(config_dir, data_dir=data_dir, env=env).hanni.logging
    except ConfigError:
        return LoggingConfig()


def main() -> int:
    try:
        return run(sys.argv[1:])
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
