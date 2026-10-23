from hanni.evals.real_world_reliability import evaluate

def test_everyday_language_development_router_probe():
    report = evaluate()
    assert report['scope'] == 'read_only_router'
    assert report['total'] == 100
    assert len(report['families']) == 10
    assert report['passed'] == report['total'], [(row['id'], row['query'], row['selected']) for row in report['results'] if not row['passed']]
