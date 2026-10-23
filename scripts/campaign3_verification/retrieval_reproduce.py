"""Independent development controls with optional archived original modules."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from hanni.memory import store as current_store, retrieval as current_retrieval
from hanni.laya import intelligence as current_intelligence

def archived_module(relative, name, revision, output):
    raw = subprocess.run(['git', 'show', f'{revision}:{relative}'], check=True, capture_output=True).stdout
    destination = output / 'source' / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    spec = importlib.util.spec_from_file_location(name, destination)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return (module, hashlib.sha256(raw).hexdigest())

def run(output, revision=None):
    output.mkdir(parents=True, exist_ok=False)
    modules = {}
    hashes = {}
    for name, relative, current in [('store', 'src/hanni/memory/store.py', current_store), ('retrieval', 'src/hanni/memory/retrieval.py', current_retrieval), ('intelligence', 'src/hanni/laya/intelligence.py', current_intelligence)]:
        if revision:
            modules[name], hashes[relative] = archived_module(relative, 'campaign3_independent_old_' + name, revision, output)
        else:
            raw = Path(relative).read_bytes()
            destination = output / 'source' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            modules[name] = current
            hashes[relative] = hashlib.sha256(raw).hexdigest()
    results = []

    def record(name, okay, **evidence):
        results.append(dict(id=name, passed=bool(okay), evidence=evidence))
    Store = modules['store'].MemoryStore
    with tempfile.TemporaryDirectory(dir=output) as root:
        root = Path(root)
        for kind, klass in [('legacy', modules['retrieval'].LocalMemoryRetriever), ('context', modules['retrieval'].ContextAwareRetriever)]:
            for field in ['source', 'source_ref', 'fact_key', 'fact_value']:
                store = Store(root / (kind + '-' + field + '.sqlite3'))
                row, _ = store.remember('Spectrometer fixture preference uses clear calibration labels')
                retriever = klass(store)
                warm = retriever.retrieve('spectrometer fixture preference calibration')
                marker = 'password is independent-imported-marker-331'
                with store._connect() as db:
                    db.execute('UPDATE memories SET ' + field + '=? WHERE id=?', (marker, row.id))
                context = retriever.retrieve('spectrometer fixture preference calibration')
                record(kind + '-metadata-' + field, not context.matches and marker not in context.text, warm_ids=[m.record.id for m in warm.matches], final_ids=[m.record.id for m in context.matches], serialized=context.text, same_updated_at=True)
                store.cleanup()
            store = Store(root / (kind + '-excluded.sqlite3'))
            row, _ = store.remember('Spectrometer calibration label is stable')
            context = klass(store).retrieve('spectrometer calibration label', exclude_ids=[row.id])
            record(kind + '-excluded-stable-id', not context.matches, context=context.text)
            store.cleanup()
            for status in ['temporary', 'question', 'hypothetical', 'inference']:
                store = Store(root / (kind + '-' + status + '.sqlite3'))
                store.remember('Spectrometer calibration label could be expanded', semantic_status=status)
                context = klass(store).retrieve('spectrometer calibration label')
                record(kind + '-epistemic-' + status, not context.matches, context=context.text)
                store.cleanup()
        store = Store(root / 'scoped-key.sqlite3')
        first, _ = store.remember('My preferred code editor is Geany', project_id='fixture-project-a')
        second, _ = store.remember('My preferred code editor is Kate', project_id='fixture-project-b')
        original = store.get(first.id)
        record('scope-keyed-preferences', first.id != second.id and original.project_id == 'fixture-project-a' and ('Geany' in original.content), first=first.to_dict(), second=second.to_dict(), readback=original.to_dict())
        store.cleanup()
        store = Store(root / 'identical-cross-scope.sqlite3')
        first, _ = store.remember('Spectrometer shared note retains original calibration', project_id='fixture-project-a')
        error = None
        try:
            store.remember(first.content, project_id='fixture-project-b')
        except Exception as exc:
            error = type(exc).__name__
        readback = store.get(first.id)
        record('identical-text-no-implicit-project-reassignment', error == 'MemoryConflictError' and readback.project_id == 'fixture-project-a', error=error, readback=readback.to_dict())
        store.cleanup()
        store = Store(root / 'scoped-correction.sqlite3')
        first, _ = store.remember('My preferred code editor is Geany', project_id='fixture-project-a')
        second, _ = store.remember('Different unkeyed spectrometer note', project_id='fixture-project-b')
        with store._connect() as db:
            db.execute('UPDATE memories SET fact_key=?,fact_value=? WHERE id=?', (first.fact_key, 'Kate', second.id))
        error = None
        try:
            changed = store.correct(first.id, 'My preferred code editor is Lapce', expected_updated_at=first.updated_at.isoformat())
        except Exception as exc:
            error = type(exc).__name__
        record('correction-no-cross-project-key-conflict', error is None, error=error, readback=store.get(first.id).to_dict())
        store.cleanup()
        store = Store(root / 'fingerprint.sqlite3')
        first, _ = store.remember('Spectrometer calibration output is TSV')
        fingerprint = store.fingerprint()
        with store._connect() as db:
            db.execute('UPDATE memories SET content=?,source_ref=? WHERE id=?', ('Spectrometer calibration output is TOML', 'controlled:changed', first.id))
        record('same-revision-all-column-fingerprint', fingerprint != store.fingerprint(), before=fingerprint, after=store.fingerprint())
        store.cleanup()
    for text, expected in [('The fixture benchmark was not completed', 'failed_claim'), ('The fixture benchmark was cancelled', 'failed_claim'), ('The fixture benchmark completed', 'completed_claim')]:
        actual = modules['intelligence'].classify_semantic_status(text)
        record('epistemic-' + text, actual == expected, actual=actual, expected=expected)
    receipt = dict(mode='independent_exposed_development', revision=revision or 'current', source_sha256=hashes, caveat='Archived modules retain current unchanged absolute-import dependencies; explicit statuses avoid classifier-dependent seeding.', results=results, total=len(results), passed=sum((r['passed'] for r in results)))
    (output / 'results.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    return dict(total=receipt['total'], passed=receipt['passed'])
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--revision')
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.revision)))
