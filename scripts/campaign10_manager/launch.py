"""Launch the actual current HANNI backend on isolated state; reuse owner model."""
import argparse
import json
import os
from pathlib import Path
import psutil
from hanni.dashboard.launcher import main as launch
from scripts.campaign10_manager.model import ModelBudget
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/campaign10-manager/native-runtime'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cycle', default='native-runtime-cycle2')
    parser.add_argument('--mode', choices=['text', 'workflow-only'], default='text')
    parser.add_argument('--start-model', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'data/campaign10-manager' / args.cycle
    if output.exists():
        raise FileExistsError('Preserve previous launch evidence.')
    output.mkdir(parents=True)
    os.environ['HANNI_LAYA_SHADOW_ENABLED'] = '0'
    process = psutil.Process()
    (output / 'PROCESS.json').write_text(json.dumps({'pid': process.pid, 'created': process.create_time(), 'parent': process.ppid(), 'scope': 'Actual original launcher/controller with disposable stores and existing configured model', 'generation_policy': 'No unassigned generation; native review is read-only'}, indent=2) + '\n', encoding='utf8')
    budget = ModelBudget(output / 'model', maximum=0)
    command = ['--config-dir', str(ROOT / 'config'), '--data-dir', str(output / 'state'), '--port', '8766', '--' + args.mode, '--no-browser', '--startup-timeout', '120']
    if args.start_model:
        prior = json.loads((ROOT / 'data/campaign10-manager/live-core-cycle1/model/ADMISSIONS.json').read_text(encoding='utf8'))
        model_file = Path(prior[0]['process']['model_path'])
        if not model_file.is_file():
            raise FileNotFoundError('The previously verified existing weights are unavailable.')
        command += ['--model-file', str(model_file)]
    else:
        command.append('--reuse-model')
    with budget.transport(starting_owned_model=args.start_model):
        return launch(command)
if __name__ == '__main__':
    raise SystemExit(main())
