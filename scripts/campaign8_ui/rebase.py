"""Structural source-locator correspondence, never current behavior proof."""
from collections import defaultdict
import json

def signature(row):
    return (row['component'], row['tag'], json.dumps(row['attributes'], sort_keys=True, ensure_ascii=False), row.get('static_child_text', ''))

def controls_with_anchors(current, previous):
    """Keep current IDs/lines; attach old matcher lines only on unique identity.

    Historical raw asset identities remain on action receipts. This mapping
    merely relocates unchanged JSX declarations after a narrow source edit.
    Renamed, modified, new or ambiguous declarations get no inherited anchor.
    """
    old_modules = {m['file']: m for m in previous['modules']}
    rows, matches, excluded = ([], [], [])
    for module in current['modules']:
        old = old_modules.get(module['file'])
        unchanged = current['source_hashes'].get(module['file']) == previous['source_hashes'].get(module['file'])
        previous_by_signature = defaultdict(list)
        current_by_signature = defaultdict(list)
        for row in (old or {}).get('controls', []):
            previous_by_signature[signature(row)].append(row)
        for row in module['controls']:
            current_by_signature[signature(row)].append(row)
        for original_row in module['controls']:
            row = dict(original_row)
            key = signature(row)
            candidates = previous_by_signature[key]
            anchor = None
            if unchanged:
                anchor = next((r for r in candidates if r['id'] == row['id']), None)
            elif len(candidates) == 1 and len(current_by_signature[key]) == 1:
                anchor = candidates[0]
            if anchor:
                row['_mapping_anchor_line'] = anchor['line']
                row['_mapping_anchor_id'] = anchor['id']
                matches.append({'current_id': row['id'], 'previous_id': anchor['id'], 'file': module['file'], 'file_bytes_unchanged': unchanged, 'scope': 'Exact unchanged declaration correspondence only; historical action retains its actual assets, not a fresh current-code execution.'})
            else:
                row['_mapping_anchor_line'] = None
                excluded.append({'current_id': row['id'], 'file': module['file'], 'reason': 'New/changed/ambiguous declaration lacks a unique unchanged structural anchor.'})
            rows.append(row)
    return (rows, {'matched': matches, 'excluded': excluded, 'historical_assets_are_not_current_execution': True})
