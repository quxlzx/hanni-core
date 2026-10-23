from copy import deepcopy
from hanni.evals.artifact_integrity import validate_llm_artifact

def sample():
    return {'model_id': 'local-test', 'model_file': 'model.gguf', 'api_model': 'local-test', 'endpoint': 'http://127.0.0.1:8080', 'quantization': 'Q4_K_M', 'config_profile': 'config/models.yaml', 'owner_timezone': 'America/New_York', 'production_timezone': 'America/New_York', 'timestamp': '2026-09-24T00:00:00+00:00', 'corpus_sha256': 'a' * 64, 'prompt_sha256': 'b' * 64, 'evaluator_sha256': 'c' * 64, 'routed_menus_sha256': 'd' * 64, 'total_scenarios': 2, 'completed_scenarios': 2, 'status': 'completed', 'results': [{'id': 'A', 'passed': True}, {'id': 'B', 'passed': False}], 'summary': {'task_success_rate': 50.0}}

def test_complete_artifact_has_provenance_and_consistent_summary():
    assert validate_llm_artifact(sample()) == []

def test_incomplete_or_duplicate_artifact_is_rejected():
    bad = deepcopy(sample())
    bad.pop('prompt_sha256')
    bad['results'][1]['id'] = 'A'
    bad['summary']['task_success_rate'] = 100.0
    errors = validate_llm_artifact(bad)
    assert any(('prompt_sha256' in error for error in errors))
    assert any(('duplicate' in error for error in errors))
    assert any(('rate' in error for error in errors))
