"""Independent receipt validators, never executors or synthetic success providers."""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
from typing import Any
VISUAL_WEIGHTS = {'typography': 0.2, 'hierarchy': 0.2, 'spacing': 0.15, 'density': 0.15, 'truthful_states': 0.15, 'windows_interaction': 0.1, 'finishing': 0.05}
FINAL_OPERATIONS = frozenset({'measure_layout', 'keyboard', 'fill_local', 'open_dialog', 'close_dialog', 'click_local', 'native_window', 'read_projection'})

def _finite_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)

def capture_receipt_errors(receipt: dict[str, Any], image_path: Path, owned_root: Path) -> list[str]:
    """Check provenance conformance; this is not itself a new native capture."""
    errors = []
    image_path, owned_root = (image_path.resolve(), owned_root.resolve())
    if not image_path.is_relative_to(owned_root):
        return ['capture is outside the owned artifact directory']
    window = receipt.get('window', {})
    capture = receipt.get('capture', {})
    if receipt.get('evidence_class') not in {'LIVE', 'CONTROLLED'}:
        errors.append('missing original evidence class')
    for key in ('pid', 'hwnd', 'dpi'):
        if type(window.get(key)) is not int or window[key] <= 0:
            errors.append(f'missing or invalid window {key}')
    if not _finite_number(window.get('create_time')) or window['create_time'] <= 0:
        errors.append('missing process creation identity')
    if not window.get('class') or not isinstance(window.get('class'), str):
        errors.append('missing window class')
    for name in ('rect', 'client_rect'):
        rect = window.get(name)
        if not isinstance(rect, list) or len(rect) != 4 or (not all((type(n) is int for n in rect))) or (rect[2] <= rect[0]) or (rect[3] <= rect[1]):
            errors.append(f'missing or invalid {name}')
    if window.get('dpi_scope') != 'current_windows_observed':
        errors.append('physical Windows DPI provenance is absent or emulated')
    if capture.get('method') not in {'owned_hwnd_printwindow', 'owned_hwnd_bitblt'}:
        errors.append('capture is not original owned HWND pixels')
    for key in ('pid_verified', 'create_time_verified', 'hwnd_verified'):
        if capture.get(key) is not True:
            errors.append(f'capture lacks {key}')
    if capture.get('scope') != 'owned_hanni_hwnd_only':
        errors.append('capture scope is not confined to the owned app')
    if not image_path.is_file():
        errors.append('capture image is absent')
    else:
        raw = image_path.read_bytes()
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            errors.append('capture is not a PNG')
        if capture.get('sha256') != hashlib.sha256(raw).hexdigest():
            errors.append('capture bytes do not match the receipt')
    return errors

def actual_capture_receipt_errors(receipt: dict[str, Any], *, session_identity: dict[str, Any], owned_root: Path) -> list[str]:
    """Validate Worker1's original flat PrintWindow receipt without inventing flags."""
    errors = []
    path = Path(receipt.get('path', '')).resolve()
    if not path.is_relative_to(owned_root.resolve()):
        return ['capture is outside the owned artifact directory']
    if receipt.get('method') != 'Win32 PrintWindow PW_RENDERFULLCONTENT':
        errors.append('capture is not original owned HWND pixels')
    if receipt.get('capture_scope') != 'Verified owned HWND client and native chrome only' or receipt.get('desktop_pixel_capture') is not False:
        errors.append('capture is not confined to the owned HWND')
    if receipt.get('evidence_class') not in {'CONTROLLED', 'LIVE'}:
        errors.append('missing original evidence class')
    for key in ('pid', 'create_time'):
        if receipt.get(key) != session_identity.get(key):
            errors.append('capture process identity differs from the original session')
    for key in ('pid', 'hwnd', 'dpi'):
        if type(receipt.get(key)) is not int or receipt[key] <= 0:
            errors.append(f'missing or invalid {key}')
    if not _finite_number(receipt.get('create_time')) or receipt['create_time'] <= 0:
        errors.append('missing process creation identity')
    if not isinstance(receipt.get('window_class'), str) or not receipt['window_class']:
        errors.append('missing window class')
    rect, size, client = (receipt.get('window_rect'), receipt.get('image_size'), receipt.get('client_region_verified'))
    if not isinstance(rect, list) or len(rect) != 4 or (not all((type(n) is int for n in rect))) or (not isinstance(size, list)) or (len(size) != 2) or (not all((type(n) is int and n > 0 for n in size))) or (size != [rect[2] - rect[0], rect[3] - rect[1]]):
        errors.append('native window and image dimensions disagree')
    if not isinstance(client, list) or len(client) != 4 or (not all((type(n) is int for n in client))) or (not isinstance(size, list)) or (len(size) != 2) or (not (0 <= client[0] < client[2] <= size[0] and 0 <= client[1] < client[3] <= size[1])):
        errors.append('verified client region is missing or outside capture')
    if not path.is_file():
        errors.append('capture image is absent')
    else:
        raw = path.read_bytes()
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            errors.append('capture is not a PNG')
        if hashlib.sha256(raw).hexdigest() != receipt.get('sha256'):
            errors.append('capture bytes do not match the receipt')
        from PIL import Image
        with Image.open(path) as pixels:
            if list(pixels.size) != size:
                errors.append('PNG dimensions do not match receipt')
    return errors

