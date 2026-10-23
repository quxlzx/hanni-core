"""The K2 challenger profile must not silently change the comparison policy."""
from pathlib import Path
import yaml

def test_k2_challenger_profile_matches_production_except_model_identity():
    config = Path(__file__).resolve().parents[2] / 'config'
    challenger = config / 'profiles' / 'k2-bakeoff'
    for filename in ('hanni.yaml', 'permissions.yaml', 'privacy.yaml'):
        assert (challenger / filename).read_bytes() == (config / filename).read_bytes()
    incumbent = yaml.safe_load((config / 'models.yaml').read_text(encoding='utf-8'))
    k2 = yaml.safe_load((challenger / 'models.yaml').read_text(encoding='utf-8'))
    assert {key: value for key, value in k2.items() if key != 'models'} == {key: value for key, value in incumbent.items() if key != 'models'}
    incumbent_model, k2_model = (incumbent['models'][0], k2['models'][0])
    assert len(incumbent['models']) == len(k2['models']) == 1
    assert {key: value for key, value in k2_model.items() if key not in {'id', 'model_file', 'hf_repo'}} == {key: value for key, value in incumbent_model.items() if key not in {'id', 'model_file', 'hf_repo'}}
    assert k2_model['id'] == 'k2-horizon-3.7b'
    assert k2_model['model_file'] == 'K2-Horizon-4B-Q4_K_M.gguf'
    assert k2_model['hf_repo'] == 'IFM/K2-Horizon-3.7B-GGUF'
