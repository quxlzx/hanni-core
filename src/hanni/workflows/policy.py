"""Trusted workflow admission layered on the original host and registry gates."""
from dataclasses import dataclass
import ctypes
from pathlib import Path
from types import CodeType

from hanni.tools.sensitive_paths import is_sensitive_path
from .types import WorkflowError, fingerprint, resource_identity, within_root


def _semantic_constant(value):
    """Encode constant values without marshal's mutable reference/intern flags."""
    if isinstance(value, CodeType):
        return ['code', _semantic_code(value)]
    if value is None or value is Ellipsis:
        return ['none' if value is None else 'ellipsis']
    if type(value) in {bool, int, str}:
        return [type(value).__name__, value]
    if type(value) is bytes:
        return ['bytes', value.hex()]
    if type(value) is float:
        return ['float', value.hex()]
    if type(value) is complex:
        return ['complex', value.real.hex(), value.imag.hex()]
    if type(value) in {tuple, frozenset}:
        items = [_semantic_constant(item) for item in value]
        if type(value) is frozenset:
            items.sort(key=fingerprint)
        return [type(value).__name__, items]
    raise WorkflowError('Unsupported implementation constant in workflow definition.')


def _semantic_code(code):
    # co_code is the public, unquickened bytecode. Debug locations, marshal
    # reference sharing and Python's runtime adaptive caches are not semantics.
    return {
        'bytecode': code.co_code.hex(),
        'constants': [_semantic_constant(value) for value in code.co_consts],
        'names': list(code.co_names), 'variables': list(code.co_varnames),
        'free_variables': list(code.co_freevars), 'cell_variables': list(code.co_cellvars),
        'name': code.co_name, 'qualified_name': code.co_qualname,
        'arguments': code.co_argcount, 'positional_only': code.co_posonlyargcount,
        'keyword_only': code.co_kwonlyargcount, 'locals': code.co_nlocals,
        'stack_size': code.co_stacksize, 'flags': code.co_flags,
        'exception_table': code.co_exceptiontable.hex(),
    }


def _callable_identity(function):
    if function is None:
        return None
    code = getattr(function, '__code__', None)
    return {
        'module': getattr(function, '__module__', ''),
        'name': getattr(function, '__qualname__', type(function).__qualname__),
        'code': fingerprint(_semantic_code(code)) if code else None,
    }


def definition_fingerprint(definition):
    """Bind schema, original policy and implementation; MCP retains its exact hash."""
    return fingerprint({
        'id': definition.name, 'description': definition.description,
        'input_schema': definition.argument_schema(),
        'output_schema': definition.json_output_schema or dict(definition.output_schema),
        'permission_level': definition.permission_level, 'risk_level': definition.risk_level,
        'side_effect': definition.side_effect, 'background_allowed': definition.background_allowed,
        'schema_version': definition.schema_version, 'retry_safe': definition.retry_safe,
        'external_definition_hash': definition.external_definition_hash,
        'workflow_binding_id': definition.workflow_binding_id,
        'handler': _callable_identity(definition.handler),
        'confirmation': _callable_identity(definition.requires_confirmation_if),
    })


def is_read(definition):
    return (definition.permission_level == definition.risk_level == 0
            and definition.side_effect in {None, 'read'}
            and definition.requires_confirmation_if is None)


def retry_safe(definition):
    return (definition.retry_safe and is_read(definition)
            and not definition.external_definition_hash
            and not definition.name.startswith('mcp.'))


def parallel_read_safe(definition):
    """Only known local reads get parallel slots; read claims remain read claims."""
    from hanni.tools.capabilities import describe
    if (not is_read(definition) or definition.external_definition_hash
            or definition.name.startswith('mcp.')):
        return False
    metadata = describe(definition)
    return metadata.source == 'local' and metadata.family != 'extensions'


def artifact_write(definition, arguments, artifact_root):
    return (definition.name == 'file.write' and artifact_root is not None
            and isinstance(arguments.get('path'), str)
            and within_root(arguments['path'], artifact_root)
            and resource_identity(arguments['path']) != resource_identity(artifact_root)
            and Path(arguments['path']).suffix.casefold() in {'.txt', '.md', '.json', '.csv', '.log'}
            and not is_sensitive_path(arguments['path']))


def _system_directory():
    """Ask Windows for its protected binary directory, not a writable PATH/env."""
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer))
        if not 0 < length < len(buffer):
            raise OSError('Windows system directory unavailable')
        return Path(buffer.value).resolve()
    except (AttributeError, OSError, RuntimeError) as exc:
        raise WorkflowError('A protected Windows application target is unavailable.') from exc


