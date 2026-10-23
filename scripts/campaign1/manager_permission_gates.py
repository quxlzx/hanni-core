"""Exercise every original dynamic-confirmation callback without foreign effects.

Only handler implementations are controlled. Schemas, actor policy and dynamic
confirmation remain original. The unconfirmed half must never dispatch.
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from hanni.config.loader import load_config
from hanni.tools.registry import build_default_registry
from hanni.tools.base import ToolRequest, ToolResult, ConfirmationRequired
from hanni.reliability.execution import close_service
from scripts.campaign1_verification.authority_audit import argument_example

def audit(output: Path):
    output = output.resolve()
    assert output.is_relative_to((ROOT / 'data/campaign1-manager').resolve())
    assert not output.exists()
    output.mkdir(parents=True)
    owned = output / 'owned'
    owned.mkdir()
    config = load_config(ROOT / 'config', data_dir=output / 'state', env={})
    registry = build_default_registry(config, data_dir=output / 'state')
    dispatched = []
    rows = []
    protected = str(Path(os.environ['WINDIR']) / 'campaign1-never-created.txt')
    try:
        for original in registry.definitions():
            if original.requires_confirmation_if is None:
                continue
            args = argument_example(original.argument_schema())
            if original.name.startswith('file.'):
                args.update(path=protected) if 'path' in original.input_schema else args.update(source=str(owned / 'never-read.txt'), destination=protected)
            elif original.name.startswith('archive.'):
                args.update(destination=str(owned))
            elif original.name == 'project.format':
                args.update(root=str(owned), apply=True)
            elif original.name == 'powershell.run':
                args.update(command='Restart-Computer')
            checked = original.validate_arguments(args)
            reason = original.requires_confirmation_if(checked)
            assert reason, f'No dynamic risk exercised for {original.name}'

            def controlled(arguments, context, request, *, name=original.name):
                dispatched.append({'tool': name, 'confirmed': request.confirmed})
                return ToolResult(name, True, 'Controlled permission receipt only.', {})
            assert registry.unregister(original.name, expected=original)
            replacement = replace(original, handler=controlled)
            registry.register(replacement)
            before = len(dispatched)
            denied = False
            try:
                registry.execute(ToolRequest(original.name, checked, confirmed=False, source='campaign1-dynamic-confirmation-audit'))
            except ConfirmationRequired:
                denied = len(dispatched) == before
            after_denied = len(dispatched)
            accepted = registry.execute(ToolRequest(original.name, checked, confirmed=True, source='campaign1-dynamic-confirmation-audit'))
            confirmed_dispatch = accepted.ok and len(dispatched) == after_denied + 1 and (dispatched[-1]['confirmed'] is True)
            rows.append({'tool': original.name, 'dynamic_reason': reason, 'unconfirmed_denied_before_handler': denied, 'confirmed_controlled_dispatch': confirmed_dispatch, 'original_metadata_retained': replacement.requires_confirmation_if is original.requires_confirmation_if and replacement.argument_schema() == original.argument_schema(), 'passed': denied and confirmed_dispatch})
    finally:
        close_service(output / 'state')
    result = {'scope': 'Original dynamic gates, controlled handlers; no foreign effects', 'definitions': len(rows), 'passed': sum((r['passed'] for r in rows)), 'unauthorized_dispatches': sum((not r['confirmed'] for r in dispatched)), 'original_foreign_handler_dispatches': 0, 'results': rows}
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'results'}))
    assert rows and all((row['passed'] for row in rows))
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    audit(parser.parse_args().output)
