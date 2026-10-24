"""One scheduling contract for the agent, conversation commands, and dashboard."""
from datetime import datetime
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from .cron import CronStore, READ_TOOLS


def default_timezone():
    import yaml
    folder = Path(os.environ.get('HANNI_CONFIG_DIR') or Path(__file__).resolve().parents[3] / 'config')
    try:
        config = yaml.safe_load((folder / 'hanni.yaml').read_text(encoding='utf-8')) or {}
        return config.get('user', {}).get('timezone', 'UTC')
    except (OSError, ValueError):
        return 'UTC'


def describe(job):
    zone = ZoneInfo(job['timezone'])
    return {**job, 'next_run_local': datetime.fromtimestamp(job['next_run'], zone).isoformat(),
            'delivery': 'Results and approval requests appear in the linked HANNI conversation. '
                        'HANNI must be running; missed runs catch up once after the next launch.'}


def create_schedule(root, args, *, conversation, request_key, zone=None):
    allowed = {'prompt', 'title', 'frequency', 'at_time', 'timezone', 'weekday', 'interval_seconds'}
    if not isinstance(args, dict) or set(args) - allowed:
        raise ValueError('Unsupported repeating task settings.')
    frequency = args.get('frequency', 'daily')
    if not isinstance(frequency, str) or frequency not in {'hourly', 'daily', 'weekly', 'interval'}:
        raise ValueError('Choose hourly, daily, weekly, or interval.')
    store = CronStore(Path(root) / 'cron.sqlite3')
    identifier = uuid5(NAMESPACE_URL, 'hanni-schedule:' + request_key).hex[:12]
    store.add(args.get('prompt', ''), 3600 if frequency == 'hourly' else args.get('interval_seconds', 3600), READ_TOOLS,
              title=args.get('title', 'Repeating task'), cadence='interval' if frequency == 'hourly' else frequency,
              at_time=args.get('at_time', '09:00'), timezone=args.get('timezone') or zone or default_timezone(),
              weekday=args.get('weekday', 0), conversation=conversation, job_id=identifier)
    return describe(store.get(identifier))


def manage_schedules(root, operation, job_id=None):
    store = CronStore(Path(root) / 'cron.sqlite3')
    if operation == 'list':
        return {'jobs': [describe(job) for job in store.list()]}
    if operation not in {'pause', 'resume', 'delete'}:
        raise ValueError('Choose list, pause, resume, or delete.')
    store.get(job_id)
    if operation == 'delete':
        store.delete(job_id)
    else:
        store.set_enabled(job_id, operation == 'resume')
    return {'id': job_id, 'operation': operation, 'message': f'Repeating task {operation} confirmed. '
            'Runs already submitted are retained; inspect their Task review before cancelling them.'}
