"""Independent exposed-development security assertions; no private holdout access."""
import pytest
from scripts.campaign9_verification import development

@pytest.mark.parametrize('probe', [development.malformed_confirmation, development.pending_confirmation, development.sensitive_source, development.dispatch_boundary, development.mcp_outgoing_credentials, development.memory_disclosure, lambda root: development.logging_disclosure(), development.http_disclosure, development.client_boundaries])
def test_independent_original_security_boundaries(tmp_path, probe, subtests):
    for row in probe(tmp_path):
        with subtests.test(id=row['id'], scope=row['scope']):
            assert row['passed'], row

def test_development_fixture_registry_keeps_original_handlers(tmp_path):
    from hanni.tools import files, content, powershell
    result = development.registry(tmp_path)
    for module in (files, content, powershell):
        for definition in module.definitions():
            assert result.get(definition.name).handler is definition.handler
