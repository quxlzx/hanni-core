"""Imported malformed confidence rejection and finite boundary controls."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from hanni.memory.store import MemoryStore
from hanni.memory.retrieval import LocalMemoryRetriever, ContextAwareRetriever

def run(output):
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    hashes = {}
    for source in ['src/hanni/memory/store.py', 'src/hanni/memory/privacy.py', 'src/hanni/memory/retrieval.py']:
        raw = Path(source).read_bytes()
        hashes[source] = hashlib.sha256(raw).hexdigest()
        path = output / 'source' / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    with tempfile.TemporaryDirectory(dir=output) as temp:
        for value, expected in [('nan', False), ('inf', False), (-1.0, False), (2.0, False), (0.0, True), (0.5, True), (1.0, True)]:
            store = MemoryStore(Path(temp) / (str(len(rows)) + '.sqlite3'))
            record, _ = store.remember('Spectrometer fixture calibration source is stable')
            with store._connect() as db:
                db.execute('PRAGMA ignore_check_constraints=ON')
                db.execute('UPDATE memories SET confidence=? WHERE id=?', (value, record.id))
            for kind, cls in [('legacy', LocalMemoryRetriever), ('context', ContextAwareRetriever)]:
                error = None
                context = None
                try:
                    context = cls(store).retrieve('spectrometer fixture calibration source')
                except Exception as exc:
                    error = type(exc).__name__
                accepted = bool(context.matches) if context else False
                serialized = context.text if context else ''
                rows.append(dict(value=value, arm=kind, accepted=accepted, error=error, raw_context=serialized, serialized_nonfinite=any((x in serialized for x in ['NaN', 'Infinity'])), passed=error is None and accepted == expected and (not any((x in serialized for x in ['NaN', 'Infinity'])))))
    receipt = dict(scope='Original retrievers with controlled imported-row confidence; no ordinary write validation bypass.', source_sha256=hashes, results=rows, total=len(rows), passed=sum((row['passed'] for row in rows)))
    (output / 'results.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    return dict(total=len(rows), passed=receipt['passed'])
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output)))
