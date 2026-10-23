"""Public development plans; original host/service/gates/handlers remain in use."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import threading
from scripts.v3_review.service_fixture import QueuedStructuredClient, ServiceFixture

def criterion(path='/data/text', expected=None, operator='present'):
    return dict(operator=operator, path=path, expected=expected)

def step(identity, path, *, dependencies=(), required=True, capability='file.read', criteria=None):
    description = ('Read the text file ' if capability == 'file.read' else 'Check whether the file exists at ') + str(path)
    return (dict(step_id=identity, description=description, kind='tool', dependencies=list(dependencies), required=required, criteria=criteria or [criterion('/data/text' if capability == 'file.read' else '/data/exists')]), dict(step_id=identity, capability_id=capability, arguments={'path': str(path)}))

def plan_client(*pairs):
    return QueuedStructuredClient(dict(summary='Controlled development workflow; no goal-understanding claim.', unsupported_reason=None, steps=[deepcopy(pair[0]) for pair in pairs]), dict(unsupported_reason=None, steps=[deepcopy(pair[1]) for pair in pairs]))

def artifact(identity='save', *, dependencies=('read',), source='read'):
    outline = dict(step_id=identity, description='Save the verified predecessor text as a managed report.', kind='artifact', dependencies=list(dependencies), required=True, criteria=[criterion('/data/path')])

    def binding(root):
        return dict(step_id=identity, capability_id='file.write', arguments=dict(path=str(Path(root) / 'report.txt'), text={'$ref': dict(step_id=source, path='/data/text', type='string')}))
    return (outline, binding)

def artifact_client(path):
    read = step('read', path)
    save, bind_save = artifact()

    def binding(messages, _):
        payload = json.loads(messages[1]['content'])
        return dict(unsupported_reason=None, steps=[read[1], bind_save(payload['artifact_root'])])
    return QueuedStructuredClient(dict(summary='Preserve actual verified source contents.', unsupported_reason=None, steps=[read[0], save]), binding)

def install(box, capability, *, before=None, after=None, **metadata):
    """Observe/fail a dependency under original definition and registry authority."""
    definition = box.registry.get(capability)
    original = definition.handler

    def handler(arguments, context, request):
        if before:
            before(arguments, context, request)
        result = original(arguments, context, request)
        if after:
            return after(arguments, context, request, result)
        return result
    assert box.registry.unregister(capability, expected=definition)
    box.registry.register(replace(definition, handler=handler, **metadata))

def reviewed_start(box, key):
    assert box.await_state(key, 'awaiting_plan_approval', 'blocked')['status'] == 'awaiting_plan_approval'
    box.control(key, 'approve_plan')
    box.control(key, 'start')

class Gate:
    """Bounded deterministic synchronous-call seam with explicit release."""

    def __init__(self):
        self.entered, self.release = (threading.Event(), threading.Event())

    def __call__(self, *_):
        self.entered.set()
        if not self.release.wait(5):
            raise AssertionError('Controlled gate was not released')
