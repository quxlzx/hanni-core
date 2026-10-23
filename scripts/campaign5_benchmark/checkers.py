"""Deterministic external graders; no model agreement or answer substitution."""
from __future__ import annotations
import ast
import json
import math
import os
from pathlib import Path
import subprocess
import sys

def parse_json(text):

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('Duplicate JSON key.')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON number.')))

def equal(actual, expected, *, numeric=False):
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        return type(actual) is type(expected) and actual == expected
    if type(expected) in (int, float):
        return type(actual) in (int, float) and math.isfinite(actual) and (math.isclose(actual, expected, rel_tol=1e-09, abs_tol=1e-09) if numeric else actual == expected)
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all((equal(a, b, numeric=numeric) for a, b in zip(actual, expected)))
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all((equal(actual[k], v, numeric=numeric) for k, v in expected.items()))
    return False

def check_dag(parsed, facts):
    graph, durations = (facts['graph'], facts['durations'])
    pending = set(graph)
    finish = {}
    possible = True
    while pending:
        ready = sorted((n for n in pending if all((d in finish for d in graph[n]))))
        if not ready:
            possible = False
            break
        for node in ready:
            finish[node] = max([finish[d] for d in graph[node]] or [0]) + durations[node]
            pending.remove(node)
    if not possible:
        return equal(parsed, {'status': 'impossible'})
    if not isinstance(parsed, dict) or set(parsed) != {'status', 'order', 'earliest_finish'}:
        return False
    order = parsed['order']
    if parsed['status'] != 'ready' or not isinstance(order, list) or any((not isinstance(x, str) for x in order)):
        return False
    if len(order) != len(graph) or set(order) != set(graph):
        return False
    positions = {x: i for i, x in enumerate(order)}
    return all((positions[d] < positions[n] for n in graph for d in graph[n])) and equal(parsed['earliest_finish'], finish)
ALLOWED_NODES = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.Assign, ast.AugAssign, ast.Expr, ast.If, ast.For, ast.Break, ast.Continue, ast.Pass, ast.Name, ast.Load, ast.Store, ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set, ast.Subscript, ast.Slice, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp, ast.Call, ast.keyword, ast.Attribute, ast.Starred, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.comprehension, ast.Lambda, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.USub, ast.UAdd, ast.And, ast.Or, ast.Not, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot, ast.BitAnd)
SAFE_BUILTINS = ('abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'float', 'int', 'len', 'list', 'max', 'min', 'next', 'range', 'reversed', 'round', 'set', 'sorted', 'str', 'sum', 'tuple', 'zip')
SAFE_ATTRIBUTES = ('append', 'extend', 'get', 'items', 'keys', 'values', 'lower', 'upper', 'strip', 'split', 'join', 'count', 'index', 'fromkeys', 'sort', 'reverse')

def validate_code(code):
    if not isinstance(code, str) or len(code.encode()) > 16384:
        raise ValueError('Code size limit.')
    tree = ast.parse(code)
    if len(list(ast.walk(tree))) > 500:
        raise ValueError('Code AST limit.')
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef) or tree.body[0].name != 'solve':
        raise ValueError('Exactly one solve function is required.')
    function = tree.body[0]
    if function.decorator_list or len(function.args.args) != 1 or function.args.args[0].arg != 'value' or function.args.defaults or function.args.vararg or function.args.kwarg or function.args.kwonlyargs or function.args.posonlyargs:
        raise ValueError('Expected solve(value) without decorators/defaults.')
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError('Unsupported code construct: ' + type(node).__name__)
        if isinstance(node, ast.Name) and (node.id.startswith('_') or node.id in {'eval', 'exec', 'compile', 'open', 'globals', 'locals', 'getattr', 'setattr', 'type', 'object', 'help', 'input', 'print', 'exit', 'quit'}):
            raise ValueError('Unsafe name.')
        if isinstance(node, ast.Attribute) and node.attr not in SAFE_ATTRIBUTES:
            raise ValueError('Unsafe attribute.')
        if isinstance(node, ast.Constant) and (isinstance(node.value, (bytes, complex)) or (type(node.value) is int and abs(node.value) > 1000000) or (isinstance(node.value, str) and len(node.value) > 4096)):
            raise ValueError('Literal budget exceeded.')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and (node.func.id not in SAFE_BUILTINS):
            raise ValueError('Only bounded builtin calls are allowed; recursion is disabled.')
    return tree

