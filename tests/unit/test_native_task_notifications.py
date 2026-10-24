"""Durable native task alerts use actual receipts, without executing actions."""
import json
from uuid import uuid4

from hanni.dashboard.features import DesktopFeatures
from hanni.hermes.state import TaskStore
from hanni.native.local_tools import local_tool_specs
from tests.unit.test_desktop_features import config_for, mutation


def submit(store, key=None):
    return store.submit(key or str(uuid4()), {'prompt': 'private prompt not for notifications',
        'origin': 'hanni', 'windows_tools': [], 'context': {}})


def sample(features):
    return features.notifications(telemetry={}, cluster={'nodes': []}, contract={})['items']


def test_completion_is_not_replayed_and_unread_history_survives_restart(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        old = submit(tasks)
        tasks.event(old['id'], 'Old result', state='review_required', result={'model_claims': 'private old result'})
        feature = DesktopFeatures(config_for(tmp_path))
        assert sample(feature) == []
        task = submit(tasks)
        tasks.event(task['id'], 'Done', state='review_required', result={'model_claims': 'private new result'})
        items = sample(feature)
        assert len(items) == 1 and items[0]['title'] == 'HANNI finished a task'
        assert items[0]['target'] == {'screen': 'tasks', 'id': task['id']}
        assert 'private' not in json.dumps(items)
        assert sample(feature) == items
        # Reopen the feature after additional work completed while it was absent.
        later = submit(tasks, 'cron-completed-while-closed')
        tasks.event(later['id'], 'Scheduled done', state='completed')
        fresh = DesktopFeatures(config_for(tmp_path))
        items = sample(fresh)
        assert len(items) == 2 and any(item['title'] == 'A scheduled task is ready' for item in items)
        fresh.mutate('notifications', mutation('notification.dismiss', {'notification_id': items[0]['id']}))
        assert sum(item['dismissed'] for item in sample(fresh)) == 1
        assert tasks.get(task['id'])['state'] == 'review_required'
    finally: tasks.close()


def test_each_pending_action_notifies_without_granting_execution(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        feature = DesktopFeatures(config_for(tmp_path))
        sample(feature)
        task = submit(tasks)
        tool = next(tool for tool in local_tool_specs() if tool['name'] == 'local_write_file')
        first = tasks.request_action(task['id'], 'first', tool, {'path': 'review.txt', 'content': 'private draft'})
        items = sample(feature)
        assert len(items) == 1 and items[0]['priority'] == 'action_required'
        assert items[0]['category'] == 'approvals'
        assert items[0]['target']['id'] == task['id']
        assert tasks.action(first['id'])['state'] == 'pending'
        assert not (tmp_path / 'workspace' / 'review.txt').exists()
        feature.mutate('notifications', mutation('notification.read', {'notification_id': items[0]['id']}))
        assert tasks.action(first['id'])['state'] == 'pending'
        tasks.settle(first['id'], 'rejected')
        second = tasks.request_action(task['id'], 'second', tool, {'path': 'another.txt', 'content': 'private draft'})
        assert len(sample(feature)) == 2
        assert tasks.action(second['id'])['state'] == 'pending'
    finally: tasks.close()


def test_failure_is_critical_and_muted_categories_do_not_backfill(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        feature = DesktopFeatures(config_for(tmp_path))
        sample(feature)
        feature.mutate('notifications', mutation('notification.preferences', {'categories': {'agents': False}}))
        task = submit(tasks)
        tasks.event(task['id'], 'Failed', state='failed', error='private error')
        assert not any(item['key'].startswith('native:') for item in sample(feature))
        feature.mutate('notifications', mutation('notification.preferences', {'categories': {'agents': True}}))
        assert not any(item['key'].startswith('native:') for item in sample(feature))
        task = submit(tasks)
        tasks.event(task['id'], 'Failed', state='uncertain', error='private error')
        item = next(item for item in sample(feature) if item['key'].startswith('native:'))
        assert item['priority'] == 'critical' and 'private' not in json.dumps(item)
    finally: tasks.close()
