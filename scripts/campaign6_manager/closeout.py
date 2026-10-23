"""Derive public Campaign 6 evidence without opening private holdout material."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data/campaign6-manager'
DOCS = ROOT / 'docs/campaign6'

def load(path):
    return json.loads(path.read_text(encoding='utf8'))

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')

def scorecard():
    result = load(DOCS / 'LIVE_SCORECARD_INITIAL.json')
    result['phase'] = 'LAST_BOUNDED_LIVE_DISCOVERY'
    observed_source = load(DATA / 'discovery-final/SOURCE_BEFORE.json')
    result['observed_production_sha256'] = {name: observed_source[name] for name in ('src/hanni/compute/registry.py', 'src/hanni/compute/scheduler.py', 'src/hanni/compute/transport.py', 'src/hanni/dashboard/cluster.py')}
    result['later_source_changes_since_live_observation'] = [name for name, before in result['observed_production_sha256'].items() if digest((ROOT / name).read_bytes()) != before]
    result['live_scope'] = 'Last authorized read-only discovery round, before the later credential-race repair. Source-bound receipts are historical observations, not a live validation of subsequent code.'
    probes = {v['node_id']: v for v in load(DATA / 'discovery-final/NODE_PROBES.json')}
    snapshots = {v['worker_id']: v for v in load(DATA / 'discovery-final/NATIVE_SNAPSHOT.json')['workers']}
    for node in result['nodes']:
        probe = probes[node['node_id']]
        node['authenticated_ssh'] = probe['authenticated_ssh']
        node['strict_host_verification'] = probe['host_verification']
        node['probe_status'] = probe['status']
        node['connection_rounds'] = 2
        node['ssh_failure_classes'] = [v['status'] for v in probe['attempts']]
        if probe['hardware'] is not None or probe['authenticated_ssh']:
            raise RuntimeError('New live evidence requires a reviewed scorecard projection')
    for worker in result['workers']:
        snapshot = snapshots[worker['worker_id']]
        if snapshot['status'] != 'unhealthy' or snapshot['model_id'] is not None:
            raise RuntimeError('Unexpected live identity requires reviewed evidence')
        worker['current_health_observation'] = snapshot['status']
        worker['health_observations'] = 2
        worker['current_snapshot_model_id'] = snapshot['model_id']
        worker['current_snapshot_verified_prompt_target'] = snapshot['max_context_verified']
        worker['reported_context_current'] = snapshot['context_reported']
        worker['resource_sampled_at_current'] = snapshot['resource_sampled_at']
        worker['availability_scope'] = 'Zero healthy native observations out of two bounded rounds; not steady-state availability.'
        worker['historical_proof_compatibility'] = 'Legacy source-unbound proof is retained on disk but is incompatible with the strengthened remote node identity.'
    result['live_generation_http_requests'] = 0
    result['source_evidence'] = ['data/campaign6-manager/discovery-initial', 'data/campaign6-manager/discovery-final', 'data/campaign6-verifier/live-confirmation-01/RESULTS.json']
    result['interpretation'] = 'Peer/TCP reachability is observed. Authentication, current hardware and model serving are blocked; unexecuted stages and null metrics are not passes or measured failure rates.'
    save(DOCS / 'LIVE_SCORECARD.json', result)

def preservation():
    baseline = load(DATA / 'baseline/PRIOR_CAMPAIGN_AND_OWNER_FILES.json')
    changes = {name: {'before': before, 'current': digest((ROOT / name).read_bytes()) if (ROOT / name).is_file() else None} for name, before in baseline.items() if not (ROOT / name).is_file() or digest((ROOT / name).read_bytes()) != before}
    allowed = {'.gitattributes', 'scripts/campaign5_intelligence/controlled.py', 'tests/integration/test_campaign5_verification.py'}
    unexpected = sorted(set(changes) - allowed)
    attrs = (ROOT / '.gitattributes').read_bytes()
    for rule in (b'evals/compute/campaign6*.json -text whitespace=cr-at-eol', b'docs/campaign6/*.json -text whitespace=cr-at-eol'):
        if attrs.count(rule) != 1:
            raise RuntimeError('Campaign Git attribute rule membership changed')
        attrs = attrs.replace(rule + b'\n', b'').replace(rule + b'\r\n', b'')
    attributes_prefix_preserved = any((digest(value) == baseline['.gitattributes'] for value in (attrs, attrs[:-1], attrs[:-2])))
    original = load(DATA / 'discovery-initial/SOURCE_BEFORE.json')
    production_changes = sorted((name for name, before in original.items() if digest((ROOT / name).read_bytes()) != before))
    expected_production = sorted(['src/hanni/compute/registry.py', 'src/hanni/compute/scheduler.py', 'src/hanni/compute/transport.py', 'src/hanni/dashboard/cluster.py'])
    owner_expected = load(DATA / 'discovery-initial/SUMMARY.json')['configured_owner_sha256']
    owner_matches = {name: digest((ROOT / 'data/compute' / name).read_bytes()) == before for name, before in owner_expected.items()}
    ssh_expected = load(DATA / 'baseline/SSH_CONFIG_IDENTITIES.json')
    ssh_matches = {}
    for name, expected in ssh_expected.items():
        path = Path.home() / '.ssh' / name
        actual = {'exists': path.exists()}
        if path.is_file():
            actual['sha256'] = digest(path.read_bytes())
        ssh_matches[name] = actual == expected
    rounds_stable = {}
    for label in ('discovery-initial', 'discovery-final'):
        folder = DATA / label
        rounds_stable[label] = load(folder / 'SOURCE_BEFORE.json') == load(folder / 'SOURCE_AFTER.json')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=ROOT, text=True).splitlines()
    result = {'prior_catalog_count': len(baseline), 'prior_catalog_changes': changes, 'approved_prior_catalog_exceptions': sorted(allowed), 'unexpected_prior_changes': unexpected, 'attributes_prefix_preserved': attributes_prefix_preserved, 'production_changes_since_campaign6_initial': production_changes, 'production_changes_match_scope': production_changes == expected_production, 'protected_owner_configuration_matches': owner_matches, 'ssh_identity_files_match': ssh_matches, 'discovery_source_rounds_stable': rounds_stable, 'head': head, 'head_preserved': head == '0aede831853b6876bc8904838a41f7b2ce8f3967', 'staged_files': staged, 'fixture_exception_scope': 'Archived-before timestamp metadata only; existing logical clocks, inputs and assertions preserved. Earlier Campaign 5 final seals and reports remain historical.'}
    result['passed'] = not unexpected and attributes_prefix_preserved and result['production_changes_match_scope'] and all(owner_matches.values()) and all(ssh_matches.values()) and all(rounds_stable.values()) and result['head_preserved'] and (not staged)
    save(DOCS / 'PRESERVATION.json', result)
    if not result['passed']:
        raise RuntimeError('Preservation audit failed; inspect the derived receipt')
    return result
if __name__ == '__main__':
    scorecard()
    result = preservation()
    print(json.dumps({'preservation_passed': result['passed'], 'catalog_files': result['prior_catalog_count'], 'production_changed_files': result['production_changes_since_campaign6_initial'], 'actual_generation_requests': 0}))
