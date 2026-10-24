from __future__ import annotations
from hanni.config.loader import load_config
from hanni.tools.capabilities import capability_catalog
from hanni.tools.capability_api import CapabilityAPI
from hanni.tools.capability_metadata import NAMESPACE_DOMAIN, READ_WRITE_CLASSES, RISKS, STATES
from hanni.tools.registry import build_default_registry
from tests.helpers import write_config_dir

def test_every_registered_capability_has_consistent_metadata(tmp_path):
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    registry = build_default_registry(config)
    catalog = capability_catalog(registry)
    assert len(catalog) == len(registry.definitions()) == 175
    assert 12 <= len({cap.family for cap in catalog}) <= 20
    assert {cap.subfamily for cap in catalog} <= NAMESPACE_DOMAIN.keys()
    assert all((cap.family and cap.subfamily and cap.source for cap in catalog))
    assert all((cap.state in STATES and cap.risk in RISKS for cap in catalog))
    assert all((cap.read_write_class in READ_WRITE_CLASSES for cap in catalog))
    assert all((cap.permission == f'level_{cap.permission_level}' for cap in catalog))
    assert all((cap.requires == cap.prerequisites for cap in catalog))
    assert all((cap.priority == 0 and cap.introduced_version == 'legacy_untracked' for cap in catalog))
    assert all((cap.read_write_class == 'destructive' for cap in catalog if cap.risk == 'destructive'))
    by_name = {cap.name: cap for cap in catalog}
    assert by_name['gmail.read'].risk == 'credential_sensitive'
    assert by_name['email.read'].risk == 'credential_sensitive'
    assert by_name['google_calendar.create'].risk == 'sensitive_write'
    assert by_name['file.delete'].risk == 'destructive'
    assert by_name['app.open'].risk == 'low_risk_write'
    schema = CapabilityAPI(registry).get('google_calendar.agenda')
    assert schema['family'] == 'productivity'
    assert schema['source'] == 'google_oauth'
    assert schema['read_write_class'] == 'read'

def test_generic_command_is_classified_high_impact(tmp_path):
    config = load_config(write_config_dir(tmp_path / 'config'), data_dir=tmp_path / 'data', env={})
    registry = build_default_registry(config)
    shell = next((cap for cap in capability_catalog(registry) if cap.name == 'powershell.run'))
    assert shell.risk == 'destructive'
    assert shell.read_write_class == 'destructive'
    assert shell.permission_level == 3
