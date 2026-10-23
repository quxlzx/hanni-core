"""Public synthetic schemas/results; no configured model or sealed inputs."""
from copy import deepcopy
import json
from pathlib import Path
import jsonschema
import pytest
from hanni.workflows.planner import BINDING_SCHEMA, OUTLINE_SCHEMA, WorkflowPlanner
from hanni.workflows.transport_schema import generation_schema
from hanni.workflows.types import WorkflowError
from hanni.workflows.verification import REPORT_SCHEMA, render_report
from tests.unit.test_workflow_planner import binding, host, outline
from tests.unit.test_workflow_service import approve_start, operation, service

@pytest.mark.parametrize('schema', [OUTLINE_SCHEMA, BINDING_SCHEMA, REPORT_SCHEMA])
def test_projection_is_detached_and_preserves_structural_schema_authority(schema):
    original = deepcopy(schema)
    projected = generation_schema(schema)

    def check(actual, transported):
        for key in ('type', 'required', 'additionalProperties', 'enum'):
            if key in actual:
                assert actual[key] == transported[key]
        assert not set(transported).intersection({'minLength', 'maxLength', 'minItems', 'maxItems', 'pattern'})
        for name, child in actual.get('properties', {}).items():
            if child:
                check(child, transported['properties'][name])
        if 'items' in actual:
            check(actual['items'], transported['items'])
    check(original, projected)
    projected['properties'].clear()
    assert schema == original

def test_schema_traversal_does_not_delete_literals_or_property_names():
    literal = {'maxLength': 2000, 'pattern': '{1,512}', 'maxItems': 16}
    schema = {'type': 'object', 'required': ['maxLength'], 'additionalProperties': False, 'properties': {'maxLength': {'type': 'string', 'maxLength': 2000}, 'data': {'enum': [literal], 'default': literal}}, '$defs': {'text': {'type': 'string', 'minLength': 1, 'maxLength': 512}}, 'anyOf': [{'properties': {'pattern': {'type': 'string', 'pattern': '^.{1,20}$'}}}]}
    result = generation_schema(schema)
    assert result['properties']['maxLength'] == {'type': 'string'}
    assert result['properties']['data']['enum'] == [literal]
    assert result['properties']['data']['default'] == literal
    assert result['required'] == ['maxLength']
    assert result['$defs']['text'] == {'type': 'string'}
    assert result['anyOf'][0]['properties']['pattern'] == {'type': 'string'}

@pytest.mark.parametrize('value', [0, 90.5, 'quoted source text', True, None, [], {'nested': [False]}])
def test_unconstrained_expected_and_report_values_preserve_all_json_types(host, value):
    proposal = outline()
    proposal['steps'][0]['criteria'][0]['expected'] = value
    client = FormatCheckingClient(proposal)
    assert WorkflowPlanner(host, client)._ask('Public typed value request.', {}, OUTLINE_SCHEMA) == proposal
    expected = client.schemas[0]['properties']['steps']['items']['properties']['criteria']['items']['properties']['expected']
    assert set(expected['type']) == {'object', 'array', 'string', 'number', 'boolean', 'null'}
    report = {'observations': [{'operation': 'value', 'sources': [{'step_id': 'source', 'path': '/data/value', 'json_path': None}], 'value': value}]}
    jsonschema.Draft202012Validator(generation_schema(REPORT_SCHEMA)).validate(report)
    assert json.loads(render_report(report)) == report

@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
def test_explicit_json_type_union_does_not_weaken_finite_output_admission(host, value):
    proposal = outline()
    proposal['steps'][0]['criteria'][0]['expected'] = value
    with pytest.raises(WorkflowError):
        WorkflowPlanner(host, FormatCheckingClient(proposal))._ask('Finite JSON required.', {}, OUTLINE_SCHEMA)
    report = {'observations': [{'operation': 'value', 'sources': [{'step_id': 'source', 'path': '/data/value', 'json_path': None}], 'value': value}]}
    with pytest.raises(WorkflowError):
        render_report(report)

class FormatCheckingClient:

    def __init__(self, *responses):
        self.responses, self.schemas = (list(responses), [])

    def chat(self, messages, **options):
        schema = options['response_format']['json_schema']['schema']
        self.schemas.append(schema)
        assert options['max_tokens'] in {2048, 3072}
        response = self.responses.pop(0)
        if isinstance(response, str):
            return response
        jsonschema.Draft202012Validator(schema).validate(response)
        return json.dumps(response)

