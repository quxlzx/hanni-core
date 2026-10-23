"""Concise evidence presentation. Model claims are never spoken as action receipts."""
import json
from urllib.parse import urlsplit


def receipt_answer(task):
    for action in task.get('actions', []):
        receipt = action.get('receipt') or {}
        verification = receipt.get('verification') or {}
        if (action['spec']['target']=='windows' and receipt.get('ok')
                and verification.get('status')=='VERIFIED' and verification.get('independent') is True):
            message = str(receipt.get('message',''))[:160]
            if message:
                return 'HANNI independently verified this action: '+message+' The report and remaining evidence are in the Hermes tab.'
    for action in task.get('actions', []):
        receipt = action.get('receipt') or {}
        if not receipt.get('ok'):
            continue
        if action['spec']['target'] == 'windows':
            if (receipt.get('verification') or {}).get('verified') is True and (receipt.get('verification') or {}).get('independent') is True:
                message = str(receipt.get('message', ''))[:160]
                if message:
                    return 'HANNI verified this action: '+message+' Review the full task evidence in the Hermes tab.'
            continue
        data = receipt.get('data') or {}
        structured = data.get('structuredContent') or data.get('structured_content')
        if structured is None:
            for block in data.get('content', []):
                if block.get('type') == 'text':
                    try:
                        structured = json.loads(block.get('text', ''))
                    except (ValueError, TypeError):
                        continue
                    break
        if not isinstance(structured, dict):
            continue
        results = structured.get('results')
        if isinstance(results, list) and results and isinstance(results[0], dict):
            first = results[0]
            title, url = first.get('title'), first.get('url')
            if isinstance(title, str) and isinstance(url, str):
                parsed = urlsplit(url)
                if parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username and not parsed.password:
                    # Source title is quoted, never treated as an instruction or a verified action claim.
                    title = ' '.join(title.split())[:100]
                    text = f'The search returned “{title}” at {url[:250]}.'
                    if structured.get('unresponsive_engines'):
                        text += ' Some search engines were unavailable.'
                    return text
    return 'Hermes returned a report. Review its model claims and execution evidence in the Hermes tab; full goal completion has not been independently verified.'
