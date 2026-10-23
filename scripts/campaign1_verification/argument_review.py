"""Pre-final semantic comparison rules; frozen literal predicates remain intact."""
import ntpath
from pathlib import Path
from scripts.campaign1_verification.contract import predicate_passes
from scripts.campaign1_verification.fixtures import PATH_KEYS, substitute

def compare(arguments, predicate, fixture_root, query):
    fixture_root = Path(fixture_root).resolve()
    literal = predicate_passes(arguments, predicate, fixture_root=fixture_root)
    result = {'literal_pass': literal, 'identity_equivalent': literal, 'identity_rule': 'literal' if literal else None, 'annotation_limitation': None}
    if literal:
        return result
    if predicate['field'] == '$path_args':
        paths = [v for k, v in arguments.items() if k in PATH_KEYS]
        allowed = {ntpath.normcase(ntpath.normpath(substitute(ntpath.normpath(p), fixture_root))) for p in predicate.get('allowed_paths', [])}
        equivalent = bool(paths) and all((isinstance(p, str) and Path(p).resolve().is_relative_to(Path(fixture_root).resolve()) and (not allowed or ntpath.normcase(ntpath.normpath(p)) in allowed) for p in paths))
        result.update(identity_equivalent=equivalent, identity_rule='Windows path identity with original owned-root requirement' if equivalent else None)
        return result
    if predicate['op'] != 'eq':
        return result
    field = predicate['field']
    actual = arguments.get(field)
    wanted = substitute(predicate.get('value'), fixture_root)
    if not isinstance(actual, str) or not isinstance(wanted, str):
        return result
    if field in PATH_KEYS:
        wanted = substitute(ntpath.normpath(predicate['value']), fixture_root)

        def key(path):
            return ntpath.normcase(ntpath.normpath(path))
        if key(actual) == key(wanted):
            result.update(identity_equivalent=True, identity_rule='Windows case and separator identity')
        elif wanted.endswith('.') and key(actual) == key(wanted[:-1]) and query.rstrip().endswith('.'):
            result['annotation_limitation'] = 'Possible unquoted sentence punctuation in frozen path predicate; literal failure retained and not credited as identity equivalence.'
    elif field == 'app' and predicate['tool'] == 'app.open' and (actual.casefold() == wanted.casefold()):
        result.update(identity_equivalent=True, identity_rule='Original application name case normalization')
    return result
