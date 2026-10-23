"""Bounded schema preflight before jsonschema can resolve any remote reference."""
import json


def safe_schema(schema):
    if not isinstance(schema,dict) or schema.get('type')!='object' or len(json.dumps(schema))>65536:
        raise ValueError('Capability schema is not a bounded object contract.')
    inspected=0
    def inspect(node, refs=(), depth=0):
        nonlocal inspected
        inspected+=1
        if inspected>10000 or depth>64:
            raise ValueError('Schema expansion exceeds the supported budget.')
        if isinstance(node,dict):
            if any(key in node for key in ('$dynamicRef','$recursiveRef','pattern','patternProperties')):
                raise ValueError('Dynamic references and regex validation are unsupported.')
            if '$ref' in node:
                ref=node['$ref']
                if not isinstance(ref,str) or not ref.startswith('#/') or ref in refs:
                    raise ValueError('Only nonrecursive local references are supported.')
                target=schema
                try:
                    for key in ref[2:].split('/'):
                        key=key.replace('~1','/').replace('~0','~')
                        target=target[int(key)] if isinstance(target,list) else target[key]
                except (ValueError,KeyError,IndexError,TypeError):
                    raise ValueError('Unresolved local schema reference.') from None
                inspect(target,refs+(ref,),depth+1)
            for child in node.values():inspect(child,refs,depth+1)
        elif isinstance(node,list):
            for child in node:inspect(child,refs,depth+1)
    inspect(schema)
    from jsonschema.validators import validator_for
    validator=validator_for(schema,default=None) if '$schema' in schema else validator_for(schema)
    if validator is None:
        raise ValueError('Unsupported schema dialect.')
    validator.check_schema(schema)
    return schema
