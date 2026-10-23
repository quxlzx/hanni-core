"""Owned SSH forwards: key-only auth, verified host keys, bounded reconnection."""
import os
import re
import socket
import subprocess
import threading


class ManagedTunnel:
    def __init__(self, config, *, popen=subprocess.Popen):
        if set(config) - {'destination', 'identity_file', 'forwards', 'ssh_executable'}:
            raise ValueError('Unknown tunnel configuration field.')
        if not re.fullmatch(r'[a-zA-Z0-9_-]+@(?:[a-zA-Z0-9.-]+)', config['destination']):
            raise ValueError('Invalid SSH destination.')
        forwards = config['forwards']
        if not isinstance(forwards, list) or not 1 <= len(forwards) <= 8:
            raise ValueError('At most eight loopback forwards are supported.')
        ports = []
        for pair in forwards:
            if not isinstance(pair, list) or len(pair) != 2 or any(type(p) is not int or not 1024 <= p <= 65535 for p in pair):
                raise ValueError('Invalid local/remote port mapping.')
            ports.append(pair[0])
        if len(set(ports)) != len(ports):
            raise ValueError('Duplicate local port.')
        self.config, self.popen = config, popen
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.process = None
        self.state, self.error = 'stopped', None
        self.thread = None

    def command(self):
        config = self.config
        command = [config.get('ssh_executable', 'ssh'), '-N', '-T', '-o', 'BatchMode=yes',
                   '-o', 'StrictHostKeyChecking=yes', '-o', 'ExitOnForwardFailure=yes',
                   '-o', 'ConnectTimeout=5', '-o', 'ConnectionAttempts=1',
                   '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=2',
                   '-o', 'PasswordAuthentication=no', '-o', 'KbdInteractiveAuthentication=no']
        if config.get('identity_file'):
            command += ['-i', config['identity_file'], '-o', 'IdentitiesOnly=yes']
        for local, remote in config['forwards']:
            command += ['-L', f'127.0.0.1:{local}:127.0.0.1:{remote}']
        return command + [config['destination']]

    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self.run, name='hanni-hermes-ssh', daemon=True)
            self.thread.start()

    def run(self):
        attempts = 0
        while not self.stop.is_set() and attempts < 8:
            for local, _ in self.config['forwards']:
                try:
                    with socket.socket() as probe:
                        if os.name == 'nt':
                            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                        probe.bind(('127.0.0.1', local))
                except OSError:
                    self.state, self.error = 'blocked', 'A mapped loopback port is occupied; it was not adopted or replaced.'
                    return
            try:
                with self.lock:
                    if self.stop.is_set():
                        return
                    self.process = self.popen(self.command(), stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    self.state, self.error = 'connecting', None
                while not self.stop.wait(.25) and self.process.poll() is None:
                    self.state = 'ssh_process_running'  # Actual authenticated health is checked separately.
            except OSError:
                pass
            attempts += 1
            self.state, self.error = 'unavailable', 'SSH unavailable; verify authorized keys and known_hosts. No password prompts.'
            if self.stop.wait(min(30, 2**attempts)):
                return
        if not self.stop.is_set():
            self.state = 'retry_limit_reached'

    def snapshot(self):
        return {'state': self.state, 'error': self.error, 'loopback_only': True}

    def close(self):
        self.stop.set()
        with self.lock:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
        if self.thread:
            self.thread.join(timeout=4)


def main():
    """Optional standalone forwards using the same owner as dashboard startup."""
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    tunnel = ManagedTunnel(json.loads(args.config.read_text())['tunnel'])
    try:
        tunnel.start()
        print('Starting SSH forwards for this script. Ctrl+C stops only its own SSH process.', flush=True)
        last = None
        while not tunnel.stop.wait(.5):
            state = tunnel.snapshot()
            if state != last:
                print(state, flush=True)
                last = state
            if state['state'] in {'blocked', 'retry_limit_reached'}:
                return 1
    except KeyboardInterrupt:
        return 0
    finally:
        tunnel.close()


if __name__ == '__main__':
    raise SystemExit(main())
