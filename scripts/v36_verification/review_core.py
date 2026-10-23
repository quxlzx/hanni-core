"""Map the prospectively sealed16 mechanical core objectives to real evidence.

This preserves the original denominator. It neither substitutes actual model
goals for these contracts nor credits deterministic test clients as intelligence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'data/v36-verification'
SEALED=BASE/'sealed/core-workflows.json'
EXPECTED_SHA='957855fc94c7314e1f8cb8a49246a0443341fa315a6e18db020cb33e01edcaed'
CORE={
 'core-file-roundtrip':'test_core_file_roundtrip_is_grounded_in_independent_bytes',
 'core-file-copy-move':'test_core_file_copy_move_preserves_original_fixture_bytes',
 'core-delete-confirmation':'test_core_fixture_delete_requires_original_confirmation',
 'core-todo-dedupe':'test_core_todo_add_deduplication_and_completion_readback',
 'core-task-cas':'test_core_desktop_task_cas_preserves_newest_record',
 'core-project-note':'test_core_project_note_reopen_preserves_explicit_association',
 'core-workspace-dedupe':'test_core_fixed_uuid_does_not_duplicate_or_rebind_write',
 'core-memory-correction':'test_core_memory_correction_replaces_current_context_without_stale_cas',
 'core-memory-delete':'test_core_memory_delete_erases_source_bound_history_and_proposals',
 'core-memory-review':'test_core_local_analysis_is_review_only_and_exact_owner_approval',
 'core-provider-offline':'test_core_empty_google_credentials_do_not_create_a_connected_calendar',
 'core-safe-mode':'test_core_persistent_safe_mode_blocks_confirmed_file_and_memory_mutation',
 'core-profile-denial':'test_core_nonowner_denial_precedes_read_handler_execution',
 'core-http-origin':'test_core_actual_http_authentication_and_origin_reject_before_mutation',
}


def cases(path):
 return list(ET.parse(path).getroot().iter('testcase'))


def passed(case):
 return not any(child.tag in {'failure','error','skipped'} for child in case)


def main():
 sealed_bytes=SEALED.read_bytes()
 assert hashlib.sha256(sealed_bytes).hexdigest()==EXPECTED_SHA
 original=json.loads(sealed_bytes)
 assert len(original)==16
 sources={name:BASE/name for name in ('core-cycle6.xml','process-publish-cycle2.xml','independent-subsystems-cycle1.xml')}
 suites={name:cases(path) for name,path in sources.items()}
 rows=[]
 for objective in original:
  key=objective['test_id']
  if key in CORE:
   source='core-cycle6.xml'
   mapped=[c for c in suites[source] if c.attrib['name']==CORE[key]]
   assert len(mapped)==1
   method='Independent original registry/store/HTTP execution with test-owned temporary state; exact readback and permission oracles'
   scope='MOCK_PASS' if key=='core-provider-offline' else 'ISOLATED_PASS'
   caveat='Original Google adapter, explicitly empty credential vault; no live provider access' if key=='core-provider-offline' else 'No configured-model generation or live provider/power/security mutation'
  elif key=='core-workflow-restart':
   source='process-publish-cycle2.xml'
   mapped=suites[source]
   assert len(mapped)==5
   method='Independent original durable scheduler/registry in ServiceFixture, real owned process death/suspension, real lease time and actual isolated file effects'
   scope='ISOLATED_PASS'
   caveat='ServiceFixture supplies deterministic bounded plans/controller client. This verifies recovery, no uncertain-write replay and stale-owner fencing, not model planning or actual original desktop goal completion. Atomic evidence-publisher repair is test-only.'
  elif key=='core-mcp-lifecycle':
   source='independent-subsystems-cycle1.xml'
   prefixes=(
    'test_actual_http_auth_failure_and_recovery_never_persist_or_export_token',
    'test_original_model_facing_session_executes_actual_external_name_and_audits',
    'test_nested_full_schema_preserved_in_original_menu_and_enforced_before_dispatch',
    'test_long_shared_prefix_and_cross_server_names_have_distinct_original_controller_wires',
    'test_imported_write_retains_original_confirmation_profile_and_safe_mode_gates',
    'test_genuine_sdk_tool_list_notification_revokes_approval_and_refreshes_definition',
   )
   mapped=[c for c in suites[source] if any(c.attrib['name'].startswith(p) for p in prefixes)]
   assert len(mapped)==7
   method='Independent actual local SDK stdio and HTTP servers, original manager/registry/controller schemas and gate checks, retained server ledgers'
   scope='ISOLATED_PASS'
   caveat='Local server is synthetic test-owned service; model-facing session mechanics use disclosed deterministic selection probe. Discovery, invocation, output-error refusal, auth recovery/reconnect, removal, stale-adapter revocation and stop gates are real. No trained or third-party live integration credit.'
  else:
   raise AssertionError(key)
  assert all(passed(c) for c in mapped),(key,[c.attrib['name'] for c in mapped if not passed(c)])
  rows.append({'test_id':key,'sealed_expected':objective['expected'],'outcome':scope,'scoped_objective_passed':True,
               'verification_method':method,'limitations':caveat,'evidence':str(sources[source].relative_to(ROOT)),
               'mapped_tests':[c.attrib['classname']+'::'+c.attrib['name'] for c in mapped],
               'actual_model_goal_completion_credit':False})
 result={'prospective_core_sha256':EXPECTED_SHA,'rows':rows,
         'summary':{'original_core_objectives':16,'scoped_objectives_passed':16,'scoped_rate':1.0,
                    'core_95_percent_contract_target_met':True,'actual_model_planned_goals_completed':0,'actual_model_planned_goals_attempted':3,
                    'disclosure':'Sixteen mechanical core objectives are the original sealed denominator. This is scoped contract acceptance including a mock empty-provider dependency and controlled planning probes. Actual model goal completion0/3 is a separate intelligence measure, not a redefined core denominator.'},
         'evidence_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.values()}}
 output=BASE/'core-workflow-review.json'
 assert not output.exists(),'Retain first mapped review'
 output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(result['summary']))


if __name__=='__main__':main()
