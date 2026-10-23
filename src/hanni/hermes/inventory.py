"""Read-only installed Hermes inventory; source inspection never grants execution."""
import ast
import json
from pathlib import Path
import threading
import time


def _literal(node, constants):
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def inspect_sources(root):
    """Parse installed source, without importing tool handlers or executing commands."""
    root = Path(root)
    result = {'toolsets': [], 'tools': [], 'commands': [], 'limitations': []}
    constants = {}
    tree = ast.parse((root/'toolsets.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    value = _literal(node.value, constants)
                    if value is not None:
                        constants[target.id] = value
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TOOLSETS' for t in node.targets):
            if not isinstance(node.value, ast.Dict):
                continue
            for key, value in zip(node.value.keys, node.value.values):
                name = _literal(key, constants)
                if not isinstance(name, str) or not isinstance(value, ast.Call):
                    continue
                description = _literal(value.args[0], constants) if value.args else None
                tools = _literal(value.args[1], constants) if len(value.args) > 1 else []
                includes = _literal(value.args[2], constants) if len(value.args) > 2 else []
                if isinstance(value.func, ast.Name) and value.func.id == '_bundle':
                    tools = constants.get('_HERMES_CORE_TOOLS', []) + (tools or [])
                for kw in value.keywords:
                    if kw.arg == 'tools': tools = _literal(kw.value, constants)
                    if kw.arg == 'includes': includes = _literal(kw.value, constants)
                result['toolsets'].append({'name': name, 'description': description or '',
                    'tools': tools if isinstance(tools, list) else [],
                    'includes': includes if isinstance(includes, (list, tuple)) else [],
                    'membership_complete': tools is not None and includes is not None})
    tree = ast.parse((root/'hermes_cli/commands.py').read_text(encoding='utf-8'))
    fields = ('name', 'description', 'category')
    for node in tree.body:
        value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if not any(isinstance(t, ast.Name) and t.id == 'COMMAND_REGISTRY' for t in targets) or not isinstance(value, (ast.List, ast.Tuple)):
            continue
        for call in value.elts:
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != 'CommandDef':
                continue
            item = {k: _literal(v, {}) for k, v in zip(fields, call.args)}
            for kw in call.keywords:
                if kw.arg in {'name','description','category','aliases','args_hint','subcommands','cli_only','gateway_only','desktop','gateway_config_gate'}:
                    item[kw.arg] = _literal(kw.value, {})
            if isinstance(item.get('name'), str):
                result['commands'].append(item)
    paths = sorted((root/'tools').glob('*.py')) + sorted((root/'tools').glob('*/tool.py'))
    for path in paths[:256]:
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (OSError, SyntaxError):
            result['limitations'].append('Could not inspect '+path.name)
            continue
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = _literal(node.value, values)
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute) or call.func.attr != 'register' or not isinstance(call.func.value, ast.Name) or call.func.value.id != 'registry':
                continue
            args = {kw.arg: _literal(kw.value, values) for kw in call.keywords}
            if not isinstance(args.get('name'), str):
                result['limitations'].append('Dynamic registration requires runtime inspection: '+str(path.relative_to(root)))
                continue
            schema = args.get('schema') or {}
            function = schema.get('function', schema) if isinstance(schema, dict) else {}
            params = function.get('parameters', {})
            result['tools'].append({'name': args['name'], 'toolset': args.get('toolset'),
                'description': str(function.get('description', ''))[:2000],
                'parameters': [{'name': name, 'type': prop.get('type'),
                    'description': str(prop.get('description',''))[:500],
                    'required': name in params.get('required', [])}
                    for name,prop in list(params.get('properties',{}).items())[:64] if isinstance(prop, dict)],
                'source': str(path.relative_to(root)), 'availability': 'not_checked',
                'availability_check': next((ast.unparse(kw.value)[:120] for kw in call.keywords if kw.arg=='check_fn'), None)})
    result['tools'] = result['tools'][:512]
    result['limitations'] = sorted(set(result['limitations']))[:64]
    return result


def collect(home):
    """Allowlisted configuration only: never output environment, headers or stdio args."""
    import sqlite3
    import subprocess
    import yaml
    from urllib.parse import urlsplit
    home = Path(home)
    result = inspect_sources(home/'.hermes/hermes-agent')
    config = yaml.safe_load((home/'.hermes/config.yaml').read_text(encoding='utf-8')) or {}
    result['platform_toolsets'] = config.get('platform_toolsets', {})
    result['resources'] = {
        'terminal_backend': config.get('terminal', {}).get('backend'),
        'terminal_working_directory': config.get('terminal', {}).get('cwd'),
        'browser_backend': config.get('browser', {}).get('backend'),
        'skills_directory': str(home/'.hermes/skills'),
        'bridge_shared_directory': str(home/'hanni-capabilities/data'),
        'model': config.get('model') if isinstance(config.get('model'), str) else
                 {k:config.get('model', {}).get(k) for k in ('default','provider')},
    }
    result['skills'] = []
    for path in sorted((home/'.hermes/skills').glob('**/SKILL.md'))[:256]:
        if path.is_symlink() or not path.resolve().is_relative_to((home/'.hermes/skills').resolve()):
            continue
        # Metadata only; skill instructions never enter the assistant context.
        text = path.read_text(encoding='utf-8')[:8192]
        meta = {}
        if text.startswith('---\n'):
            try:
                meta = yaml.safe_load(text.split('---',2)[1]) or {}
            except yaml.YAMLError:
                pass
        if not isinstance(meta, dict):
            meta = {}
        result['skills'].append({'name':str(meta.get('name',path.parent.name))[:200],
            'description':str(meta.get('description',''))[:1200],
            'source':str(path.relative_to(home/'.hermes'))})
    result['mcp_servers'] = []
    for name, item in list(config.get('mcp_servers', {}).items())[:32]:
        endpoint = None
        if isinstance(item.get('url'), str):
            url = urlsplit(item['url'])
            endpoint = f'{url.scheme}://{url.hostname}' + (f':{url.port}' if url.port else '') + url.path
        result['mcp_servers'].append({'name': name, 'enabled': item.get('enabled', True),
            'transport': 'http' if endpoint else 'stdio', 'endpoint': endpoint,
            'include': item.get('tools', {}).get('include'), 'exclude': item.get('tools', {}).get('exclude')})
    result['observations'] = {}
    path = home/'hanni-hermes-bridge/state/catalog.sqlite3'
    if path.exists():
        db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)
        try:
            result['observations'] = {name:json.loads(payload) for name,payload in db.execute('SELECT name,payload FROM catalog_observations')}
        finally:
            db.close()
    result['services'] = {}
    for unit in ('hermes-gateway.service', 'hanni-hermes-bridge.service'):
        run = subprocess.run(['systemctl','--user','is-active',unit], capture_output=True, text=True, timeout=3)
        result['services'][unit] = run.stdout.strip()[:64]
    result['checked_at'] = time.time()
    result['source'] = 'Installed Hermes source and configuration on Karina; cached MCP observations'
    result['limitations'].append('Installed tools and configured toolsets are not proof of live availability. Native slash commands execute in Hermes, not through this tab. Dynamic/plugin registrations may require runtime inspection.')
    return result


