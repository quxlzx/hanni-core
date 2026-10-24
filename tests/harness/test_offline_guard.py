"""The default safety boundary is exercised, including real Python children."""
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

import pytest

from hanni_test_guard import TestBoundaryBlocked

REPO = Path(__file__).resolve().parents[2]


def test_external_tcp_is_blocked_before_connecting():
    with socket.socket() as connection, pytest.raises(TestBoundaryBlocked, match='network disabled'):
        connection.connect(('203.0.113.10', 443))


def test_unowned_loopback_service_cannot_be_used_as_a_fixture():
    with socket.socket() as connection, pytest.raises(TestBoundaryBlocked, match='network disabled'):
        connection.connect(('127.0.0.1', 8311))


def test_external_dns_and_udp_are_disabled():
    with pytest.raises(TestBoundaryBlocked, match='DNS'):
        socket.getaddrinfo('network-must-not-run.invalid', 443)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connection:
        with pytest.raises(TestBoundaryBlocked, match='network disabled'):
            connection.sendto(b'fixture', ('203.0.113.10', 123))


@pytest.mark.parametrize('operation', ['open', 'database', 'mkdir'])
def test_production_storage_is_unavailable_even_when_application_defaults_are_wrong(operation):
    target = REPO / 'state' / 'harness-must-not-write.sqlite3'
    with pytest.raises(TestBoundaryBlocked, match='Live HANNI'):
        if operation == 'open':
            target.write_text('must not be created')
        elif operation == 'database':
            sqlite3.connect(target)
        else:
            target.mkdir()
    assert not target.exists()


def test_hardware_and_capture_launchers_are_disabled():
    with pytest.raises(TestBoundaryBlocked, match='subprocess disabled'):
        subprocess.run(['powershell.exe', '-NoProfile', '-Command', 'exit'], check=True)
    import sounddevice
    with pytest.raises(TestBoundaryBlocked, match='microphone'):
        sounddevice.InputStream()
    from PIL import ImageGrab
    with pytest.raises(TestBoundaryBlocked, match='screen capture'):
        ImageGrab.grab()


def test_python_child_inherits_the_offline_guard(tmp_path):
    code = "import socket\ntry:\n socket.create_connection(('203.0.113.10',443))\nexcept PermissionError:\n print('OFFLINE_GUARD_ACTIVE')\n"
    result = subprocess.run([sys.executable, '-c', code], cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0 and result.stdout.strip() == 'OFFLINE_GUARD_ACTIVE', result.stderr
