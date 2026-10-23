"""Private fixed workflow controls attached to HANNI's original controller.

Reading history creates no model session or tool executor. Only a live original
controller can attach the bounded runner. No generic tool or path endpoint.
"""
from __future__ import annotations

from dataclasses import asdict
import math
from pathlib import Path
import sqlite3
import threading
import time

from hanni.dashboard.features import request_id


OPERATIONS = frozenset({'goal.submit', 'start', 'pause', 'resume', 'cancel',
                       'approve_plan', 'approve_step', 'reject', 'revoke', 'retry_safe'})


class WorkflowHub:
    def __init__(self, config, features, telemetry, *, service=None, compute=None):
        self.config, self.features, self.telemetry = config, features, telemetry
        self.root = Path(config.paths.data_dir).resolve() if config else None
        self.service = service
        self.registry = None
        self.runner_attached = False
        self.closed = False
        self.error = None
        self.compute = compute
        self.lock = threading.RLock()

    def require(self):
        with self.lock:
            if self.closed or self.config is None:
                raise RuntimeError('Workflow history is unavailable in this session.')
            if self.service is None:
                from hanni.workflows import WorkflowService, WorkflowLimits
                values = asdict(self.config.hanni.workflows)
                values.pop('enabled')
                values.pop('default_mode')
                protected = (self.config.paths.config_dir, Path(__file__).resolve().parents[3])
                self.service = WorkflowService(self.root, limits=WorkflowLimits(**values),
                                               protected_roots=protected, planning_contract='intent')
            return self.service

    def _resource_probe(self):
        # The existing telemetry worker owns GPU probes; HTTP and workflow
        # admission read its actual cached measurements, never launch probes.
        sample = self.telemetry.snapshot()
        resources = sample.get('resources') or {}
        stamp = sample.get('sampled_at')
        ram = resources.get('ram_percent')
        valid = (isinstance(ram, (int, float)) and not isinstance(ram, bool)
                 and math.isfinite(ram) and 0 <= ram <= 100
                 and isinstance(stamp, (int, float)) and not isinstance(stamp, bool)
                 and math.isfinite(stamp) and 0 <= time.time() - stamp <= 30)
        allowed = valid and ram < self.config.models.critical_ram_percent
        reason = (None if allowed else 'Fresh RAM telemetry is unavailable.' if not valid
                  else 'RAM pressure exceeds the existing model resource policy.')
        return {'allowed': allowed, 'reason': reason, 'ram_percent': ram if valid else None,
                'cpu_percent': resources.get('cpu_percent'), 'gpu': resources.get('gpus')}

    def _notify(self, event):
        # Preserve notification preferences, bounded retention and persistent
        # deduplication in the original workspace store.
        item = dict(event)
        item['priority'] = ('action_required' if event.get('priority') == 'high'
                            else 'informational')
        self.features.store.ingest([item])

    def attach_controller(self, registry, client, host):
        with self.lock:
            if self.closed or self.config is None or not self.config.hanni.workflows.enabled:
                return
            if self.registry is registry and self.runner_attached:
                return
            if self.registry is not None and self.registry is not registry:
                self.registry = None
                self.runner_attached = False
                try:
                    self.require().detach()
                except (ValueError, OSError, RuntimeError, sqlite3.Error):
                    self.error = 'Workflow controller cleanup failed. New admissions are disabled.'
                    return
            try:
                service = self.require()
                from hanni.core.interaction import interaction
                service.attach(host=host, registry=registry, client=client,
                               interaction=interaction, resource_probe=self._resource_probe,
                               notification_sink=self._notify, compute_scheduler=self.compute)
                if self.compute is not None:
                    self.compute.start_monitor()
                service.start()
                self.registry = registry
                self.runner_attached = True
                self.error = None
            except (ValueError, OSError, RuntimeError, sqlite3.Error):
                self.error = 'Workflow storage or runner is unavailable. Existing data was retained.'
                self.registry = None
                self.runner_attached = False
                if self.service is not None:
                    try:
                        self.service.detach()
                    except (ValueError, OSError, RuntimeError, sqlite3.Error):
                        pass  # Facade admissions stay disabled; original controller cleanup continues.

    def detach_controller(self, registry):
        with self.lock:
            if self.registry is registry:
                self.registry = None
                self.runner_attached = False
                if self.service is not None:
                    try:
                        self.service.detach()
                    except (ValueError, OSError, RuntimeError, sqlite3.Error):
                        self.error = 'Workflow controller cleanup failed. New admissions are disabled.'
                        raise

    def _envelope(self):
        reason = self.error
        if self.config is None:
            reason = 'Local workflow configuration is unavailable.'
        elif not self.config.hanni.workflows.enabled:
            reason = 'Workflow execution is disabled in local configuration.'
        elif not self.runner_attached:
            reason = reason or 'Start the assistant or workflow backend to execute goals.'
        return {'available': self.config is not None and not self.closed and not self.error,
                'reason': reason, 'runner_attached': self.runner_attached and not self.closed,
                'controller_attached': self.registry is not None and not self.closed,
                'max_goal_chars': self.config.hanni.workflows.max_goal_chars if self.config else 4000,
                'sampled_at': time.time()}

    def snapshot(self, *, limit=50):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError('Choose a workflow history limit from 1 to 100.')
        envelope = self._envelope()
        items = self.require().snapshot(limit=limit) if envelope['available'] else []
        # Service snapshot returns summaries; facade availability and creation
        # controls reflect actual backend lifecycle, never a fake live runner.
        if isinstance(items, dict):
            if items.get('available') is False:
                envelope.update(available=False, reason='Workflow storage is unavailable. Existing data was retained.')
            items = items.get('items', [])
        if not isinstance(items, list):
            raise RuntimeError('Workflow history is unavailable. Existing data was retained.')
        return {**envelope, 'items': items, 'controls': {'goal.submit': {
            'enabled': bool(envelope['runner_attached'] and envelope['available']), 'reason': envelope['reason']}}}

    def detail(self, workflow_id):
        envelope = self._envelope()
        result = self.require().detail(workflow_id) if envelope['available'] else None
        if isinstance(result, dict) and not self.runner_attached:
            result = dict(result)
            result['controls'] = {key: {'enabled': False, 'reason': envelope['reason']}
                                  for key in result.get('controls', {})}
        if isinstance(result, dict) and self.compute is not None:
            result = dict(result, compute_jobs=self.compute.registry.jobs(workflow_id))
        return {**envelope, 'workflow': result}

    def mutate(self, body):
        if not isinstance(body, dict) or set(body) != {'id', 'operation', 'data'}:
            raise ValueError('Expected request ID, fixed workflow operation and data.')
        request_id(body['id'])
        if (not isinstance(body.get('operation'), str) or body['operation'] not in OPERATIONS
                or not isinstance(body.get('data'), dict)):
            raise ValueError('Unsupported workflow operation.')
        if not self.runner_attached or self.closed:
            raise RuntimeError(self._envelope()['reason'] or 'Workflow runner is unavailable.')
        if body['operation'] == 'goal.submit' and 'mode' not in body['data']:
            body = {**body, 'data': {**body['data'], 'mode': self.config.hanni.workflows.default_mode}}
        # WorkflowService owns durable payload-bound deduplication and revision,
        # approval, scope and original tool gates; no in-memory-only ledger.
        result = self.require().mutate(body, actor_profile='owner')
        if self.compute is not None and body['operation'] in {'pause', 'cancel', 'revoke'}:
            self.compute.cancel_workflow(body['data'].get('workflow_id'))
        if isinstance(result, dict) and 'workflow_id' in result:
            if result.get('expired') is True:
                return {**result, 'workflow': None}
            return {**result, 'workflow': self.require().detail(result['workflow_id'])}
        return result

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.runner_attached = False
            self.registry = None
            if self.service is not None:
                self.service.close()


def close_workflows_for_cleanup(hub):
    """A workflow cleanup fault must not skip the original backend teardown."""
    if hub is not None:
        try:
            hub.close()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning('Workflow cleanup failed (%s).', type(exc).__name__)
