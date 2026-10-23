"""Post-run source accounting; never an execution or model-quality oracle."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from .assessments import build as action_assessments, candidates, reviewed_groups
from .scorecard import build, markdown

def stream_assessments(source, review_path):
    review = json.loads(Path(review_path).read_text(encoding='utf8'))
    required = ('raw_SSE_equals_original_API', 'raw_SSE_equals_persisted_SQLite_assistant', 'full_native_render_equals_API_in_two_samples')
    if not all((review['assertions'].get(k) is True for k in required)):
        raise ValueError('Actual transport/storage/native correspondence is required.')
    for item in review['evidence']:
        if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Independently reviewed streaming evidence changed.')
    native_path = review['evidence'][0]['path']
    raw = json.loads(Path(native_path).read_text(encoding='utf8'))
    controls = [r for m in source['modules'] for r in m['controls']]
    routes = [r['route'] for r in source['routes']]
    rows = []
    for action in raw['actions']:
        step = action['input']
        if not (step.get('selector') == '#chat-input' or step.get('name') == 'Send message'):
            continue
        matched = candidates(controls, step, 'chat', routes)
        if len(matched) != 1:
            raise ValueError('Actual composer action lacks a unique declaration.')
        evidence = {'file': native_path, 'action_id': action['id'], 'input': step, 'actual_assets': raw['assets'], 'evidence_class': 'GENUINE_EXISTING_MODEL'}
        rows.append({'source_slot_ids': [matched[0]['id']], 'outcome': 'PASS', 'reason': 'Actual original native composer action on the second bounded existing-model request; independently verified raw SSE, API, SQLite and fully settled native rendering agree. No general semantic-quality or Mini-surface pass.', 'action_evidence': [evidence], 'readback_evidence': [{'file': str(review_path), 'scope': review['scope'], 'assertions': {k: review['assertions'][k] for k in required}}], 'evidence_references': [evidence, {'file': str(review_path)}], 'semantic_readback': review['verdict'], 'coverage_scope': 'One bounded actual existing-model native text request and original storage/render correspondence, not tool selection or semantic benchmark quality.'})
    return rows

def residual(row):
    component = row['component']
    line = row.get('_mapping_anchor_line')
    if line is None:
        line = row['line']
    label = row['declaration']['label']
    if component in {'ComputeWorkers', 'ComputeJobs'}:
        return ('Original disposable deployment has workers=[] and no distributed compute jobs. This per-worker/job row or review dialog has no concrete instance; real cluster/compute control remains outside the no-process/no-remote-write test authority.', 'absent_worker_or_job_instance')
    if component == 'WorkflowCollaborationView':
        return ('The original manually seeded workflows have no collaboration participants/rounds. These per-participant receipt summaries have no rendered instance. No collaborative/model success is inferred from seeded local history.', 'absent_collaboration_instance')
    if component == 'NodePower':
        return ('Original isolated node power operations are disabled; no pending power request was created. This confirmation/cancel variant therefore has no dialog instance. No reboot/sleep/SSH operation is invoked.', 'unavailable_power_confirmation')
    if component == 'GpuSettings':
        return ('Original controlled GPU discovery returns503 with no device choice; the original selector/Apply gate requires devices.length>0. Refresh failure is independently observed; no GPU placement, configuration Apply or restart is claimed.', 'unavailable_gpu_dependency')
    if component == 'WorkflowsPage':
        return ('Original workflow status reports runner/controller unattached and goal.submit disabled. The New goal form cannot be opened through its original gate, so its fields/cancel/submit have no eligible rendered instance. Seeded completed history is a separate scope.', 'unavailable_goal_submission')
    if component == 'WorkflowDetailView':
        if line in {553, 560}:
            return ('This is the unavailable-detail fallback branch. The original selected synthetic workflow resolves successfully, so the fallback Back/Refresh control is absent; the normal detail Back/Refresh controls are separately exercised.', 'absent_error_fallback')
        if line == 605:
            return ('Original goal summary appears only for goal.length>180. Both bounded original seeded goals are shorter; this long-goal expansion instance is absent. No source-only visibility or expansion pass is credited.', 'absent_long_goal_variant')
        if line in {1069, 1108}:
            return ('Original plan/step approval actions are disabled by the unattached runner/controller. No approval-review dialog was opened; binding and Keep reviewing are conditional dialog instances, not missing handlers.', 'unavailable_approval_dialog')
        if line == 1133:
            return ('The output dialog was opened and closed with Escape in independent native evidence. This Close button is a distinct unclicked input gesture for the same original dialog closure, so it retains NOT_RUN rather than visibility credit.', 'equivalent_close_gesture_unobserved')
        return ('The original runner/controller is unattached, so retry/execution authority is unavailable. Read-only completed workflow detail, arguments, artifact and history controls are reviewed separately; this conditional declaration has no additional native action receipt.', 'unavailable_or_unobserved_workflow_variant')
    if component == 'ProjectView':
        return ('Original isolated project context has no explicit workflow links/verified workflow results. This Inspect/workflow row/Unlink requires such a relation and is absent. Project note/context and alias add/remove are separate observed original-service scopes.', 'absent_linked_workflow_instance')
    if component == 'MemoryPage':
        return ('The original review fixtures contain add proposals, without the target_id needed by Inspect target record. This correction-target branch is not rendered; actual proposal generation/review/record correction are separately scoped.', 'absent_targeted_suggestion_variant')
    if component == 'ModelLabPage':
        if label == 'Download JSON':
            return ('This optional browser download is not rendered when the actual native pywebview bridge exists. Native View JSON is tested through exact serialized text/selection without changing download policy; this separate browser file-delivery branch is NOT_RUN.', 'browser_only_download_variant')
        if label in {'View JSON', 'Complete benchmark JSON', 'Select JSON', 'Close'}:
            return ('The current bounded JSON viewer is a newly approved frontend repair after faithful native downloads were canceled. These exact new controls require their separately sealed native Results/Compare text/selection/closure afterproof; historical Blob-only export receipts do not establish success.', 'new_json_view_afterproof_pending')
        if line in {1029, 1054}:
            return ('Original routing-only run history now contains real persisted results. These alternate history-row title/Inspect buttons were not independently clicked; the current-run Inspect result and case detail paths are separately verified. This is an enabled shared-handler/view gap, not a missing-model dependency.', 'alternate_history_inspect_unobserved')
        if line in {1069, 1076}:
            return ('Original isolated history contains fewer than51 runs and history_has_more=false. Next runs is disabled; Previous is disabled on page0. Case pagination100+1 is genuinely exercised separately; no artificial51-run history was created.', 'absent_run_history_page')
        if line == 731:
            return ('Original model-required endpoint options are disabled by benchmark eligibility on the controlled unavailable model. Routing-development explicitly disables the endpoint field because it uses no model. No eligible model option selection is possible in this fixture.', 'unavailable_benchmark_endpoint')
        if line == 1101:
            return ('The Benchmark runner Resume checkpoint control is genuinely exercised with original durable continuation. This Results-tab duplicate declaration is not clicked independently; no pass is inherited merely from the shared handler.', 'duplicate_view_control_unobserved')
        return ('This per-endpoint quality/history row requires original measured benchmark evidence for that endpoint. The fixture has no genuine model evaluations; routing-only results have endpoint_id=None. The endpoint-specific Inspect variant is absent or unobserved.', 'absent_endpoint_quality_variant')
    if component == 'ModelRoutingPage':
        if line == 257:
            return ('Original model-routing GET loads successfully, so the error-only Retry loading branch is absent. Refresh endpoints and policy actions have independent native/readback evidence.', 'absent_error_fallback')
        return ('This exclusion-details summary requires an original failed-selection decision with exclusions. No model request/selection is dispatched in this unavailable fixture, so that concrete decision-detail branch is absent.', 'absent_routing_decision_variant')
    if component == 'Mini':
        return ('Default isolated fixtures have no attached inference controller, so Mini Send is disabled there. A separate exactly-one-request genuine Mini extension is manager-authorized and remains a distinct pending scope until actual request-time identity/resource admission and native evidence are recorded.', 'genuine_mini_extension_pending')
    if component == 'ConversationScreen':
        if line == 231:
            return ('Original Clear history requires ready=true and an idle controller. Default fixtures are unattached; actual owned history clear/token rotation was independently verified through original HTTP after streaming, not by clicking this distinct native button.', 'native_clear_variant_unobserved')
        if line == 258:
            return ('Original isolated display history never exceeds the loaded message page. hasOlder is false, so the older-message control has no rendered instance. Memory/Activity paging is not chat-history paging evidence.', 'absent_older_chat_page')
        return ('No native chat tool execution occurred; the real bounded response used no tools. This per-tool trace summary has no concrete tool event instance.', 'absent_chat_tool_event')
    if component == 'ToolActivity' or component == 'ExecutionTracePanel':
        return ('Original fixture has no live assistant tool-call trace for this per-event branch. Separate Activity audit records and filters are genuinely reviewed, but they do not create a model tool-event row or detailed execution trace.', 'absent_live_tool_trace')
    if component in {'App', 'HomeScreen'}:
        if component == 'App' and line == 1230:
            return ('The original inspector is opened and dismissed through its own accessible control in native evidence. Review settings is an enabled alternate Settings-navigation button within that inspector, but has no direct click receipt; sidebar Settings navigation is a separate observed scope.', 'alternate_settings_navigation_unobserved')
        if line in {132, 984, 1378}:
            return ('The non-inference fixtures have empty conversation history, so this per-message navigation row is absent. Genuine stream rendering was separately tested in Conversation; no recent-message row navigation is inferred.', 'absent_message_navigation_variant')
        if line == 1396:
            return ('The palette routing result was selected in native evidence, but this distinct capability-result preparation branch was not selected. It requires a capability-matching palette query; no pass is inherited from screen-route selection.', 'distinct_palette_result_unobserved')
        if line in {288, 302}:
            return ('Dialogs were opened and closed through their actual Cancel/Escape actions. This backdrop-click/Close-icon declaration is a distinct input gesture with no direct action receipt, not a missing close handler.', 'equivalent_close_gesture_unobserved')
        if line == 1441:
            return ('This shared confirmation button includes destructive session/model shutdown and owned-history clear variants. Stop confirmations were deliberately cancelled; owned history clear is verified through original HTTP only. No native confirmation pass is inherited.', 'confirmation_variant_unobserved')
        return ('This conditional App navigation/status/data variant has no distinct source-bound action receipt. Shared route navigation and local state actions are independently scoped; those passes do not establish every alternate rendered declaration.', 'distinct_app_variant_unobserved')
    if component == 'Modal' or component == 'FeatureDialog':
        return ('Actual dialog opening/focus/Cancel/Escape closure is independently reviewed. This backdrop/close declaration has no distinct direct click receipt; equivalent closure does not establish every input gesture.', 'equivalent_close_gesture_unobserved')
    if component == 'WorkspacePage':
        if line in {837, 845}:
            return ('The original Planner Upcoming calendar panel has this enabled local refresh/navigation control despite the disconnected Google provider. Calendar-page refresh/navigation and Planner filters are independently tested, but this distinct Planner declaration was not clicked. Provider absence is not a handler or permission block.', 'alternate_planner_calendar_control_unobserved')
        return ('Original empty Google vault and controlled provider failure prevent eligible external calendar actions. Local task/project/note/link handlers are tested separately; a provider-dependent or alternate calendar branch cannot inherit local CRUD success.', 'unavailable_calendar_variant')
    if component == 'MCPHubPage' and line == 591:
        return ('This is the removed-server fallback Back to servers branch. The actual selected configuration remains present in the controlled fixture, so this error fallback is absent; normal All servers/remount navigation is separately exercised.', 'absent_removed_server_fallback')
    return ('Actual original fixture did not render or directly exercise this specific conditional data/view variant. The source predicate below remains explicit; no visibility-only or shared-handler pass is inferred.', 'unobserved_conditional_variant')

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--review', type=Path, action='append', required=True)
    parser.add_argument('--anchor-inventory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Preserve prior coverage and grading checkpoints.')
    source = json.loads(args.inventory.read_text(encoding='utf8'))
    groups = reviewed_groups(args.review)
    controls, correspondence = (None, None)
    if args.anchor_inventory:
        from .rebase import controls_with_anchors
        previous = json.loads(args.anchor_inventory.read_text(encoding='utf8'))
        controls, correspondence = controls_with_anchors(source, previous)
    assessments, unmatched = action_assessments(source, groups, controls_override=controls)
    assessments += stream_assessments(source, 'docs/campaign8/STREAMING_REVIEW_CYCLE2.json')
    value = build(source, source_file=args.inventory.as_posix(), assessments=assessments)
    if controls is not None:
        anchored = {row['id']: row for row in controls}
        for row in value['rows']:
            for key in ('_mapping_anchor_line', '_mapping_anchor_id'):
                if key in anchored[row['id']]:
                    row[key] = anchored[row['id']][key]
    references = [{'file': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'scope': 'Independent original native/readback fixture state; neither visibility nor absence establishes PASS.'} for p in args.review]
    for row in value['rows']:
        if row['outcome'] == 'NOT_RUN':
            explanation, classification = residual(row)
            row['reason'] = explanation
            row['residual_classification'] = classification
            row['actual_render_predicates'] = row.get('render_boundaries', [])
            row['evidence_references'] += references
        elif row['outcome'] == 'BLOCKED' and row['component'] == 'MCPHubPage':
            row['reason'] = 'This external Test & Discover/Refresh/Reconnect/Disconnect branch has no actual SDK/provider operation receipt. The separate explicitly inert initialization/list fixture exercises original config-hash approval and manager Enable/Disable with mocked leaves; it does not establish this SDK/network/process action or live-provider connection.'
            row['evidence_references'] += references
    value['inventory_sha256'] = hashlib.sha256(args.inventory.read_bytes()).hexdigest()
    value['unmatched_reviewed_steps'] = unmatched
    value['structural_source_correspondence'] = correspondence
    if args.anchor_inventory:
        value['anchor_inventory'] = {'file': args.anchor_inventory.as_posix(), 'sha256': hashlib.sha256(args.anchor_inventory.read_bytes()).hexdigest()}
    value['residual_counts'] = dict(Counter((r.get('residual_classification') for r in value['rows'] if r['outcome'] == 'NOT_RUN')))
    value['universal_functional_acceptance'] = False
    value['fraction_reason'] = 'Every static declaration is accounted for, but declarations are not concrete control instances. Explicit remaining NOT_RUN, BLOCKED and NOT_IMPLEMENTED scopes are retained; no universal eligible functional fraction is inferred.'
    args.output.mkdir(parents=True)
    for name, obj in [('STATIC_SCORECARD.json', value), ('UNMATCHED.json', unmatched)]:
        (args.output / name).write_text(json.dumps(obj, indent=2) + '\n', encoding='utf8', newline='\n')
    (args.output / 'STATIC_SCORECARD.md').write_text(markdown(value), encoding='utf8', newline='\n')
    print(json.dumps({'slots': value['static_slot_count'], 'outcomes': value['outcome_counts'], 'residuals': value['residual_counts']}))
if __name__ == '__main__':
    main()
