"""Run a sealed owner-session fixture through local HANNI, once per model.

This runner is intentionally fixture-only: it never executes a real capability.
It reports contract checks that can be evaluated mechanically and leaves
subjective or causality claims for the anonymized human review artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.request
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from hanni.config.loader import load_config
from hanni.core.orchestrator import TextSession, system_prompt_for
from hanni.evals.routing import build_default_host
from hanni.mcp.session import McpToolSession
from hanni.models.client import LlamaCppClient


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _result(name, message, data=None, ok=True):
    return {'name': name, 'ok': ok, 'message': message, 'data': data or {},
            **({} if ok else {'error': {'code': 'FIXTURE_UNAVAILABLE', 'retryable': False}})}


class Fixture:
    def __init__(self, raw):
        self.raw = raw
        self.clock = datetime.fromisoformat(raw['clock']['now'])
        self.zone = ZoneInfo(raw['clock']['timezone'])
        self.events = list(raw['calendar']['events'])
        self.media = {'running': True, 'playing': raw['media']['initial_state'].casefold() == 'playing',
                      'now_playing': raw['media']['initial_track']}
        self.opened = set()
        self.calls = []

    def call(self, tool, supplied):
        name = tool.capability_id
        args = {**supplied, **tool.fixed_arguments}
        self.calls.append({'capability': name, 'arguments': args})
        try:
            if name in {'google_calendar.agenda', 'google_calendar.next'}:
                result = self._calendar(name, args)
            elif name == 'google_calendar.create':
                result = self._create(args)
            elif name == 'disk.usage':
                rows = [{'drive': v['name'], 'filesystem': v['filesystem'],
                         'total_gb': v['total_gb'], 'free_gb': v['free_gb'],
                         'used_gb': v['total_gb'] - v['free_gb']}
                        for v in self.raw['system']['volumes']]
                requested = str(args.get('drive') or '').upper().rstrip(':\\/')
                present = any(row['drive'].upper().startswith(requested + ':') for row in rows) if requested else None
                message = (f"{requested}: is not among the mounted fixed drives." if requested and not present
                           else '; '.join(f"{r['drive']} {r['free_gb']} GB free of {r['total_gb']} GB"
                                          for r in rows if not requested or r['drive'].upper().startswith(requested + ':')))
                result = _result(name, message, {'drives': rows, 'requested_drive': requested or None,
                                                 'present': present})
            elif name == 'disk.free_space':
                drive = str(args.get('drive') or 'C:').upper()[:2]
                row = next((v for v in self.raw['system']['volumes'] if v['name'].upper()[:2] == drive), None)
                result = _result(name, f"{drive} has {row['free_gb']} GB free." if row else f'{drive} is not mounted.',
                                 {'drive': drive, 'present': bool(row), 'free_gb': row['free_gb'] if row else None})
            elif name in {'system.stats', 'system.performance'}:
                state = self.raw['system']
                result = _result(name, f"CPU is at {state['cpu_percent']}% and RAM is at {state['ram_percent']}%.",
                                 {'cpu_percent': state['cpu_percent'], 'ram_percent': state['ram_percent']})
            elif name == 'process.top_cpu':
                rows = self.raw['system']['cpu_top']
                result = _result(name, 'Top CPU process: ' + ', '.join(f"{r['name']} {r['cpu_percent']}%" for r in rows),
                                 {'processes': rows})
            elif name in {'process.top_memory', 'process.top_disk_io'}:
                result = _result(name, 'No per-process fixture measurement is available.',
                                 {'processes': [], 'fixture_incomplete': True})
            elif name in {'gpu.memory', 'gpu.top_processes'}:
                gpu = self.raw['system']['gpu']
                result = _result(name, f"{gpu['name']} uses {gpu['vram_used_gb']} GB of {gpu['vram_total_gb']} GB VRAM.",
                                 {'gpus': [gpu], 'processes': gpu['top_processes']})
            elif name == 'model.status':
                model = self.raw['system']['model']
                placement = bool(not model['cpu_only'] and model['gpu_adapter'] and model['observed_vram_mb'])
                result = _result(name, (f"{model['name']} appears to use {model['gpu_adapter']} with "
                                        f"{model['observed_vram_mb']} MB observed VRAM." if placement else
                                        f"{model['name']} GPU placement is unverified."),
                                 {'model_id': model['name'], 'selected_device_name': model['gpu_adapter'],
                                  'placement_verified': placement, 'observed_vram_mb': model['observed_vram_mb'],
                                  'quantization': model['quant'], 'context_length': model['context']})
            elif name in {'app.open', 'spotify.launch'}:
                result = self._open(name, args)
            elif name.startswith('spotify.') or name.startswith('media.'):
                result = self._media(name, args)
            elif name == 'file.search':
                root = str(args.get('root') or '').casefold()
                query = str(args.get('query') or '').casefold()
                hits = [item for item in self.raw['filesystem']['files']
                        if (not root or root in item.casefold()) and
                        (not query or all(token in item.casefold() for token in query.split()))]
                result = _result(name, f'Found {len(hits)} matching files.',
                                 {'matches': hits, 'root': args.get('root') or 'common user folders'})
            elif name in {'time.now', 'time.convert'}:
                result = _result(name, self.clock.strftime('%A, %B %-d, %Y %I:%M %p') if os.name != 'nt'
                                 else self.clock.strftime('%A, %B %d, %Y %I:%M %p'),
                                 {'local_time': self.clock.isoformat(), 'requested_date': self.clock.date().isoformat()})
            elif name == 'hanni.capabilities':
                result = _result(name, 'I can use the capabilities enabled in this session, including app opening and Spotify control.',
                                 {'total': 150})
            else:
                result = _result(name, 'No frozen fixture result is defined for this capability.',
                                 {'fixture_incomplete': True}, ok=False)
        except (KeyError, TypeError, ValueError) as exc:
            result = _result(name, f'Fixture could not answer: {type(exc).__name__}.',
                             {'fixture_incomplete': True}, ok=False)
        self.calls[-1]['result'] = result
        return result

    def _calendar(self, name, args):
        from hanni.tools.google_access import calendar_summary
        start = (datetime.fromisoformat(str(args['start_date'])).replace(tzinfo=self.zone)
                 if args.get('start_date') else self.clock)
        end = start + timedelta(days=int(args.get('days', 1 if name.endswith('agenda') else 30)))
        rows = []
        for index, event in enumerate(self.events):
            first = datetime.fromisoformat(event['start'])
            last = datetime.fromisoformat(event['end'])
            if first.tzinfo is None: first = first.replace(tzinfo=self.zone)
            if last.tzinfo is None: last = last.replace(tzinfo=self.zone)
            if first >= end or last <= start or (name.endswith('next') and first < self.clock):
                continue
            rows.append({'id': f'fixture-{index}', 'summary': event['title'],
                         'account': 'personal', 'calendar_id': self.raw['calendar']['calendar_id'],
                         'start': {'dateTime': first.isoformat()}, 'end': {'dateTime': last.isoformat()},
                         'start_local': first.astimezone(self.zone).isoformat(),
                         'start_utc': first.isoformat(), 'all_day': False})
        rows.sort(key=lambda row: row['start_utc'])
        if name.endswith('next'): rows = rows[:1]
        availability = None
        if args.get('availability_at') or args.get('availability_start'):
            def clock(value):
                hour, minute = map(int, value.split(':'))
                return start.replace(hour=hour, minute=minute)
            point = clock(args['availability_at']) if args.get('availability_at') else None
            left = clock(args['availability_start']) if args.get('availability_start') else None
            right = clock(args['availability_end']) if args.get('availability_end') else None
            conflicts = []
            for row in rows:
                first = datetime.fromisoformat(row['start']['dateTime'])
                last = datetime.fromisoformat(row['end']['dateTime'])
                if (point is not None and first <= point < last) or (left is not None and left < last and right > first):
                    conflicts.append(row['id'])
            availability = {'at': point.isoformat() if point else None,
                            'start': left.isoformat() if left else None,
                            'end': right.isoformat() if right else None,
                            'busy': bool(conflicts), 'conflicting_event_ids': conflicts, 'verified': True}
        data = {'events': rows, 'event_count': len(rows), 'errors': [], 'partial': False,
                'truncated': False, 'window_start': start.isoformat(), 'window_end': end.isoformat(),
                'resolved_date': start.date().isoformat(), 'calendar_id': self.raw['calendar']['calendar_id'],
                'timezone': str(self.zone), 'time_min': start.isoformat(), 'time_max': end.isoformat(),
                'availability': availability}
        if name.endswith('next'):
            data['event'] = rows[0] if rows else None
            data['current_local_time'] = self.clock.isoformat()
            data['minutes_until_start'] = round((datetime.fromisoformat(rows[0]['start_local']) - self.clock).total_seconds()/60) if rows else None
        return _result(name, calendar_summary(data), data)

    def _create(self, args):
        title = str(args.get('summary') or 'Event')
        first = str(args.get('start') or args.get('start_date') or '')
        last = str(args.get('end') or args.get('end_date') or '')
        if not first or not last:
            return _result('google_calendar.create', 'No exact start and end were supplied.', ok=False)
        self.events.append({'title': title, 'start': first, 'end': last})
        return _result('google_calendar.create', f"Added '{title}' to Google Calendar; read-back was not attempted.",
                       {'id': f'created-{len(self.events)}', 'summary': title, 'start': first,
                        'end': last, 'created': True, 'outcome': 'created_but_not_reverified'})

    def _open(self, name, args):
        if name == 'spotify.launch':
            self.media['running'] = True
            return _result(name, 'Spotify client started.', dict(self.media))
        app = str(args.get('app') or '')
        fixture = next((value for key, value in self.raw['apps'].items()
                        if key.casefold() == app.casefold()), None)
        if not fixture or not fixture['launch_succeeds']:
            return _result(name, f'Could not launch {app}.', {'app': app, 'outcome': 'failed'}, False)
        self.opened.add(app.casefold())
        outcome = 'window_detected' if fixture['window_detected'] else 'process_started' if fixture['process_started'] else 'accepted'
        return _result(name, f'{app} started.' if outcome != 'accepted' else f'Launch request sent for {app}.',
                       {'app': app, 'outcome': outcome, 'verified': fixture['window_detected']})

    def _media(self, name, args):
        state = self.media
        if name in {'spotify.play_pause', 'media.play_pause'}:
            state['playing'] = not state['playing']
        elif name in {'spotify.next', 'media.next_track'}:
            state['now_playing'] = self.raw['media']['next_track']
            state['playing'] = True
        elif name == 'media.stop':
            state['playing'] = False
        return _result(name, 'Spotify is playing ' + state['now_playing'] if state['playing'] else 'Spotify is paused.',
                       dict(state))


class TimedClient:
    def __init__(self, client):
        self.client = client
        self.latencies = []
        self.tokens = 0
        self.first_token_ms = []

    def complete_with_tools(self, *args, **kwargs):
        started = time.perf_counter()
        turn = self.client.complete_with_tools(*args, **kwargs)
        self.latencies.append((time.perf_counter()-started)*1000)
        self.tokens += turn.usage.get('completion_tokens', 0)
        return turn

    def stream_chat(self, *args, **kwargs):
        started = time.perf_counter()
        first = True
        for part in self.client.stream_chat(*args, **kwargs):
            if first:
                self.first_token_ms.append((time.perf_counter()-started)*1000)
                first = False
            yield part
        self.latencies.append((time.perf_counter()-started)*1000)

    def chat(self, *args, **kwargs):
        started = time.perf_counter()
        answer = self.client.chat(*args, **kwargs)
        self.latencies.append((time.perf_counter()-started)*1000)
        return answer


def _checks(contract, calls, answer):
    checks = {}
    names = [call['capability'] for call in calls if call.get('result', {}).get('ok')]
    calendar = next((call['result']['data'] for call in reversed(calls)
                     if call['capability'] in {'google_calendar.agenda', 'google_calendar.next'}
                     and call.get('result', {}).get('ok')), None)
    if 'resolved_date' in contract:
        checks['resolved_date'] = bool(calendar and calendar['resolved_date'] == contract['resolved_date'])
    if 'expect_event_count' in contract:
        checks['event_count'] = bool(calendar and calendar['event_count'] == contract['expect_event_count'])
    if 'expect_busy' in contract:
        checks['availability'] = bool(calendar and calendar.get('availability') and
                                      calendar['availability']['busy'] is contract['expect_busy'])
    if 'expect_existing_drive' in contract or 'expect_nonexistent_drive' in contract:
        drive = contract.get('expect_existing_drive') or contract.get('expect_nonexistent_drive')
        observation = next((call['result']['data'] for call in reversed(calls)
                            if call['capability'] == 'disk.usage'), None)
        mounted = bool(observation and any(str(row['drive']).casefold().startswith(str(drive).casefold().rstrip(':') + ':')
                                               for row in observation['drives']))
        checks['drive'] = mounted if 'expect_existing_drive' in contract else bool(observation) and not mounted
    if contract.get('must_execute'):
        checks['action_executed'] = any(name in {'app.open', 'google_calendar.create', 'spotify.play_pause',
                                                'spotify.next', 'media.play_pause', 'media.next_track'} for name in names)
    if 'expect_created' in contract:
        checks['created'] = 'google_calendar.create' in names
    if contract.get('must_ack_process_started'):
        checks['process_acknowledged'] = any(call['capability'] == 'app.open' and
                                             call['result']['data'].get('outcome') in {'process_started', 'window_detected'}
                                             for call in calls) and bool(re.search(r'\b(?:started|opened|running)\b', answer, re.I))
    if 'expect_contains' in contract:
        checks['expected_content'] = all(str(word).casefold() in answer.casefold() for word in contract['expect_contains'])
    if contract.get('inherit_provider'):
        checks['provider_inherited'] = any(name.startswith('spotify.') for name in names)
    if contract.get('must_not_claim_visual_confirmation'):
        verified = any(call['capability'] == 'app.open' and call['result']['data'].get('verified') for call in calls)
        checks['visual_claim'] = verified or not bool(re.search(r'\b(?:window is open|i can see|on screen)\b', answer, re.I))
    return checks


def run_model(holdout, *, name, model_path, exe, port=18080, max_turns=None):
    from hanni.evals.routing import build_default_host
    config = load_config(Path('config'), data_dir=Path('data/eval-routing'), env={})
    spec = replace(config.models.supervisor, endpoint=f'http://127.0.0.1:{port}/v1')
    command = [str(exe), '-m', str(model_path), '--alias', spec.api_model, '--host', '127.0.0.1',
               '--port', str(port), '-c', '16384', '--parallel', '1', '-ngl', '99', '--device', 'Vulkan1',
               '--split-mode', 'none', '--main-gpu', '0', '--flash-attn', 'on', '-ctk', 'q8_0', '-ctv', 'q8_0',
               '--jinja', '--reasoning', 'off', '--load-mode', 'mmap']
    log_path = Path(os.environ['TEMP']) / ('hanni-final-' + name.lower().replace(' ', '-') + '.log')
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    rows = []
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and process.poll() is None:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2) as response:
                    if json.load(response).get('status') == 'ok': break
            except Exception:
                pass
            time.sleep(1)
        else:
            return {'name': name, 'status': 'NOT_RUN', 'reason': 'local server failed to become healthy',
                    'log_path': str(log_path)}
        timed = TimedClient(LlamaCppClient(spec, max_attempts=1))
        for scenario in holdout['scenarios']:
            fixture = Fixture(holdout['fixture'])
            host = build_default_host()
            route = host.route
            host.route = lambda query, *, history=(), now=None: route(query, history=history, now=fixture.clock if now is None else now)
            host.call = fixture.call
            fallback = TextSession(timed, system_prompt=system_prompt_for(config.hanni.personality),
                                   clock=lambda: 0.0)
            session = McpToolSession(fallback, timed, host,
                                     max_rounds=config.hanni.mcp.max_tool_rounds)
            for turn in scenario['turns']:
                if max_turns is not None and len(rows) >= max_turns: break
                previous_calls = len(fixture.calls)
                started = time.perf_counter()
                error = None
                try:
                    answer = ''.join(session.stream_response(turn['user']))
                except Exception as exc:
                    answer, error = '', f'{type(exc).__name__}: {exc}'
                calls = fixture.calls[previous_calls:]
                checks = _checks(turn['contract'], calls, answer)
                rows.append({'scenario': scenario['id'], 'turn_index': turn['turn_index'],
                             'family': turn['contract'].get('family'),
                             'answer': answer, 'calls': calls, 'checks': checks,
                             'passed': all(checks.values()) if checks else None,
                             'latency_ms': round((time.perf_counter()-started)*1000, 1),
                             'error': error})
            if max_turns is not None and len(rows) >= max_turns: break
        assessed = [row for row in rows if row['passed'] is not None]
        families = {}
        for family in sorted({row['family'] for row in rows}):
            selected = [row for row in rows if row['family'] == family]
            judged = [row for row in selected if row['passed'] is not None]
            families[family] = {'turns': len(selected), 'assessed': len(judged),
                                'passed': sum(row['passed'] for row in judged)}
        return {'name': name, 'status': 'completed', 'model_file': str(model_path),
                'model_sha256': _hash(model_path), 'model_size_bytes': model_path.stat().st_size,
                'runtime': 'llama.cpp', 'gpu': 'Vulkan1 NVIDIA GeForce RTX 5060 Laptop GPU',
                'context_size': 16384, 'temperature': 0.35, 'top_p': 0.9,
                'overall_task_success': {'passed': sum(row['passed'] for row in assessed),
                                         'assessed': len(assessed), 'total': len(rows)},
                'families': families, 'mean_latency_ms': round(sum(row['latency_ms'] for row in rows)/len(rows), 1),
                'mean_stream_first_token_ms': (round(sum(timed.first_token_ms)/len(timed.first_token_ms), 1)
                                               if timed.first_token_ms else None),
                'generated_tokens': timed.tokens, 'peak_vram_mb': None,
                'rows': rows}
    finally:
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('holdout', type=Path)
    parser.add_argument('--name', required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-turns', type=int, help='development smoke test only; never use on final holdout')
    args = parser.parse_args(argv)
    raw = args.holdout.read_bytes()
    holdout = json.loads(raw)
    report = run_model(holdout, name=args.name, model_path=args.model, exe=args.exe,
                       max_turns=args.max_turns)
    report['holdout_sha256'] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
