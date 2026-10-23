"""Reference-only relevance/interrupt checks, explicitly not acoustic decoding."""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from hanni.config.schema import SpeechConfig
from hanni.speech.barge_in import BargeInClassifier
from hanni.speech.relevance import SpeechRelevanceClassifier

def run(corpus, output):
    corpus, output = (Path(corpus), Path(output))
    refs = json.loads((corpus / 'references.json').read_text(encoding='utf8'))
    settings = SpeechConfig()
    rows = []
    for ref in refs['samples']:
        classifier = SpeechRelevanceClassifier(wake_names=settings.relevance.wake_names, engagement_seconds=settings.relevance.engagement_seconds, disengage_phrases=settings.relevance.disengage_phrases, filler_words=settings.relevance.filler_words, acknowledgement_words=settings.relevance.acknowledgement_words)
        if ref['state_before'] == 'engaged':
            classifier.classify('Hanni')
        started = time.perf_counter()
        if ref['state_before'] == 'playing':
            observed = BargeInClassifier(interrupt_phrases=settings.barge_in.interrupt_phrases, filler_words=settings.relevance.filler_words, echo_min_words=settings.barge_in.echo_min_words, echo_overlap_ratio=settings.barge_in.echo_overlap_ratio).classify(ref['transcript'], spoken_text=ref['spoken_text'])
            checks = {'interrupt': observed.interrupt == ref['barge_expected'], 'route': observed.route_after_interrupt == ref['barge_routes_after_interrupt']}
        else:
            observed = classifier.classify(ref['transcript'])
            checks = {'wake': observed.wake_word_detected == ref['wake_expected'], 'relevant': observed.relevant == ref['relevance_expected'], 'disengaged': observed.disengaged == ref['disengaged_expected']}
        rows.append({'id': ref['id'], 'category': ref['category'], 'checks': checks, 'passed': all(checks.values()), 'decision': asdict(observed), 'latency_ms': (time.perf_counter() - started) * 1000})
    report = {'schema_version': 1, 'scope': 'Original deterministic classifiers consume prospectively authored reference text. No WAV decoding, STT/VAD inference, microphone or playback; no acoustic accuracy claim.', 'reference_sha256': hashlib.sha256((corpus / 'references.json').read_bytes()).hexdigest(), 'effective_classifier_config': {'relevance': asdict(settings.relevance), 'barge_in': asdict(settings.barge_in)}, 'count': len(rows), 'passed': sum((r['passed'] for r in rows)), 'category_counts': dict(Counter((r['category'] for r in rows))), 'cases': rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError('Preserve existing reference-classifier receipts.')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({'output': output.as_posix(), 'count': report['count'], 'passed': report['passed'], 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'scope': report['scope']}))
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.corpus, args.output)
