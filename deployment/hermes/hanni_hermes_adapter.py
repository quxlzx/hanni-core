"""Loaded by the installed Hermes bootstrap, never a second messaging gateway."""
from pathlib import Path
import runpy
import sys

root = Path.home()/'hanni-hermes-bridge'/'lib'
sys.path.insert(0, str(root))
if len(sys.argv) < 2 or sys.argv[1] not in {'service', 'worker', 'check'}:
    raise SystemExit('Choose service, worker, or check.')
mode = sys.argv.pop(1)
if mode == 'check':
    import inspect
    from run_agent import AIAgent
    import mcp, hermes_yaml, jsonschema
    from hanni.hermes.worker import mcp_request
    from hanni.hermes.service import Bridge
    required = {'skip_memory', 'skip_background_review', 'enabled_toolsets', 'run_budget_seconds'}
    if not required <= set(inspect.signature(AIAgent.__init__).parameters):
        raise SystemExit('Installed Hermes interface is incompatible; deployment blocked.')
    if not callable(getattr(AIAgent, 'run_conversation', None)):
        raise SystemExit('Installed Hermes lacks the required conversation lifecycle.')
    print('HANNI Hermes adapter import/interface check passed; no inference or execution performed.')
    if '--catalog-probe' in sys.argv:
        import json
        from hanni.hermes.catalog import Catalog
        from hanni.hermes.worker import discover
        specs = discover(Catalog(Path.home()/'hanni-hermes-bridge/state/catalog.sqlite3').snapshot())
        print(json.dumps([{'server':s['remote']['server'],'tool':s['remote']['name'],'hash':s['hash']} for s in specs]))
else:
    runpy.run_module('hanni.hermes.'+mode, run_name='__main__', alter_sys=True)
