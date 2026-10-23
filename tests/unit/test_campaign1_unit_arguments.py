"""Unit spelling contracts preserve the original numerical conversion factors."""
import pytest
from hanni.tools import compute
from hanni.tools.base import ToolRequest, ToolValidationError

def unit_definition():
    return next((item for item in compute.definitions() if item.name == 'unit.convert'))

def convert(value, source, target):
    definition = unit_definition()
    request = ToolRequest('unit.convert', {'value': value, 'from_unit': source, 'to_unit': target})
    arguments = definition.validate_arguments(request.arguments)
    return definition.handler(arguments, None, request)

@pytest.mark.parametrize('value,source,target,expected', [(2.5, 'kilometers', 'meters', 2500.0), (0.75, 'kilometres', 'centimetres', 75000.0), (350, 'grams', 'kilograms', 0.35), (1700, 'milliseconds', 'seconds', 1.7), (1, 'gigabytes', 'bytes', 1024.0 ** 3)])
def test_advertised_and_family_consistent_full_unit_names_are_supported(value, source, target, expected):
    result = convert(value, source, target)
    assert result.ok is True
    assert result.data['converted'] == pytest.approx(expected)

@pytest.mark.parametrize('value,source,target,expected', [(3, 'KiB', 'bytes', 3072.0), (2, 'MiB', 'KiB', 2048.0), (0.5, 'GiB', 'bytes', 0.5 * 1024.0 ** 3), (1, 'TiB', 'GiB', 1024.0), (2, 'kibibytes', 'bytes', 2048.0)])
def test_explicit_iec_binary_spellings_use_the_existing_binary_factors(value, source, target, expected):
    result = convert(value, source, target)
    assert result.ok is True
    assert result.data['family'] == 'data'
    assert result.data['converted'] == pytest.approx(expected)

@pytest.mark.parametrize('value,source,target,expected', [(1, 'KB', 'bytes', 1024.0), (1, 'MB', 'bytes', 1024.0 ** 2), (1, 'GB', 'bytes', 1024.0 ** 3), (1, 'TB', 'bytes', 1024.0 ** 4), (8, 'bits', 'bytes', 1.0), (0.75, 'km', 'm', 750.0), (1, 'lb', 'kg', 0.45359237), (6, 'hours', 's', 21600.0), (1, 'mph', 'mps', 0.44704), (32, 'fahrenheit', 'celsius', 0.0), (273.15, 'kelvin', 'celsius', 0.0), (-40, 'C', 'F', -40.0), (2, ' KM ', ' m ', 2000.0)])
def test_legacy_scale_temperature_and_case_whitespace_behavior_are_preserved(value, source, target, expected):
    assert convert(value, source, target).data['converted'] == pytest.approx(expected)

@pytest.mark.parametrize('source,target', [('furlongish', 'meters'), ('meters', 'banana'), ('Ki B', 'bytes'), ('meter; restart windows', 'm'), ('km', 'kg'), ('celsius', 'bytes')])
def test_unknown_nonsense_and_incompatible_dimensions_still_fail(source, target):
    with pytest.raises(ValueError):
        convert(1, source, target)

def test_unit_schema_conveys_required_values_and_legal_spelling_semantics():
    schema = unit_definition().argument_schema()
    assert set(schema['required']) == {'value', 'from_unit', 'to_unit'}
    assert schema['additionalProperties'] is False
    for name in ('value', 'from_unit', 'to_unit'):
        kinds = schema['properties'][name]['type']
        assert 'null' not in (kinds if isinstance(kinds, list) else [kinds])
    for name in ('from_unit', 'to_unit'):
        description = schema['properties'][name].get('description', '').casefold()
        assert all((token in description for token in ('km', 'kilometers', 'kib', 'bytes')))
        assert '1024' in description

@pytest.mark.parametrize('arguments', [{'from_unit': 'm', 'to_unit': 'km'}, {'value': 1, 'to_unit': 'km'}, {'value': 1, 'from_unit': 'm'}, {'value': None, 'from_unit': 'm', 'to_unit': 'km'}, {'value': 1, 'from_unit': None, 'to_unit': 'km'}, {'value': 1, 'from_unit': 'm', 'to_unit': None}, {'value': True, 'from_unit': 'm', 'to_unit': 'km'}, {'value': float('nan'), 'from_unit': 'm', 'to_unit': 'km'}, {'value': float('inf'), 'from_unit': 'm', 'to_unit': 'km'}, {'value': 1, 'from_unit': '', 'to_unit': 'km'}])
def test_missing_null_empty_and_invalid_numeric_arguments_fail_before_handler(arguments):
    with pytest.raises(ToolValidationError):
        unit_definition().validate_arguments(arguments)
