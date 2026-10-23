"""Verify Model Lab release source, metadata and imports without model loading."""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    wheel, output = args.wheel.resolve(), args.output.resolve()
    assert wheel.is_relative_to((ROOT/'data/v43-manager').resolve())
    assert output.is_relative_to((ROOT/'data/v43-manager').resolve())
    assert not output.exists()
    checks, members = [], {}
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.endswith('/'):
                continue
            assert not name.startswith(('data/', 'config/', '.env', '.git/'))
            assert not name.endswith(('.sqlite3', '.gguf', '.key', '.pyc'))
            if name.startswith('hanni/'):
                source = ROOT/'src'/name
                content = archive.read(name)
                assert source.is_file() and source.read_bytes() == content, name
                members[name] = hashlib.sha256(content).hexdigest()
        checks.append('Every packaged HANNI source and static file matches the workspace')
        checks.append('Private deployment data, configuration, weights and keys are excluded')
        metadata_name = next(name for name in archive.namelist() if name.endswith('.dist-info/METADATA'))
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        assert metadata['Version'] == '0.13.0'
        description = metadata.get_payload(decode=True).decode('utf8').replace('\r\n', '\n').strip()
        assert description == (ROOT/'README.md').read_text(encoding='utf8').replace('\r\n', '\n').strip()
        checks.append('Release metadata contains the current UTF-8 README and version')
        stylesheet = archive.read('hanni/dashboard/static/style.css')
        assert b'Geist Sans' in stylesheet and b'base64' in stylesheet
        assert b'Geist' in archive.read('hanni/dashboard/static/THIRD_PARTY_NOTICES.txt')
        checks.append('Local Geist font and third-party license remain packaged')
        assert b'.model-lab' in stylesheet
        application = archive.read('hanni/dashboard/static/app.js')
        assert b'Model Intelligence Lab' in application and b'/api/model-lab' in application
        checks.append('Built Model Lab interface and styles are included in desktop assets')
        for name in ('hanni/evals/model_lab.py', 'hanni/dashboard/model_lab.py',
                     'hanni/models/adaptive.py', 'hanni/dashboard/server.py'):
            assert name in members
    modules = ['hanni.evals.model_lab', 'hanni.dashboard.model_lab',
               'hanni.dashboard.server', 'hanni.evals.llm_tools',
               'hanni.evals.routing', 'hanni.models.adaptive',
               'hanni.models.collaboration', 'hanni.models.manager',
               'hanni.compute.scheduler', 'hanni.memory.retrieval',
               'hanni.workflows.service', 'hanni.cli']
    code = ('import importlib,sys;sys.path.insert(0,sys.argv[1]);'
            'mods=[importlib.import_module(n) for n in sys.argv[2:]];'
            'assert all(m.__file__.startswith(sys.argv[1]) for m in mods);'
            'import hanni;assert hanni.__version__=="0.13.0";'
            'print("12 archive imports passed")')
    result = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-c', code,
                             str(wheel), *modules], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    checks.append('Twelve runtime modules import directly from the wheel, version 0.13.0')
    report = {'wheel': str(wheel.relative_to(ROOT)), 'bytes': wheel.stat().st_size,
              'sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
              'packaged_file_count': len(members), 'checks': checks,
              'source_sha256': members}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k != 'source_sha256'}, indent=2))


if __name__ == '__main__':
    main()
