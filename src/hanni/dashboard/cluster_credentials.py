"""Owner-configured sudo credentials in Windows Credential Manager only."""
from __future__ import annotations

import argparse
import getpass
import hashlib
from pathlib import Path
import sys

from dotenv import load_dotenv

from hanni.config.loader import resolve_data_dir
from hanni.config.secrets import Secret
from hanni.dashboard.cluster import load_nodes
from hanni.logs.redaction import register_secret


SERVICE = 'HANNI.Cluster.Sudo.v1'


def _backend():
    if sys.platform != 'win32':
        raise RuntimeError('Cluster sudo credentials require Windows Credential Manager.')
    from keyring.backends.Windows import WinVaultKeyring
    return WinVaultKeyring()


def _key(node, data_dir):
    if data_dir is None or node not in load_nodes(data_dir) or node.maintenance or not node.username or not (node.tailscale_ip or node.lan_ip):
        raise ValueError('A configured data directory and active roster node are required.')
    scope = hashlib.sha256(str(Path(data_dir).resolve()).casefold().encode('utf-8')).hexdigest()
    return f'{scope}:{node.id}:{node.username}@{node.tailscale_ip or node.lan_ip}'


def _validate(value):
    if (not isinstance(value, str) or not value or len(value) > 1024
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError('The sudo password must be a nonempty single line.')
    return value


def get_sudo_password(node, data_dir):
    try:
        key = _key(node, data_dir)
        value = _backend().get_password(SERVICE, key)
        if value is None:
            return None
        _validate(value)
        register_secret(f'cluster.sudo.{node.id}', value)
        return Secret(value)
    except Exception:
        # Vault/backend failures fail closed. Their messages may contain secrets.
        return None


def set_sudo_password(node, data_dir, value):
    value, key = _validate(value), _key(node, data_dir)
    register_secret(f'cluster.sudo.{node.id}', value)
    try:
        _backend().set_password(SERVICE, key, value)
    except Exception:
        raise RuntimeError('Could not save the sudo credential in Windows Credential Manager.') from None


def main():
    parser = argparse.ArgumentParser(description='Save cluster sudo credentials securely.')
    nodes = parser.add_mutually_exclusive_group(required=True)
    nodes.add_argument('--all', action='store_true', help='Configure every active roster node.')
    nodes.add_argument('--node', help='A configured active node ID.')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--password-stdin', action='store_true', help='Read one line from a private stdin pipe.')
    args = parser.parse_args()
    load_dotenv(override=False)
    data_dir = resolve_data_dir(args.data_dir)
    try:
        selected = [node for node in load_nodes(data_dir) if not node.maintenance and
                    node.username and (node.tailscale_ip or node.lan_ip) and (args.all or node.id == args.node)]
        if not selected:
            parser.error('No matching configured active cluster node.')
    except (OSError, ValueError):
        parser.error('Protected cluster configuration is unavailable or invalid.')
    value = (sys.stdin.readline().rstrip('\r\n') if args.password_stdin
             else getpass.getpass('Cluster sudo password: '))
    try:
        for node in selected:
            set_sudo_password(node, data_dir, value)
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    print(f'Saved sudo credentials for {len(selected)} active node(s) in Windows Credential Manager.')


if __name__ == '__main__':
    main()
