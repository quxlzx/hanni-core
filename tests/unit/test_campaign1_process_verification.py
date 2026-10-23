"""Verify the original process-list result contract without touching processes.

The original handler sees controlled psutil records only.
"""
from types import SimpleNamespace
import pytest
from hanni.reliability.verification import inspect_result
from hanni.tools.base import ToolRequest
from hanni.tools import system

def test_original_process_list_memory_percent_rows_are_verified(monkeypatch):
    processes = [SimpleNamespace(info={'pid': 7101, 'name': 'ControlledCanvas.exe', 'memory_percent': 2.0}), SimpleNamespace(info={'pid': 7102, 'name': 'ControlledCapture.exe', 'memory_percent': 4.75})]
    monkeypatch.setattr(system.psutil, 'process_iter', lambda attributes: iter(processes))
    request = ToolRequest('process.list', {'limit': 5})
    result = system._process_list(request.arguments, None, request)
    assert result.data['processes'] == [{'pid': 7102, 'name': 'ControlledCapture.exe', 'memory_percent': 4.75}, {'pid': 7101, 'name': 'ControlledCanvas.exe', 'memory_percent': 2.0}]
    verification = inspect_result('process.list', request.arguments, result.to_dict())
    assert verification['status'] == 'VERIFIED'
    assert verification['checks']['valid_rows'] is True
    assert verification['independent'] is False

@pytest.mark.parametrize('percent', [0, 100, 12.5])
def test_process_list_accepts_finite_memory_percentage_boundaries(percent):
    result = {'ok': True, 'data': {'processes': [{'pid': 7101, 'name': 'ControlledCanvas.exe', 'memory_percent': percent}]}}
    assert inspect_result('process.list', {}, result)['status'] == 'VERIFIED'

@pytest.mark.parametrize('row', [{'name': 'ControlledCanvas.exe'}, {'name': 'ControlledCanvas.exe', 'memory_mb': 12}, {'name': 'ControlledCanvas.exe', 'memory_percent': None}, {'name': 'ControlledCanvas.exe', 'memory_percent': True}, {'name': 'ControlledCanvas.exe', 'memory_percent': '12.5'}, {'name': 'ControlledCanvas.exe', 'memory_percent': float('nan')}, {'name': 'ControlledCanvas.exe', 'memory_percent': float('inf')}, {'name': 'ControlledCanvas.exe', 'memory_percent': float('-inf')}, {'name': 'ControlledCanvas.exe', 'memory_percent': -0.1}, {'name': 'ControlledCanvas.exe', 'memory_percent': 100.1}, {'name': '', 'memory_percent': 12}, {'name': '   ', 'memory_percent': 12}, {'name': None, 'memory_percent': 12}, {'memory_percent': 12}, 'malformed row'])
def test_process_list_does_not_verify_malformed_or_unsupported_rows(row):
    result = {'ok': True, 'data': {'processes': [row]}}
    verification = inspect_result('process.list', {}, result)
    assert verification['status'] == 'UNVERIFIED'
    assert verification['checks']['valid_rows'] is False

def test_process_list_keeps_failed_execution_and_empty_evidence_unverified():
    rows = [{'name': 'ControlledCanvas.exe', 'memory_percent': 12}]
    assert inspect_result('process.list', {}, {'ok': False, 'data': {'processes': rows}})['status'] == 'UNVERIFIED'
    assert inspect_result('process.list', {}, {'ok': True, 'data': {'processes': []}})['status'] == 'UNVERIFIED'

@pytest.mark.parametrize('name,metric,value', [('process.top_cpu', 'cpu_percent', 24.0), ('process.top_memory', 'rss_mb', 8192.0)])
def test_resource_rankings_retain_their_original_metrics(name, metric, value):
    result = {'ok': True, 'data': {'processes': [{'name': 'ControlledCapture.exe', metric: value}]}}
    assert inspect_result(name, {}, result)['status'] == 'VERIFIED'
