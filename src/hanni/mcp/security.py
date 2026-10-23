"""Owner-approved MCP settings and fail-closed network/credential boundaries."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import ipaddress
import json
import math
import logging
import os
from pathlib import Path
import re
import socket
from urllib.parse import urlsplit, urlunsplit

from hanni.config.secrets import Secret
from hanni.logs.redaction import register_secret

MAX_SERVERS = 32
MAX_TOOLS = 256
MAX_DEFINITION = 65536
MAX_DISCOVERY = 2 * 1024 * 1024
MAX_RESULT = 1024 * 1024
CLASSIFICATIONS = frozenset({'read_only', 'write', 'destructive', 'unknown'})
_ENV_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,127}$')
_SECRET_ARGUMENT = re.compile(r'(?i)(?:^|[-_])(?:password|passwd|token|api[-_]?key|secret|authorization)(?:=|$)')


class SDKDiagnosticsFilter(logging.Filter):
    """SDK exception packets can include private values, even short credentials."""
    def filter(self, record):
        record.msg = 'External MCP SDK diagnostic; inspect the redacted MCP Hub connection state.'
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        return True


_SDK_DIAGNOSTICS = SDKDiagnosticsFilter()


def protect_sdk_diagnostics():
    import sys
    for name, module in list(sys.modules.items()):
        if name == 'mcp' or name.startswith('mcp.'):
            logger = getattr(module, 'logger', None)
            if isinstance(logger, logging.Logger) and _SDK_DIAGNOSTICS not in logger.filters:
                logger.addFilter(_SDK_DIAGNOSTICS)


class MCPConfigurationError(ValueError):
    pass


class MCPAuthenticationRequired(RuntimeError):
    pass


def json_copy(value, *, limit=MAX_DEFINITION, depth=24):
    """Bound data before validation; reject non-JSON, nonfinite, and recursive input."""
    def visit(item, level):
        if level > depth:
            raise MCPConfigurationError('JSON nesting is too deep.')
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise MCPConfigurationError('JSON object keys must be strings.')
            for child in item.values(): visit(child, level + 1)
        elif isinstance(item, list):
            for child in item: visit(child, level + 1)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise MCPConfigurationError('Only JSON values are supported.')
        elif isinstance(item, float) and not math.isfinite(item):
            raise MCPConfigurationError('JSON numbers must be finite.')
    visit(value, 0)
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    except (ValueError, TypeError, RecursionError):
        raise MCPConfigurationError('Invalid JSON data.') from None
    if len(raw.encode('utf-8')) > limit:
        raise MCPConfigurationError('JSON data exceeds the supported size.')
    return json.loads(raw)


def definition_hash(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _text(value, label, *, maximum=8192, optional=False):
    if optional and value in (None, ''): return None
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise MCPConfigurationError(f'{label} must be a nonempty single line (at most {maximum} characters).')
    return value


def endpoint(url, *, allow_local_http=False, resolve=False, resolver=socket.getaddrinfo):
    """Only HTTPS public addresses, or explicitly approved literal loopback MCP ports."""
    url = _text(url, 'Endpoint URL')
    try:
        parsed = urlsplit(url)
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == 'https' else 80)
    except ValueError:
        raise MCPConfigurationError('Endpoint URL or port is invalid.') from None
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.fragment or parsed.query or '\\' in url or port < 1):
        raise MCPConfigurationError('Use an HTTP(S) endpoint without credentials, query, or fragment.')
    host = parsed.hostname
    try: literal = ipaddress.ip_address(host)
    except ValueError: literal = None
    local = bool(allow_local_http and literal and str(literal) in {'127.0.0.1', '::1'} and port >= 1024)
    if parsed.scheme != 'https' and not local:
        raise MCPConfigurationError('Remote endpoints require HTTPS; local HTTP requires explicit loopback approval.')
    if literal and not literal.is_global and not local:
        raise MCPConfigurationError('Private, reserved, and metadata endpoints are not permitted.')
    normalized = urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', '', ''))
    addresses = []
    if resolve:
        try:
            addresses = sorted({item[4][0] for item in resolver(host, port, type=socket.SOCK_STREAM)})
        except OSError:
            raise MCPConfigurationError('Endpoint DNS resolution failed.') from None
        if not addresses:
            raise MCPConfigurationError('Endpoint DNS returned no addresses.')
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global and not (local and str(ip) == str(literal)):
                raise MCPConfigurationError('Endpoint DNS resolves to a prohibited address.')
    return {'url': normalized, 'host': host, 'port': port, 'addresses': addresses}


def normalize_config(config):
    config = json_copy(config, limit=32768)
    if not isinstance(config, dict): raise MCPConfigurationError('Server configuration must be an object.')
    allowed = {'name', 'transport', 'command', 'args', 'cwd', 'env_refs', 'url', 'auth',
               'allow_local_http', 'auto_connect', 'timeout_seconds'}
    if set(config) - allowed: raise MCPConfigurationError('Unsupported server configuration fields.')
    name = _text(config.get('name'), 'Server name', maximum=100)
    transport = config.get('transport')
    if transport not in {'stdio', 'streamable_http'}:
        raise MCPConfigurationError('Supported transports are stdio and streamable_http.')
    refs = config.get('env_refs', {})
    if not isinstance(refs, dict) or len(refs) > 32 or any(
        not _ENV_NAME.fullmatch(key) or not isinstance(value, str) or not _ENV_NAME.fullmatch(value)
        for key, value in refs.items()
    ): raise MCPConfigurationError('Environment settings must map variable names to environment references.')
    auth = config.get('auth') or {'type': 'none', 'reference': None}
    if not isinstance(auth, dict) or set(auth) - {'type', 'reference'}:
        raise MCPConfigurationError('Authentication accepts a type and secret reference only.')
    if auth.get('type') not in {'none', 'bearer_env', 'bearer_secret'}:
        raise MCPConfigurationError('Unsupported authentication type.')
    reference = _text(auth.get('reference'), 'Authentication reference', maximum=128, optional=auth['type'] == 'none')
    if auth['type'] == 'bearer_env' and not _ENV_NAME.fullmatch(reference):
        raise MCPConfigurationError('Bearer environment authentication requires a variable name.')
    auth = {'type': auth['type'], 'reference': reference if auth['type'] != 'none' else None}
    for key in ('allow_local_http', 'auto_connect'):
        if type(config.get(key, False)) is not bool: raise MCPConfigurationError(f'{key} must be a boolean.')
    timeout = config.get('timeout_seconds', 20)
    if type(timeout) not in {int, float} or not math.isfinite(timeout) or not 2 <= timeout <= 120:
        raise MCPConfigurationError('Timeout must be between 2 and 120 seconds.')
    args = config.get('args', [])
    if not isinstance(args, list) or len(args) > 64 or any(
        not isinstance(arg, str) or len(arg) > 8192 or '\x00' in arg or '\r' in arg or '\n' in arg
        for arg in args
    ): raise MCPConfigurationError('Arguments must be a list of at most 64 single-line strings.')
    if any(_SECRET_ARGUMENT.search(arg) for arg in args):
        raise MCPConfigurationError('Pass credentials through environment or secure references, not command arguments.')
    command = _text(config.get('command'), 'Executable', optional=transport != 'stdio')
    cwd = _text(config.get('cwd'), 'Working directory', optional=True)
    url = None
    if transport == 'stdio':
        if config.get('url') or auth['type'] != 'none':
            raise MCPConfigurationError('Stdio authentication must use explicit environment references.')
        runner = Path(command).name.casefold().removesuffix('.exe').removesuffix('.cmd')
        if runner == 'npx' and '--no-install' not in args:
            raise MCPConfigurationError('Use preinstalled packages with npx --no-install; package downloads are not started by MCP Hub.')
        if runner == 'uvx' and '--offline' not in args:
            raise MCPConfigurationError('Use a preinstalled server or uvx --offline.')
    else:
        if command or args or cwd or refs:
            raise MCPConfigurationError('HTTP servers do not accept local command or environment settings.')
        url = endpoint(config.get('url'), allow_local_http=config.get('allow_local_http', False))['url']
    return {'name': name, 'transport': transport, 'command': command, 'args': args,
            'cwd': cwd, 'env_refs': refs, 'url': url, 'auth': auth,
            'allow_local_http': config.get('allow_local_http', False),
            'auto_connect': config.get('auto_connect', False), 'timeout_seconds': timeout}


def resolve_credentials(config, *, env=None, vault=None):
    env = os.environ if env is None else env
    child = {}
    for key, reference in config['env_refs'].items():
        value = env.get(reference)
        if not isinstance(value, str) or not value or '\x00' in value:
            raise MCPAuthenticationRequired('A referenced environment variable is unavailable.')
        register_secret(f'mcp.env.{reference}', value)
        child[key] = value
    auth, headers = config['auth'], {}
    if auth['type'] != 'none':
        if auth['type'] == 'bearer_env': value = env.get(auth['reference'])
        else:
            try:
                if vault is None:
                    if os.name != 'nt': raise RuntimeError()
                    from keyring.backends.Windows import WinVaultKeyring
                    vault = WinVaultKeyring()
                value = vault.get_password('HANNI.MCP.v1', auth['reference'])
            except Exception:
                raise MCPAuthenticationRequired('Secure authentication credential is unavailable.') from None
        if not isinstance(value, str) or not value or len(value) > 8192 or any(ord(c) < 32 for c in value):
            raise MCPAuthenticationRequired('Authentication credential is missing or invalid.')
        register_secret('mcp.auth.' + auth['reference'], value)
        headers['Authorization'] = 'Bearer ' + Secret(value).reveal()
    return child, headers


def validate_schema(schema):
    from jsonschema.validators import validator_for
    schema = json_copy(schema)
    if not isinstance(schema, dict) or schema.get('type') != 'object':
        raise MCPConfigurationError('Tool input schemas must explicitly describe a JSON object.')
    inspected = 0
    def inspect(node, refs=()):
        nonlocal inspected
        inspected += 1
        if inspected > 10000: raise MCPConfigurationError('Schema reference expansion exceeds the supported size.')
        if isinstance(node, dict):
            # Remote references and arbitrary regex evaluation are not delegated to untrusted definitions.
            if any(key in node for key in ('$dynamicRef', '$recursiveRef', 'pattern', 'patternProperties')):
                raise MCPConfigurationError('This schema uses unsupported dynamic references or regex validation.')
            if '$ref' in node and (not isinstance(node['$ref'], str) or not node['$ref'].startswith('#/')):
                raise MCPConfigurationError('Only local JSON Schema references are supported.')
            if '$ref' in node:
                reference = node['$ref']
                if reference in refs: raise MCPConfigurationError('Recursive schema references are not supported.')
                target = schema
                try:
                    for key in reference[2:].split('/'):
                        key = key.replace('~1', '/').replace('~0', '~')
                        target = target[int(key)] if isinstance(target, list) else target[key]
                except (KeyError, ValueError, IndexError, TypeError):
                    raise MCPConfigurationError('Schema contains an unresolved local reference.') from None
                inspect(target, refs + (reference,))
            for child in node.values(): inspect(child, refs)
        elif isinstance(node, list):
            for child in node: inspect(child, refs)
    inspect(schema)
    try:
        validator = validator_for(schema, default=None) if '$schema' in schema else validator_for(schema)
        if validator is None: raise MCPConfigurationError('Unsupported JSON Schema dialect.')
        validator.check_schema(schema)
    except Exception:
        raise MCPConfigurationError('Invalid JSON Schema definition.') from None
    return schema
