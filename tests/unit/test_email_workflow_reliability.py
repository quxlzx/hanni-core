"""Reported workflow phrases through the real planner, Gmail adapter and formatter."""
from dataclasses import replace
from datetime import datetime
import pytest
from hanni.evals.routing import build_default_host
from hanni.mcp.session import McpToolSession
from hanni.tools.email_analysis import email_summary
from hanni.tools.email_provider import GmailEmailProvider
from hanni.tools.email_routing import email_search_plan
from hanni.tools.email_tools import EmailService, dedupe_email_results
from hanni.tools.google_access import GoogleAccess
from tests.unit.test_email_capability import Mailbox, Vault, mail, search, NOW, ROOT, ZONE

def full_calls(mailbox):
    return [path for _, path, params in mailbox.calls if params.get('format') == 'full']

@pytest.mark.parametrize('prompt,intent', [('What job applications need action?', 'job_action'), ('Do I have any applications I need to finish?', 'job_action'), ('Do I need to do anything for my internships?', 'job_action'), ('Are there application emails I need to respond to?', 'job_action'), ('Do I have recruiting tasks pending?', 'job_action'), ('Anything I need to finish for job applications?', 'job_action'), ('Do I have any application deadlines?', 'job_deadline'), ('Did any company ask me to respond?', 'respond'), ('Did any company ask me to schedule an interview?', 'interview'), ('Did any company ask me to verify my email?', 'verification')])
def test_workflow_phrases_route_to_email(prompt, intent):
    plan = email_search_plan(prompt, now=NOW, timezone_name=ZONE)
    assert plan and plan.relation == 'workflow' and (plan.workflow_intent == intent)
    host = build_default_host(config_dir=ROOT / 'config', timezone_name=ZONE)
    decision = host.route(prompt, now=NOW)
    assert [tool.capability_id for tool in decision.tools] == ['email.search']

def test_application_action_synonym_and_completed_thread():
    messages = [mail('pending', 'TikTok Recruiting <jobs@tiktok.com>', 'CodeSignal assessment', 'Please complete the assessment by Sep 27.'), mail('old', 'Workiva Recruiting <example-a46ef68fd9@example.com>', 'Assessment invitation', 'Please complete the assessment.', date='2026-09-20T09:00:00-04:00', thread='workiva'), mail('done', 'Workiva Recruiting <example-a46ef68fd9@example.com>', 'Assessment completed', 'Your assessment has been completed.', date='2026-09-23T09:00:00-04:00', thread='workiva')]
    data, mailbox = search('Do I have any applications I need to finish?', messages)
    answer = email_summary(data)
    assert 'TikTok' in answer and 'Complete the assessment' in answer
    assert 'Workiva' not in answer and 'cannot verify' not in answer.lower()
    assert data['bodies_fetched'] <= 5 and full_calls(mailbox)

def test_explicit_application_deadline_and_no_inferred_deadline():
    messages = [mail('deadline', 'TikTok Recruiting <jobs@tiktok.com>', 'CodeSignal assessment', 'Please complete the assessment by September 27.'), mail('vague', 'Workiva Recruiting <example-a46ef68fd9@example.com>', 'Application update', 'Please respond soon.')]
    data, _ = search('Do I have any application deadlines?', messages)
    answer = email_summary(data)
    assert 'TikTok' in answer and 'Assessment due Sep 27' in answer and ('Workiva' not in answer)
    no_date, _ = search('Do I have any application deadlines?', messages[1:])
    assert no_date['status'] == 'NO_RESULTS'
    assert "didn't find any explicit application deadlines" in email_summary(no_date)

def test_current_reminder_retains_explicit_deadline_from_earlier_thread_message():
    messages = [mail('invite', 'TikTok Recruiting <jobs@tiktok.com>', 'Assessment invitation', 'Please complete the assessment by September 27.', date='2026-09-20T09:00:00-04:00', thread='tiktok'), mail('reminder', 'TikTok Recruiting <jobs@tiktok.com>', 'Assessment reminder', 'Please complete the assessment.', date='2026-09-24T09:00:00-04:00', thread='tiktok')]
    data, _ = search('Do I have any application deadlines?', messages)
    assert 'Sep 27' in email_summary(data)
    assert len(data['action_items']) == 1

def test_respond_and_interview_requests_have_grounded_answers():
    messages = [mail('reply', 'Capital One Recruiting <example-704fb13f37@example.com>', 'Interview availability', 'Please reply with your availability for an interview.'), mail('social', 'Reddit <news@reddit.com>', 'Interview tips', 'Please reply to this post.')]
    for prompt in ('Did any company ask me to respond?', 'Did any company ask me to schedule an interview?'):
        data, _ = search(prompt, messages)
        answer = email_summary(data)
        assert answer.startswith('Yes.') and 'Capital One' in answer
        assert 'Reddit' not in answer and 'Email lookup completed' not in answer
        assert "couldn't verify" not in answer.lower()

