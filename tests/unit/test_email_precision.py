"""Regressions for sender false positives, concise lists and body-call budgets."""
from datetime import datetime
import pytest
from hanni.evals.routing import build_default_host
from hanni.tools.email_analysis import email_summary, sender_matches
from hanni.tools.email_provider import GmailEmailProvider
from hanni.tools.email_routing import email_search_plan
from hanni.tools.email_tools import EmailService, definitions
from hanni.tools.google_access import GoogleAccess, GoogleAccessError
from tests.unit.test_email_capability import Mailbox, Vault, mail, search, NOW, ZONE, ROOT

def full_calls(mailbox):
    return [path for _, path, params in mailbox.calls if params.get('format') == 'full']

@pytest.mark.parametrize('query,sender,entity', [('Did Intel email me?', 'Intel Onboarding <onboarding@intel.com>', 'Intel'), ('latest email from tik tok', 'TikTok Recruiting <jobs@tiktok.com>', 'TikTok'), ('What is my latest email from NVIDIA?', 'NVIDIA <jobs@nvidia.com>', 'NVIDIA')])
def test_exact_false_positive_regressions_reject_subject_body_and_snippet_mentions(query, sender, entity):
    messages = [mail('real', sender, 'Your onboarding instructions', 'Private content'), mail('reddit', 'Reddit <alerts@reddit.com>', f'Article about {entity}', f'{entity} news'), mail('linkedin', 'LinkedIn <notify@linkedin.com>', f'An employee at {entity} posted', f'{entity} onboarding'), mail('gu', 'GU USA <news@gu.example>', 'Where Winds Meet', entity)]
    messages[-1]['snippet'] = entity

    class BroadMailbox(Mailbox):

        def __call__(self, account, path, params):
            if path.endswith('/messages'):
                self.calls.append((account, path, dict(params)))
                return {'messages': [{'id': m['id']} for m in self.messages]}
            return super().__call__(account, path, params)
    mailbox = BroadMailbox(messages)
    service = EmailService(GmailEmailProvider(GoogleAccess(Vault(), mailbox, ZONE)), ZONE)
    plan = email_search_plan(query, now=NOW, timezone_name=ZONE)
    data = service.search(plan)
    assert plan.relation == 'from' and plan.metadata_only
    assert [m['message_id'] for m in data['messages']] == ['real']
    assert not full_calls(mailbox)
    assert all(('from:' in params['q'] for _, path, params in mailbox.calls if path.endswith('/messages')))
    assert all((word not in email_summary(data) for word in ('Reddit', 'LinkedIn', 'GU USA', 'Private content', 'incomplete')))

def test_from_never_falls_back_to_about_and_aliases_use_sender_evidence():
    messages = [mail('mention', 'Reddit <reddit@example.test>', 'Intel news', 'Intel emailed someone')]
    data, mailbox = search('Did Intel email me?', messages)
    assert not data['messages'] and 'directly from intel' in email_summary(data)
    assert not full_calls(mailbox)
    about, mailbox = search('Find the email about Intel', messages)
    assert about['relation'] == 'about' and about['messages'][0]['message_id'] == 'mention'
    assert not full_calls(mailbox)
    assert sender_matches('tik tok', 'TikTok Recruiting', 'jobs@tiktok.com')
    assert sender_matches('capital one', '', 'capitalone@myworkday.com')
    assert sender_matches('TASA', 'TASA at UMCP', 'tasa@example.test')
    assert sender_matches('Intel', '', 'intel@myworkday.com')
    assert not sender_matches('Intel', 'News', 'editor@intel.com.evil.test')
    assert not sender_matches('Intel', 'Intelligence Digest', 'news@intelligence.com')

@pytest.mark.parametrize('query', ['What emails did I get today?', 'What emails did I get yesterday?', 'What emails did I get this week?', 'show my latest emails', 'what was my most recent email?', 'What were my 5 most recent emails?', 'What emails did I get this month?'])
def test_recent_queries_route_directly_and_never_read_bodies(query):
    host = build_default_host(config_dir=ROOT / 'config', timezone_name=ZONE)
    route = host.route(query, now=NOW)
    assert [t.capability_id for t in route.tools] == ['email.search']
    plan = route.tools[0].fixed_arguments['plan']
    assert plan['relation'] == 'recent' and plan['metadata_only'] and (not plan['require_body'])
    messages = [mail('today', 'News <news@example.test>', 'News today', 'Do not read', date='2026-09-25T09:00:00-04:00'), mail('yesterday', 'GitHub <ci@github.com>', 'CI failed', 'Do not read')]
    data, mailbox = search(query, messages)
    assert data['messages'] and (not full_calls(mailbox))
    assert 'access' not in email_summary(data).lower() and 'Do not read' not in email_summary(data)

def test_five_recent_emails_are_five_numbered_messages_sorted_by_date():
    messages = [mail(str(i), f'Sender {i} <news@company{i}.test>', f'Subject {i}', 'Hidden body', date=f'2026-09-{18 + i:02d}T12:00:00-04:00', thread='same') for i in range(7)]
    data, mailbox = search('What were my 5 most recent emails?', messages)
    assert [m['message_id'] for m in data['messages']] == ['6', '5', '4', '3', '2']
    lines = email_summary(data).splitlines()
    assert len(lines) == 5 and all((line.startswith(f'{i}. ') for i, line in enumerate(lines, 1)))
    assert lines[0] == '1. Sender 6 — "Subject 6"'
    assert not full_calls(mailbox)

