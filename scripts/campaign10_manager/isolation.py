"""Campaign scope fence before original dispatch; never a product permission pass."""
from pathlib import Path
LOCAL_MODULES = {'file.': {'hanni.tools.files', 'hanni.tools.content', 'hanni.tools.insight'}, 'archive.': {'hanni.tools.content'}, 'note.': {'hanni.tools.notes'}, 'todo.': {'hanni.tools.todos'}, 'workspace.': {'hanni.dashboard.features'}, 'hanni.': {'hanni.tools.diagnostics'}}
READ_ONLY_SYSTEM = {'system.stats', 'system.performance', 'process.top_memory', 'process.list', 'process.inspect', 'system.cpu', 'system.memory', 'system.battery', 'system.disk_usage'}

def validate_dispatch(state, request, root):
    root = Path(root).resolve()
    if Path(state.config.paths.data_dir).resolve() != root:
        raise PermissionError('HARNESS_ISOLATION: registry data directory differs from the owned root.')
    name, arguments = (request.name, request.arguments)
    if name in {'file.open', 'folder.open'}:
        raise PermissionError('HARNESS_ISOLATION: opening user applications is outside this executor.')
    definition = state.registry.get(name)
    module = getattr(definition.handler, '__module__', '')
    manager = getattr(state, 'mcp_manager', None)
    factory = getattr(manager, 'connection_factory', None)
    inert_mcp = module == 'hanni.mcp.adapter' and manager is not None and (manager in getattr(state, 'managers', [])) and (getattr(factory, '__module__', '') == 'scripts.campaign10_core.harness') and (getattr(factory, '__qualname__', '') == '_mcp.<locals>.PartsBinConnection') and any((cell.cell_contents is manager for cell in definition.handler.__closure__ or ()))
    safe = module == 'hanni.tools.compute' or (name in READ_ONLY_SYSTEM and module == 'hanni.tools.system') or any((name.startswith(prefix) and module in modules for prefix, modules in LOCAL_MODULES.items())) or inert_mcp
    if not safe:
        raise PermissionError('HARNESS_ISOLATION: non-fixture OS/provider surface is outside this executor.')
    if name.startswith(('file.', 'archive.')):
        values = []
        for key in ('root', 'path', 'source', 'destination', 'left', 'right', 'archive'):
            value = arguments.get(key)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError('HARNESS_ISOLATION: explicit nonempty disposable paths are required.')
                values.append(value)
        for key in ('paths', 'sources'):
            value = arguments.get(key)
            if value is not None:
                if not isinstance(value, list) or any((not isinstance(v, str) or not v.strip() for v in value)):
                    raise ValueError('HARNESS_ISOLATION: archive inputs must be explicit disposable paths.')
                values.extend(value)
        if not values:
            raise ValueError('HARNESS_ISOLATION: filesystem execution requires an explicit disposable path.')
        for value in values:
            if not Path(value).expanduser().resolve().is_relative_to(root):
                raise ValueError('HARNESS_ISOLATION: tool path escapes the disposable root.')
        if name in {'file.search', 'file.locate'} and (not arguments.get('root')):
            raise ValueError('HARNESS_ISOLATION: search requires an explicit disposable root.')
