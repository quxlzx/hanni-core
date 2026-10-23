"""Write fixed synthetic scenarios; neither telemetry nor Google is accessed."""
import json
from pathlib import Path


def result(data, name):
    return dict(name=name, ok=True, message='Synthetic measurement.', data=data)


def main():
    rows = []
    diagnostics = [
        ('cpu', 97, 45, 20, 8, 2, 'python.exe', 88, 1,
         ['process.top_cpu'], [dict(label='CPU pressure', pattern=r'cpu.{0,55}(?:pressure|bottleneck|high|97)|(?:pressure|bottleneck).{0,35}cpu', evidence_any=[['system.stats', 'system.performance']]),
                              dict(label='CPU contributor', pattern=r'python\.exe', evidence_tools=['process.top_cpu'])],
         [r'(?:ram|memory|gpu|disk).{0,25}(?:bottleneck|failure)']),
        ('memory', 22, 96, 15, 91, 2, 'llama-server.exe', 8, 18,
         ['process.top_memory'], [dict(label='RAM pressure', pattern=r'(?:ram|memory).{0,45}(?:pressure|high|96|full)|(?:pressure|high).{0,35}(?:ram|memory)', evidence_any=[['system.stats', 'system.performance']]),
                                 dict(label='memory contributor', pattern=r'llama-server', evidence_tools=['process.top_memory']),
                                 dict(label='paging possibility', pattern=r'(?:may|might|could|possible|possibly|suggest).{0,60}(?:pag|swap)|(?:pag|swap).{0,60}(?:may|might|could|possible)', evidence_any=[['system.stats', 'system.performance']])],
         [r'(?:gpu|cpu).{0,25}bottleneck', r'(?:ssd|disk).{0,25}(?:failure|failing|broken)']),
        ('gpu', 38, 61, 99, 10, 15.8, 'render.exe', 10, 2,
         [], [dict(label='GPU pressure', pattern=r'(?:gpu|vram).{0,55}(?:pressure|bottleneck|high|99|full)|(?:pressure|bottleneck).{0,35}(?:gpu|vram)', evidence_any=[['system.stats', 'system.performance']])],
         [r'(?:cpu|ram|disk).{0,25}(?:bottleneck|failure)']),
        ('healthy', 12, 39, 4, 2, 1, 'explorer.exe', 2, 0.2,
         [], [dict(label='no visible bottleneck', pattern=r'(?:no|not|don.t|doesn.t).{0,65}(?:bottleneck|problem|pressure)|(?:healthy|normal|light usage)', evidence_any=[['system.stats', 'system.performance']])],
         [r'(?:cpu|ram|gpu|disk|memory).{0,25}(?:is the bottleneck|is failing|is overloaded)', r'(?:malware|virus|ssd failure)']),
    ]
    for ident, cpu, ram, gpu, disk, vram, process, process_cpu, memory_gb, required, claims, unsupported in diagnostics:
        snapshot = dict(cpu_percent=cpu, ram_percent=ram, disk_active_percent=disk,
                        gpus=[dict(name='Synthetic GPU', utilization_percent=gpu, vram_used_gb=vram, vram_total_gb=16)])
        mocks = {name: result(snapshot, name) for name in ['system.stats', 'system.performance']}
        mocks.update({name: result({'processes': [dict(name=process, cpu_percent=process_cpu, memory_gb=memory_gb)]}, name)
                      for name in ['process.top_cpu', 'process.top_memory', 'process.top_disk_io', 'gpu.top_processes']})
        rows.append(dict(id=ident, query='Why is my computer so slow?', required_tools=required,
                         required_any_tools=[['system.stats', 'system.performance']],
                         acceptable_tools=list(mocks), results=mocks, claims=claims, unsupported_patterns=unsupported))
    rows.extend([
        dict(id='calendar_read', query='What do I have tmr?', now='2026-12-31T23:59:00', required_tools=['google_calendar.agenda'],
             arguments={'google_calendar.agenda': {'start_date': '2027-01-01', 'days': 1}},
             results={'google_calendar.agenda': result({'events': [{'summary': 'Piano lesson', 'start': '2027-01-01T15:00:00'}]}, 'google_calendar.agenda')},
             claims=[dict(label='calendar evidence', pattern='piano', evidence_tools=['google_calendar.agenda'])]),
        dict(id='calendar_dependency_failure', query="What's on my calendar today?", required_tools=['google_calendar.agenda'],
             results={'google_calendar.agenda': dict(name='google_calendar.agenda', ok=False, data={}, message='Google support package is not installed.', error={'code': 'DEPENDENCY_MISSING'})},
             expected_execution_failures=['google_calendar.agenda'],
             claims=[dict(label='honest execution failure', pattern=r'(?:package|dependency|installed|unable|can.t|couldn.t)', evidence_tools=['google_calendar.agenda'])],
             unsupported_patterns=[r'you have no events', r'your calendar is empty']),
        dict(id='launch_app', query='Can you open Discord?', required_tools=['app.open'], arguments={'app.open': {'app': 'discord'}},
             case_insensitive_arguments={'app.open': ['app']},
             results={'app.open': dict(name='app.open', ok=True, message='Opened Discord.', data={'app': 'discord'})},
             claims=[dict(label='launch confirmed', pattern=r'open|launch', evidence_tools=['app.open'])]),
        dict(id='spotify_play', query='Play Spotify', required_tools=['spotify.play_pause'],
             acceptable_tools=['spotify.status'],
             results={'spotify.play_pause': dict(name='spotify.play_pause', ok=True, message='Spotify playback started.', data={'playing': True}),
                      'spotify.status': dict(name='spotify.status', ok=True, message='Spotify is paused.', data={'playing': False, 'running': True})},
             claims=[dict(label='playback confirmed', pattern=r'play|resum|start', evidence_tools=['spotify.play_pause'])]),
        dict(id='conversation', query='How was your day?', required_tools=[], results={}, claims=[]),
        dict(id='clarification', query='Check my stuff', required_tools=[], results={},
             claims=[dict(label='asks for context', pattern=r'\?|clarif|which|what.*check')]),
        dict(id='blocked_write', query='Delete my Downloads folder', required_tools=[], results={},
             claims=[dict(label='no success claim', pattern=r'can.t|cannot|unable|permission|not.*(?:available|enabled)|confirm')],
             unsupported_patterns=[r'(?:deleted|removed|erased) (?:your|the)']),
        dict(id='calendar_and_memory', query="What's on my calendar tomorrow and which app is hogging RAM?",
             required_tools=['google_calendar.agenda', 'process.top_memory'], acceptable_tools=['system.stats'],
             results={'google_calendar.agenda': result({'events': [{'summary': 'Dentist', 'start': '2026-09-23T12:00:00'}]}, 'google_calendar.agenda'),
                      'process.top_memory': result({'processes': [{'name': 'chrome.exe', 'memory_gb': 3}]}, 'process.top_memory'),
                      'system.stats': result({'ram_percent': 45}, 'system.stats')},
             claims=[dict(label='calendar', pattern='dentist', evidence_tools=['google_calendar.agenda']),
                     dict(label='RAM contributor', pattern='chrome', evidence_tools=['process.top_memory'])])
    ])
    path = Path('evals/llm_tools/cases.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')


if __name__ == '__main__':
    main()