def _memory_job(process):
    """Bound only the disposable coding child on Windows; never owner processes."""
    if os.name != 'nt':
        return None
    import ctypes
    from ctypes import wintypes as w

    class Basic(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64), ('flags', w.DWORD), ('min_working', ctypes.c_size_t), ('max_working', ctypes.c_size_t), ('active', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ('readops', 'writeops', 'otherops', 'readbytes', 'writebytes', 'otherbytes')]

    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise OSError('Could not create bounded coding job.')
    info = Extended()
    info.basic.flags = 256 | 8192
    info.process_memory = 128 * 1024 * 1024
    if not kernel.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)) or not kernel.AssignProcessToJobObject(job, w.HANDLE(int(process._handle))):
        kernel.CloseHandle(job)
        raise OSError('Could not bound coding child memory.')
    return lambda: kernel.CloseHandle(job)

def check_code(code, facts):
    validate_code(code)
    if len(json.dumps(facts).encode()) > 32768:
        raise ValueError('Coding fixture budget exceeded.')
    child = subprocess.Popen([sys.executable, '-I', str(Path(__file__).resolve()), '--code-child'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=Path(__file__).resolve().parent, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    close_job = None
    try:
        close_job = _memory_job(child)
        stdout, stderr = child.communicate(json.dumps({'code': code, 'tests': facts['tests']}), timeout=2)
        if len(stdout.encode()) > 65536:
            return {'passed': False, 'reason': 'Code output budget exceeded.'}
        if child.returncode:
            return {'passed': False, 'reason': 'Code child failed.', 'exit_code': child.returncode, 'stderr': stderr[:2000]}
        values = parse_json(stdout)
        expected = [t['expected'] for t in facts['tests']]
        return {'passed': equal(values, expected), 'observed': values, 'expected': expected, 'child_exit_code': child.returncode}
    except subprocess.TimeoutExpired:
        child.kill()
        child.communicate()
        return {'passed': False, 'reason': 'Two-second coding deadline exceeded.'}
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()
        if close_job:
            close_job()

def grade(answer, oracle):
    kind = oracle['checker_id']
    try:
        if kind == 'python_function':
            return check_code(answer, oracle['checker_inputs'])
        parsed = parse_json(answer)
        if kind == 'dag':
            passed = check_dag(parsed, oracle['checker_inputs'])
        elif kind == 'tool_selection':
            import jsonschema
            if not isinstance(parsed, dict) or set(parsed) != {'capability', 'arguments'}:
                raise ValueError('Tool recommendation envelope mismatch.')
            jsonschema.Draft202012Validator(oracle['checker_inputs']['schema']).validate(parsed['arguments'])
            normalized = dict(parsed['arguments'])
            expected = oracle['expected']
            properties = oracle['checker_inputs']['schema'].get('properties', {})
            for key in set(normalized) - set(expected['arguments']):
                if 'default' in properties.get(key, {}) and normalized[key] == properties[key]['default']:
                    normalized.pop(key)
            passed = parsed['capability'] == expected['capability'] and equal(normalized, expected['arguments'])
        elif kind in {'json_exact', 'json_numeric'}:
            passed = equal(parsed, oracle['expected'], numeric=kind == 'json_numeric')
        else:
            raise ValueError('Unsupported external checker.')
        return {'passed': passed, 'checker': kind, 'observed': parsed, 'expected': oracle.get('expected')}
    except Exception as exc:
        return {'passed': False, 'checker': kind, 'error_class': type(exc).__name__, 'reason': str(exc)[:1000]}

def code_child():
    value = json.loads(sys.stdin.read(65537))
    code = value['code']
    tree = validate_code(code)
    if os.name != 'nt':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    namespace = {'__builtins__': {name: getattr(__import__('builtins'), name) for name in SAFE_BUILTINS}}
    exec(compile(tree, '<synthetic-benchmark>', 'exec'), namespace)
    output = [namespace['solve'](test['input']) for test in value['tests']]
    text = json.dumps(output, allow_nan=False)
    if len(text.encode()) > 65536:
        raise ValueError('Code result budget exceeded.')
    sys.stdout.write(text)
if __name__ == '__main__':
    if sys.argv[1:] == ['--code-child']:
        code_child()
    else:
        raise SystemExit('This module exposes deterministic grading only.')
