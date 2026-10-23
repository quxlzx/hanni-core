import importlib.util
from pathlib import Path
import zipfile
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('distribution_checker', ROOT / 'scripts/check_distribution.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

def test_checker_rejects_credentials_and_runtime_files_without_echoing_values(tmp_path):
    archive = tmp_path / 'hanni-test.whl'
    with zipfile.ZipFile(archive, 'w') as handle:
        handle.writestr('hanni/tools/safe.py', 'print("safe")')
        handle.writestr('hanni/config/google-oauth-client.json', '{"client_secret":"private-value"}')
        handle.writestr('hanni/data/chat.jsonl', 'private conversation')
    findings = checker.check_archive(archive)
    assert any(('google-oauth-client.json' in name for name, _ in findings))
    assert any(('chat.jsonl' in name for name, _ in findings))
    assert 'private-value' not in str(findings)

def test_checker_accepts_package_models_code_and_synthetic_example(tmp_path):
    archive = tmp_path / 'hanni-test.whl'
    with zipfile.ZipFile(archive, 'w') as handle:
        handle.writestr('hanni/models/runtime.py', 'MODEL = "Qwen3.5-4B"')
        handle.writestr('hanni.egg-info/PKG-INFO', 'Name: hanni')
    assert checker.check_archive(archive) == []

def test_checker_flags_personal_email_without_revealing_it():
    email = b'owner' + b'@gmail.com'
    findings = checker.check_member('hanni/notes.txt', b'Account: ' + email)
    assert findings == ['personal email']
    assert email.decode() not in str(findings)
