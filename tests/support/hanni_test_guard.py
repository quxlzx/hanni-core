"""Test-only guard: fixture loopback sockets, temporary state, no live sensors."""
import ipaddress
import json
import os
from pathlib import Path
import socket
import sys
import threading
from functools import lru_cache
from contextlib import contextmanager

_installed = False
_lock = threading.RLock()
_offset = 0
_ports = {}


class TestBoundaryBlocked(PermissionError):
    __test__ = False
    pass


def install():
    global _installed
    if _installed:
        return
    root_value = os.environ.get('PYTEST_HANNI_GUARD_ROOT')
    if not root_value:
        return
    _installed = True
    root = Path(root_value).resolve()
    root.mkdir(parents=True, exist_ok=True)
    registry = root / 'sockets.jsonl'
    repo = Path(os.environ['PYTEST_HANNI_REPO']).resolve()
    protected = [repo / 'state', repo / 'data', Path.home() / '.hanni', Path.home() / 'hanni-hermes-bridge']
    original_bind, original_close = socket.socket.bind, socket.socket.close

    @contextmanager
    def serialized_registry():
        # O_APPEND alone does not make independent Windows CRT handles atomic.
        # Share a kernel lock with guarded child processes as well as threads.
        with _lock:
            descriptor = os.open(root / 'sockets.lock', os.O_RDWR | os.O_CREAT, 0o600)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == 'nt':
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)

    def record(item):
        wire = (json.dumps(item) + '\n').encode()
        if not root.is_dir():
            return  # A late destructor after the test session owns no server.
        with serialized_registry():
            descriptor = os.open(registry, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(descriptor, wire)
            finally:
                os.close(descriptor)

    def bind(sock, address):
        result = original_bind(sock, address)
        actual = sock.getsockname()
        if isinstance(actual, tuple) and len(actual) >= 2:
            record({'op': 'bind', 'pid': os.getpid(), 'fd': sock.fileno(), 'port': actual[1]})
        return result

    def close(sock):
        if sock.fileno() >= 0:
            record({'op': 'close', 'pid': os.getpid(), 'fd': sock.fileno()})
        return original_close(sock)

    def owned(port):
        global _offset
        with serialized_registry():
            if registry.exists():
                with registry.open('rb') as stream:
                    stream.seek(_offset)
                    while line := stream.readline():
                        if not line.endswith(b'\n'):
                            break
                        row = json.loads(line)
                        key = (row['pid'], row['fd'])
                        if row['op'] == 'bind':
                            _ports[key] = row['port']
                        else:
                            _ports.pop(key, None)
                        _offset = stream.tell()
            return port in _ports.values()

    def loopback(host):
        if host in {'localhost', b'localhost'}:
            return True
        try:
            return ipaddress.ip_address(host.decode() if isinstance(host, bytes) else host).is_loopback
        except (ValueError, TypeError):
            return False

    @lru_cache(maxsize=32768)
    def private_path(raw):
        if raw.startswith('file:'):
            if 'mode=memory' in raw or raw.startswith('file::memory:'):
                return False
            from urllib.parse import unquote, urlsplit
            raw = unquote(urlsplit(raw).path)
            if os.name == 'nt' and len(raw) > 2 and raw[0] == '/' and raw[2] == ':':
                raw = raw[1:]
        path = Path(raw).resolve()
        return path == repo / '.env' or any(path == parent or path.is_relative_to(parent) for parent in protected)

    def check_path(value):
        if isinstance(value, (str, bytes, os.PathLike)) and value not in {':memory:', b':memory:'}:
            if private_path(os.fsdecode(value)):
                raise TestBoundaryBlocked('Live HANNI state and credentials are unavailable to tests; use temporary storage.')

    def audit(event, args):
        if event in {'socket.connect', 'socket.sendto'}:
            address = args[1]
            if isinstance(address, tuple) and len(address) >= 2:
                if not loopback(address[0]) or not owned(address[1]):
                    raise TestBoundaryBlocked('Test network disabled: only loopback servers bound by this test session are allowed.')
        elif event in {'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr'}:
            if not loopback(args[0]) and args[0] is not None:
                raise TestBoundaryBlocked('External DNS is disabled in offline tests; fake the service boundary.')
        elif event in {'open', 'sqlite3.connect'}:
            check_path(args[0])
        elif event in {'os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.utime'}:
            check_path(args[0])
        elif event in {'os.rename', 'os.symlink', 'os.link', 'shutil.copyfile'}:
            check_path(args[0])
            check_path(args[1])
        elif event == 'subprocess.Popen':
            executable, argv = args[:2]
            if executable is None:
                import shlex
                executable = (shlex.split(argv, posix=False) if isinstance(argv, str) else argv)[0]
            name = Path(str(executable).strip('"')).name.lower()
            if name in {'powershell', 'powershell.exe', 'pwsh', 'pwsh.exe', 'ssh', 'ssh.exe', 'nvidia-smi', 'nvidia-smi.exe', 'rocm-smi', 'llama-server', 'llama-server.exe'}:
                raise TestBoundaryBlocked('Host service/device subprocess disabled in offline tests; replace the adapter with a controlled fake.')

    socket.socket.bind = bind
    socket.socket.close = close
    sys.addaudithook(audit)
