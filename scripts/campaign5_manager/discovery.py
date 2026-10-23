"""Fresh native endpoint discovery using isolated copies of owner configuration."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
import zipfile
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]
from hanni.compute import ComputeRegistry, ComputeScheduler
from hanni.config.loader import load_config
from hanni.models.adaptive import AdaptiveModelEngine, ModelRequest
from scripts.campaign3_manager.model_probe import runtime_snapshot

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str) + '\n', encoding='utf8', newline='\n')

def run(output):
    output = output.resolve()
    if output.exists() or not output.is_relative_to((ROOT / 'data/campaign5-manager').resolve()):
        raise ValueError('Choose a fresh campaign-owned discovery directory')
    output.mkdir(parents=True)
    paths = sorted([*(ROOT / 'src/hanni').rglob('*.py'), *(ROOT / 'config').rglob('*.yaml')])
    source = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
    save(output / 'SOURCE_BEFORE.json', source)
    with zipfile.ZipFile(output / 'source.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        for p in paths:
            content = p.read_bytes()
            if hashlib.sha256(content).hexdigest() != source[p.relative_to(ROOT).as_posix()]:
                raise RuntimeError('Source changed during baseline archive')
            archive.writestr(p.relative_to(ROOT).as_posix(), content)
    copied = {}
    state = output / 'state'
    for name in ('deployment.json', 'context-measurements.json'):
        original = ROOT / 'data/compute' / name
        if original.exists():
            if original.is_symlink() or original.stat().st_size > 1048576:
                raise RuntimeError('Unsafe owner deployment/context file')
            target = state / 'compute' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read_bytes())
            copied[name] = digest(original)
    config = load_config(ROOT / 'config', data_dir=state, env={})
    save(output / 'IDENTITY_BEFORE.json', runtime_snapshot(config))
    registry = ComputeRegistry(state)
    compute = ComputeScheduler(registry)
    engine = AdaptiveModelEngine(config, compute_scheduler=compute, data_dir=state)
    save(output / 'REGISTERED.json', {'models': [asdict(s) for s in config.models.models], 'workers': registry.workers(), 'deployment_enabled': registry.enabled, 'configuration_error': registry.config_error, 'copied_owner_bytes_sha256': copied})
    began = time.perf_counter()
    try:
        snapshot = engine.refresh()
        save(output / 'SNAPSHOT.json', snapshot)
        save(output / 'OBSERVATIONS.json', {'local': engine.observations, 'workers': registry.observations})
        requests = {'synthetic_short_text': ModelRequest(task_category='analysis', complexity='simple', privacy_categories=frozenset({'synthetic'}), context_tokens=512, output_tokens=256, allow_legacy_default=True, interactive=False), 'synthetic_native_tools': ModelRequest(task_category='tool_selection', privacy_categories=frozenset({'synthetic'}), context_tokens=1024, output_tokens=256, capabilities=frozenset({'text', 'tool_calling'}), tool_calling_format='openai_function', allow_legacy_default=True, interactive=False), 'synthetic_memory_facts': ModelRequest(task_category='memory', privacy_categories=frozenset({'synthetic'}), context_tokens=1024, output_tokens=256, allow_legacy_default=True, interactive=False), 'actual_private_memory': ModelRequest(task_category='memory', privacy_categories=frozenset({'memory', 'sensitive'}), context_tokens=1024, output_tokens=256, allow_legacy_default=True, interactive=False)}
        decisions = {name: engine.select(request) for name, request in requests.items()}
        save(output / 'ADMISSION.json', decisions)
        endpoints = snapshot.get('endpoints', snapshot.get('models', []))
        rows = []
        for row in endpoints:
            rows.append({k: row.get(k) for k in ('endpoint_id', 'label', 'configured_model', 'model_id', 'identity', 'enabled', 'health', 'context_configured', 'context_reported', 'max_context_verified', 'capabilities', 'allowed_categories', 'ram_available_bytes', 'vram_free_bytes', 'blocked_reasons')})
        summary = {'endpoint_count': len(rows), 'endpoints': rows, 'discovery_duration_seconds': time.perf_counter() - began, 'model_generation_requests': 0, 'owner_services_started_or_stopped': 0, 'synthetic_short_selection': decisions['synthetic_short_text'].get('endpoint'), 'scope': 'Original native discovery/admission; isolated registry; no inference or service changes.'}
        summary['worker_errors'] = {worker_id: observation.get('error') for worker_id, observation in registry.observations.items()}
        save(output / 'SUMMARY.json', summary)
        print(json.dumps({'endpoint_count': len(rows), 'endpoints': rows, 'discovery_duration_seconds': summary['discovery_duration_seconds']}, default=str), flush=True)
    finally:
        engine.close()
        compute.close()
        registry.close()
        save(output / 'IDENTITY_AFTER.json', runtime_snapshot(config))
        after = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
        save(output / 'SOURCE_AFTER.json', after)
        if source != after:
            raise RuntimeError('Implementation/configuration changed during discovery')
        for name, expected in copied.items():
            if digest(ROOT / 'data/compute' / name) != expected:
                raise RuntimeError('Owner configuration bytes changed during discovery')
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
