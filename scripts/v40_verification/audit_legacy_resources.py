"""Read-only production measurement audit; replay only into an isolated DB copy.

No health probe, model startup, inference, production preference write or evidence
reimport occurs. Stored identities are used only to test receipt compatibility;
this is not a new runtime identity or eligibility certification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src')]
from hanni.config.loader import load_config
from hanni.models.adaptive import AdaptiveModelEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to((ROOT / 'data/v40-verification').resolve()) and not output.exists()
    output.mkdir(parents=True)
    source_path = ROOT / 'data/model-routing/profiles.sqlite3'
    source = sqlite3.connect(source_path.resolve().as_uri() + '?mode=ro', uri=True)
    copy_root = output / 'copy/model-routing'
    copy_root.mkdir(parents=True)
    copied = sqlite3.connect(copy_root / 'profiles.sqlite3')
    engine = None
    try:
        rows = source.execute('SELECT id,endpoint,identity,category,payload FROM measurements ORDER BY id').fetchall()
        assert len(rows) == 32 and all(row[0].startswith('v40-real:') for row in rows)
        assert all('resource_observations' not in json.loads(row[4]) for row in rows)
        source.backup(copied)
        copied.close()
        config = load_config(ROOT / 'config', env={})
        engine = AdaptiveModelEngine(config, data_dir=output / 'copy')
        identities = {row[1]: row[2] for row in rows}
        engine.endpoint_identity = lambda endpoint: identities[endpoint]
        profiles = {endpoint: engine._profiles(endpoint, identity) for endpoint, identity in identities.items()}
        for endpoint, identity in identities.items():
            for profile in profiles[endpoint].values():
                assert profile['resource_sample_count'] == 0
                assert all(summary == {'sample_count': 0, 'mean': None, 'min': None, 'max': None}
                           for summary in profile['resource_observations'].values())
                assert profile['confidence'] == 'insufficient'
        for identifier, endpoint, identity, category, encoded in rows:
            payload = json.loads(encoded)
            payload.pop('created_at')
            engine.record_evaluation(endpoint, identity=identity, task_category=category,
                                     evaluation_id=identifier, **payload)
        copied_rows = engine._connect().execute(
            'SELECT id,endpoint,identity,category,payload FROM measurements ORDER BY id').fetchall()
        final_source = source.execute(
            'SELECT id,endpoint,identity,category,payload FROM measurements ORDER BY id').fetchall()
        assert copied_rows == rows and final_source == rows
        result = {'production_read_only': True, 'model_probes_or_startups': 0,
            'legacy_rows_readable': len(rows), 'idempotent_copy_replays': len(rows),
            'production_measurements_unchanged': True, 'legacy_unknown_resources_invented': 0,
            'rows_sha256': hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest(),
            'disclosure': 'Stored identities replayed only in isolated copy to audit serialization; not new runtime proof.',
            'per_endpoint_samples': {endpoint: sum(profile['sample_count'] for profile in values.values())
                                     for endpoint, values in profiles.items()}}
        (output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf8')
        print(json.dumps(result, indent=2))
    finally:
        if engine:
            engine.close()
        else:
            copied.close()
        source.close()


if __name__ == '__main__':
    main()
