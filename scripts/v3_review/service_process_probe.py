"""Owned subprocess probe of real Service crash boundaries, never production data.

No handler wrapper is registered: original plain file handlers retain their actual
restart-stable identities. The documented commit observer stops this process.
"""
import argparse
import json
import os
from pathlib import Path
import time

from hanni.workflows.types import WorkflowLimits
from scripts.v3_review.service_fixture import QueuedStructuredClient, ServiceFixture


def durable_json(path, value):
    path = Path(path)
    # The parent treats existence as committed evidence. Publish only after
    # the complete JSON is flushed; opening the final path first exposes an
    # empty/partial file to a concurrent reader on Windows.
    staged = path.with_name(path.name + f'.{os.getpid()}.publishing')
    with staged.open('w', encoding='utf-8') as stream:
        stream.write(json.dumps(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(staged, path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--mode', choices=('before_dispatch', 'after_result', 'hold_result'), required=True)
    parser.add_argument('--target', choices=('write', 'safe_read'), default='write')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / 'source.txt'
    source.write_text('One original fixture effect.', encoding='utf-8')
    client = QueuedStructuredClient()
    proposed = [
                        {'step_id': 'read', 'description': 'Read the text file ' + str(source),
                         'kind': 'tool', 'dependencies': [], 'required': True,
                         'criteria': [{'operator': 'equals', 'path': '/data/text',
                                       'expected': 'One original fixture effect.'}]},
                        {'step_id': 'save', 'description': 'Save the verified fixture report.',
                         'kind': 'artifact', 'dependencies': ['read'], 'required': True,
                         'criteria': [{'operator': 'present', 'path': '/data/path', 'expected': None}]}]
    if args.target == 'safe_read':
        proposed = [
            {'step_id': 'stat', 'description': 'Check whether file ' + str(source) + ' exists and hash its bytes.',
             'kind': 'tool', 'dependencies': [], 'required': True,
             'criteria': [{'operator': 'equals', 'path': '/data/exists', 'expected': True}]},
            dict(proposed[0], dependencies=['stat'])]
    client.enqueue({'summary': 'Read the exact original fixture evidence.', 'unsupported_reason': None,
                    'steps': proposed})
    def binding(messages, _kwargs):
        data = json.loads(messages[1]['content'])
        bound = [
            {'step_id': 'read', 'capability_id': 'file.read', 'arguments': {'path': str(source)}},
            {'step_id': 'save', 'capability_id': 'file.write', 'arguments': {
                'path': str(Path(data['artifact_root']) / 'report.txt'),
                'text': {'$ref': {'step_id': 'read', 'path': '/data/text', 'type': 'string'}}}}]
        if args.target == 'safe_read':
            bound = [{'step_id': 'stat', 'capability_id': 'file.stat',
                      'arguments': {'path': str(source), 'hash': True}}, bound[0]]
        return {'unsupported_reason': None, 'steps': bound}
    client.enqueue(binding)
    box = {}
    def observer(stage, metadata):
        fixture = box['fixture']
        invocation = metadata
        if stage == 'after_result':
            invocation = next(row for row in fixture.detail(box['key'])['invocations']
                              if row['invocation_id'] == metadata['invocation_id'])
        target = 'stat' if args.target == 'safe_read' else 'save'
        if invocation.get('step_id') != target:
            return
        if stage != ('after_result' if args.mode == 'hold_result' else args.mode):
            return
        detail = fixture.detail(box['key'])
        saved = next(row for row in detail['steps'] if row['step_id'] == target)
        durable_json(root / 'boundary.json', {'stage': stage, 'workflow_id': box['key'],
                    'invocation_id': invocation['invocation_id'],
                    'path': saved['resolved_arguments']['path'], 'pid': os.getpid(),
                    'lease': fixture.service.lease})
        if args.mode == 'hold_result':
            while not (root / 'release').exists():
                time.sleep(.02)
        else:
            os._exit(73)
    with ServiceFixture(root / 'run', client=client, limits=WorkflowLimits(lease_seconds=1),
                        observer=observer) as fixture:
        box['fixture'] = fixture
        key = fixture.submit('Read the supplied local text file and save its verified contents.')
        box['key'] = key
        fixture.await_state(key, 'awaiting_plan_approval')
        fixture.control(key, 'approve_plan')
        fixture.control(key, 'start')
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if args.mode == 'hold_result' and (root / 'release').exists():
                time.sleep(.25)
                durable_json(root / 'stale-completion.json', fixture.detail(key))
                return
            time.sleep(.02)
        raise AssertionError('The actual Service did not reach the requested commit boundary.')


if __name__ == '__main__':
    main()
