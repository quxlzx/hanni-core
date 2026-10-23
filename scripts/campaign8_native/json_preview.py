"""Read-only full preview/source measurement; no text assignment or downloads."""
import hashlib
import json
from uuid import UUID

def source_text(page):
    """Assemble the original serialized strings without numeric rewriting."""
    if page.get('format') != 'hanni-model-lab-v1' or not isinstance(page.get('run_json'), str) or (not isinstance(page.get('results_json'), list)) or any((not isinstance(v, str) for v in page['results_json'])) or (page.get('export_complete') is not True) or (page.get('next_offset') is not None):
        raise ValueError('The controlled source page must be a complete original serialized export.')
    text = '{"format":"hanni-model-lab-v1","run":' + page['run_json'] + ',"results":[' + ','.join(page['results_json']) + '],"export_complete":true}'
    if len(text.encode('utf8')) > 8 * 1024 ** 2:
        raise ValueError('Original source measurement exceeded its finite preview bound.')
    return text

def measure_json_preview(session, dom):
    fields = [v for v in dom.get('controls', []) if v.get('tag') == 'textarea' and v.get('name') == 'Complete benchmark JSON' and v.get('visible')]
    if not fields:
        return {'present': False}
    if len(fields) != 1 or fields[0].get('valueRedacted') or (not isinstance(fields[0].get('value'), str)):
        raise ValueError('The original preview field is ambiguous or withheld.')
    field = fields[0]
    text = field['value']
    if len(text.encode('utf8')) > 8 * 1024 ** 2:
        raise ValueError('Preview observation exceeded the original 8 MiB bound.')
    document = json.loads(text)
    run_id = str(UUID(document['run']['id']))
    from scripts.campaign8_native.development import authenticated_readback
    source = authenticated_readback(session, '/api/model-lab/export/' + run_id + '?representation=serialized')
    original = source_text(source['data']) if source['status'] == 200 else None
    return {'present': True, 'scope': 'Actual original field and authenticated serialized source; read-only', 'run_id': run_id, 'readOnly': field.get('readOnly'), 'source': source, 'utf8_bytes': len(text.encode('utf8')), 'utf16_length': len(text.encode('utf-16-le')) // 2, 'selectionStart': field.get('selectionStart'), 'selectionEnd': field.get('selectionEnd'), 'text_sha256': hashlib.sha256(text.encode('utf8')).hexdigest(), 'source_text_sha256': hashlib.sha256(original.encode('utf8')).hexdigest() if original is not None else None, 'entire_text_matches_source': original is not None and text == original, 'clipboard_or_download_effect': False}
