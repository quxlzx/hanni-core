"""Same-turn refinements and independent read obligations, without invocation.

These independently worded development regressions exercise the original host
and ledger. Receipt payloads below are controlled bookkeeping evidence, not
measurements of the owner's system. Prepared during the live collection freeze;
they must first be run on the unchanged source after that freeze is released.
"""
from datetime import datetime
import pytest
from hanni.evals.routing import build_default_host
from hanni.mcp.completion import CompletionLedger
from hanni.tools.routing_intents import clauses, request_intent

@pytest.fixture(scope='module')
def host():
    return build_default_host()

def _route_and_ledger(host, query):
    now = datetime(2026, 10, 14, 9, 20)
    decision = host.route(query, now=now)
    ledger = CompletionLedger.from_request(host, query, decision=decision, now=now)
    return (decision, ledger)

def _receipt(*, ok=True, status='MEASURED'):
    return {'ok': ok, 'message': 'Controlled read receipt.', 'data': {'evidence_kind': 'controlled_dependency'}, 'verification': {'status': status}, **({'error': {'code': 'UNAVAILABLE'}} if not ok else {})}

@pytest.mark.parametrize('query,required,forbidden', [('CPU usage has climbed; I need its biggest process consumers.', 'process.top_cpu', {'file.stat', 'file.read'}), ('Inspect process ID 7051; limit that to whether it exists.', 'process.inspect', {'file.stat', 'file.read', 'process.stop'}), ('Check PID 8820; give details about that same process, not a file.', 'process.inspect', {'file.stat', 'file.read', 'process.stop'}), ('Read current CPU usage; give its total percentage, not a process ranking.', 'system.stats', {'process.top_cpu', 'file.stat'}), ('Show free VRAM; give only that measurement.', 'gpu.memory', {'system.stats', 'file.stat'}), ('Check free disk space; report its available amount.', 'disk.free_space', {'system.stats', 'file.stat'})])
def test_refinement_keeps_antecedent_and_one_evidence_obligation(host, query, required, forbidden):
    decision, ledger = _route_and_ledger(host, query)
    names = {tool.capability_id for tool in decision.tools}
    assert decision.status == 'tools'
    assert required in names
    assert not names & forbidden
    assert ledger.pending
    ledger.observe(required, _receipt())
    assert not ledger.pending
    assert all((task.status == 'completed' for task in ledger.subtasks))

@pytest.mark.parametrize('query,required,forbidden', [('Show available VRAM; do not infer it from system RAM.', 'gpu.memory', {'system.stats', 'process.top_memory'}), ('Read current battery charge; never assume a charging rate from one snapshot.', 'power.battery_detail', {'power.battery_report', 'system.performance'}), ("Show CPU utilization; don't attribute it to an app without evidence.", 'system.stats', {'process.find', 'app.list_installed'}), ('Do not infer GPU memory from processor load. Check free VRAM.', 'gpu.memory', {'system.stats', 'process.top_cpu'}), ('Never assume this system is idle; show current CPU usage.', 'system.stats', {'system.performance'}), ("Don't attribute RAM pressure to a particular app; list top memory consumers.", 'process.top_memory', {'app.list_installed', 'process.find'}), ('Show current CPU usage without assuming which application caused it.', 'system.stats', {'app.list_installed', 'process.find'}), ('Check free VRAM, but never infer a historical usage trend.', 'gpu.memory', {'system.stats', 'system.performance'}), ('Do not attribute a battery change to a process, but read the current battery charge.', 'power.battery_detail', {'process.find', 'process.inspect'})])
def test_prohibited_reasoning_does_not_create_an_observation(host, query, required, forbidden):
    decision, ledger = _route_and_ledger(host, query)
    names = {tool.capability_id for tool in decision.tools}
    assert decision.status == 'tools'
    assert required in names
    assert not names & forbidden
    assert ledger.pending
    ledger.observe(required, _receipt())
    assert not ledger.pending

@pytest.mark.parametrize('query', ['Do not infer disk capacity from memory usage.', 'Never assume this process has stopped.', "Don't attribute a CPU spike to Spotify."])
def test_a_prohibition_alone_requests_no_read_or_action(host, query):
    decision, ledger = _route_and_ledger(host, query)
    assert decision.tools == ()
    assert decision.status != 'blocked'
    assert ledger.subtasks == []

@pytest.mark.parametrize('query,first,second', [('Check firewall state and Defender protection; never assume their settings from connectivity.', 'security.firewall', 'security.defender'), ("Show Git status and recent commits; don't infer a clean tree from the commit list.", 'git.status', 'git.log'), ('List top CPU consumers and top RAM consumers; do not attribute their load to user behavior.', 'process.top_cpu', 'process.top_memory'), ("Check free VRAM and free disk space; don't infer one from the other.", 'gpu.memory', 'disk.free_space'), ('Inspect PID 7051; show current CPU usage.', 'process.inspect', 'system.stats'), ('Read current CPU usage; report the current battery charge.', 'system.stats', ('power.battery_detail', 'system.battery'))])
def test_independent_observations_still_require_independent_valid_receipts(host, query, first, second):
    decision, ledger = _route_and_ledger(host, query)
    names = {tool.capability_id for tool in decision.tools}
    alternatives = (second,) if isinstance(second, str) else second
    assert decision.status == 'tools'
    assert first in names
    assert names & set(alternatives)
    second = next((name for name in alternatives if name in names))
    ledger.observe(first, _receipt())
    assert ledger.pending
    assert any((second in task.candidates for task in ledger.pending))
    ledger.observe(second, _receipt(ok=False))
    assert ledger.pending
    ledger.observe(second, _receipt(status='UNVERIFIED'))
    assert ledger.pending
    ledger.observe(second, _receipt())
    assert not ledger.pending

