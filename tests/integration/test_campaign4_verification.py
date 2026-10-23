"""Prospective independent verifier boundary controls, no private case loading."""
import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4
from scripts.campaign4_verification.executor import PRIVATE, run_case
from scripts.campaign4_verification.scoring import evaluate

def fixture(key, controls=None, faults=None, steps=None):
    read = dict(step_id='read', description='Read the text file {root}/sample.txt', kind='tool', capability_id='file.read', dependencies=[], required=True, criteria=[dict(operator='nonempty', path='/data/text', expected=None)], arguments=dict(path='{root}/sample.txt'))
    save = dict(step_id='save', description='Save the verified read as a managed report.', kind='artifact', capability_id='file.write', dependencies=['read'], required=True, criteria=[dict(operator='present', path='/data/path', expected=None)], arguments=dict(path='{artifact_root}/report.txt', text={'$ref': dict(step_id='read', path='/data/text', type='string')}))
    return dict(id=key, category='exposed_boundary', scenario=key, goal='Read the exact text file {root}/sample.txt and save its verified contents as a managed report.', files={'sample.txt': 'Independent development specimen 42.'}, steps=steps or [read, save], mode='assisted', controls=controls if controls is not None else [dict(at='planned', operation='approve_plan'), dict(at='ready', operation='start')], faults=faults or [], limits=dict(lease_seconds=1, max_plan_attempts=1, step_timeout_seconds=3))