class InventoryCache:
    """Dashboard reads trigger one bounded background SSH read per minute."""
    def __init__(self, data_dir):
        self.root = Path(data_dir)
        self.lock = threading.Lock()
        self.running = False
        self.checked = 0
        self.value = None
        self.error = None
        self.closed = False

    def snapshot(self):
        with self.lock:
            if not self.closed and not self.running and time.monotonic()-self.checked >= 60:
                self.running = True
                threading.Thread(target=self.refresh, name='hanni-hermes-inventory', daemon=True).start()
            return {'loading': self.running, 'error': self.error, 'data': self.value,
                    'stale': self.error is not None or bool(self.value and time.time()-self.value['checked_at']>120),
                    'refresh_seconds': 60}

    def refresh(self):
        try:
            from hanni.dashboard.cluster import load_nodes, _ssh_prefix, _run, _tailscale_executable
            node = next(n for n in load_nodes(self.root) if n.id == 'karina')
            config = json.loads((self.root/'hermes'/'config.json').read_text(encoding='utf-8'))
            if not isinstance(config, dict) or not isinstance(config.get('tunnel'), dict):
                raise RuntimeError('Existing Hermes access reference needs review.')
            destination = config['tunnel'].get('destination')
            if (node.maintenance or not node.username or not node.tailscale_ip
                    or config.get('enabled') is not True
                    or destination != f'{node.username}@{node.tailscale_ip}'):
                raise RuntimeError('Existing Karina access reference needs review.')
            program = Path(__file__).read_text(encoding='utf-8') + '\nprint(json.dumps(collect(Path.home())))\n'
            run = _run(_ssh_prefix(node,node.tailscale_ip,tailscale=_tailscale_executable())+
                ["python3 -c 'import sys; exec(sys.stdin.read())'"], input=program, timeout=18)
            if run.returncode or len(run.stdout) > 1_000_000:
                raise RuntimeError('Read-only Hermes inventory unavailable.')
            value = json.loads(run.stdout)
            with self.lock:
                if not self.closed:
                    self.value, self.error = value, None
        except (RuntimeError, OSError, ValueError, StopIteration):
            with self.lock:
                self.error = 'Hermes inventory unavailable; check the existing SSH access. Previous observations, if shown, are stale.'
        finally:
            with self.lock:
                self.running, self.checked = False, time.monotonic()

    def close(self):
        with self.lock:
            self.closed = True
