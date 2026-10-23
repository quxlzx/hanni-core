"""Verify that a new Git repository cannot accidentally stage local state."""
from pathlib import Path
import shutil
import subprocess
ROOT = Path(__file__).resolve().parents[2]

def test_gitignore_blocks_private_files_and_keeps_public_eval_corpora(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    shutil.copyfile(ROOT / '.gitignore', tmp_path / '.gitignore')
    private = ['.env', 'config/google-oauth-client.json', 'config/client_secret_123.json', 'config/my_api_keys.json', 'config/backup_credentials.json', 'data/chat.jsonl', 'models/Qwen3.5-4B.gguf', 'evals/real_world/curated.jsonl', 'evals/real_world/inbox/raw.jsonl', 'evals/checkpoints/local.json', 'evals/llm_tools/results/local.json', '.pytest-work/output.txt', '.pytest-github-ready/output.txt']
    public = ['.env.example', 'evals/llm_tools/cases.jsonl', 'evals/llm_tools/capability_coverage_v1.jsonl', 'evals/routing/language_generalization_v4.jsonl', 'evals/personality/personality_v2.jsonl']
    for name in private:
        result = subprocess.run(['git', '-C', str(tmp_path), 'check-ignore', '-q', '--no-index', name])
        assert result.returncode == 0, f'{name} should be ignored'
    for name in public:
        result = subprocess.run(['git', '-C', str(tmp_path), 'check-ignore', '-q', '--no-index', name])
        assert result.returncode == 1, f'{name} should remain available'
