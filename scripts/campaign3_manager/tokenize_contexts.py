"""Native tokenizer counts of synthetic retrieval outputs, not model answers."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tempfile
import urllib.request
from urllib.parse import urlsplit
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from hanni.config.loader import load_config

def run(receipts, output):
    receipts, output = (receipts.resolve(), output.resolve())
    rows = []
    with tempfile.TemporaryDirectory(prefix='hanni-c3-tokenizer-config-') as folder:
        cfg = load_config(ROOT / 'config', data_dir=Path(folder), env={})
        base = cfg.models.supervisor.endpoint.rstrip('/').removesuffix('/v1')
        if urlsplit(base).hostname not in {'127.0.0.1', 'localhost'}:
            raise ValueError('Only the existing loopback tokenizer is eligible')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for path in sorted(receipts.glob('*/*.json')):
            receipt = json.loads(path.read_text(encoding='utf8'))
            for index, context in enumerate(receipt.get('contexts', [])):
                text = context.get('context_text', '')
                row = {'case_id': receipt['id'], 'arm': receipt['retriever_kind'], 'category': receipt['category'], 'context_index': index, 'raw_receipt': str(path.relative_to(ROOT)), 'raw_receipt_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'context_sha256': hashlib.sha256(text.encode('utf8')).hexdigest(), 'context_chars': len(text), 'utf8_byte_upper_bound': len(text.encode('utf8'))}
                request = urllib.request.Request(base + '/tokenize', data=json.dumps({'content': text, 'add_special': False, 'parse_special': True}).encode('utf8'), method='POST', headers={'Content-Type': 'application/json'})
                try:
                    with opener.open(request, timeout=3) as response:
                        result = json.load(response)
                    tokens = result['tokens']
                    if not isinstance(tokens, list) or any((type(token) is not int for token in tokens)):
                        raise ValueError('Invalid native tokenizer output')
                    row.update(status='measured', context_tokens=len(tokens), native_response=result)
                except Exception as exc:
                    row.update(status='unavailable', context_tokens=None, error={'type': type(exc).__name__, 'message': str(exc)})
                rows.append(row)
    output.mkdir(parents=True, exist_ok=True)
    raw = output / 'TOKEN_RECEIPTS.json'
    raw.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    summary = {'captured_at': datetime.now(timezone.utc).isoformat(), 'scope': 'Actual installed tokenizer applied to synthetic retrieval outputs, including explicit warm queries. Not injected model context, model usage or generated answers.', 'actual_model_inference_requests': 0, 'tokenizer_requests': len(rows), 'raw_receipts': str(raw.relative_to(ROOT)), 'raw_receipts_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(), 'arms': {}}
    for arm in sorted({row['arm'] for row in rows}):
        group = [row for row in rows if row['arm'] == arm]
        measured = [row['context_tokens'] for row in group if row['status'] == 'measured']
        summary['arms'][arm] = {'contexts': len(group), 'measured': len(measured), 'unavailable': len(group) - len(measured), 'empty_contexts': sum((value == 0 for value in measured)), 'mean_context_tokens': statistics.mean(measured) if measured else None, 'median_context_tokens': statistics.median(measured) if measured else None, 'max_context_tokens': max(measured) if measured else None}
    (output / 'SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf8')
    print(json.dumps(summary), flush=True)
    return summary
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.receipts, args.output)
