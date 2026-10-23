"""Post-run development scoring of original native receipts.

The executor never imports this module or sees its oracle. Missing measurement
stays unverified; successful click dispatch alone never proves the requested
application effect. Each original failed attempt is retained independently.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path

def contains_fields(rows, expected):
    return any((all((row.get(key) == value for key, value in expected.items())) for row in rows))

def original_data(receipt, prefix):
    for row in receipt.get('backend_readbacks', []):
        if row['path'].split('?', 1)[0] == prefix and row.get('status') == 200:
            return row['data']
    return {}

def check(receipt, name, expected, previous=None):
    """Return observed evidence and pass/false/unknown without oracle mutation."""
    product = original_data(receipt, '/api/productivity')
    memory = original_data(receipt, '/api/memory/explorer')
    suggestions = original_data(receipt, '/api/memory/suggestions')
    notifications = original_data(receipt, '/api/notifications')
    mcp = original_data(receipt, '/api/mcp')
    lab = original_data(receipt, '/api/model-lab')
    route = original_data(receipt, '/api/model-routing')
    dom = receipt.get('dom', {})
    controls = [c for c in dom.get('controls', []) if c.get('visible')]
    names = [c.get('name', '') for c in controls]
    if name.startswith('persisted_') and name in {'persisted_task', 'persisted_project', 'persisted_note'}:
        key = {'persisted_task': 'tasks', 'persisted_project': 'projects', 'persisted_note': 'notes'}[name]
        rows = product.get(key)
        return (contains_fields(rows, expected), rows) if isinstance(rows, list) else (None, None)
    kinds = {'task': ('tasks', 'title'), 'project': ('projects', 'name'), 'link': ('links', 'label')}
    for kind, (collection, field) in kinds.items():
        if name in {kind + '_retained', kind + '_absent'}:
            rows = product.get(collection)
            if not isinstance(rows, list):
                return (None, None)
            found = any((row.get(field) == expected for row in rows))
            return (not found if name.endswith('_absent') else found, rows)
    if name == 'persisted_note_body':
        rows = product.get('notes')
        return (any((row.get('body') == expected for row in rows)), rows) if isinstance(rows, list) else (None, None)
    if name in {'memory_content', 'memory_content_retained'}:
        rows = memory.get('records')
        return (any((row.get('content') == expected for row in rows)), rows) if isinstance(rows, list) else (None, None)
    if name == 'memory_retained':
        rows = memory.get('records')
        return (bool(rows), rows) if isinstance(rows, list) else (None, None)
    if name == 'notes_retained':
        rows = product.get('notes')
        return (bool(rows), rows) if isinstance(rows, list) else (None, None)
    if name == 'original_project_retained':
        rows = product.get('projects')
        return (any((row.get('name') == 'Controlled QA observatory' for row in rows)), rows) if isinstance(rows, list) else (None, None)
    if name == 'suggestion_pending':
        rows = suggestions.get('items')
        return (any((row.get('status') == 'pending' for row in rows)), rows) if isinstance(rows, list) else (None, None)
    if name == 'no_new_memory':
        count = memory.get('total_stored')
        return (count == 1, count) if count is not None else (None, None)
    if name == 'suggestion_rejected':
        return (None, {'pending_count': memory.get('pending_suggestions'), 'items': suggestions.get('items')})
    if name.startswith('notification_') and name.endswith('_count_minimum'):
        field = 'read' if 'read_count' in name else 'dismissed'
        rows = notifications.get('items')
        count = sum((row.get(field) is True for row in rows)) if isinstance(rows, list) else None
        return (count >= expected, count) if count is not None else (None, None)
    if name == 'notification_history_retained':
        rows = notifications.get('items')
        return (any((row.get('dismissed') is True for row in rows)), rows) if isinstance(rows, list) else (None, None)
    if name == 'original_local_category_preference':
        observed = notifications.get('preferences', {}).get('categories', {}).get('approvals')
        return (observed is expected, observed) if type(observed) is bool else (None, observed)
    if name == 'dialog_closed':
        observed = dom.get('dialogs')
        return (not any((row.get('open') for row in observed)), observed) if isinstance(observed, list) else (None, None)
    if name == 'palette_visible':
        dialogs = dom.get('dialogs')
        return (any((row.get('open') and row.get('label') == 'Search workspace' for row in dialogs)), dialogs) if isinstance(dialogs, list) else (None, None)
    if name == 'visible_text':
        matched = any((expected in value for value in names))
        return (True, names) if matched else (None, names)
    if name == 'persisted_policy':
        value = route.get('policy')
        return (value == expected, value) if value is not None else (None, None)
    if name == 'server_config':
        rows = mcp.get('servers')
        configs = [row.get('config', {}) for row in rows] if isinstance(rows, list) else None
        return (contains_fields(configs, expected), configs) if configs is not None else (None, None)
    if name in {'server_absent', 'server_retained'}:
        rows = mcp.get('servers')
        if not isinstance(rows, list):
            return (None, None)
        exists = any((row.get('name') == expected for row in rows))
        return (not exists if name.endswith('_absent') else exists, rows)
    if name == 'never_connected':
        rows = mcp.get('servers')
        return (all((row.get('last_connected_at') is None and row.get('state') == 'disabled' for row in rows)), rows) if isinstance(rows, list) else (None, None)
    if name in {'no_fake_results', 'empty_history_visible', 'no_measured_comparison_claim'}:
        count = lab.get('history_count')
        return (count == 0 and lab.get('runs') == [], {'count': count, 'runs': lab.get('runs')}) if count is not None else (None, None)
    if name == 'preferred_endpoint_control_visible':
        found = [c for c in controls if c.get('name') == 'Preferred endpoint']
        return (True if found else None, found)
    if name in {'no_connected_provider', 'not_connected'}:
        calendar = original_data(receipt, '/api/calendar')
        value = calendar.get('connected')
        accounts = calendar.get('accounts')
        return (value is False and isinstance(accounts, list) and all((account.get('connected') is False for account in accounts)), calendar) if type(value) is bool else (None, None)
    if name == 'original_store_projection_current':
        return (memory.get('available') is True and memory.get('source') == 'authoritative-memory', memory) if memory else (None, None)
    if name == 'original_config_projection_current':
        value = original_data(receipt, '/api/workspace')
        return (isinstance(value.get('screens'), list) and bool(value.get('policies')), value) if value else (None, None)
    if name == 'pending_approval_blocked_unattached_controller':
        value = original_data(receipt, '/api/workflows')
        items = [row for row in value.get('items', []) if row.get('status') == 'awaiting_plan_approval']
        return (value.get('controller_attached') is False and bool(items) and all((row.get('controls', {}).get('approve_plan', {}).get('enabled') is False for row in items)), items) if value else (None, None)
    if name in {'no_mutation', 'no_delete_write', 'no_create_write', 'no_correction_write', 'no_review_write', 'no_consolidation_write', 'no_suggestion_write', 'no_configuration_commit'} and previous:
        old = original_data(previous, '/api/productivity')
        if product and old:
            keys = ('tasks', 'projects', 'notes', 'links')
            same = all((product.get(k) == old.get(k) for k in keys))
            return (same, {'current': {k: product.get(k) for k in keys}, 'previous': {k: old.get(k) for k in keys}})
        old = original_data(previous, '/api/mcp')
        if mcp and old:
            return (mcp.get('revision') == old.get('revision'), {'current_revision': mcp.get('revision'), 'previous_revision': old.get('revision')})
        old_memory = original_data(previous, '/api/memory/explorer')
        old_suggestions = original_data(previous, '/api/memory/suggestions')
        if memory and old_memory:
            observations = {'current_records': memory.get('records'), 'previous_records': old_memory.get('records'), 'current_pending_count': memory.get('pending_suggestions'), 'previous_pending_count': old_memory.get('pending_suggestions')}
            same = memory.get('records') == old_memory.get('records') and memory.get('pending_suggestions') == old_memory.get('pending_suggestions')
            if suggestions and old_suggestions:
                same = same and suggestions.get('items') == old_suggestions.get('items')
            return (same, observations)
    return (None, None)

def grade(receipt, oracle, *, previous=None, supplemental=()):
    assertions = []
    supplemental = {row['check']: row for row in supplemental}
    for name, expected in oracle['check'].items():
        passed, observed = check(receipt, name, expected, previous)
        evidence = 'Original per-case authenticated API/DOM measurement'
        if name in supplemental:
            extra = supplemental[name]
            if not extra.get('evidence') or type(extra.get('passed')) is not bool:
                raise ValueError('Supplemental proof requires explicit observed judgment and evidence.')
            passed, observed = (extra['passed'], extra.get('observed'))
            evidence = extra['evidence']
        assertions.append({'check': name, 'expected': expected, 'observed': observed, 'passed': passed, 'evidence': evidence})
    executed = receipt.get('executed') is True
    if not executed:
        outcome = 'EXECUTION_ERROR'
    elif any((row['passed'] is False for row in assertions)):
        outcome = 'FAIL'
    elif any((row['passed'] is None for row in assertions)):
        outcome = 'UNVERIFIED'
    else:
        outcome = 'PASS'
    return {'id': oracle['id'], 'route': receipt['input']['route'], 'outcome': outcome, 'executed': executed, 'error': receipt.get('error'), 'assertions': assertions, 'window': receipt.get('window'), 'screenshot': receipt.get('screenshot', receipt.get('error_screenshot')), 'readback_errors': [{'path': row['path'], 'status': row['status']} for row in receipt.get('backend_readbacks', []) if row['status'] != 200], 'scope': 'Original isolated backend/native case only. Execution errors and actual persisted effects are separate; unknown measurement is not PASS.'}

def publish(receipts, oracles, output, supplemental=None):
    output = Path(output)
    if output.exists():
        raise ValueError('Preserve all earlier semantic grading checkpoints.')
    raw = json.loads(Path(receipts).read_text(encoding='utf8'))
    expected = {row['id']: row for row in json.loads(Path(oracles).read_text(encoding='utf8'))}
    extra = json.loads(Path(supplemental).read_text(encoding='utf8')) if supplemental else {}
    rows, previous = ([], None)
    for case in raw['development_cases']:
        identifier = case['input']['id']
        rows.append(grade(case, expected[identifier], previous=previous, supplemental=extra.get(identifier, [])))
        previous = case
    output.mkdir(parents=True)
    value = {'receipts': Path(receipts).as_posix(), 'receipts_sha256': hashlib.sha256(Path(receipts).read_bytes()).hexdigest(), 'oracles': Path(oracles).as_posix(), 'oracles_sha256': hashlib.sha256(Path(oracles).read_bytes()).hexdigest(), 'cases': len(rows), 'counts': dict(Counter((row['outcome'] for row in rows))), 'rows': rows, 'no_executor_oracle_access': True, 'unverified_is_not_pass': True}
    (output / 'SEMANTIC_RESULTS.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps(value['counts']))
    return value
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipts', required=True)
    parser.add_argument('--oracles', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--supplemental')
    args = parser.parse_args()
    publish(args.receipts, args.oracles, args.output, args.supplemental)
