import importlib.util
from pathlib import Path
import zipfile
import pytest
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('exporter', ROOT / 'scripts/export_source.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_real_export_includes_every_source_package(tmp_path):
    output = tmp_path / 'source.zip'
    module.export(ROOT, output)
    with zipfile.ZipFile(output) as z:
        names = set(z.namelist())
        for path in (ROOT / 'src/hanni').rglob('*.py'):
            assert 'hanni/' + path.relative_to(ROOT).as_posix() in names
        assert 'hanni/src/hanni/models/client.py' in names
        assert 'hanni/src/hanni/tools/google_access.py' in names
        assert 'hanni/START_BRAIN.cmd' in names
        assert 'hanni/SETUP_TEAMS.cmd' in names
        assert 'hanni/START_TEAMS.cmd' in names
        assert 'hanni/start_brain.sh' in names
        assert 'hanni/soul/SOUL.md' in names
        assert 'hanni/soul/skills/recurring-tasks/SKILL.md' in names
        assert 'hanni/soul/skills/pdf-reading/SKILL.md' in names
        assert 'hanni/tests/fixtures/documents/legacy.xls.b64.txt' in names
        assert 'hanni/evals/routing/cases.jsonl' in names
        for name in ('evals/routing/language_generalization_v2.jsonl', 'evals/routing/language_generalization_v3.jsonl', 'evals/routing/multiturn_v1.jsonl', 'evals/routing/voice_routing_v1.jsonl', 'evals/llm_tools/cases.jsonl', 'evals/llm_tools/capability_coverage_v1.jsonl', 'evals/personality/personality_v1.jsonl', 'evals/personality/personality_v2.jsonl'):
            assert 'hanni/' + name in names
        assert 'hanni/evals/llm_tools/cases.jsonl' in names
        assert 'hanni/evals/routing/capability-coverage.json' in names
        assert 'hanni/evals/real_world/curated.jsonl' not in names
        assert not any(('/results/' in name or '/checkpoints/' in name for name in names))
        for name in ['START_HANNI.cmd', 'START_HANNI_OS.cmd', 'LICENSE', 'CONTRIBUTING.md', 'SECURITY.md', 'src/hanni/dashboard/static/index.html', 'src/hanni/dashboard/static/app.js', 'src/hanni/dashboard/static/style.css', 'frontend/src/workspace.tsx', 'frontend/src/screens.tsx', 'frontend/src/screens.css', 'frontend/package.json', 'frontend/package-lock.json', 'desktop/main.py', 'desktop/requirements.txt', 'desktop/HANNI OS.spec', 'desktop/app.manifest', 'desktop/hanni.ico', 'docs/HANNI_DESKTOP.md', 'scripts/start_desktop.ps1', 'scripts/build_desktop.ps1']:
            assert 'hanni/' + name in names
    with pytest.raises(FileExistsError):
        module.export(ROOT, output)

def test_export_excludes_credentials_and_runtime_files(tmp_path):
    files = ['src/hanni/models/client.py', 'config/credentials.json', 'config/client_secret_app.json', 'config/google-oauth-client.json', 'config/token.json', 'data/private.json', 'models/settings.json', 'src/hanni/models/weights.gguf', 'src/hanni/__pycache__/cache.pyc', 'docs/guide.md', 'evals/real_world/curated.jsonl', 'evals/real_world/inbox/notes.jsonl', 'evals/real_world/private.local.jsonl', 'evals/routing/voice_routing_v1.jsonl', 'evals/routing/multiturn_v1.jsonl', 'evals/llm_tools/results/private.json', 'evals/checkpoints/private.json', 'config/account.json', 'config/google_credentials.json', 'desktop/.env', 'desktop/request-token.json', 'desktop/model.gguf', 'build/desktop-venv/private.json', 'dist/HANNI OS/private.json']
    for name in files:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('fixture')
    actual = {p.relative_to(tmp_path).as_posix() for p in module.source_files(tmp_path)}
    assert actual == {'src/hanni/models/client.py', 'docs/guide.md', 'evals/routing/voice_routing_v1.jsonl', 'evals/routing/multiturn_v1.jsonl'}
