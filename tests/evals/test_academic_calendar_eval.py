"""Check academic Calendar routing and resolved bounds, separate from result matching."""
from pathlib import Path
from hanni.evals.routing import build_default_host, load_cases, run_benchmark
ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / 'evals' / 'routing' / 'academic_calendar.jsonl'

def test_academic_calendar_routing_and_date_range_eval():
    cases = load_cases(CASES)
    assert len(cases) == 11
    report = run_benchmark(build_default_host(config_dir=ROOT / 'config', timezone_name='America/New_York'), cases)
    assert report.pass_rate == 100, [(row.case_id, row.reasons) for row in report.results if not row.passed]
    assert all((row.metrics['date_resolution'] for row in report.results))