def test_today_and_month_end_at_current_local_time():
    for phrase, start in [('today', '2026-09-25T00:00:00-04:00'), ('this month', '2026-09-01T00:00:00-04:00')]:
        plan = email_search_plan('What emails did I get ' + phrase, now=NOW, timezone_name=ZONE)
        assert plan.start_time == start and plan.end_time == NOW.isoformat()
    spring = datetime.fromisoformat('2026-03-09T10:00:00-04:00')
    plan = email_search_plan('What emails did I get yesterday', now=spring, timezone_name=ZONE)
    assert plan.start_time == '2026-03-08T00:00:00-05:00'
    assert plan.end_time == '2026-03-09T00:00:00-04:00'

def test_topic_metadata_success_prevents_body_fallback():
    for query, subject in [('Find the temporary password email.', 'Your temporary password'), ('Find the email about my laptop setup.', 'Mail Out PC Shipment/Delivery Notice'), ('Find my Intel onboarding email.', 'Intel Onboarding Essentials')]:
        data, mailbox = search(query, [mail('a', 'Intel Onboarding <example-1f9cff7a6e@example.com>', subject, 'PRIVATE_BODY')])
        assert [m['message_id'] for m in data['messages']] == ['a']
        assert not full_calls(mailbox) and 'PRIVATE_BODY' not in email_summary(data)
        assert 'Email excerpt' not in email_summary(data)

def test_about_body_fallback_is_small_and_only_returns_metadata():
    messages = [mail(str(i), 'Support <support@example.test>', 'Welcome', 'Your initial password: SECRET_VALUE') for i in range(7)]
    data, mailbox = search('Find the temporary password email', messages)
    assert data['messages'] and len(full_calls(mailbox)) == 3
    assert all((m['body_text'] is None for m in data['messages']))
    assert 'SECRET_VALUE' not in str(data) and 'Email excerpt' not in email_summary(data)
    assert data['limited'] and (not data['partial']) and ('incomplete' not in email_summary(data))

def test_organization_and_important_views_are_metadata_only():
    messages = [mail('github', 'GitHub <ci@github.com>', 'Run failed: CI main', 'Hidden'), mail('starbucks', 'Starbucks Rewards <example-e4c51e459c@example.com>', 'Bonus stars', 'Hidden'), mail('tasa', 'TASA <example-cd0c18a0bd@gmail.com>', 'Big Little pairings', 'Hidden'), mail('person', 'Jane Doe <example-988b074286@gmail.com>', 'Hello', 'Hidden'), mail('repeat', 'GitHub <ci@github.com>', 'Run succeeded', 'Hidden'), mail('work', 'Acme Recruiting <jobs@acme.test>', 'Assessment deadline', 'Hidden'), mail('capital', 'Capital One <capitalone@myworkday.test>', 'Application update', 'Hidden')]
    data, mailbox = search('What companies emailed me this week?', messages)
    answer = email_summary(data)
    assert all((name in answer for name in ('GitHub', 'Starbucks', 'TASA', 'Acme')))
    assert 'Jane' not in answer and answer.count('GitHub') == 1 and ('Run failed' not in answer)
    assert not full_calls(mailbox)
    assert 'Capital One' in data['organizations']
    assert '• GitHub' in answer
    data, mailbox = search('What important emails do I need to look at?', messages)
    answer = email_summary(data)
    assert 'Run failed' in answer and 'Assessment deadline' in answer
    assert 'Bonus stars' not in answer and 'Hello' not in answer and (not full_calls(mailbox))

def test_workflow_ignores_form_receipts_and_weak_next_steps():
    messages = [mail('receipt', 'Forms Response Receipts <forms@example.test>', 'Application form response receipt', 'Next steps: complete assessment'), mail('weak', 'Company <jobs@acme.test>', 'Application status', 'See our website for next steps.'), mail('news', 'News <news@example.test>', 'Daily news', 'Internship assessment required')]
    data, mailbox = search('What job applications need action?', messages)
    assert "didn't find any clearly actionable" in email_summary(data)
    assert all(('/receipt' not in path and '/news' not in path for path in full_calls(mailbox)))
    assert not any((item['status'] == 'ACTION_REQUIRED' for item in data['action_items']))

def test_explicit_body_request_only_opens_matching_sender():
    messages = [mail('real', 'Intel <example-8604f2fd68@example.com>', 'Setup', 'Follow these instructions.'), mail('other', 'Reddit <news@reddit.com>', 'Intel update', 'Unrelated')]
    data, mailbox = search('What did the Intel email say?', messages)
    assert full_calls(mailbox) == ['/gmail/v1/users/me/messages/real']
    assert 'Follow these instructions' in email_summary(data)

def test_normal_page_cap_has_no_warning_but_provider_failure_is_reported():

    class Capped(Mailbox):

        def __call__(self, account, path, params):
            result = super().__call__(account, path, params)
            return {**result, 'nextPageToken': 'more'} if path.endswith('/messages') else result
    mailbox = Capped([mail('a', 'Intel <example-8604f2fd68@example.com>', 'Welcome', 'Hidden')])
    data = EmailService(GmailEmailProvider(GoogleAccess(Vault(), mailbox, ZONE)), ZONE).search(email_search_plan('Did Intel email me?', now=NOW, timezone_name=ZONE))
    assert data['limited'] and (not data['partial'])
    assert 'incomplete' not in email_summary(data) and 'additional' not in email_summary(data)

    def fail(*args):
        raise GoogleAccessError('rate limited (HTTP 429)')
    result = definitions(GoogleAccess(Vault(), fail, ZONE))[0].handler({'query': 'Did Intel email me?'}, None, None)
    assert not result.ok and 'rate limiting' in result.message and ('directly from' not in result.message)
