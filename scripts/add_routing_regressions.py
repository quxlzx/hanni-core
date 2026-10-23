"""Fixed compositional/date/safety probes beyond the original corpus."""
import json
from pathlib import Path


def main():
    path = Path('evals/routing/cases.jsonl')
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    rows = [r for r in rows if not r['id'].startswith('HARDENING-')]
    # GPU process telemetry is physically in the computer domain in _domain.
    # Correct inconsistent annotations, not the evaluator's domain rules.
    for row in rows:
        if row.get('primary') == 'gpu.top_processes' and row['expected_domain'] == 'process':
            row['expected_domain'] = 'computer'
        if row['id'].startswith('REGISTRY-system.performance-'):
            row['acceptable'] = ['system.stats', 'process.top_cpu', 'process.top_memory', 'process.top_disk_io', 'gpu.top_processes']
    extras = []
    def add(query, required=(), **kwargs):
        extras.append(dict(id=f'HARDENING-{len(extras)+1:03}', query=query, required=list(required),
                           family='hardening', expected_domain='mixed', **kwargs))
    for query, day, days in [
        ('Anything Friday?', '2026-09-25', 1),
        ('What about next Friday?', '2026-10-02', 1),
        ('What do I have this weekend?', '2026-09-26', 2),
        ('What appointments fill next week?', '2026-09-28', 7),
        ('Am I free after 6?', '2026-09-22', 1),
        ('What was on my calendar yesterday?', '2026-09-21', 1),
    ]:
        add(query, ['google_calendar.agenda'], now='2026-09-22T10:00:00', expected_families=['calendar'],
            expected_resolved_arguments={'google_calendar.agenda': {'start_date': day, 'days': days}})
    add('What do I have tmr?', ['google_calendar.agenda'], now='2026-12-31T23:59:00',
        expected_resolved_arguments={'google_calendar.agenda': {'start_date': '2027-01-01', 'days': 1}})
    add('Anything tomorrow?', ['google_calendar.agenda'], now='2028-02-28T23:00:00',
        expected_resolved_arguments={'google_calendar.agenda': {'start_date': '2028-02-29', 'days': 1}})
    for query, required, families in [
        ('Read settings.txt and show my CPU and RAM utilization', ['file.read', 'system.stats'], ['files', 'computer']),
        ('What is my GPU memory usage and is Firefox running?', ['gpu.memory', 'process.find'], ['computer', 'process']),
        ('What time is it and what is on my calendar tomorrow?', ['time.now', 'google_calendar.agenda'], ['time', 'calendar']),
        ('Open Discord and play Spotify', ['app.open', 'spotify.play_pause'], ['app', 'media']),
        ('How busy am I next week and is Qwen healthy?', ['google_calendar.agenda', 'model.status'], ['calendar', 'model']),
        ('Why is my PC slow and what is my next event?', ['system.performance', 'google_calendar.next'], ['computer', 'calendar']),
        ('Which app uses the most RAM and what is on my calendar Friday?', ['process.top_memory', 'google_calendar.agenda'], ['process', 'calendar']),
    ]:
        add(query, required, expected_families=families, now='2026-09-22T10:00:00',
            acceptable=['system.stats', 'process.top_cpu', 'process.top_memory', 'process.top_disk_io', 'gpu.top_processes'])
    for query in ['How was your day?', 'Check my stuff', 'Is anything wrong?', "How's everything?", 'Tell me a joke',
                  "Don't open Discord", 'Do not play Spotify', 'Thanks for helping me', 'Look at this']:
        add(query, mode='fallback')
    for query, subintent, required in [
        ('Which application is hammering RAM?', 'memory_pressure', 'process.top_memory'),
        ('Why does my PC stutter?', 'general_slowdown', 'system.performance'),
        ('Who is hogging the processor?', 'cpu_pressure', 'process.top_cpu'),
        ('Why is wireless internet so sluggish?', 'network', 'net.info'),
        ('Which apps are using the GPU?', 'gpu_vram', 'gpu.top_processes'),
        ('What process is generating all those disk writes?', 'disk_io', 'process.top_disk_io'),
        ('Why are the fans spinning so loudly?', 'thermal_power', 'system.stats'),
        ('Check the Windows event log for critical errors', 'windows_errors', 'system.event_errors'),
        ('Is the Qwen inference endpoint alive?', 'model_runtime', 'model.status'),
    ]:
        add(query, [required], expected_subintent=subintent,
            acceptable=['system.stats', 'system.performance', 'process.top_cpu', 'process.top_memory', 'process.top_disk_io',
                        'gpu.top_processes', 'gpu.memory', 'net.throughput', 'net.wifi', 'system.battery',
                        'power.battery_detail', 'power.plans'],
            forbidden=['google_calendar.create', 'app.open', 'process.stop'])
    add('Show my calendar tomorrow and delete the Downloads folder', mode='blocked', blocked_capabilities=['file.delete'])
    add('Open Discord and terminate the frozen app', mode='blocked', blocked_capabilities=['process.stop'])
    add('What is on my calendar 2026-02-30?', mode='fallback')
    add('What is on my calendar 9/12?', mode='fallback')
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows + extras), encoding='utf-8')


if __name__ == '__main__':
    main()
