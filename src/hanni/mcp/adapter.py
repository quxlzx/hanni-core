"""External MCP calls behind the original registry's permission and audit gates."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json

from hanni.logs.redaction import redact_value
from hanni.mcp.security import MCPConfigurationError, MAX_RESULT, json_copy
from hanni.tools.base import ToolDefinition, ToolError, ToolResult, ToolValidationError


def validate_json_arguments(schema, arguments):
    from jsonschema.validators import validator_for
    try:
        result = json_copy(dict(arguments))
        error = next(validator_for(schema)(schema).iter_errors(result), None)
        if error:
            # Validation errors include private input values; report only the rule.
            raise ToolValidationError(f'Imported tool arguments do not match the schema ({error.validator}).')
        return result
    except ToolValidationError: raise
    except (MCPConfigurationError, RecursionError, ValueError, TypeError):
        raise ToolValidationError('Imported tool arguments are invalid or exceed supported limits.') from None


def result_contract(raw, output_schema):
    from jsonschema.validators import validator_for
    raw = json_copy(raw, limit=MAX_RESULT)
    if not isinstance(raw, dict) or not isinstance(raw.get('content'), list):
        raise ToolError('MCP server returned an invalid result.')
    structured = raw.get('structuredContent')
    failed = raw.get('isError', False)
    if type(failed) is not bool: raise ToolError('MCP result error flag is invalid.')
    if not failed and output_schema is not None:
        if structured is None or next(validator_for(output_schema)(output_schema).iter_errors(structured), None):
            raise ToolError('MCP structured result does not match the approved output schema.')
    content = []
    for block in raw['content']:
        if not isinstance(block, dict) or block.get('type') not in {'text', 'image', 'audio', 'resource_link', 'resource'}:
            raise ToolError('MCP content type is unsupported.')
        # Binary and resource contents are bounded inert JSON data. This adapter
        # never fetches resource URLs, opens files, renders HTML, or decodes images.
        content.append(deepcopy(block))
    texts = [item.get('text', '') for item in content if item['type'] == 'text' and isinstance(item.get('text'), str)]
    message = '\n'.join(texts)[:12000] or ('MCP tool returned an error.' if failed else 'MCP tool completed.')
    return not failed, message, {'content': content, 'structured_content': structured,
                                 'metadata': raw.get('_meta'), 'is_error': failed}


def definition(manager, server, tool):
    classification = tool['classification']
    level, risk = {'read_only': (0, 0), 'write': (2, 2),
                   'destructive': (3, 3), 'unknown': (3, 3)}[classification]
    identity, digest = tool['internal_id'], tool['definition_hash']
    original, server_id = tool['original_name'], server['id']

    def handler(arguments, context, request):
        arguments = validate_json_arguments(tool['input_schema'], arguments)
        raw = manager.execute_remote(server_id, original, digest, classification, arguments, context, request)
        ok, message, data = result_contract(raw, tool['output_schema'])
        data['correlation'] = {'server_id': server_id, 'original_name': original,
                               'definition_hash': digest, 'capability_id': identity,
                               'correlation_id': request.correlation_id}
        return ToolResult(identity, ok, message, redact_value(data),
                          error=None if ok else {'code': 'MCP_TOOL_ERROR', 'message': 'External MCP tool reported an error.', 'retryable': False})

    return ToolDefinition(
        identity, tool['description'], level, risk, {}, {'content': 'array', 'structured_content': 'object'}, handler,
        timeout_seconds=int(server['config']['timeout_seconds']), retry_attempts=1,
        requires_confirmation_if=(None if classification == 'read_only' else
                                  lambda arguments: 'External MCP operations require explicit execution confirmation.'),
        side_effect='read' if classification == 'read_only' else 'destructive' if classification in {'destructive', 'unknown'} else 'external_action',
        tags=(server['name'], original, 'mcp'), aliases=(original, server['name'] + ' ' + original),
        background_allowed=False, schema_version=tool['version'], display_name=original,
        categories=('mcp',), json_input_schema=deepcopy(tool['input_schema']),
        json_output_schema=deepcopy(tool['output_schema']), external_definition_hash=digest)
