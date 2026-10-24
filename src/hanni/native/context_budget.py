"""The shared native-loop compression threshold, reserving room for output."""


def compression_threshold(model, max_tokens):
    return max(1024, int(model.get('context_length', 16384)) - max_tokens - 2048)


def transfer_context(context, *, max_encoded_chars=34000):
    """Bound the bridge package, including JSON escaping and large retry receipts.

    The current task prompt is transported separately and is never shortened.
    History and original receipts remain available in their durable stores.
    """
    import json
    result = json.loads(json.dumps(context))
    marker = '\n[excerpt; retrieve full history or original task receipts]\n'
    if len(json.dumps(result)) > max_encoded_chars and result.get('previous_tool_receipts'):
        result['previous_tool_receipts'] = [{'ok': receipt.get('ok'), 'receipt_excerpt':
            (lambda text: text if len(text) <= 8000 else text[:4000] + marker + text[-4000:])(json.dumps(receipt)),
            'truncated': True} for receipt in result['previous_tool_receipts'] if isinstance(receipt, dict)]
        result['context_transfer_excerpt'] = True
    def strings(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, str) and len(item) > 100:
                    yield value, key, item
                elif isinstance(item, (dict, list)):
                    yield from strings(item)
        elif isinstance(value, list):
            for key, item in enumerate(value):
                if isinstance(item, str) and len(item) > 100:
                    yield value, key, item
                elif isinstance(item, (dict, list)):
                    yield from strings(item)
    while len(json.dumps(result)) > max_encoded_chars:
        result['context_transfer_excerpt'] = True
        history = result.get('conversation') or []
        if len(history) > 2:
            history.pop(0)
            continue
        receipts = result.get('previous_tool_receipts') or []
        if len(receipts) > 2:
            receipts.pop(0)
            continue
        candidates = list(strings(result))
        if not candidates:
            raise ValueError('Historical context cannot fit the bridge package; reduce input or compress history.')
        container, key, text = max(candidates, key=lambda row: len(json.dumps(row[2])))
        width = max(1, (len(text) // 2 - len(marker)) // 2)
        container[key] = text[:width] + marker + text[-width:]
    return result
