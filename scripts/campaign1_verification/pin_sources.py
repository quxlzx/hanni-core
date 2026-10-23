"""Snapshot only the exact listed acceptance dependencies before final execution."""
import argparse, hashlib, json, sys, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from scripts.campaign1_verification.run import sources

def pin(output):
    output = output.resolve()
    assert output.is_relative_to((ROOT / 'data/campaign1-verifier').resolve()) and (not output.exists())
    output.mkdir(parents=True)
    hashes = sources()
    archive = output / 'pinned-sources.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as package:
        for name, digest in hashes.items():
            path = ROOT / name
            data = path.read_bytes()
            assert hashlib.sha256(data).hexdigest() == digest
            package.writestr(Path(name).as_posix(), data)
    with zipfile.ZipFile(archive) as package:
        assert len(package.infolist()) == len(hashes)
        for name, digest in hashes.items():
            assert hashlib.sha256(package.read(Path(name).as_posix())).hexdigest() == digest
    assert sources() == hashes, 'Acceptance dependencies changed while snapshotting.'
    proof = {'scope': 'Exact production/config/evaluator/fixture/rubric/schema-migration bytes only; no owner data, model weights, final cases or oracles.', 'source_hashes': hashes, 'snapshot_archive': str(archive), 'snapshot_archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'snapshot_entries': len(hashes), 'final_case_oracles_unchanged': True}
    (output / 'freeze-proof.json').write_text(json.dumps(proof, indent=2) + '\n', encoding='utf8')
    return proof

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    proof = pin(a.output)
    print(json.dumps({k: v for k, v in proof.items() if k != 'source_hashes'}))
if __name__ == '__main__':
    main()