def test_recruiting_this_week_filters_old_messages_before_ranking_and_reads_no_bodies():
    messages = [mail('week', 'TikTok Recruiting <jobs@tiktok.com>', 'Assessment invitation', 'Secret', date='2026-09-22T09:00:00-04:00'), mail('older', 'Workiva Recruiting <example-a46ef68fd9@example.com>', 'Assessment invitation', 'Secret', date='2026-09-11T09:00:00-04:00'), mail('oldest', 'NVIDIA Recruiting <jobs@nvidia.com>', 'Application update', 'Secret', date='2026-09-03T09:00:00-04:00')]
    data, mailbox = search('What recruiting emails did I get this week?', messages)
    answer = email_summary(data)
    assert data['query_type'] == 'job_search' and data['view'] == 'job'
    assert data['messages'][0]['message_id'] == 'week' and len(data['messages']) == 1
    assert answer.startswith('This week:') and 'TikTok' in answer
    assert 'Workiva' not in answer and 'NVIDIA' not in answer and (not full_calls(mailbox))
    plan = email_search_plan('What recruiting emails did I get this week?', now=NOW, timezone_name=ZONE)
    assert plan.start_time == '2026-09-21T00:00:00-04:00' and plan.end_time == NOW.isoformat()
    last_seven = email_search_plan('What recruiting emails did I get in the last 7 days?', now=NOW, timezone_name=ZONE)
    assert last_seven.start_time == '2026-09-18T10:00:00-04:00' and last_seven.end_time == NOW.isoformat()

def test_latest_job_application_uses_metadata_and_date():
    messages = [mail('new', 'TikTok Recruiting <jobs@tiktok.com>', 'Assessment', 'Secret', date='2026-09-22T09:00:00-04:00'), mail('old', 'Workiva Recruiting <example-a46ef68fd9@example.com>', 'Application update', 'Secret', date='2026-09-11T09:00:00-04:00')]
    data, mailbox = search('What is my most recent job application email?', messages)
    assert [row['message_id'] for row in data['messages']] == ['new']
    assert email_summary(data).startswith('TikTok Recruiting') and 'Sep 22' in email_summary(data)
    assert not full_calls(mailbox)

def test_interview_about_search_prefers_recruiter_and_rejects_social_only():
    messages = [mail('social', 'Reddit <notify@reddit.com>', 'Google SWE internship Interview Scheduled?', 'Interview discussion', date='2026-09-24T09:00:00-04:00'), mail('real', 'Capital One Recruiting <example-704fb13f37@example.com>', 'Schedule your interview', 'Choose a time', date='2026-09-22T09:00:00-04:00')]
    data, mailbox = search('Find the email about my interview.', messages)
    assert [row['message_id'] for row in data['messages']] == ['real']
    assert not full_calls(mailbox)
    only_social, _ = search('Find the email about my interview.', messages[:1])
    assert not only_social['messages']

def test_verification_is_email_address_specific():
    messages = [mail('email', 'Roblox <example-a990b28e14@example.com>', 'Verify your email', 'Please verify your email address.'), mail('code', 'GitHub <example-4fcf45c01c@example.com>', 'Sudo authentication code', 'Use your 2FA code.'), mail('phone', 'Handshake Recruiting <example-d730c94e7c@example.com>', 'Phone verification', 'Please verify your phone number.')]
    data, _ = search('Did any company ask me to verify my email?', messages)
    answer = email_summary(data)
    assert 'Roblox' in answer and 'GitHub' not in answer and ('Handshake' not in answer)

def test_dedupe_uses_thread_then_sender_subject_near_time():
    from hanni.tools.email_provider import normalize_message
    base = mail('one', 'NVIDIA HR <example-f97c0e4ce7@example.com>', 'Thank you for your interest', 'Text', thread='thread-a')
    same_thread = mail('two', 'NVIDIA HR <example-f97c0e4ce7@example.com>', 'Thank you for your interest', 'Text', thread='thread-a')
    other_application = mail('three', 'NVIDIA HR <example-f97c0e4ce7@example.com>', 'Thank you for your interest', 'Text', thread='thread-b')
    rows = [normalize_message(row, 'personal') for row in (base, same_thread, other_application)]
    assert {row.message_id for row in dedupe_email_results(rows)} == {'one', 'three'}
    no_thread = [replace(row, thread_id=None, received_at=NOW) for row in rows]
    assert len(dedupe_email_results(no_thread)) == 1

def test_partial_success_uses_one_consistent_outcome_and_legacy_marker_is_filtered():
    messages = [mail('a', 'TikTok Recruiting <jobs@tiktok.com>', 'Assessment', 'Complete the assessment.')]
    data, _ = search('What job applications need action?', messages)
    data['errors'] = [{'message': 'Gmail could not complete this request.'}]
    answer = email_summary(data)
    assert 'TikTok' in answer and 'Some accounts could not be checked.' in answer
    assert "couldn't verify" not in answer.lower()

    class History:

        def build_messages(self, prompt, system_suffix=''):
            return [{'role': 'system', 'content': system_suffix}, {'role': 'assistant', 'content': '[Email lookup completed; source content is not retained in history.]'}, {'role': 'user', 'content': prompt}]
    session = McpToolSession(History(), None, object())
    assert all(('Email lookup completed' not in row['content'] for row in session._messages('hello', '')))
