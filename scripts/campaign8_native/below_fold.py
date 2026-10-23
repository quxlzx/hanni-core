"""Read-only native captures of previously unpictured original lower sections."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from scripts.campaign8_native.development import authenticated_readback
from scripts.campaign8_native.session import NativeSession

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    import psutil
    ready = json.loads(args.ready.read_text(encoding='utf8'))
    if psutil.Process(ready['pid']).create_time() != ready['create_time']:
        raise RuntimeError('Original owned backend identity changed.')
    with NativeSession(url=ready['url'], output=args.output, maximum_seconds=120) as session:
        session.report['lower_section_captures'] = []
        session.execute({'id': 'lower-sections-size', 'action': 'resize', 'size': [1280, 800]})
        session.execute({'id': 'original-workflow-route', 'action': 'route', 'route': 'workflows'})
        session.execute({'id': 'completed-workflow-filter', 'action': 'select', 'role': 'combobox', 'name': 'Workflow status', 'value': 'completed'})
        session.execute({'id': 'open-original-completed-history', 'action': 'click', 'selector': '.workflow-row'})
        session.execute({'id': 'show-original-checkpoints', 'action': 'click', 'selector': '.workflow-history summary'})
        session.page.get_by_role('heading', name='Checkpoints', exact=True).scroll_into_view_if_needed(timeout=5000)
        session.report['lower_section_captures'].append({'id': 'actual-workflow-checkpoint-rows', 'dom': session.dom(), 'visible_section_text': session.page.locator('.workflow-history').inner_text(), 'api': authenticated_readback(session, '/api/workflows'), 'screenshot': session.capture('actual-workflow-checkpoint-rows')})
        session.execute({'id': 'original-activity-route', 'action': 'route', 'route': 'activity'})
        session.execute({'id': 'original-activity-task-filter', 'action': 'fill', 'selector': 'input[aria-label="Search activity and capabilities"]', 'value': 'workspace.task'})
        session.page.get_by_role('heading', name='Execution history', exact=True).scroll_into_view_if_needed(timeout=5000)
        session.report['lower_section_captures'].append({'id': 'actual-activity-search-results', 'dom': session.dom(), 'visible_section_text': session.page.locator('.execution-list').inner_text(), 'api': authenticated_readback(session, '/api/agents'), 'screenshot': session.capture('actual-activity-search-results')})
        session.execute({'id': 'original-activity-failed-filter', 'action': 'select', 'role': 'combobox', 'name': 'Filter execution status', 'value': 'failed'})
        session.page.get_by_role('heading', name='Execution history', exact=True).scroll_into_view_if_needed(timeout=5000)
        session.report['lower_section_captures'].append({'id': 'actual-activity-status-results', 'dom': session.dom(), 'visible_section_text': session.page.locator('.execution-list').inner_text(), 'api': authenticated_readback(session, '/api/agents'), 'screenshot': session.capture('actual-activity-status-results')})
        session.report['scope_note'] = 'Original seeded durable history; fixture workflow was manually fenced and verified, not live model planning or scheduler evidence. Read-only UI actions; no invented audit rows.'
        session.report['complete'] = True
if __name__ == '__main__':
    main()