@pytest.mark.parametrize('kind', ['summary_length', 'description_length', 'path_length', 'step_pattern', 'steps_count', 'criteria_count', 'dependency_count', 'unsupported_length'])
def test_outline_full_local_bounds_reject_transport_valid_output(host, kind):
    proposal = outline()
    step = proposal['steps'][0]
    if kind == 'summary_length':
        proposal['summary'] = 'x' * 2001
    elif kind == 'description_length':
        step['description'] = 'x' * 2001
    elif kind == 'path_length':
        step['criteria'][0]['path'] = '/' + 'x' * 512
    elif kind == 'step_pattern':
        step['step_id'] = 'invalid step id'
    elif kind == 'steps_count':
        proposal['steps'] = [deepcopy(step) for _ in range(17)]
    elif kind == 'criteria_count':
        step['criteria'] *= 9
    elif kind == 'dependency_count':
        step['dependencies'] = [str(i) for i in range(17)]
    else:
        proposal['unsupported_reason'] = 'x' * 1001
    client = FormatCheckingClient(proposal)
    with pytest.raises(WorkflowError, match='invalid bounded'):
        WorkflowPlanner(host, client)._ask('Unchanged public test request.', {}, OUTLINE_SCHEMA)
    assert OUTLINE_SCHEMA['properties']['steps']['maxItems'] == 16
    assert len(client.schemas) == 1

def test_binding_local_array_bound_still_denies_transport_valid_output(host):
    proposal = binding()
    proposal['steps'] *= 17
    with pytest.raises(WorkflowError, match='invalid bounded'):
        WorkflowPlanner(host, FormatCheckingClient(proposal))._ask('Public binding request.', {}, BINDING_SCHEMA)

@pytest.mark.parametrize('text', ['not JSON', '{', '{"steps": true}', '{"summary": NaN}'])
def test_malformed_model_output_never_bypasses_original_plan_validation(host, text):
    with pytest.raises(WorkflowError):
        WorkflowPlanner(host, FormatCheckingClient(text))._ask('Public validation request.', {}, OUTLINE_SCHEMA)

def report_proposal():
    return {'observations': [{'operation': 'percentage', 'sources': [{'step_id': 'read', 'path': '/data/text', 'json_path': '/passed'}, {'step_id': 'read', 'path': '/data/text', 'json_path': '/total'}], 'value': 90}]}

class ReportWorkflowClient(FormatCheckingClient):

    def __init__(self, source, report):
        self.source, self.destination = (source, None)
        outline_response = {'summary': 'Read supplied JSON and save a checked calculation.', 'unsupported_reason': None, 'steps': [{'step_id': 'read', 'description': 'Read the text file ' + source, 'kind': 'tool', 'dependencies': [], 'required': True, 'criteria': [{'operator': 'json_valid', 'path': '/data/text', 'expected': None}]}, {'step_id': 'analyze', 'description': 'Calculate the percentage from cited source values.', 'kind': 'analysis', 'dependencies': ['read'], 'required': True, 'criteria': [{'operator': 'evidence_report', 'path': '/data/report', 'expected': None}]}, {'step_id': 'save', 'description': 'Save the checked source calculation.', 'kind': 'artifact', 'dependencies': ['analyze'], 'required': True, 'criteria': [{'operator': 'present', 'path': '/data/path', 'expected': None}]}]}
        super().__init__(outline_response, None, report)

    def chat(self, messages, **options):
        if len(self.schemas) == 1:
            data = json.loads(messages[1]['content'])
            self.destination = str(Path(data['artifact_root']) / 'checked-report.json')
            self.responses[0] = {'unsupported_reason': None, 'steps': [{'step_id': 'read', 'capability_id': 'file.read', 'arguments': {'path': self.source}}, {'step_id': 'analyze', 'capability_id': None, 'arguments': {'sources': ['read']}}, {'step_id': 'save', 'capability_id': 'file.write', 'arguments': {'path': self.destination, 'text': {'$ref': {'step_id': 'analyze', 'path': '/data/text', 'type': 'string'}}}}]}
        return super().chat(messages, **options)

@pytest.mark.parametrize('invalid', [None, 'observations_count', 'sources_count', 'path_length', 'wrong_calculation'])
def test_all_three_real_service_calls_project_grammar_keep_original_report_checks(service, invalid):
    source = service.client.source
    Path(source).write_text('{"passed":9,"total":10}', encoding='utf-8')
    report = report_proposal()
    if invalid == 'observations_count':
        report['observations'] *= 17
    elif invalid == 'sources_count':
        report['observations'][0]['sources'] *= 9
    elif invalid == 'path_length':
        report['observations'][0]['sources'][0]['path'] = '/' + 'x' * 512
    elif invalid == 'wrong_calculation':
        report['observations'][0]['value'] = 91
    client = ReportWorkflowClient(source, report)
    service.client = client
    key = operation(service, 'goal.submit', {'goal': 'Read supplied JSON in ' + source + ' and save a checked percentage.', 'mode': 'assisted'})['workflow_id']
    detail = service.wait(key)
    assert detail['status'] == 'awaiting_plan_approval', detail
    approve_start(service, key, detail)
    final = service.wait(key)
    assert len(client.schemas) == 3
    assert [schema['required'] for schema in client.schemas] == [OUTLINE_SCHEMA['required'], BINDING_SCHEMA['required'], REPORT_SCHEMA['required']]
    if invalid is None:
        assert final['status'] == 'completed', final
        assert json.loads(Path(client.destination).read_text()) == report
    else:
        assert final['status'] in {'blocked', 'partially_completed'}, final
        assert not Path(client.destination).exists()
        assert final['counts']['verified'] == 1
    assert REPORT_SCHEMA['properties']['observations']['maxItems'] == 16