def pin_application(value):
    """Pin an original alias to one existing protected OS image; never shell-resolve."""
    from hanni.tools.windows import APP_ALIASES, _find_start_menu_shortcut
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError('Workflow application launch requires an original safe application alias.')
    alias = value.strip().casefold()
    safe_commands = {command.casefold() for command in APP_ALIASES.values()
                     if command.casefold().endswith('.exe') and command.casefold() != 'wt.exe'}
    supplied = Path(value).expanduser()
    if supplied.is_absolute():
        system = _system_directory()
        target = supplied.resolve()
        if (resource_identity(target.parent) != resource_identity(system)
                or target.name.casefold() not in safe_commands or not target.is_file()):
            raise WorkflowError('Workflow application target is not a protected original OS binary.')
        return str(target)
    if alias not in APP_ALIASES or APP_ALIASES[alias].casefold() not in safe_commands:
        raise WorkflowError('Workflow application launch requires an original safe application alias.')
    # The original interactive resolver prioritizes supplied paths and shortcuts.
    # Refuse these ambiguous inputs rather than inspecting or executing their data.
    if supplied.exists() or Path(APP_ALIASES[alias]).exists():
        raise WorkflowError('A local path shadows the requested application alias.')
    if _find_start_menu_shortcut(value) is not None:
        raise WorkflowError('An uninspected shortcut shadows the requested application alias.')
    target = _system_directory() / APP_ALIASES[alias]
    if not target.is_file():
        raise WorkflowError('This alias has no protected Windows binary available to workflows.')
    target = target.resolve()
    if resource_identity(target.parent) != resource_identity(_system_directory()):
        raise WorkflowError('Workflow application target is unavailable.')
    return str(target)


def validate_policy(definition, arguments, *, mode, artifact_root, protected_roots=()):
    if (definition.name == 'powershell.run' or definition.risk_level >= 3
            or definition.side_effect == 'destructive'
            or definition.name.startswith(('cluster.', 'ssh.', 'terminal.'))):
        raise WorkflowError('This capability is unavailable to autonomous workflows.')
    if definition.name == 'file.open' or definition.name.startswith('ui.') and not is_read(definition):
        raise WorkflowError('Shell-open and scripted user-interface actions are unavailable to workflows.')
    if definition.name == 'app.open':
        pin_application(arguments.get('app'))
    if definition.name == 'file.write':
        if not isinstance(arguments.get('path'), str) or not arguments['path'].strip():
            raise WorkflowError('Workflow file writes require a concrete path.')
        if within_root(arguments['path'], artifact_root) and not artifact_write(definition, arguments, artifact_root):
            raise WorkflowError('Workflow artifacts are bounded report data, not executable scripts or tools.')
    if mode == 'background' and not definition.background_allowed:
        raise WorkflowError('This capability is foreground-only; background admission is unavailable.')
    if not is_read(definition):
        system_roots = ()
        if hasattr(ctypes, 'windll'):
            windows = _system_directory().parent
            system_roots = (windows, windows.parent / 'Program Files', windows.parent / 'Program Files (x86)')
        for key in ('path', 'source', 'destination', 'root'):
            path = arguments.get(key)
            if isinstance(path, str):
                if is_sensitive_path(path):
                    raise WorkflowError('Credential paths are unavailable to workflows.')
                own_artifact = artifact_write(definition, arguments, artifact_root) and key == 'path'
                if not own_artifact and any(within_root(path, root) for root in (*protected_roots, *system_roots)):
                    raise WorkflowError('Workflow mutation of application code or configuration is prohibited.')
    return arguments


def resource_keys(definition, arguments):
    if is_read(definition):
        return ()
    paths = [arguments[key] for key in ('path', 'source', 'destination', 'root')
             if isinstance(arguments.get(key), str)]
    # Unknown external effect identity deliberately conflicts with all writes.
    return tuple(sorted({'path:' + resource_identity(path) for path in paths}))


@dataclass(frozen=True)
class WorkflowAuthority:
    """Constructed by the trusted scheduler, never by a model/tool payload."""
    actor_profile: str
    confirmed: bool
    mode: str
    artifact_root: Path
    approved_capabilities: tuple[str, ...]
    definition_hash: str
    argument_hash: str
    protected_roots: tuple[Path, ...] = ()
    execution_guard: object = None

    def validate(self, definition, arguments):
        if definition.name not in self.approved_capabilities:
            raise WorkflowError('Capability is outside the approved workflow scope.')
        if definition_fingerprint(definition) != self.definition_hash:
            raise WorkflowError('Tool definition changed after workflow approval.')
        if fingerprint(arguments) != self.argument_hash:
            raise WorkflowError('Prepared arguments changed after workflow approval.')
        validate_policy(definition, arguments, mode=self.mode, artifact_root=self.artifact_root,
                        protected_roots=self.protected_roots)

