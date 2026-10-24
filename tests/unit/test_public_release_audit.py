import importlib.util
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from audit_public_release import findings, audit_history

def test_public_github_ssh_identity_is_not_a_personal_mailbox():
    assert not findings(b'git clone git@github.com:owner/repo.git', 'auth.md')
    assert findings(b'person' + b'@github.com', 'auth.md')[0]['category'] == 'personal_email'

def test_secret_scan_finds_keys_without_disclosing_values():
    key = 'ghp_' + 'A' * 36
    result = findings(key.encode(), 'test.txt')
    assert result[0]['category'] == 'credential'
    assert key not in str(result)
    assert not findings(('task-' + 'A' * 36).encode(), 'test.txt')
    from check_distribution import check_member
    assert 'API credential' in check_member('sample.txt', key.encode())
    assert not check_member('sample.txt', ('task-' + 'A' * 36).encode())

def test_local_and_documentation_ips_are_allowed_but_real_networks_blocked():
    assert not findings(b'127.0.0.1 0.0.0.0 ::1 192.0.2.10 2001:db8::1', 'sample')
    private_address = '.'.join(('10', '42', '0', '20')).encode()
    overlay_address = '.'.join(('100', '92', '1', '20')).encode()
    assert findings(private_address, 'sample')[0]['category'] == 'nonpublic_endpoint'
    assert findings(overlay_address, 'sample')[0]['category'] == 'nonpublic_endpoint'

def test_deleted_secret_is_still_found_in_history(tmp_path):
    import subprocess

    def git(*args):
        subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)
    git('init')
    git('config', 'user.name', 'Example')
    git('config', 'user.email', 'user@example.com')
    (tmp_path / 'sample.txt').write_text('ghp_' + 'B' * 36)
    git('add', '.')
    git('commit', '-m', 'fixture')
    (tmp_path / 'sample.txt').write_text('removed')
    git('add', '.')
    git('commit', '-m', 'cleanup')
    assert any((f['category'] == 'credential' for f in audit_history(tmp_path)['findings']))

def test_public_fixtures_retain_network_and_sender_validation_semantics(tmp_path):
    import ipaddress
    from prepare_public_release import prepare
    private = tmp_path / 'private'
    (private / 'tests').mkdir(parents=True)
    fixture = private / 'tests' / 'fixture.py'
    tailnet = '.'.join(('100', '64', '0', '10'))
    public = '.'.join(('8', '8', '8', '8'))
    mailbox = 'jane' + '@gmail.com'
    fixture.write_text(f'tailnet={tailnet!r}\npublic={public!r}\nsender={mailbox!r}\nurl="https://user:password@example.invalid/mcp"\n')
    output = tmp_path / 'public'
    result = prepare(private, output)
    scope = {}
    exec((output / 'tests' / 'fixture.py').read_text(), scope)
    assert scope['tailnet'] == tailnet
    assert not ipaddress.ip_address(scope['public']).is_private
    assert scope['sender'].endswith('@gmail.com') and scope['sender'] != mailbox
    assert scope['url'] == 'https://user:password@example.invalid/mcp'
    assert not result['audit']['findings']

def test_dummy_credentials_do_not_exempt_real_private_information():
    assert not findings(b'https://user:password@example.invalid/mcp', 'fixture.py')
    value = '://'.join(('https', 'user:example-00744662f1@example.com/mcp'))
    assert any((item['category'] == 'authenticated_url' for item in findings(value.encode(), 'fixture.py')))
    assert findings(('info' + '@private-owner-domain.net').encode(), 'sample.txt')
