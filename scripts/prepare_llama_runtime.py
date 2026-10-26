"""Prepare a checksum-pinned, app-local Windows llama.cpp distribution."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import urllib.request
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'desktop/llama-runtime.lock.json'
REQUIRED = ('llama-server.exe', 'llama-bench.exe', 'llama.dll', 'ggml-base.dll')
WINDOWS_CRT = ('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')


def checksum(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_lock(path=LOCK):
    lock = json.loads(Path(path).read_text(encoding='utf-8'))
    if lock.get('schema') != 1 or not re.fullmatch(r'b\d+', lock.get('release', '')):
        raise ValueError('Invalid llama.cpp runtime lock file.')
    if {item['directory'] for item in lock['assets']} != {'windows-x86_64', 'windows-vulkan'} or len(lock['assets']) != 2:
        raise ValueError('The runtime lock must contain CPU and Vulkan Windows x64 builds.')
    for item in [*lock['assets'], lock['license']]:
        if not re.fullmatch(r'[a-f0-9]{64}', item['sha256']): raise ValueError('Missing runtime SHA-256.')
    for item in lock['assets']:
        prefix = f"https://github.com/ggml-org/llama.cpp/releases/download/{lock['release']}/"
        if not item['url'].startswith(prefix) or not item['url'].endswith('.zip'):
            raise ValueError('Runtime archives must come from the pinned upstream release.')
        if type(item['size']) is not int or not 0 < item['size'] <= 256 * 1024**2:
            raise ValueError('Invalid runtime archive size.')
    if lock['license']['url'] != f"https://raw.githubusercontent.com/ggml-org/llama.cpp/{lock['release']}/LICENSE":
        raise ValueError('Runtime license must match the pinned release.')
    return lock


def download(item, target, *, offline=False, fetch=urllib.request.urlopen):
    target = Path(target)
    if target.is_file() and checksum(target) == item['sha256']: return
    if offline: raise RuntimeError('Verified runtime download is not cached. Run the build once with internet access.')
    target.parent.mkdir(parents=True, exist_ok=True)
    limit = item.get('size', 65536)
    with tempfile.NamedTemporaryFile(dir=target.parent, suffix='.part', delete=False) as output:
        temporary = Path(output.name)
        try:
            request = urllib.request.Request(item['url'], headers={'User-Agent': 'HANNI-runtime-builder/1'})
            with fetch(request, timeout=60) as response:
                total = 0
                while chunk := response.read(1024**2):
                    total += len(chunk)
                    if total > limit: raise ValueError('Runtime download exceeded its pinned size.')
                    output.write(chunk)
            output.close()
            if 'size' in item and total != item['size']: raise ValueError('Runtime download was incomplete.')
            if checksum(temporary) != item['sha256']: raise ValueError('Runtime checksum mismatch. Nothing was installed.')
            temporary.replace(target)
        finally:
            output.close(); temporary.unlink(missing_ok=True)


def extract_runtime(archive, destination):
    """Extract only runtime executables, DLLs and notices; reject unsafe entries."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if len(entries) > 2000 or sum(item.file_size for item in entries) > 1024**3:
            raise ValueError('Runtime archive exceeded extraction limits.')
        seen = set()
        for item in entries:
            original_name = item.orig_filename
            name = PurePosixPath(item.filename)
            if (name.is_absolute() or '..' in name.parts or '\\' in original_name or ':' in original_name
                    or any(ord(c) < 32 for c in original_name)
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError('Runtime archive contains an unsafe path or symbolic link.')
            if item.is_dir(): continue
            # Upstream packages have either a flat layout or a single root.
            if len(name.parts) > 2: raise ValueError('Unexpected nested runtime archive layout.')
            relative = name.name
            keep = (relative in {'llama-server.exe', 'llama-bench.exe'}
                    or relative.lower().endswith(('.dll', '.txt', '.md'))
                    or relative.lower().startswith(('license', 'copying', 'notice')))
            if not keep: continue
            if relative.casefold() in seen: raise ValueError('Runtime archive has colliding filenames.')
            seen.add(relative.casefold())
            with bundle.open(item) as source, (destination / relative).open('xb') as output:
                shutil.copyfileobj(source, output)
    if not all((destination / name).is_file() for name in REQUIRED):
        raise ValueError('Runtime archive is missing its server, benchmark or required DLLs.')


def validate_cache(destination, lock):
    destination = Path(destination)
    manifest_path = destination / 'runtime-manifest.json'
    if not manifest_path.is_file(): return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['lock_sha256'] != hashlib.sha256(json.dumps(lock, sort_keys=True).encode()).hexdigest(): return False
        files = manifest['files']
        if not isinstance(files, dict) or not files: return False
        expected = {'LICENSE.llama.cpp.txt', 'THIRD_PARTY_NOTICES.txt',
                    *(f"{item['directory']}/{name}" for item in lock['assets'] for name in (*REQUIRED, *WINDOWS_CRT))}
        if not expected <= files.keys(): return False
        actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
        if actual != {*files, 'runtime-manifest.json'}: return False
        for name, digest in files.items():
            path = destination / name
            if not path.resolve().is_relative_to(destination.resolve()) or path.is_symlink() or checksum(path) != digest: return False
        return True
    except (OSError, ValueError, KeyError, TypeError): return False


def copy_windows_crt(stage, assets, *, source=None):
    """App-local deployment: consumers need no separate VC++ runtime install."""
    source = Path(source or Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32')
    for name in WINDOWS_CRT:
        path = source / name
        if not path.is_file():
            raise RuntimeError('The build machine needs the Microsoft Visual C++ x64 Redistributable to bundle its app-local runtime DLLs. See https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist .')
        # This package targets x64; refuse WOW64/ARM files from a wrong build environment.
        with path.open('rb') as stream:
            header = stream.read(64)
            if len(header) < 64 or header[:2] != b'MZ': raise ValueError('Invalid Windows CRT binary.')
            stream.seek(int.from_bytes(header[60:64], 'little'))
            signature = stream.read(6)
            if signature != b'PE\0\0\x64\x86': raise ValueError('The bundled Microsoft CRT must target Windows x64.')
        for item in assets: shutil.copy2(path, stage / item['directory'] / name)
    (stage / 'THIRD_PARTY_NOTICES.txt').write_text(
        'llama.cpp: MIT License; see LICENSE.llama.cpp.txt.\n'
        'Microsoft Visual C++ Runtime: Copyright Microsoft Corporation. All rights reserved.\n'
        'App-local DLLs originate from the build machine\'s Microsoft redistributable installation.\n'
        'Builders must have redistribution rights under their Microsoft Software License Terms.\n'
        'https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files\n'
        'https://visualstudio.microsoft.com/license-terms/\n', encoding='utf-8')


def prepare(destination, *, lock_path=LOCK, cache=None, offline=False):
    lock = load_lock(lock_path)
    destination = Path(destination).resolve()
    cache = Path(cache or ROOT / 'build/llama-downloads').resolve()
    if validate_cache(destination, lock): return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination == destination.parent or destination == ROOT or destination == Path.home().resolve():
        raise ValueError('Choose a dedicated runtime build directory.')
    if destination.exists() and any(destination.iterdir()) and not (destination / 'runtime-manifest.json').is_file():
        raise ValueError('Refusing to replace a directory that is not a prepared HANNI runtime cache.')
    with tempfile.TemporaryDirectory(prefix='llama-stage-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        for item in lock['assets']:
            archive = cache / item['url'].rsplit('/', 1)[-1]
            download(item, archive, offline=offline)
            extract_runtime(archive, stage / item['directory'])
        license_path = cache / f"LICENSE-{lock['release']}.txt"
        download(lock['license'], license_path, offline=offline)
        shutil.copy2(license_path, stage / 'LICENSE.llama.cpp.txt')
        copy_windows_crt(stage, lock['assets'])
        manifest = {'schema': 1, 'release': lock['release'], 'source': lock['source'],
            'lock_sha256': hashlib.sha256(json.dumps(lock, sort_keys=True).encode()).hexdigest(),
            'assets': lock['assets'],
            'files': {p.relative_to(stage).as_posix(): checksum(p) for p in sorted(stage.rglob('*')) if p.is_file()}}
        (stage / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        # Do not overwrite live DLLs or leave a partially updated runtime. Build
        # cache replacement uses a same-parent rename with rollback on failure.
        backup = destination.with_name(destination.name + '.previous')
        if backup.resolve().parent != destination.parent or stage.resolve().parent != destination.parent:
            raise RuntimeError('Runtime staging paths left the intended build directory.')
        if backup.exists(): raise RuntimeError('An earlier runtime backup exists. Inspect it before rebuilding.')
        if destination.exists(): destination.rename(backup)
        try: stage.rename(destination)
        except BaseException:
            if backup.exists(): backup.rename(destination)
            raise
        if backup.exists():
            if backup.resolve().parent != destination.parent:
                raise RuntimeError('Runtime backup left the intended build directory.')
            shutil.rmtree(backup)
    return destination


def verify(destination):
    if os.name != 'nt': raise RuntimeError('Verify the Windows runtime on Windows.')
    for directory in ('windows-x86_64', 'windows-vulkan'):
        path = Path(destination) / directory
        for name in ('llama-server.exe', 'llama-bench.exe'):
            result = subprocess.run([str(path / name), '--version'], cwd=path, capture_output=True,
                timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode: raise RuntimeError(f'Bundled {directory}/{name} failed its version check.')


def package_application(runtime, destination):
    runtime, destination = Path(runtime).resolve(), Path(destination).resolve()
    application = runtime.parents[2]
    if runtime != application / '_internal/runtimes/llama.cpp' or not (application / 'HANNI OS.exe').is_file():
        raise ValueError('Archive a built HANNI OS application, not an arbitrary directory.')
    if destination.is_relative_to(application): raise ValueError('The release archive must be outside the application directory.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.zip.part', delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with ZipFile(temporary, 'w', compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(application.rglob('*')):
                if path.is_symlink() or path.is_junction(): raise ValueError('Application package contains a filesystem link.')
                if path.is_file(): archive.write(path, application.name + '/' + path.relative_to(application).as_posix())
        temporary.replace(destination)
    finally: temporary.unlink(missing_ok=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=ROOT / 'build/llama-runtime')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--check-only', action='store_true', help='Verify an existing package without downloading or repairing it.')
    parser.add_argument('--archive', type=Path, help='Create a ZIP of the complete application containing this runtime.')
    args = parser.parse_args()
    if args.check_only:
        directory = args.destination.resolve()
        if not validate_cache(directory, load_lock()): raise RuntimeError('Packaged runtime integrity check failed. Rebuild the application.')
    else:
        directory = prepare(args.destination, offline=args.offline)
    if args.verify: verify(directory)
    if args.archive: print(f'Application archive ready: {package_application(directory, args.archive)}')
    print(f'Bundled llama.cpp {load_lock()["release"]} ready: {directory}')


if __name__ == '__main__': main()
