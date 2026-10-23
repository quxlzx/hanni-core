"""New public prospective inputs for the resumed shared-adapter seam.

These are controlled contract inputs, not a replacement development cohort or
private final tasks. Expected results live in independent test assertions.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

def public_cases():

    def envelope(key, prompt, fixture, actions, *, actor='owner', confirmed=False):
        return {'version': 1, 'id': 'PUBLIC-SYSTEMS-' + key, 'family': 'shared_adapter_smoke', 'difficulty': 'medium', 'description': prompt, 'user_turns': [{'prompt': prompt, 'actor_profile': actor, 'confirmed': confirmed}], 'fixtures': fixture, 'actions': actions}
    goal = 'Read {root}/a.txt then {root}/b.txt.'

    def read(key, name, dependencies):
        return {'step_id': key, 'description': 'Read the local text file {root}/' + name, 'kind': 'tool', 'capability_id': 'file.read', 'dependencies': dependencies, 'required': True, 'criteria': [{'operator': 'present', 'path': '/data/text', 'expected': None}], 'arguments': {'path': '{root}/' + name}}
    fixture = {'adapter': 'workflow', 'goal': goal, 'mode': 'assisted', 'files': {'a.txt': 'First synthetic source.', 'b.txt': 'Second synthetic source.'}, 'steps': [read('first', 'a.txt', []), read('second', 'b.txt', ['first'])]}
    reviewed = deepcopy(fixture)
    reviewed.update(auto_approve=True, auto_start=True)
    failure = deepcopy(reviewed)
    failure['goal'] = 'Check the SHA-256 hash of {root}/a.txt before reading {root}/b.txt.'
    failure['steps'][0].update(description='Check file properties and SHA-256 hash of {root}/a.txt', capability_id='file.stat', arguments={'path': '{root}/a.txt', 'hash': True}, criteria=[{'operator': 'present', 'path': '/data/sha256', 'expected': None}])
    failure['faults'] = [{'method': 'hash', 'path': '{root}/a.txt', 'kind': 'timeout_before', 'times': 9}]
    failure['limits'] = {'max_retries': 1}
    actions = [{'operation': 'workflow.run', 'args': {}}]
    cases = [envelope('MEMORY', 'Find the archived build summary.', {'adapter': 'memory', 'memories': [{'content': 'Archived build summaries include test counts.'}]}, [{'operation': 'memory.search', 'args': {'query': 'archived build summaries test counts'}}]), envelope('UNREVIEWED', goal, fixture, actions, confirmed=True), envelope('REVIEWED', goal, reviewed, actions), envelope('PREREQUISITE', failure['goal'], failure, actions), envelope('NONOWNER', goal, {'adapter': 'workflow', 'goal': goal, 'mode': 'assisted'}, actions, actor='everyone_else', confirmed=True), envelope('MISSINGPLAN', goal, {'adapter': 'workflow', 'goal': goal, 'mode': 'assisted'}, actions), envelope('TEXT', 'Classify the supplied text without acoustic input.', {'adapter': 'voice_text'}, [{'operation': 'voice_text.classify', 'args': {'text': 'Hanni, show the build summary'}}]), envelope('MISSINGARG', 'Retrieve my build preference.', {'adapter': 'memory'}, [{'operation': 'memory.retrieve', 'args': {}}]), envelope('MIXEDACTORS', 'Retrieve a synthetic preference.', {'adapter': 'memory'}, [{'operation': 'memory.retrieve', 'args': {'query': 'synthetic preference'}}])]
    cases[-1]['user_turns'].append({'prompt': 'Apply a correction.', 'actor_profile': 'everyone_else', 'confirmed': True})
    return cases

def seal(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    raw = (json.dumps({'cases': public_cases()}, indent=2, sort_keys=True) + '\n').encode('utf-8')
    (destination / 'inputs.json').write_bytes(raw)
    metadata = {'task_count': len(public_cases()), 'input_sha256': hashlib.sha256(raw).hexdigest(), 'scope': 'New public controlled compatibility smoke; original 60 and schema-only 12 unchanged.', 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'real_model_requests': 0, 'private_final_accessed': False}
    (destination / 'SEAL.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8', newline='\n')
    return metadata
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    print(json.dumps(seal(parser.parse_args().output), indent=2))
