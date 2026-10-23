from hanni.evals.email import run

def test_email_grounding_eval_covers_each_requested_category():
    report = run()
    categories = {row['category'] for row in report['results']}
    assert categories >= {'email_sender_search', 'email_semantic_search', 'email_latest', 'email_followup', 'email_job_action', 'email_thread_state', 'email_deadline', 'email_no_result', 'email_provider_failure', 'email_prompt_injection'}
    assert report['passed'] == report['cases'], [row for row in report['results'] if not row['passed']]
