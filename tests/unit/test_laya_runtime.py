from __future__ import annotations
from dataclasses import replace
from hanni.config.loader import load_config
from hanni.laya.runtime import advisory_for_config, current_advisory, stop_advisory
from hanni.laya.manager import stop_shadow

def test_runtime_is_scoped_default_disabled_and_read_only_lookup(tmp_path):
    config = load_config(data_dir=tmp_path, env={})
    stop_advisory()
    assert current_advisory(config) is None
    client = advisory_for_config(config)
    assert client.status == 'disabled'
    assert client._worker is None
    assert current_advisory(config) is client
    assert advisory_for_config(config) is client
    stop_shadow()
    assert current_advisory(config) is None

def test_config_changes_close_old_client_and_requested_flags_cannot_assert_gate(tmp_path):
    config = load_config(data_dir=tmp_path, env={})
    first = advisory_for_config(config)
    second_config = replace(config, hanni=replace(config.hanni, laya=replace(config.hanni.laya, advisory_enabled=True)))
    assert current_advisory(second_config) is None
    second = advisory_for_config(second_config)
    assert first._closed
    assert second.status.startswith('unavailable')
    assert second._worker is None
    assert not second.enabled
    stop_advisory(second_config)

def test_later_session_cannot_relax_controller_guard(tmp_path):
    config = load_config(data_dir=tmp_path, env={})
    first = advisory_for_config(config, admission_guard=lambda: False)
    second = advisory_for_config(config, admission_guard=lambda: True)
    assert first is second
    assert not second.admission_guard()
    stop_advisory(config)
