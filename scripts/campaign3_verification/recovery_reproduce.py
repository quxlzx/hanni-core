"""Independent malformed-row recovery and budget-preserving fallback proofs."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
from hanni.config.loader import load_config
from hanni.core.shutdown import EmergencyStop, Actor, StopSource
from hanni.laya.runtime import stop_advisory
from hanni.memory.integration import configured_retriever
from hanni.memory.retrieval import ContextAwareRetriever
from hanni.memory.session import MemoryAwareSession
from hanni.memory.store import MemoryStore
from scripts.campaign3_verification.boundary_reproduce import Capture, speak

class Unavailable:

    def __init__(self, budget):
        self.max_tokens = budget
        self.max_chars = 4000

    def retrieve(self, query):
        raise RuntimeError('Controlled unavailable optional context')

def run(output):
    output.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for file in ['src/hanni/memory/session.py', 'src/hanni/memory/integration.py']:
        raw = Path(file).read_bytes()
        hashes[file] = hashlib.sha256(raw).hexdigest()
        target = output / 'source' / file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    rows = []
    with tempfile.TemporaryDirectory(dir=output) as work:
        root = Path(work)
        for field in ['created_at', 'updated_at', 'confidence']:
            for query in ['Show my memories', 'Show my memories about spectrometer', 'What calibration label does the spectrometer use?']:
                private = root / (field + '-' + str(len(rows)))
                store = MemoryStore(private / 'memory.sqlite3')
                record, _ = store.remember('Spectrometer calibration label is silver')
                with store._connect() as db:
                    db.execute('PRAGMA ignore_check_constraints=ON')
                    db.execute('UPDATE memories SET ' + field + '=? WHERE id=?', ('independent-invalid-value', record.id))
                fallback = Capture()
                reply = None
                error = None
                before = store.fingerprint()
                try:
                    reply = speak(MemoryAwareSession(fallback, store, extraction_enabled=False), query)
                except Exception as exc:
                    error = type(exc).__name__
                rows.append(dict(kind='malformed', field=field, query=query, error=error, reply=reply, passed=error is None and reply is not None and ("isn't available safely" in reply) and ('independent-invalid-value' not in reply) and (not fallback.calls), original_stored_state_unchanged=before == store.fingerprint()))
                try:
                    store.cleanup()
                except RuntimeError as exc:
                    rows[-1]['owned_corrupt_fixture_cleanup_error'] = type(exc).__name__
        for budget in [128, 256, 512]:
            for route in ['factory', 'outage', 'safe_mode']:
                private = root / (str(budget) + '-' + route)
                config = load_config(Path('config'), data_dir=private, env={})
                config = replace(config, hanni=replace(config.hanni, memory=replace(config.hanni.memory, context_enabled=False, max_context_tokens=budget)))
                store = MemoryStore(private / 'memory.sqlite3')
                store.remember('Spectrometer calibration label uses a silver etching and a measured reference')
                fallback = Capture()
                stop = None
                if route == 'factory':
                    retriever = configured_retriever(config, store)
                elif route == 'outage':
                    retriever = Unavailable(budget)
                else:
                    retriever = ContextAwareRetriever(store, max_tokens=budget)
                    stop = EmergencyStop()
                    stop.trip(source=StopSource.OWNER_TEXT, requested_by=Actor.owner('independent-fixture'), reason='Controlled safe mode')
                session = MemoryAwareSession(fallback, store, extraction_enabled=False, context_retriever=retriever, emergency_stop=stop)
                error = None
                try:
                    speak(session, 'What calibration label does the spectrometer use?')
                except Exception as exc:
                    error = type(exc).__name__
                context = fallback.calls[-1][1].get('memory_context', '') if fallback.calls else ''
                rows.append(dict(kind='budget', route=route, budget=budget, context_utf8_bytes=len(context.encode('utf8')), context=context, error=error, passed=error is None and len(context.encode('utf8')) <= budget, actual_model_calls=0, controlled_optional_dependency=route == 'outage'))
                store.cleanup()
                stop_advisory(config)
    receipt = dict(scope='Original session/factory and original fallback; synthetic corrupted rows and controlled dependency only', source_sha256=hashes, results=rows, total=len(rows), passed=sum((row['passed'] for row in rows)))
    (output / 'results.json').write_text(json.dumps(receipt, indent=2), encoding='utf8')
    return dict(total=len(rows), passed=receipt['passed'])
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output)))
