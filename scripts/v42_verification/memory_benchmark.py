"""Exact-content recall benchmark over a sealed 2000-record synthetic database."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from hanni.memory.store import MemoryStore
from hanni.memory.retrieval import ContextAwareRetriever


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();assert output.is_relative_to((ROOT/'data/v42-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    protocol={'objective':'Reduce repeated context assembly P50 at least50% retaining exact provenance and immediate correction/deletion',
        'records':2000,'content_template':'Synthetic project atlas benchmark batch {i} uses route amber.',
        'ids':'m0...m1999','source':'audit','source_ref':'synthetic-audit','project_id':'audit',
        'memory_type':'project','status':'statement','confidence':.8,
        'timestamps':'2026-10-09T00:00:00+00:00','query':'atlas benchmark route','repetitions':25,
        'purpose':'Explicit synthetic data, never owner private memory; Python retrieval time not GPU speed.'}
    encoded=json.dumps(protocol,sort_keys=True).encode();digest=hashlib.sha256(encoded).hexdigest()
    (output/'protocol.json').write_bytes(encoded);(output/'protocol.sha256').write_text(digest)
    store=MemoryStore(output/'memory.sqlite3')
    with store._connect() as db:
        for i in range(protocol['records']):
            text=protocol['content_template'].format(i=i)
            db.execute('INSERT INTO memories(id,content,normalized_content,memory_type,source,confidence,created_at,updated_at,project_id,semantic_status,source_ref) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (f'm{i}',text,text.casefold(),protocol['memory_type'],protocol['source'],protocol['confidence'],
                 protocol['timestamps'],protocol['timestamps'],protocol['project_id'],protocol['status'],protocol['source_ref']))
    retriever=ContextAwareRetriever(store,project_id=protocol['project_id'])
    times=[];hashes=[];text=None
    for i in range(protocol['repetitions']):
        began=time.perf_counter();context=retriever.retrieve(protocol['query']);times.append((time.perf_counter()-began)*1000)
        hashes.append(hashlib.sha256(context.text.encode()).hexdigest());text=context.text
        assert context.matches and all(row.record.project_id=='audit' for row in context.matches)
    assert len(set(hashes))==1
    values=sorted(times)
    result={'protocol_sha256':digest,'latency_ms_samples':times,'context_sha256':hashes[0],
            'context_text':text,'passed':True,'summary':{'count':len(values),'p50':statistics.median(values),'p95':values[__import__('math').ceil(.95*len(values))-1]}}
    (output/'results.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({k:result[k] for k in ('protocol_sha256','context_sha256','summary','passed')}))


if __name__=='__main__':main()
