"""Original project provider must not emit a withdrawn package snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from uuid import uuid4
from hanni.dashboard.productivity import ProductivityStore
from hanni.logs.redaction import register_secret
from hanni.memory.store import MemoryStore
from hanni.memory.projects import ProjectContext
from hanni.memory.integration import PersonalContextProvider

def run(output):
    output.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for source in ['src/hanni/memory/projects.py', 'src/hanni/memory/integration.py', 'src/hanni/memory/privacy.py']:
        raw = Path(source).read_bytes()
        hashes[source] = hashlib.sha256(raw).hexdigest()
        path = output / 'source' / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    rows = []
    with tempfile.TemporaryDirectory(dir=output) as folder:
        for change in ['content', 'source', 'confidence', 'delete', 'registered_secret']:
            root = Path(folder) / change
            store = MemoryStore(root / 'memory.sqlite3')
            workspace = ProductivityStore(root / 'workspace')
            project = workspace.mutate('project.create', dict(name='Spectrometer', description='Controlled fixture'), str(uuid4()))['project']
            marker = 'independent-late-private-marker-662'
            content = 'Spectrometer calibration previously used a violet reference label'
            if change == 'registered_secret':
                content += ' ' + marker
            record, _ = store.remember(content, project_id=project['id'])
            projects = ProjectContext(store, workspace)
            original = projects.package
            calls = []

            def changed_after_package(*args, **kwargs):
                result = original(*args, **kwargs)
                calls.append(True)
                if change == 'delete':
                    store.delete(record.id)
                elif change == 'registered_secret':
                    register_secret('campaign3-independent-late-registration', marker)
                else:
                    value = {'content': 'Spectrometer calibration now uses a golden reference label', 'source': 'password is independent-provenance-marker', 'confidence': 'nan'}[change]
                    with store._connect() as db:
                        db.execute('PRAGMA ignore_check_constraints=ON')
                        db.execute('UPDATE memories SET ' + change + '=? WHERE id=?', (value, record.id))
                return result
            projects.package = changed_after_package
            context = PersonalContextProvider(store, project_context=projects).retrieve('Continue Spectrometer project')
            rows.append(dict(change=change, passed=record.content not in context.text, obsolete_text_omitted=record.content not in context.text, context=context.text, returned_ids=[match.record.id for match in context.matches], original_package_calls=len(calls), dependency_seam='Mutation after actual original package before actual original provider return'))
    receipt = dict(mode='Actual original provider with controlled late store/privacy change', source_sha256=hashes, results=rows, total=len(rows), passed=sum((row['passed'] for row in rows)))
    (output / 'results.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    return dict(total=len(rows), passed=receipt['passed'])
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output)))