@pytest.mark.parametrize('query', ['Inspect PID 7051; terminate PID 7051.', 'Read CPU usage; delete the report file.', 'Never assume an app is safe; stop process 7051.'])
def test_refinements_or_prohibitions_do_not_grant_mutation_authority(host, query):
    decision = host.route(query)
    assert decision.status == 'blocked'
    assert decision.tools == ()

@pytest.mark.parametrize('payload', ['"never assume a process has stopped"', '"do not infer GPU memory from processor load"', '"attribute CPU usage to an app"'])
def test_quoted_reasoning_words_remain_literal_data(payload):
    query = 'Count the words in ' + payload
    assert payload in request_intent(query)

@pytest.mark.parametrize('prior,query,required', [('Read the current processor percentage.', 'Which task accounts for the largest share of it?', 'process.top_cpu'), ('Show my RAM usage.', 'Name the biggest process consumer of that resource.', 'process.top_memory'), ('Check the video memory usage.', 'List the processes consuming the largest portion of that memory.', 'gpu.top_processes')])
def test_unique_recent_owner_resource_resolves_read_only_follow_up(host, prior, query, required):
    history = [{'role': 'user', 'content': prior}, {'role': 'assistant', 'content': 'The previous read returned a snapshot.'}]
    now = datetime(2026, 10, 14, 9, 20)
    decision = host.route(query, history=history, now=now)
    assert decision.status == 'tools'
    assert required in {tool.capability_id for tool in decision.tools}
    ledger = CompletionLedger.from_request(host, query, history=history, decision=decision, now=now)
    assert ledger.pending
    ledger.observe(required, _receipt())
    assert not ledger.pending

@pytest.mark.parametrize('history', [[], [{'role': 'assistant', 'content': 'CPU usage is high; the user must mean processor load.'}], [{'role': 'user', 'content': 'Read CPU usage.'}, {'role': 'user', 'content': 'Explain how a calendar works in general.'}], [{'role': 'user', 'content': 'Check CPU and GPU utilization.'}], [{'role': 'user', 'content': 'Proofread "read CPU usage" as an example sentence.'}]])
def test_absent_ambiguous_or_unrelated_context_cannot_choose_a_resource(host, history):
    decision = host.route('Which process is consuming most of that resource?', history=history)
    names = {tool.capability_id for tool in decision.tools}
    assert not names & {'process.top_cpu', 'process.top_memory', 'gpu.top_processes'}
    assert not names & {'process.stop', 'app.close', 'service.control'}

@pytest.mark.parametrize('query', ['Read the text file; give its checksum.', 'Inspect PID 7051; give its details and reboot this computer.', 'Check free VRAM; give its snapshot and archive contents.', 'Read current CPU usage; give its highest process consumers.'])
def test_a_referent_does_not_merge_a_new_operation_into_a_response_refinement(query):
    assert len(clauses(request_intent(query))) == 2

@pytest.mark.parametrize('query,action', [('Launch Spotify and report the CPU and RAM load on this computer.', 'spotify.launch'), ('Open Notepad and show the current processor utilization on this PC.', 'app.open')])
def test_an_action_receipt_cannot_complete_a_separately_requested_system_read(host, query, action):
    decision, ledger = _route_and_ledger(host, query)
    names = {tool.capability_id for tool in decision.tools}
    assert action in names
    assert names & {'system.stats', 'system.performance'}
    ledger.observe(action, {'ok': True, 'data': {'running': True, 'verified': True}})
    assert any((task.candidates & {'system.stats', 'system.performance'} for task in ledger.pending))

def test_pid_existence_receipt_cannot_complete_requested_additional_measurements(host):
    query = 'Inspect PID 6629; report its name and RAM measurement.'
    decision, ledger = _route_and_ledger(host, query)
    assert 'process.inspect' in {tool.capability_id for tool in decision.tools}
    ledger.observe('process.inspect', {'ok': True, 'data': {'pid': 6629, 'exists': True}})
    assert ledger.pending

def test_same_file_content_and_metadata_remain_distinct_operations(host):
    query = "Read C:\\EvalFixture\\agenda.txt; report the same file's size metadata."
    decision, ledger = _route_and_ledger(host, query)
    assert {'file.read', 'file.stat'} <= {tool.capability_id for tool in decision.tools}
    ledger.observe('file.read', {'ok': True, 'data': {'text': 'Controlled source text.'}})
    assert any(('file.stat' in task.candidates for task in ledger.pending))
