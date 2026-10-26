"""Pinned runtime packaging, safe extraction and app-local startup selection."""
from io import BytesIO
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile, ZipInfo

import pytest

from hanni.models import bundled_runtime, runtime
from hanni.native.probe import Facts
from tests.test_stick import firstboot
from tests.unit.test_desktop import desktop

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('prepare_llama_runtime', ROOT / 'scripts/prepare_llama_runtime.py')
builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)


def archive(path, entries=None):
    with ZipFile(path, 'w') as bundle:
        for name in builder.REQUIRED:
            bundle.writestr(name, b'fixture-binary')
        bundle.writestr('llama-cli.exe', b'omit unrelated CLI')
        bundle.writestr('THIRD_PARTY.txt', b'upstream notice')
        for name, value in (entries or {}).items(): bundle.writestr(name, value)


def test_lock_pins_both_official_archives_and_license():
    lock = builder.load_lock()
    assert {row['directory'] for row in lock['assets']} == {'windows-vulkan', 'windows-x86_64'}
    assert all(len(row['sha256']) == 64 for row in [*lock['assets'], lock['license']])
    assert lock['release'] in lock['license']['url']


def test_validated_download_checks_size_and_digest_and_reuses_offline_cache(tmp_path):
    raw = b'fixture-runtime-zip'
    item = {'url': 'https://example.test/archive.zip', 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    target = tmp_path / 'archive.zip'
    fetch = Mock(return_value=BytesIO(raw))
    builder.download(item, target, fetch=fetch)
    builder.download(item, target, offline=True, fetch=fetch)
    assert fetch.call_count == 1 and target.read_bytes() == raw
    target.write_bytes(b'bad')
    with pytest.raises(RuntimeError, match='not cached'): builder.download(item, target, offline=True)


@pytest.mark.parametrize('raw', [b'too long for the pin', b'bad'])
def test_bad_download_never_replaces_existing_archive_or_leaves_partial_file(tmp_path, raw):
    target = tmp_path / 'archive.zip'; target.write_bytes(b'previous')
    item = {'url': 'https://example.test/archive.zip', 'size': 10, 'sha256': '0' * 64}
    with pytest.raises(ValueError): builder.download(item, target, fetch=lambda *args, **kw: BytesIO(raw))
    assert target.read_bytes() == b'previous'
    assert list(tmp_path.iterdir()) == [target]


def test_extraction_keeps_all_dlls_and_notices_but_omits_other_executables(tmp_path):
    source = tmp_path / 'runtime.zip'; archive(source, {'ggml-vulkan.dll': b'gpu', 'vendor-license.md': b'notice'})
    output = tmp_path / 'output'
    builder.extract_runtime(source, output)
    assert (output / 'ggml-vulkan.dll').read_bytes() == b'gpu'
    assert (output / 'vendor-license.md').is_file()
    assert not (output / 'llama-cli.exe').exists()


@pytest.mark.parametrize('entry', ['../escape.dll', '/absolute.dll', 'C:/escape.dll', 'root\\escape.dll', 'root/../../escape.dll'])
def test_archive_traversal_is_rejected(tmp_path, entry):
    source = tmp_path / 'runtime.zip'; archive(source, {entry: b'bad'})
    # ZipFile normalizes native backslashes when creating an archive on Windows;
    # restore the hostile raw entry name in both ZIP headers for this check.
    if '\\' in entry:
        source.write_bytes(source.read_bytes().replace(entry.replace('\\', '/').encode(), entry.encode()))
    with pytest.raises(ValueError, match='unsafe'): builder.extract_runtime(source, tmp_path / 'output')
    assert not (tmp_path / 'escape.dll').exists()


def test_archive_symlink_and_flattened_filename_collisions_are_rejected(tmp_path):
    for symlink in (True, False):
        source = tmp_path / f'runtime-{symlink}.zip'
        with ZipFile(source, 'w') as bundle:
            if symlink:
                info = ZipInfo('outside.dll'); info.external_attr = (stat.S_IFLNK | 0o777) << 16
                bundle.writestr(info, '../outside')
            else:
                bundle.writestr('a/llama.dll', b'a'); bundle.writestr('b/llama.dll', b'b')
        with pytest.raises(ValueError): builder.extract_runtime(source, tmp_path / str(symlink))


def test_assembled_cache_detects_damage_missing_dependencies_and_lock_changes(tmp_path, monkeypatch):
    lock = builder.load_lock()
    cache = tmp_path / 'downloads'; cache.mkdir()
    for item in lock['assets']:
        path = cache / item['url'].rsplit('/', 1)[-1]; archive(path)
        item['size'] = path.stat().st_size; item['sha256'] = builder.checksum(path)
    license_path = cache / f"LICENSE-{lock['release']}.txt"; license_path.write_bytes(b'fixture license')
    lock['license']['sha256'] = builder.checksum(license_path)
    lock_path = tmp_path / 'lock.json'; lock_path.write_text(json.dumps(lock))
    def copy_crt(stage, assets, **kwargs):
        for asset in assets:
            for name in builder.WINDOWS_CRT: (stage / asset['directory'] / name).write_bytes(b'fixture-crt')
        (stage / 'THIRD_PARTY_NOTICES.txt').write_text('fixture notices')
    monkeypatch.setattr(builder, 'copy_windows_crt', copy_crt)
    output = builder.prepare(tmp_path / 'runtime', lock_path=lock_path, cache=cache, offline=True)
    assert builder.validate_cache(output, lock)
    assert builder.prepare(output, lock_path=lock_path, cache=cache, offline=True) == output
    (output / 'windows-vulkan/llama.dll').write_bytes(b'damaged')
    assert not builder.validate_cache(output, lock)
    builder.prepare(output, lock_path=lock_path, cache=cache, offline=True)
    assert builder.validate_cache(output, lock)
    (output / 'windows-x86_64/msvcp140.dll').unlink()
    assert not builder.validate_cache(output, lock)
    lock['release'] = 'b1'
    assert not builder.validate_cache(output, lock)


def test_prepare_refuses_to_replace_unrelated_directory(tmp_path):
    (tmp_path / 'personal.txt').write_text('keep')
    with pytest.raises(ValueError, match='not a prepared'): builder.prepare(tmp_path, offline=True)
    assert (tmp_path / 'personal.txt').read_text() == 'keep'


def test_explicit_packaged_runtime_wins_without_path_or_winget(tmp_path, monkeypatch):
    bundle = tmp_path / 'copied-app/_internal/runtimes/llama.cpp'
    directory = bundle / ('windows-vulkan' if os.name == 'nt' else 'linux-vulkan')
    directory.mkdir(parents=True)
    server = directory / ('llama-server.exe' if os.name == 'nt' else 'llama-server'); server.write_bytes(b'fixture')
    monkeypatch.setenv('HANNI_LLAMA_RUNTIME_DIR', str(bundle))
    with patch.object(runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
         patch.object(runtime.shutil, 'which', side_effect=AssertionError('PATH must not be consulted')):
        assert runtime.executable_prefix() == [str(server)]


def test_packaged_cpu_fallback_beats_old_developer_cpu_runtime(tmp_path, monkeypatch):
    bundle = tmp_path / 'app/_internal/runtimes/llama.cpp'
    monkeypatch.setenv('HANNI_LLAMA_RUNTIME_DIR', str(bundle))
    monkeypatch.setattr(firstboot, 'STICK', tmp_path)
    cpu = 'windows-x86_64' if os.name == 'nt' else 'linux-x86_64'
    gpu = 'windows-vulkan' if os.name == 'nt' else 'linux-vulkan'
    for directory in (bundle / gpu, bundle / cpu, tmp_path / 'binaries' / cpu):
        directory.mkdir(parents=True)
        for name in ('llama-server', 'llama-bench'): (directory / name).write_bytes(b'fixture')
    with patch.object(firstboot.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
         patch('hanni.native.acceleration.devices', return_value=[]):
        assert firstboot.pick_binary(Facts()) == bundle / cpu


def test_desktop_passes_its_own_runtime_path_to_backend(tmp_path, monkeypatch):
    bundle = tmp_path / 'runtime'; bundle.mkdir(); (bundle / 'runtime-manifest.json').write_text('{}')
    monkeypatch.setattr(desktop, 'resource_path', lambda name: bundle)
    process = Mock(); process.poll.return_value = None
    popen = Mock(return_value=process)
    session = desktop.BackendSession(desktop.DEFAULT_URL, ROOT, verify=lambda url: False, popen=popen)
    session.start_assistant(tmp_path)
    assert popen.call_args.kwargs['env']['HANNI_LLAMA_RUNTIME_DIR'] == str(bundle.resolve())
    session.log.close()


def test_crt_packaging_requires_complete_x64_dependencies(tmp_path):
    assets = [{'directory': 'windows-x86_64'}, {'directory': 'windows-vulkan'}]
    stage = tmp_path / 'stage'; source = tmp_path / 'crt'; source.mkdir()
    for item in assets: (stage / item['directory']).mkdir(parents=True)
    with pytest.raises(RuntimeError, match='Redistributable'):
        builder.copy_windows_crt(stage, assets, source=source)
    pe = bytearray(70); pe[:2] = b'MZ'; pe[60:64] = (64).to_bytes(4, 'little'); pe[64:70] = b'PE\0\0\x4c\x01'
    for name in builder.WINDOWS_CRT: (source / name).write_bytes(pe)
    with pytest.raises(ValueError, match='x64'):
        builder.copy_windows_crt(stage, assets, source=source)
    pe[68:70] = b'\x64\x86'
    for name in builder.WINDOWS_CRT: (source / name).write_bytes(pe)
    builder.copy_windows_crt(stage, assets, source=source)
    assert all((stage / item['directory'] / name).is_file() for item in assets for name in builder.WINDOWS_CRT)
    assert (stage / 'THIRD_PARTY_NOTICES.txt').is_file()


def test_release_archive_contains_the_complete_app_and_rejects_output_inside_it(tmp_path):
    application = tmp_path / 'HANNI OS'; runtime = application / '_internal/runtimes/llama.cpp'
    runtime.mkdir(parents=True)
    (application / 'HANNI OS.exe').write_bytes(b'fixture-client')
    (runtime / 'runtime-manifest.json').write_text('{}')
    (runtime / 'LICENSE.llama.cpp.txt').write_text('fixture license')
    destination = builder.package_application(runtime, tmp_path / 'release.zip')
    with ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert 'HANNI OS/HANNI OS.exe' in archive.namelist()
        assert 'HANNI OS/_internal/runtimes/llama.cpp/LICENSE.llama.cpp.txt' in archive.namelist()
    with pytest.raises(ValueError, match='outside'):
        builder.package_application(runtime, application / 'recursive.zip')
