"""Short presentations of typed, already-verified evidence, never execution."""
import math
import re

from hanni.core.response_style import sanitize_assistant_text

SIMPLE_READS = frozenset({'system.stats', 'system.os_info', 'system.battery',
                          'process.top_cpu', 'process.top_memory', 'disk.usage',
                          'disk.free_space', 'time.now'})


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def present_read(name, result):
    data = result.get('data') or {}
    if not result.get('ok') or (result.get('verification') or {}).get('status') == 'UNVERIFIED':
        return None
    if name == 'system.stats' and all(_number(data.get(k)) for k in ('cpu_percent', 'ram_percent')):
        return f"CPU is at {data['cpu_percent']:.0f} percent; RAM is at {data['ram_percent']:.0f} percent."
    if name in {'process.top_cpu', 'process.top_memory'}:
        rows = data.get('processes') or []
        if rows and isinstance(rows[0], dict):
            row = rows[0]
            label = sanitize_assistant_text(str(row.get('name', 'The top process')))
            if name == 'process.top_cpu' and _number(row.get('cpu_percent')):
                return f"{label} is the largest CPU user, at {row['cpu_percent']:.1f} percent in this sample."
            if name == 'process.top_memory' and _number(row.get('rss_mb')):
                return f"{label} uses the most RAM, about {row['rss_mb'] / 1024:.1f} GB."
    if name == 'disk.usage':
        rows = data.get('drives') or []
        parts = [f"{row['drive']} has {row['free_gb']:.1f} GB free" for row in rows[:4]
                 if isinstance(row, dict) and isinstance(row.get('drive'), str) and _number(row.get('free_gb'))]
        if parts:
            return '; '.join(parts) + '.'
    if name == 'disk.free_space' and _number(data.get('free_gb')):
        answer = f"{data.get('drive', 'The drive')} has {data['free_gb']:.1f} GB free."
        if data.get('needed_gb'):
            answer += ' That is ' + ('enough' if data.get('sufficient') else 'not enough') + ' for the requested size.'
        return answer
    if name in {'time.now', 'system.os_info', 'system.battery'}:
        return sanitize_assistant_text(str(result.get('message') or '')) or None
    return None


def concise_receipts(results):
    """Combine verified results, keeping failures/uncertainty rather than guesses."""
    parts, unconfirmed = [], False
    for name, _, result, read in results:
        status = (result.get('verification') or {}).get('status', 'UNVERIFIED')
        if not result.get('ok'):
            text = sanitize_assistant_text(str(result.get('message') or 'The requested check failed.'))
        elif status == 'UNVERIFIED':
            unconfirmed = True
            if name.startswith('mcp.'):
                continue  # External excerpts retain their original untrusted-data path.
            if read:
                continue
            text = sanitize_assistant_text(str(result.get('message') or 'The action was attempted.'))
            # Only attempted/accepted wording is safe without outcome evidence.
            if re.search(r'\b(?:successfully|completed|created|deleted|sent|changed)\b', text, re.I):
                text = 'The action was attempted.'
        else:
            text = present_read(name, result) if read else None
            text = text or sanitize_assistant_text(str(result.get('message') or 'The tool returned supporting evidence.'))
        if text and text not in parts:
            parts.append(text)
        if status == 'PARTIALLY_VERIFIED' and (result.get('verification') or {}).get('scope') == 'calendar_creation_receipt':
            caveat = 'The provider returned an event receipt; independent verification is unavailable.'
            if caveat not in parts:
                parts.append(caveat)
    if unconfirmed:
        parts.append('I could not verify the remaining requested outcome.')
    return ' '.join(parts)