class IndependentExecutorTests(unittest.TestCase):

    def run_exposed(self, case):
        root = PRIVATE / 'harness-tests' / str(uuid4())
        return run_case(case, root)

    def test_original_artifact_has_authorized_stable_effect_receipt(self):
        result = self.run_exposed(fixture('one-copy'))
        self.assertIsNone(result['harness_error'])
        self.assertEqual(result['workflow']['status'], 'completed')
        effects = result['effect_ledger']
        self.assertEqual(len(effects), 1)
        self.assertTrue(effects[0]['actual_effect'])
        self.assertTrue(effects[0]['authorized'])
        self.assertIsNotNone(effects[0]['invocation_id'])
        self.assertEqual(len(result['handler_entries']), 2)
        self.assertEqual(len(result['planner_calls']), 2)
        self.assertEqual(result['pending_controls'], [])

    def test_verified_post_commit_pause_and_real_readback(self):
        result = self.run_exposed(fixture('durable-pause', controls=[dict(at='planned', operation='approve_plan'), dict(at='ready', operation='start'), dict(at='verified:read', operation='pause'), dict(at='paused', operation='reopen_store_readback')]))
        self.assertIsNone(result['harness_error'])
        self.assertEqual(result['workflow']['status'], 'paused')
        self.assertEqual(len(result['effect_ledger']), 0)
        self.assertTrue(result['controls'][-1]['readback_equal'])
        self.assertEqual(result['pending_controls'], [])

    def test_controlled_forged_plan_is_originally_rejected(self):
        result = self.run_exposed(fixture('forged', controls=[], faults=[dict(kind='planner_reply', stage='outline', extra_fields=dict(confirmed=True))]))
        self.assertIsNone(result['harness_error'])
        self.assertEqual(result['workflow']['status'], 'blocked')
        self.assertEqual(result['handler_entries'], [])

    def test_actual_owned_process_restart_preserves_verified_read(self):
        result = self.run_exposed(fixture('real-restart', controls=[dict(at='planned', operation='approve_plan'), dict(at='ready', operation='start'), dict(at='verified:read', operation='owned_process_exit'), dict(at='stopped', operation='restart'), dict(at='paused', operation='resume')]))
        self.assertEqual(result['workflow']['status'], 'completed')
        self.assertTrue(result['actual_owned_process_restart'])
        self.assertTrue(all((row['parent_verified'] for row in result['processes'])))
        self.assertNotEqual(*[row['identity']['pid'] for row in result['processes']])
        reads = [row for row in result['workflow']['invocations'] if row['step_id'] == 'read']
        self.assertEqual(len(reads), 1)
        self.assertEqual(len(result['effect_ledger']), 1)
        self.assertTrue(result['effect_ledger'][0]['authorized'])

    def test_parallel_reads_overlap_at_original_leaf(self):
        case = fixture('parallel')
        first = case['steps'][0]
        second = json.loads(json.dumps(first))
        second['step_id'] = 'other'
        second['description'] = 'Read the text file {root}/other.txt'
        second['arguments']['path'] = '{root}/other.txt'
        case['files']['other.txt'] = 'Another independent development observation.'
        case['steps'] = [first, second]
        case['goal'] = 'Read the text files {root}/sample.txt and {root}/other.txt.'
        case['faults'] = [dict(kind='barrier', step_ids=['read', 'other'], release_after_both_enter=True)]
        result = self.run_exposed(case)
        self.assertEqual(result['workflow']['status'], 'completed')
        grade = evaluate(result, dict(stop_status='completed', writes=0, max_concurrent_reads=2, observed_read_overlap_required=True))
        self.assertTrue(grade['passed'], grade['failures'])

    def test_actual_copy_waits_for_original_bound_approval(self):
        case = fixture('copy-approval')
        case['steps'] = [dict(step_id='copy', description='Copy the file {root}/sample.txt to {root}/copy.txt', kind='tool', capability_id='file.copy', dependencies=[], required=True, criteria=[dict(operator='present', path='/data/destination', expected=None)], arguments=dict(source='{root}/sample.txt', destination='{root}/copy.txt'))]
        case['goal'] = 'Copy the file {root}/sample.txt to {root}/copy.txt after approval.'
        case['allowed_actions'] = ['file.copy']
        case['controls'] += [dict(at='waiting_approval', operation='observe_no_dispatch'), dict(at='waiting_approval', operation='approve_step')]
        result = self.run_exposed(case)
        grade = evaluate(result, dict(stop_status='completed', writes=1, approval_wait_has_no_effect=True, copied_file='copy.txt', source_file='sample.txt'))
        self.assertTrue(grade['passed'], grade['failures'])

    def test_scorer_rejects_invented_evidence_and_unknown_oracle(self):
        result = self.run_exposed(fixture('scorer-control'))
        grade = evaluate(result, dict(stop_status='completed', writes=1, invented_oracle=True, completed_notification_only_after_verification=True))
        self.assertFalse(grade['passed'])
        self.assertTrue(grade['checks']['completed_notification_only_after_verification']['passed'])
        result['effect_ledger'][0]['authorized'] = False
        denied = evaluate(result, dict(stop_status='completed', writes=1))
        self.assertFalse(denied['passed'])
        self.assertIn('no_unauthorized_original_effect', denied['failures'])

    def test_owned_interruptions_before_and_after_write_never_replay(self):
        for boundary, expected_writes in [('before_dispatch', 0), ('after_result', 1)]:
            with self.subTest(boundary=boundary):
                case = fixture('uncertain-' + boundary, controls=[dict(at='planned', operation='approve_plan'), dict(at='ready', operation='start'), dict(at=boundary + ':save', operation='owned_process_exit'), dict(at='stopped', operation='restart'), dict(at='blocked', operation='resume_expect_denial'), dict(at='blocked', operation='retry_safe_expect_denial', step_id='save')])
                result = self.run_exposed(case)
                grade = evaluate(result, dict(stop_status='blocked', writes=expected_writes, owned_process_failure_required=True, uncertain_invocation_required=True, write_replay_forbidden=True, no_completed_claim=True))
                self.assertTrue(grade['passed'], grade['failures'])
                self.assertEqual(len(result['workflow']['invocations']), 2)
                denied = [row for row in result['controls'] if row['operation'].endswith('_expect_denial')]
                self.assertEqual(len(denied), 2)
                self.assertTrue(all((row['ok'] is False for row in denied)))

    def test_original_cited_analysis_is_measured_as_protocol(self):
        case = fixture('analysis')
        case['files']['sample.txt'] = '{"rows":[2,4,9]}'
        case['steps'][0]['criteria'] = [dict(operator='json_valid', path='/data/text', expected=None)]
        case['steps'][1]['arguments']['text']['$ref']['step_id'] = 'analyze'
        case['steps'][1]['dependencies'] = ['analyze']
        analysis = dict(step_id='analyze', description='Count the observed rows from the verified source.', kind='analysis', capability_id=None, dependencies=['read'], required=True, criteria=[dict(operator='evidence_report', path='/data/report', expected=None)], arguments=dict(sources=['read']))
        case['steps'].insert(1, analysis)
        case['analysis_replies'] = {'analyze': dict(observations=[dict(operation='count', sources=[dict(step_id='read', path='/data/text', json_path='/rows')], value=3)])}
        result = self.run_exposed(case)
        self.assertEqual(result['workflow']['status'], 'completed')
        self.assertEqual(len(result['planner_calls']), 3)
        self.assertEqual(result['actual_model_calls'], 0)
        self.assertEqual([row for row in result['workflow']['steps'] if row['step_id'] == 'analyze'][0]['status'], 'verified')
if __name__ == '__main__':
    unittest.main()
