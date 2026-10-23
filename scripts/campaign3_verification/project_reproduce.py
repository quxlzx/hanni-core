"""Independent exposed project-name and continuation controls."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from uuid import uuid4
from hanni.dashboard.productivity import ProductivityStore
from hanni.memory.projects import ProjectContext
from hanni.memory.store import MemoryStore

def run(output):
    output.mkdir(parents=True, exist_ok=False)
    source = Path('src/hanni/memory/projects.py').read_bytes()
    (output / 'projects.py').write_bytes(source)
    results = []
    with tempfile.TemporaryDirectory(dir=output) as work:
        root = Path(work)
        memory = MemoryStore(root / 'memory.sqlite3')
        workspace = ProductivityStore(root / 'workspace')
        context = ProjectContext(memory, workspace)
        ids = {}
        for name in ['Nimbus', 'Nimbus Desktop', 'Moss', 'Moss Viewer']:
            ids[name] = workspace.mutate('project.create', dict(name=name, description='Synthetic project'), str(uuid4()))['project']['id']
        cases = [('Nimbus Desktop execution notes', 'matched', 'Nimbus Desktop'), ('Review the Moss Viewer project decision', 'matched', 'Moss Viewer'), ('Compare Nimbus and Nimbus Desktop', 'ambiguous', None), ('Please continue it', 'ambiguous', None), ('Resume our work', 'ambiguous', None), ('Resume the playback queue', 'none', None), ('Tell me about rainy weekends', 'none', None)]
        for query, status, name in cases:
            result = context.resolve(query)
            passed = result['status'] == status and (name is None or result['project_id'] == ids[name])
            results.append(dict(query=query, expected_status=status, expected_name=name, passed=passed, result=result))
        memory.cleanup()
    receipt = dict(mode='independent_exposed_development', source_sha256=hashlib.sha256(source).hexdigest(), results=results, passed=sum((row['passed'] for row in results)), total=len(results))
    (output / 'results.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    return dict(total=len(results), passed=receipt['passed'])
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output)))
