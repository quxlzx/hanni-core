"""Independent claim checks: documented coverage must not imply live success."""
from copy import deepcopy
from hashlib import sha256
import pytest
from scripts.campaign2_verification.scorecard import DIMENSIONS, check_scorecard, digest

def records():
    inventory = {'builtins': [{'id': 'isolated.alpha', 'definition_hash': 'a', 'handler_module': 'original.alpha', 'handler_sha256': 'b'}], 'owner_enabled_mcp_tools': [{'internal_id': 'enabled.but-unavailable', 'definition_hash': 'c', 'available': False}], 'inventory_sha256': 'dynamic-hash'}
    rows = []
    for name, fingerprint in (('isolated.alpha', 'a'), ('enabled.but-unavailable', 'c')):
        row = {'id': name, 'definition_hash': fingerprint, 'handler_module': 'original.alpha', 'handler_sha256': 'b', 'dimensions': {}}
        for dimension in DIMENSIONS:
            if name.startswith('enabled.'):
                entry = {'status': 'blocked', 'mode': 'no_connection', 'reason': 'No authorized live connection.', 'receipt': {}}
            else:
                receipt = {'original_handler_entered': True, 'readback': 'owned-state'}
                entry = {'status': 'pass', 'mode': 'isolated_original', 'receipt': receipt, 'receipt_sha256': digest(receipt), 'assertions': [{'check': 'observed owned readback', 'passed': True, 'observed': 'owned-state', 'expected': 'owned-state'}]}
                if dimension == 'natural_language_selection':
                    entry['mode'] = 'retrieval_only'
            row['dimensions'][dimension] = entry
        rows.append(row)
    return (inventory, {'inventory_sha256': 'dynamic-hash', 'discovered_count': len(rows), 'discovered_ids': [row['id'] for row in rows], 'capabilities': rows})

def test_unavailable_enabled_capability_is_in_dynamic_coverage_without_success():
    inventory, card = records()
    result = check_scorecard(card, inventory)
    assert result['accepted']
    assert result['discovered_count'] == 2
    assert result['dimension_outcomes']['end_to_end'] == {'pass': 1, 'blocked': 1}
    assert result['original_implementation_end_to_end_passes'] == 1

@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'unknown', 'count', 'inventory_hash', 'definition_hash', 'handler_hash'])
def test_dynamic_identity_faults_are_rejected(fault):
    inventory, card = records()
    if fault == 'missing':
        card['capabilities'].pop()
    elif fault == 'duplicate':
        card['capabilities'].append(deepcopy(card['capabilities'][0]))
    elif fault == 'unknown':
        card['capabilities'][0]['id'] = 'removed.capability'
    elif fault == 'count':
        card['discovered_count'] += 1
    elif fault == 'inventory_hash':
        card['inventory_sha256'] = 'obsolete'
    elif fault == 'definition_hash':
        card['capabilities'][0]['definition_hash'] = 'stale'
    elif fault == 'handler_hash':
        card['capabilities'][0]['handler_sha256'] = 'replaced'
    assert not check_scorecard(card, inventory)['accepted']

@pytest.mark.parametrize('fault', ['missing_dimension', 'invalid_status', 'no_assertion', 'false_assertion', 'no_observed', 'no_receipt', 'no_handler', 'only_gate', 'receipt_mutated'])
def test_false_implementation_claims_are_rejected(fault):
    inventory, card = records()
    dimensions = card['capabilities'][0]['dimensions']
    entry = dimensions['end_to_end']
    if fault == 'missing_dimension':
        dimensions.pop('permission_enforcement')
    elif fault == 'invalid_status':
        entry['status'] = 'probably'
    elif fault == 'no_assertion':
        entry['assertions'] = []
    elif fault == 'false_assertion':
        entry['assertions'][0]['passed'] = False
    elif fault == 'no_observed':
        entry['assertions'][0].pop('observed')
    elif fault == 'no_receipt':
        entry['receipt'] = {}
    elif fault == 'no_handler':
        entry['receipt']['original_handler_entered'] = False
    elif fault == 'only_gate':
        entry['mode'] = 'original_gate'
    elif fault == 'receipt_mutated':
        entry['receipt']['readback'] = 'changed-after-measurement'
    assert not check_scorecard(card, inventory)['accepted']

@pytest.mark.parametrize('fault', ['metadata_model', 'mock_live', 'blocked_no_reason'])
def test_mode_overclaims_and_undocumented_blocks_are_rejected(fault):
    inventory, card = records()
    if fault == 'metadata_model':
        card['capabilities'][0]['dimensions']['natural_language_selection']['model_evaluation_passed'] = True
    elif fault == 'mock_live':
        entry = card['capabilities'][0]['dimensions']['end_to_end']
        entry.update(mode='original_mock_dependency', live_integration_verified=True)
    else:
        card['capabilities'][1]['dimensions']['valid_arguments'].pop('reason')
    assert not check_scorecard(card, inventory)['accepted']

def test_external_evidence_mutation_is_detected(tmp_path):
    inventory, card = records()
    proof = tmp_path / 'proof.json'
    proof.write_text('{}', encoding='utf8')
    entry = card['capabilities'][0]['dimensions']['output_contract']
    entry.update(artifact='proof.json', artifact_sha256=sha256(proof.read_bytes()).hexdigest())
    assert check_scorecard(card, inventory, artifact_root=tmp_path)['accepted']
    proof.write_text('{"changed":true}', encoding='utf8')
    assert not check_scorecard(card, inventory, artifact_root=tmp_path)['accepted']

def test_pre_handler_refusal_cannot_pass_dependency_implementation():
    inventory, card = records()
    entry = card['capabilities'][0]['dimensions']['dependency_unavailable']
    entry['receipt'] = {'original_handler_entered': False, 'error': {'type': 'ToolValidationError'}}
    entry['receipt_sha256'] = digest(entry['receipt'])
    assert not check_scorecard(card, inventory)['accepted']
    entry['mode'] = 'original_gate'
    assert check_scorecard(card, inventory)['accepted']

def test_failure_outcome_still_requires_an_observation_or_reason():
    inventory, card = records()
    entry = card['capabilities'][0]['dimensions']['end_to_end']
    entry.update(status='fail', receipt={}, assertions=[])
    assert not check_scorecard(card, inventory)['accepted']
    entry['reason'] = 'The original implementation returned an explicit dependency failure.'
    assert check_scorecard(card, inventory)['accepted']
