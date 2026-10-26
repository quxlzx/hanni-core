# Build from an isolated native client environment; backend/models stay in the repo.
from pathlib import Path

desktop = Path(SPECPATH)
runtime = desktop.parent / 'build/llama-runtime'
if not (runtime / 'runtime-manifest.json').is_file():
    raise RuntimeError('Prepare the bundled engine first: python scripts/prepare_llama_runtime.py --verify')
a = Analysis([str(desktop/'main.py')], pathex=[str(desktop)],
    binaries=[], datas=[(str(desktop/'hanni.ico'), '.'), (str(runtime), 'runtimes/llama.cpp')],
    hiddenimports=['webview.platforms.winforms', 'webview.platforms.edgechromium', 'pystray._win32'],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'cefpython3', 'tkinter', 'gi', 'hanni', 'torch', 'transformers'],
    noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='HANNI OS', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=False,
    icon=str(desktop/'hanni.ico'), version=str(desktop/'version.txt'),
    manifest=str(desktop/'app.manifest'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='HANNI OS')