def control_coverage(inventory: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Dynamic occurrence coverage, with blocked/unknown controls kept visible."""
    ids = [item.get('id') for item in inventory]
    if any((not isinstance(cid, str) or not cid for cid in ids)) or len(set(ids)) != len(ids):
        raise ValueError('control inventory needs unique nonempty occurrence IDs')
    by_id: dict[str, list[dict[str, Any]]] = {cid: [] for cid in ids}
    extra = []
    for row in outcomes:
        if row.get('id') not in by_id:
            extra.append(row.get('id'))
        else:
            by_id[row['id']].append(row)
    counts = {name: 0 for name in ('pass', 'fail', 'blocked', 'unsupported', 'not_run', 'unknown')}
    classified = []
    for item in inventory:
        rows = by_id[item['id']]
        if not rows:
            status = 'not_run'
        elif len(rows) != 1:
            status = 'unknown'
        else:
            row = rows[0]
            status = row.get('status', 'unknown')
            if status not in counts:
                status = 'unknown'
            if status == 'pass' and (row.get('evidence_class') not in {'LIVE', 'CONTROLLED'} or row.get('native') is not True or row.get('assertions_verified') is not True or (not row.get('receipt_sha256')) or (type(row.get('unauthorized_effects')) is not int) or (row.get('unauthorized_effects') != 0)):
                status = 'unknown'
        counts[status] += 1
        classified.append({'id': item['id'], 'status': status, 'primary': item.get('primary', False), 'dangerous': item.get('dangerous', False)})
    primary_count = sum((row['primary'] is True for row in classified))
    return {'inventoried': len(inventory), 'counts': counts, 'extra_outcome_ids': extra, 'controls': classified, 'primary_count': primary_count, 'all_primary_controls_verified': primary_count > 0 and all((row['status'] == 'pass' for row in classified if row['primary'])), 'scope': 'Receipt coverage only; CONTROLLED is not live provider or model proof'}

def visual_result(dimensions: dict[str, Any], *, template_score: Any, native_capture_verified: bool, screenshot_sha256: str | None, critical_defects: list[str]) -> dict[str, Any]:
    if set(dimensions) != set(VISUAL_WEIGHTS):
        raise ValueError('every independent visual dimension is required')
    if any((not _finite_number(v) or not 0 <= v <= 10 for v in dimensions.values())):
        raise ValueError('visual scores must be finite numeric values from 0 through 10')
    if not _finite_number(template_score) or not 0 <= template_score <= 10:
        raise ValueError('template score must be finite and from 0 through 10')
    score = sum((dimensions[k] * VISUAL_WEIGHTS[k] for k in VISUAL_WEIGHTS))
    eligible = native_capture_verified is True and bool(screenshot_sha256)
    return {'score': round(score, 4), 'template_score': template_score, 'typography_score': dimensions['typography'], 'eligible': eligible, 'critical_defects': list(critical_defects), 'accepted': eligible and score >= 8.6 and (dimensions['typography'] >= 8.6) and (template_score <= 2) and (not critical_defects), 'score_scope': 'Independent screenshot judgment, not inferred from CSS or a font name'}

def final_input_errors(value: dict[str, Any]) -> list[str]:
    errors = []
    if 'expected' in value or 'oracle' in value:
        errors.append('executor input contains grading answers')
    if value.get('operation') not in FINAL_OPERATIONS:
        errors.append('unsupported final operation')
    if value.get('authority_mode') != 'owner_read_only':
        errors.append('unfrozen authority mode')
    return errors
