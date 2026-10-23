"""Fresh independently viewed Campaign 10 native presentation judgments.

Numbers below apply only to the actual 38 reviewed cycle-1 PNGs. Missing
interaction evidence remains null; no historical acceptance score is inherited.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import mean
WEIGHTS = {'typography': 0.2, 'hierarchy': 0.2, 'spacing': 0.15, 'density': 0.15, 'truthful_states': 0.15, 'windows_interaction': 0.1, 'finishing': 0.05}
JUDGMENTS = {'home': (8.7, 8.5, 8.8, 8.6, 6.5, 8.6, 1.1, 'Clear sections and readable metadata. Assistant ready conflicts with unavailable conversation; no current controller-ready readback for this frame.'), 'chat': (8.7, 8.9, 8.8, 8.8, 8.8, 8.7, 1.0, 'Unavailable composition is disabled with clear instructions; comfortable history/composer separation at both sizes.'), 'voice': (8.7, 8.8, 8.8, 8.4, 8.7, 8.6, 1.1, 'Unavailable/Not measured labels avoid physical success claims. Wide device section is still skeleton loading; compact controls wrap without overlap.'), 'planner': (8.7, 8.9, 8.8, 8.7, 8.8, 8.7, 1.1, 'Attention and upcoming events separate cleanly; compact layout stacks sections. Empty state does not invent work.'), 'tasks': (8.7, 8.9, 8.8, 8.8, 8.9, 8.7, 1.0, 'New-task action and filters are legible; empty state agrees with exact empty original-store readback.'), 'calendar': (8.7, 8.8, 8.8, 8.7, 8.8, 8.7, 1.1, 'Explicit no-events-loaded instruction and separate local deadlines. Connected indicates account metadata only; no provider event read is demonstrated.'), 'projects': (8.7, 8.8, 8.8, 8.8, 8.9, 8.7, 1.0, 'Simple master/detail empty state; typography and divisions remain clear at both sizes.'), 'memory': (8.7, 8.9, 8.7, 8.6, 8.9, 8.7, 1.0, 'LAYA disabled, stored count zero, search scope and review separation are readable; compact filters reflow into two columns.'), 'mission': (8.7, 8.8, 8.8, 8.6, 8.7, 8.6, 1.2, 'Telemetry and residency sections are clear; missing RAM is explicitly unavailable. Compact lower content requires scroll not exercised here.'), 'models': (8.65, 8.8, 8.7, 8.55, 8.8, 8.7, 1.2, 'Model filename wraps at compact width without horizontal overflow. Healthy/loaded state is distinguished from verified context and installed identity.'), 'agents': (8.7, 8.8, 8.7, 8.6, 8.9, 8.7, 1.1, 'Actual controller unavailable state and172 capabilities agree with readback; capability table and history remain legible.'), 'cluster': (8.65, 8.8, 8.7, 8.6, 8.9, 8.7, 1.1, 'Checking changes to unreachable across elapsed capture time; unavailable CPU/RAM are never zero. Compact filters stack; lower nodes require scroll.'), 'activity': (8.7, 8.8, 8.8, 8.8, 8.8, 8.7, 1.0, 'Separates execution from evidence checks; empty trace/history remains clear. Captured supplemental DOM/readback missing for this route.'), 'screen': (8.7, 8.9, 8.8, 8.8, 8.9, 8.7, 1.0, 'Capture/context unavailable and saved retention policy are explicit. Disabled analysis avoids a false screen-awareness claim.'), 'notifications': (8.7, 8.8, 8.8, 8.8, 8.9, 8.7, 1.0, 'Recorded events only, clear unread/category filters, and no false approval implication.'), 'settings': (8.65, 8.8, 8.7, 8.5, 8.7, 8.6, 1.1, 'Audio labels and next-start GPU state are clear. Wide GPU section remains loading; compact form stays inside viewport.'), 'mcp': (8.7, 8.9, 8.8, 8.7, 8.9, 8.7, 1.1, 'Zero connected/discovered tools agrees with original readback; approval explanation and empty state distinguish configuration from tool execution.'), 'workflows': (8.7, 8.9, 8.8, 8.8, 8.8, 8.7, 1.0, 'No-saved-workflow state is clear and describes approval before execution; does not establish working planning/model quality.'), 'model-routing': (8.65, 8.8, 8.7, 8.55, 8.8, 8.7, 1.1, 'Unverified context, unknown queue and unmeasured timing are explicit; compact endpoint metrics reflow. Current keyboard policy controls untested.')}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def review(repo):
    repo = Path(repo)
    raw = repo / 'data/campaign10-native/current-desktop-cycle1/RESULTS.json'
    data = json.loads(raw.read_text(encoding='utf-8'))
    if not data.get('complete') or not data.get('owned_native_cleanup'):
        raise ValueError('A complete owned-window capture and cleanup record is required.')
    if not data.get('cdp_attachment', {}).get('no_defaults'):
        raise ValueError('Native context defaults must remain original.')
    screenshots = data['screenshots']
    assert len(screenshots) == 38 and len(data['declared_routes']) == 19
    for capture in screenshots:
        if sha(capture['path']) != capture['sha256']:
            raise ValueError('Screenshot integrity failed.')
        assert capture['method'] == 'Win32 PrintWindow PW_RENDERFULLCONTENT'
        assert capture['desktop_pixel_capture'] is False and capture['dpi'] == 120
    screens = []
    for route, values in JUDGMENTS.items():
        typography, hierarchy, spacing, density, truthful, finishing, template, note = values
        dimensions = {'typography': typography, 'hierarchy': hierarchy, 'spacing': spacing, 'density': density, 'truthful_states': truthful, 'windows_interaction': None, 'finishing': finishing}
        viewed = [{'path': p['path'], 'sha256': p['sha256'], 'window_rect': p['window_rect']} for p in screenshots if Path(p['path']).stem.endswith('-' + route)]
        assert len(viewed) == 2
        screens.append({'route': route, 'dimensions': dimensions, 'weighted_complete_score': None, 'measured_presentation_score': round(sum((WEIGHTS[d] * v for d, v in dimensions.items() if v is not None)) / 0.9, 4), 'template_appearance': template, 'observations': note, 'viewed_captures': viewed})
    result = {'version': 1, 'reviewed_at': datetime.now(timezone.utc).isoformat(), 'state': 'PRESENTATION_MEASURED_FULL_VISUAL_ACCEPTANCE_INCOMPLETE', 'reviewer': 'independent Campaign10 verifier', 'source_receipt_sha256': sha(raw), 'source_sha256': data['source_sha256'], 'assets': data['assets'], 'executable_sha256': data['executable_sha256'], 'rubric': {'path': 'docs/campaign8/VISUAL_RUBRIC.md', 'sha256': sha(repo / 'docs/campaign8/VISUAL_RUBRIC.md'), 'weights': WEIGHTS}, 'actual_dpi': 120, 'actual_scaling_percent': 125, 'actual_window_sizes': [[1280, 850], [1000, 700]], 'viewed_screenshots': 38, 'routes': 19, 'template_max': max((s['template_appearance'] for s in screens)), 'minimum_typography': min((s['dimensions']['typography'] for s in screens)), 'mean_measured_presentation_score': round(mean((s['measured_presentation_score'] for s in screens)), 4), 'minimum_measured_presentation_score': min((s['measured_presentation_score'] for s in screens)), 'complete_weighted_visual_score': None, 'complete_visual_acceptance': None, 'all_route_horizontal_overflow_observed': False, 'javascript_errors': data['javascript_errors'], 'historical_scores_reused': False, 'screens': screens, 'limitations': ['No fresh keyboard/focus/minimize/restore evidence in route-only capture.', 'No lower-scroll reachability, Mini surface or populated-state evidence in this cycle.', 'Home ready/unavailable wording contradicts current controller presentation.', 'Wide voice/GPU settings include pending loading skeletons.', 'Account metadata availability does not establish live calendar provider reads.', 'No physical microphone, speaker, HANNI screen capture or perception evidence.']}
    target = repo / 'docs/campaign10/NATIVE_VISUAL_REVIEW_CYCLE1.json'
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return {key: result[key] for key in ('state', 'viewed_screenshots', 'minimum_typography', 'mean_measured_presentation_score', 'minimum_measured_presentation_score', 'complete_visual_acceptance')}

def review_cycle3(repo):
    """New judgments after normal text-launcher state, including failed captures."""
    repo = Path(repo)
    raw = repo / 'data/campaign10-native/current-desktop-cycle3/RESULTS.json'
    data = json.loads(raw.read_text(encoding='utf-8'))
    if not data.get('complete') or not data.get('owned_native_cleanup'):
        raise ValueError('Complete capture and owned-window cleanup are required.')
    if not data.get('cdp_attachment', {}).get('no_defaults'):
        raise ValueError('Native attachment must preserve original defaults.')
    captures = data['screenshots']
    assert len(captures) == 44 and len(data['declared_routes']) == 19
    for item in captures:
        assert sha(item['path']) == item['sha256']
        assert item['method'] == 'Win32 PrintWindow PW_RENDERFULLCONTENT'
        assert item['desktop_pixel_capture'] is False and item['dpi'] == 120
    judgments = dict(JUDGMENTS)
    judgments.update({'home': (8.7, 8.9, 8.8, 8.7, 8.9, 8.7, 1.1, 'Normal text-launcher readiness matches enabled composer and controller readback. Compact sections stack without overlap.'), 'chat': (8.7, 8.9, 8.8, 8.8, 8.9, 8.7, 1.0, 'Composer is enabled with the original text controller ready; history and empty state remain clear.'), 'voice': (8.7, 8.8, 8.8, 8.7, 8.9, 8.7, 1.1, 'Unavailable physical voice and unmeasured metrics are explicit; both device selectors now loaded. No physical audio evidence.'), 'agents': (8.7, 8.8, 8.7, 8.6, 8.9, 8.7, 1.1, 'Current ready controller and172 capabilities agree with original readback. Lower capability rows require separate scroll evidence.'), 'activity': (8.7, 8.8, 8.8, 8.8, 8.9, 8.7, 1.0, 'Execution and evidence checks remain distinct; exact current original trace/history readback is present.'), 'settings': (8.65, 8.8, 8.7, 8.6, 8.9, 8.6, 1.1, 'Audio defaults and GPU selection loaded at both widths; next-start scope explicit. Compact lower permissions require scrolling.')})
    screens = []
    for route, values in judgments.items():
        typography, hierarchy, spacing, density, truthful, finishing, template, note = values
        dims = {'typography': typography, 'hierarchy': hierarchy, 'spacing': spacing, 'density': density, 'truthful_states': truthful, 'windows_interaction': None, 'finishing': finishing}
        selected = [p for p in captures if Path(p['path']).stem in {'1280-' + route, '1000-' + route}]
        assert len(selected) == 2
        screens.append({'route': route, 'dimensions': dims, 'weighted_complete_score': None, 'measured_presentation_score': round(sum((WEIGHTS[d] * v for d, v in dims.items() if v is not None)) / 0.9, 4), 'template_appearance': template, 'observations': note, 'viewed_captures': [{'path': p['path'], 'sha256': p['sha256']} for p in selected]})
    failed = [p for p in captures if Path(p['path']).stem == 'restored-window' or Path(p['path']).stem.startswith('lower-')]
    assert len(failed) == 5
    result = {'version': 1, 'reviewed_at': datetime.now(timezone.utc).isoformat(), 'state': 'PRESENTATION_MEASURED_INTERACTION_CAPTURE_INCOMPLETE', 'reviewer': 'independent Campaign10 verifier', 'source_receipt_sha256': sha(raw), 'launcher_source_pin_sha256': data['source_sha256'], 'whole_source_freeze': False, 'assets': data['assets'], 'executable_sha256': data['executable_sha256'], 'rubric': {'path': 'docs/campaign8/VISUAL_RUBRIC.md', 'sha256': sha(repo / 'docs/campaign8/VISUAL_RUBRIC.md'), 'weights': WEIGHTS}, 'actual_dpi': 120, 'actual_scaling_percent': 125, 'actual_window_sizes': [[1280, 850], [1000, 700]], 'viewed_screenshots': 44, 'routes': 19, 'current_route_readbacks': len(data['current_route_readbacks']), 'template_max': max((s['template_appearance'] for s in screens)), 'minimum_typography': min((s['dimensions']['typography'] for s in screens)), 'mean_measured_presentation_score': round(mean((s['measured_presentation_score'] for s in screens)), 4), 'minimum_measured_presentation_score': min((s['measured_presentation_score'] for s in screens)), 'complete_weighted_visual_score': None, 'complete_visual_acceptance': None, 'keyboard_skip_link_focus_visible': True, 'win32_minimized_state_verified': data['minimize']['minimized'] is True, 'win32_restored_state_verified': data['restore']['minimized'] is False, 'restored_content_readability_verified': False, 'lower_scrolled_content_readability_verified': False, 'failed_interaction_captures': [{'path': p['path'], 'sha256': p['sha256'], 'observation': 'Native chrome visible but client content blank; DOM text is insufficient pixel evidence.'} for p in failed], 'javascript_errors': data['javascript_errors'], 'historical_scores_reused': False, 'screens': screens, 'limitations': ['Five post-minimize/restore PrintWindow frames cannot prove restored or lower-scroll readability; capture versus compositor cause unresolved.', 'No fresh Mini surface or populated-state review in this cycle.', 'Account metadata does not establish live calendar-provider reads.', 'No physical microphone, speaker, HANNI screen capture or perception evidence.']}
    (repo / 'docs/campaign10/NATIVE_VISUAL_REVIEW_CYCLE3.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return {key: result[key] for key in ('state', 'viewed_screenshots', 'minimum_typography', 'mean_measured_presentation_score', 'minimum_measured_presentation_score', 'complete_visual_acceptance')}

def review_cycle4(repo):
    """Complete primary-shell scores from viewed cycles3/4; Mini still absent."""
    repo = Path(repo)
    base_path = repo / 'docs/campaign10/NATIVE_VISUAL_REVIEW_CYCLE3.json'
    base = json.loads(base_path.read_text(encoding='utf-8'))
    raw = repo / 'data/campaign10-native/current-desktop-cycle4/RESULTS.json'
    data = json.loads(raw.read_text(encoding='utf-8'))
    assert data['complete'] and data['owned_native_cleanup'] and data['cdp_attachment']['no_defaults']
    assert data['assets'] == base['assets'] and data['executable_sha256'] == base['executable_sha256']
    assert len(data['screenshots']) == 16
    for item in data['screenshots']:
        assert sha(item['path']) == item['sha256'] and item['dpi'] == 120
        assert item['method'] == 'Win32 PrintWindow PW_RENDERFULLCONTENT' and item['desktop_pixel_capture'] is False
    assert data['minimize']['minimized'] and (not data['restore_resize']['minimized'])
    assert data['restore_resize']['window_rect'][2:] == [1001, 700]
    assert all((row['backend_readback']['status'] == 200 for row in data['current_route_readbacks']))
    screens = base['screens']
    for screen in screens:
        screen['dimensions']['windows_interaction'] = 8.6
        screen['weighted_complete_score'] = round(sum((WEIGHTS[key] * score for key, score in screen['dimensions'].items())), 4)
    result = {'version': 1, 'state': 'PRIMARY_VISUAL_THRESHOLDS_MET_MINI_NOT_MEASURED', 'reviewed_at': datetime.now(timezone.utc).isoformat(), 'reviewer': 'independent Campaign10 verifier', 'rubric': base['rubric'], 'historical_scores_reused': False, 'source_receipts': [{'path': 'data/campaign10-native/current-desktop-cycle3/RESULTS.json', 'sha256': base['source_receipt_sha256']}, {'path': 'data/campaign10-native/current-desktop-cycle4/RESULTS.json', 'sha256': sha(raw)}], 'cycle3_review_sha256': sha(base_path), 'assets': data['assets'], 'executable_sha256': data['executable_sha256'], 'cycle4_viewed_screenshots': 16, 'primary_routes': 19, 'actual_dpi': 120, 'actual_scaling_percent': 125, 'mean_primary_weighted_score': round(mean((row['weighted_complete_score'] for row in screens)), 4), 'minimum_primary_weighted_score': min((row['weighted_complete_score'] for row in screens)), 'minimum_typography': base['minimum_typography'], 'template_max': base['template_max'], 'primary_visual_thresholds_met': all((row['weighted_complete_score'] >= 8.6 for row in screens)), 'mini_score': None, 'complete_visual_acceptance': None, 'final_frozen_native_acceptance': False, 'screens': screens, 'supplemental_viewed_captures': [{'path': item['path'], 'sha256': item['sha256']} for item in data['screenshots']], 'interaction_observations': ['Tab reveals a clear skip-link focus ring.', 'Original owned HWND minimizes and restores; restored pixels render after1.2seconds settling,1pixel realresize,then1.2seconds settling.', 'Home recent activity, lower registered cluster nodes, settings interface/session controls and ModelLab eligibility/benchmark notes are readable before minimize.', 'Prior cycle3 blank PrintWindow frames are preserved; this supplemental repaint condition is not a production repair.'], 'limitations': ['Mini has no current independently viewed native pixels and cannot inherit Campaign8 score.', 'This is exposed visual development evidence before whole-source final freeze.', 'Only physical Windows125percent DPI observed; no other physical DPI claimed.', 'Route-specific keyboard actions and populated workflow/calendar states were not exhaustively exercised.', 'Physical voice, HANNI screen acquisition and live calendar-provider outcomes remain unverified.']}
    (repo / 'docs/campaign10/NATIVE_VISUAL_PRIMARY_REVIEW.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return {key: result[key] for key in ('state', 'mean_primary_weighted_score', 'minimum_primary_weighted_score', 'minimum_typography', 'complete_visual_acceptance')}

def review_mini_cycle3(repo):
    """Independent Mini pixel judgment; missing keyboard/minimize stays null."""
    repo = Path(repo)
    raw = repo / 'data/campaign10-native/current-mini-cycle3/RESULTS.json'
    data = json.loads(raw.read_text(encoding='utf8'))
    primary_path = repo / 'docs/campaign10/NATIVE_VISUAL_PRIMARY_REVIEW.json'
    primary = json.loads(primary_path.read_text(encoding='utf8'))
    assert data['complete'] and data['owned_native_cleanup'] and data['cdp_attachment']['no_defaults']
    assert data['assets'] == primary['assets'] and data['executable_sha256'] == primary['executable_sha256']
    captures = data['screenshots']
    assert len(captures) == 2 and [item['image_size'] for item in captures] == [[620, 560], [525, 560]]
    for item in captures:
        assert sha(item['path']) == item['sha256'] and item['dpi'] == 120
        assert item['method'] == 'Win32 PrintWindow PW_RENDERFULLCONTENT' and item['desktop_pixel_capture'] is False
    assert all((not row['dom']['horizontalOverflow'] for row in data['mini_captures']))
    pin = [row for row in data['bridge_checks'] if row['input']['method'] == 'pin']
    assert [row['after']['topmost'] for row in pin] == [True, False]
    assert data['after_expand']['main']['visible'] and (not data['after_expand']['mini']['visible'])
    assert data['readback']['status'] == 200
    dimensions = {'typography': 8.7, 'hierarchy': 8.8, 'spacing': 8.7, 'density': 8.6, 'truthful_states': 8.8, 'windows_interaction': None, 'finishing': 8.7}
    result = {'version': 1, 'state': 'MINI_PRESENTATION_MEASURED_WINDOWS_INTERACTION_INCOMPLETE', 'reviewed_at': datetime.now(timezone.utc).isoformat(), 'reviewer': 'independent Campaign10 verifier', 'source_receipt_sha256': sha(raw), 'assets': data['assets'], 'executable_sha256': data['executable_sha256'], 'rubric': primary['rubric'], 'historical_scores_reused': False, 'dimensions': dimensions, 'measured_presentation_score': round(sum((WEIGHTS[k] * v for k, v in dimensions.items() if v is not None)) / 0.9, 4), 'weighted_complete_score': None, 'template_appearance': 1.0, 'actual_dpi': 120, 'actual_scaling_percent': 125, 'physical_window_sizes': [[620, 560], [525, 560]], 'requested_narrow_width': 480, 'enforced_minimum_physical_width': 525, 'viewed_screenshots': 2, 'viewed_captures': [{'path': p['path'], 'sha256': p['sha256']} for p in captures], 'loaded_font_observation': data['mini_fonts'], 'original_backend_readback': {'path': data['readback']['path'], 'status': data['readback']['status'], 'scope': 'Current workspace feature/configuration readback; no submitted chat generation or acoustic operation.'}, 'observations': ['Segoe UI controls and text are readable at both actual widths; heading, inactive voice row and composer have clear hierarchy.', 'No overlap or inaccessible horizontal clipping; the narrow requested width480 is constrained to actual525.', 'Inactive voice actions are disabled; empty composer keeps Send disabled.', 'Actual owned Mini HWND pin switches topmost true then false; original get_state and expand bridges succeed.', 'Expansion hides Mini and shows the main conversation; no chat generation or physical voice outcome was attempted.'], 'limitations': ['Mini was shown through owned HWND control for pixel evidence; the original main Open Mini menu path is not verified.', 'Mini keyboard traversal, keyboard activation and a real minimize/restore cycle are absent; Windows interaction remains unmeasured.', 'Two prior failed Mini capture attempts are retained and do not become presentation failures.', 'This is exposed visual development evidence before the whole-source final freeze.'], 'complete_visual_acceptance': None, 'final_frozen_native_acceptance': False}
    target = repo / 'docs/campaign10/NATIVE_VISUAL_MINI_REVIEW_CYCLE3.json'
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    combined = {'version': 1, 'state': 'PRIMARY_THRESHOLDS_MET_MINI_INTERACTION_NOT_MEASURED', 'primary_review_sha256': sha(primary_path), 'mini_review_sha256': sha(target), 'primary_routes': 19, 'mean_primary_weighted_score': primary['mean_primary_weighted_score'], 'minimum_primary_weighted_score': primary['minimum_primary_weighted_score'], 'mini_measured_presentation_score': result['measured_presentation_score'], 'mini_weighted_complete_score': None, 'minimum_typography': min(primary['minimum_typography'], dimensions['typography']), 'template_max': max(primary['template_max'], result['template_appearance']), 'complete_visual_acceptance': None, 'final_frozen_native_acceptance': False, 'historical_scores_reused': False}
    (repo / 'docs/campaign10/NATIVE_VISUAL_COMBINED_REVIEW.json').write_text(json.dumps(combined, indent=2) + '\n', encoding='utf8')
    return combined

def review_mini_cycle5(repo):
    """Add actual restore evidence without inferring absent keyboard focus."""
    repo = Path(repo)
    base_path = repo / 'docs/campaign10/NATIVE_VISUAL_MINI_REVIEW_CYCLE3.json'
    result = json.loads(base_path.read_text(encoding='utf8'))
    raw = repo / 'data/campaign10-native/current-mini-cycle5/RESULTS.json'
    data = json.loads(raw.read_text(encoding='utf8'))
    assert data['complete'] and data['owned_native_cleanup'] and data['cdp_attachment']['no_defaults']
    assert data['assets'] == result['assets'] and data['executable_sha256'] == result['executable_sha256']
    assert len(data['screenshots']) == 4
    for item in data['screenshots']:
        assert sha(item['path']) == item['sha256'] and item['dpi'] == 120
        assert item['method'] == 'Win32 PrintWindow PW_RENDERFULLCONTENT' and item['desktop_pixel_capture'] is False
    assert data['mini_minimize']['minimized'] and (not data['mini_restore']['minimized'])
    assert data['mini_restored_pixels']['image_size'] == [621, 560]
    assert data['mini_keyboard']['dom']['focused']['tag'] == 'BODY'
    result.update(reviewed_at=datetime.now(timezone.utc).isoformat(), source_receipt_sha256=sha(raw), prior_mini_review_sha256=sha(base_path), viewed_screenshots=4, viewed_captures=[{'path': p['path'], 'sha256': p['sha256']} for p in data['screenshots']], actual_minimize_verified=True, actual_restore_verified=True, restored_pixels_readable=True, restore_pixel_precondition='Settling plus real620-to621 pixel resize before restored capture.', keyboard_input_layer=data['keyboard_input_layer'], keyboard_focus_control_verified=False, keyboard_activation_verified=False, native_foreground_verified=False, native_focus_errors=[data['native_focus_error'], data['restored_native_focus_error']])
    result['observations'].append('Owned Mini minimizes and restores; rendered restored content is readable after settling and a1pixel realresize.')
    result['limitations'][1] = 'CDP Tab traversal ends on BODY without a visible focused control; no keyboard activation is shown. Two SetForegroundWindow calls failed. Windows interaction remains unmeasured.'
    result['limitations'].append('Conditional restored repaint does not demonstrate immediate repaint or repair the preserved earlier blank primary captures.')
    target = repo / 'docs/campaign10/NATIVE_VISUAL_MINI_REVIEW_CYCLE5.json'
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    combined_path = repo / 'docs/campaign10/NATIVE_VISUAL_COMBINED_REVIEW.json'
    combined = json.loads(combined_path.read_text(encoding='utf8'))
    combined.update(mini_review_sha256=sha(target), mini_review='NATIVE_VISUAL_MINI_REVIEW_CYCLE5.json', mini_restore_measured=True, mini_keyboard_focus_control_verified=False, native_foreground_verified=False)
    combined_path.write_text(json.dumps(combined, indent=2) + '\n', encoding='utf8')
    return combined
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--cycle', type=int, choices=[1, 3, 4, 5], default=1)
    parser.add_argument('--mini', action='store_true')
    args = parser.parse_args()
    fn = review_mini_cycle5 if args.mini and args.cycle == 5 else review_mini_cycle3 if args.mini else review if args.cycle == 1 else review_cycle3 if args.cycle == 3 else review_cycle4
    print(json.dumps(fn(Path(__file__).resolve().parents[2])))
