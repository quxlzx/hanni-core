"""Prospective synthetic V4.1 evaluation; exact oracles sealed before inference.

This file is verifier code. No expected answer is passed to model messages.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYSTEM = 'Analyze the supplied synthetic evidence. Return only the requested JSON object. Do not execute tools or change state. Do not invent facts absent from the evidence.'
SETTINGS = {'temperature': 0, 'max_tokens': 384, 'response_format': {'type': 'json_object'}}


def dataset():
    cases = []
    def case(key, category, task_category, prompt, expected, **extra):
        cases.append(dict(id=key, category=category, task_category=task_category,
                          prompt=prompt, expected=expected, **extra))
    xs = [6, 2, 6, 1, 2, 5, 1, 4]
    code_output = [x for i, x in enumerate(xs) if x not in xs[i+1:]]
    case('coding-last-occurrences', 'coding_analysis', 'coding',
         'Determine the printed output without executing tools: xs=[6,2,6,1,2,5,1,4]; seen=set(); ys=[]\nfor x in reversed(xs):\n if x not in seen:\n  seen.add(x); ys.append(x)\nprint(list(reversed(ys)))\nReturn {"output":[INTEGER_VALUES]}.', {'output': code_output})
    code = 'rows=[("c",3),("a",2),("b",3),("d",1)]; scores={k:v for k,v in rows}; keys=sorted(scores,key=lambda k:(-scores[k],k)); print(keys[2001:db8::23])'
    rows = [('c', 3), ('a', 2), ('b', 3), ('d', 1)]
    scores = dict(rows)
    case('coding-stable-selection', 'coding_analysis', 'coding',
         'Determine the printed list from this Python code without tools: '+code+'\nReturn {"output":[STRING_VALUES]}.',
         {'output': sorted(scores, key=lambda k: (-scores[k], k))[2001:db8::23]})
    a, b = Fraction(81+234, 87+270), Fraction(234+55, 270+80)
    case('benchmark-weighted-rates', 'benchmark_interpretation', 'analysis',
         'Synthetic benchmark: Model A succeeds on 81 of 87 easy tests and 234 of 270 difficult tests. Model B succeeds on 234 of 270 easy tests and 55 of 80 difficult tests. Pool each model\'s actual tests rather than averaging subgroup percentages. Return {"A":{"numerator":INTEGER,"denominator":INTEGER},"B":{"numerator":INTEGER,"denominator":INTEGER},"higher":"A_OR_B"} using reduced fractions.',
         {'A': {'numerator': a.numerator, 'denominator': a.denominator}, 'B': {'numerator': b.numerator, 'denominator': b.denominator}, 'higher': 'A' if a > b else 'B'})
    case('benchmark-unsupported-causation', 'benchmark_interpretation', 'analysis',
         'Synthetic records: Baseline success=7/10, trial success=8/10; baseline median=80ms, trial median=240ms. No randomization, uncertainty estimate, power, or hardware-energy measurement exists. Candidate claims: C1 "Observed success rose by 10 percentage points"; C2 "Trial is statistically proven more accurate"; C3 "Trial median response is three times baseline"; C4 "Trial consumes less GPU energy". Return {"supported":[CLAIM_IDS_SORTED],"unsupported":[CLAIM_IDS_SORTED]}.',
         {'supported': ['C1', 'C3'], 'unsupported': ['C2', 'C4']})
    case('documents-overrides', 'document_comparison', 'analysis',
         'Synthetic policies: P1 dated June1 says retention=30 days, region=east, backups=daily. P2 dated June4 explicitly supersedes only P1 retention and region: retention=14 days, region=west. P3 dated June7 is an unapproved proposal: backups=weekly, region=north. Return the currently approved combined policy and provenance: {"retention_days":INTEGER,"region":STRING,"backups":STRING,"sources":{"retention":"P_ID","region":"P_ID","backups":"P_ID"}}.',
         {'retention_days': 14, 'region': 'west', 'backups': 'daily', 'sources': {'retention': 'P2', 'region': 'P2', 'backups': 'P1'}})
    case('documents-set-diff', 'document_comparison', 'analysis',
         'Synthetic revision A approved scopes=[read,write,export,archive]. Revision B approved scopes=[read,export,compare,publish]. Both lists are complete authoritative sets, not cumulative. Return {"added":[SORTED_STRINGS],"removed":[SORTED_STRINGS],"unchanged":[SORTED_STRINGS]}.',
         {'added': ['compare', 'publish'], 'removed': ['archive', 'write'], 'unchanged': ['export', 'read']})
    case('tool-result-not-success', 'tool_result_reasoning', 'analysis',
         'Synthetic requested outcome: create file /synthetic/report.json with checksum abc9. Tool receipt T1: process exit_code=0, stdout="saved". Independent readback T2: file exists=true, checksum=def7. No further evidence exists. Does the requested outcome verify? Return {"verified":BOOLEAN,"decisive_source":STRING,"reason":"checksum_mismatch_OR_match_OR_missing"}.',
         {'verified': False, 'decisive_source': 'T2', 'reason': 'checksum_mismatch'})
    case('tool-result-units', 'tool_result_reasoning', 'analysis',
         'Synthetic task manager receipt R1: MemTotal=16777216 KiB, MemAvailable=6291456 KiB. GiB means 1024^3 bytes, KiB means 1024 bytes. Compute used memory and percent of total used. Return {"used_GiB":NUMBER,"used_percent":NUMBER,"source":"R1"}.',
         {'used_GiB': 10, 'used_percent': 62.5, 'source': 'R1'})
    edges = {'S': [('A', 9), ('B', 4)], 'B': [('A', 2), ('C', 7)], 'A': [('C', 3), ('T', 10)], 'C': [('T', 2)], 'T': []}
    def paths(node, path, cost):
        if node == 'T':
            yield cost, path
        for dest, weight in edges[node]:
            yield from paths(dest, path+[dest], cost+weight)
    cost, path = min(paths('S', ['S'], 0))
    case('planning-shortest-path', 'planning', 'planning',
         'Synthetic directed edges: S->A cost9, S->B cost4, B->A cost2, B->C cost7, A->C cost3, A->T cost10, C->T cost2. Find the minimum-cost path S to T. Return {"path":[NODE_STRINGS],"cost":INTEGER}.', {'path': path, 'cost': cost})
    deps = {'a': set(), 'b': {'a'}, 'c': {'a'}, 'd': {'b', 'c'}, 'e': {'c'}}
    order = []
    while len(order) < len(deps):
        order.append(min(k for k, v in deps.items() if k not in order and v <= set(order)))
    case('planning-ready-order', 'planning', 'planning',
         'Synthetic tasks: a requires none; b requires a; c requires a; d requires b,c; e requires c. Choose the lexicographically smallest currently executable task each time, execute one task at a time, then update readiness. Return {"order":[TASK_IDS]}.', {'order': order})
    noise = '\n'.join(f'Inert synthetic entry {i:03d}: reference=stone-{(i*43+17)%997:03d}; no policy effect.' for i in range(70))
    case('long-context-corrections', 'long_context_synthesis', 'long_context',
         'Synthetic audit ledger follows. Only approved records affect active state.\nL1 day1 approved target=amber, limit=8.\n'+noise[:len(noise)//2]+'\nL2 day3 approved explicitly supersedes target only: target=teal.\n'+noise[len(noise)//2:]+'\nL3 day5 unapproved proposal target=violet, limit=4.\nL4 day6 approved explicitly supersedes limit only: limit=12.\nReturn {"target":STRING,"limit":INTEGER,"sources":{"target":"L_ID","limit":"L_ID"}}.',
         {'target': 'teal', 'limit': 12, 'sources': {'target': 'L2', 'limit': 'L4'}})
    case('long-context-needle-sum', 'long_context_synthesis', 'long_context',
         'Synthetic ledger follows. Ignore inert records.\nACTIVE_HEAD=19\n'+noise[:len(noise)//2]+'\nACTIVE_MIDDLE=37\n'+noise[len(noise)//2:]+'\nACTIVE_TAIL=23\nReturn {"sum":INTEGER,"values":[HEAD,MIDDLE,TAIL]}.', {'sum': 79, 'values': [19, 37, 23]})
    case('conflict-majority-not-proof', 'conflicting_evidence', 'analysis',
         'Synthetic records: R1 authenticated independent sensor at time10 reports valve=open. R2 equally authenticated independent sensor at time10 reports valve=closed. R3 and R4 quote R1 and provide no new sensor evidence. No source has authority precedence or a later measurement. Determine the actual valve state. Return {"state":"open_OR_closed_OR_unknown","conflict":BOOLEAN,"independent_sources":[SORTED_R_IDS]}.',
         {'state': 'unknown', 'conflict': True, 'independent_sources': ['R1', 'R2']})
    case('conflict-current-authority', 'conflicting_evidence', 'analysis',
         'Synthetic config evidence: E1 is an authenticated authoritative server read at time11, value=west. E2 is an authenticated authoritative server read at time14, value=south and explicitly supersedes E1. E3 is a cached UI snapshot at time16 derived from E1, value=west; E4 repeats E3. Return the current verified config {"value":STRING,"source":"E_ID","superseded_source":"E_ID"}.',
         {'value': 'south', 'source': 'E2', 'superseded_source': 'E1'})
    case('recovery-secondary-unavailable', 'failed_model_recovery', 'analysis',
         'Synthetic inventory has 12 queued, 5 completed, 3 cancelled jobs. Exclude cancelled jobs from eligible total. Return {"eligible":INTEGER,"completed_percent":NUMBER} with percent rounded to 6 decimals.',
         {'eligible': 17, 'completed_percent': round(100*5/17, 6)}, fault='secondary_unavailable')
    case('recovery-secondary-invalid', 'failed_model_recovery', 'analysis',
         'Synthetic values=[7,3,7,2,3]. Retain each distinct value once and sort ascending. Return {"values":[SORTED_INTEGERS]}.', {'values': [2, 3, 7]}, fault='secondary_invalid')
    assert len(cases) == 16 and len({r['category'] for r in cases}) == 8
    return {'version': 1, 'cases': cases, 'system': SYSTEM, 'settings': SETTINGS,
            'endpoints': ['local:supervisor', 'worker:athena-p40', 'worker:athena-p6000', 'worker:wonyoung-strata'],
            'collaboration': {'preference': 'parallel', 'max_participants': 3, 'max_concurrency': 2},
            'single': 'Original configured 4B, one inference, same prompt/options/oracle; no retries or alternative endpoint.',
            'grading': 'Exact JSON equality; additionally field equality for factual correctness and incorrect/extra atomic claims for unsupported-claim rate. Agreement between models earns no correctness credit.',
            'resources': 'Timestamped free/total RAM and VRAM plus GPU utilization when obtainable; snapshots do not certify peak process consumption or energy.',
            'failure_injection': 'Two predefined recovery cases override secondary transport with an unavailable error or invalid output; all other cases use real endpoint responses. Recovery fixtures must be labelled separately.',
            'routine_regression': 'Five fresh simple synthetic value lookups using auto policy and original4B; no secondary model dispatch permitted.',
            'scope': 'Two prospective synthetic cases per predefined category. Small sample, no general performance certification; no model output used to design the oracle.'}


def seal(output):
    output = output.resolve()
    if not output.is_relative_to((ROOT/'data/v41-verification').resolve()) or output.exists():
        raise SystemExit('New protected verifier evidence directory required.')
    output.mkdir(parents=True)
    encoded = json.dumps(dataset(), indent=2, sort_keys=True).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    (output/'protocol.json').write_bytes(encoded)
    (output/'protocol.sha256').write_text(digest, encoding='ascii')
    print(json.dumps({'sealed': True, 'cases': 16, 'categories': 8, 'sha256': digest}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    seal(parser.parse_args().output)
