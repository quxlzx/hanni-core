"""Imported project record provenance is validated as a whole unit."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from uuid import uuid4
from hanni.dashboard.productivity import ProductivityStore
from hanni.memory.store import MemoryStore
from hanni.memory.projects import ProjectContext
from hanni.memory.integration import PersonalContextProvider

def run(output):
    output.mkdir(parents=True, exist_ok=False)
    source = Path('src/hanni/memory/projects.py').read_bytes()
    (output / 'projects.py').write_bytes(source)
    rows = []
    with tempfile.TemporaryDirectory(dir=output) as folder:
        for field in ['source', 'source_ref', 'fact_key', 'fact_value']:
            root = Path(folder) / field
            store = MemoryStore(root / 'memory.sqlite3')
            workspace = ProductivityStore(root / 'workspace')
            project = workspace.mutate('project.create', dict(name='Spectrometer', description='Controlled fixture'), str(uuid4()))['project']
            record, _ = store.remember('Spectrometer calibration uses a blue reference label', project_id=project['id'])
            with store._connect() as db:
                db.execute('UPDATE memories SET ' + field + '=? WHERE id=?', ('password is independent-project-import-marker', record.id))
            projects = ProjectContext(store, workspace)
            package = projects.package(project['id'])
            context = PersonalContextProvider(store, project_context=projects).retrieve('Continue the Spectrometer project')
            rows.append(dict(field=field, package_ids=[row['id'] for row in package['memories']], provider_ids=[match.record.id for match in context.matches], context=context.text, passed=not package['memories'] and (not context.matches) and (record.content not in context.text), source_not_emitted='independent-project-import-marker' not in context.text, source_row_unchanged=getattr(store.get(record.id), field) == 'password is independent-project-import-marker'))
            store.cleanup()
    receipt = dict(mode='Original project package and native PersonalContextProvider, controlled imported metadata only', source_sha256=hashlib.sha256(source).hexdigest(), results=rows, total=len(rows), passed=sum((row['passed'] for row in rows)))
    (output / 'results.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    return dict(total=len(rows), passed=receipt['passed'])
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output)))
