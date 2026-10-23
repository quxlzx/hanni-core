"""Real original-primary routed responses with measured telemetry, isolated state."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from hanni.config.loader import load_config
from hanni.models.adaptive import AdaptiveModelEngine,ModelRequest
from hanni.workflows.verification import parse_evidence_json


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();assert output.is_relative_to((ROOT/'data/v42-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    evidence=(ROOT/'data/v42-verification/local-baseline-20261009-a/results.json').read_bytes()
    measured=json.loads(evidence)
    context=next(row for row in measured['rows'] if row['category']=='long_context' and row['target_context']==16384)
    assert context['passed'] and context['usage']['prompt_tokens']>=.9*16384
    config=load_config(ROOT/'config',data_dir=output/'state',env={});engine=AdaptiveModelEngine(config)
    rows=[]
    try:
        engine.refresh();identity=engine.endpoint_identity('local:supervisor')
        engine.record_capability_evidence('local:supervisor',identity=identity,capabilities=['text','structured_json'],
            context_tokens=16384,observed_prompt_tokens=context['usage']['prompt_tokens'],retrieval_passed=True,
            metadata={'structured_output_formats':['json_object']},evidence_sha256=hashlib.sha256(evidence).hexdigest(),
            environment='actual same configured primary allocation; independent 8K16K threeposition probes plus exact JSON cases')
        for i in range(3):
            # Synthetic privacy canary proves DTO does not echo prompt contents.
            messages=[{'role':'user','content':'Synthetic private-memory canary v42-cobalt. Return only {"serial":8427,"available":false}.'}]
            telemetry={}
            value=engine.execute(messages,request=ModelRequest(task_category='analysis',
                privacy_categories=frozenset({'conversation','sensitive'}),output_tokens=192),
                endpoint_id='local:supervisor',max_fallbacks=0,telemetry=telemetry,
                validator=lambda text:parse_evidence_json(text)=={'serial':8427,'available':False},
                temperature=0,top_p=1,response_format={'type':'json_object'})
            snapshot=engine.snapshot()
            current=next(row for row in snapshot['endpoints'] if row['endpoint_id']=='local:supervisor')
            assert 'v42-cobalt' not in json.dumps(snapshot)
            performance=current['performance']
            assert performance['sample_count']==i+1 and performance['ttft_ms'] is not None
            assert performance['generation_tps'] is not None and performance['prompt_tps'] is not None
            assert current['profiles']['analysis']['correctness_sample_count']==0, 'Unscored live measurements cannot create quality proof.'
            assert current['profiles']['analysis']['confidence']=='insufficient'
            rows.append({'iteration':i,'passed':True,'response':value,'telemetry':telemetry,
                'performance':performance,'unscored_runtime_does_not_upgrade_quality':True})
        report={'real_primary':True,'private_context_local_only':True,'remote_dispatches':0,
                'local_allocated_context':16384,'controller_attached':engine.controller_attached,
                'primary_identity':identity,'rows':rows}
        (output/'results.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({'responses':len(rows),'all_passed':True,'latest_performance':rows[-1]['performance']}))
    finally:engine.close()


if __name__=='__main__':main()
