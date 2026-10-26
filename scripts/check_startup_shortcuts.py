"""Opt-in Windows shortcut verification; only disposable folders are modified."""
import os,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def powershell(script, *args):
    return subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), *map(str, args)],
        capture_output=True, text=True, timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def test_startup_shortcut_is_idempotent_and_repairs_a_stale_installation(tmp_path):
    # The real Startup/Desktop folders are never touched in this check.
    startup = tmp_path / 'isolated Startup'
    repo = tmp_path / 'work laptop install'; executable = repo / 'dist/HANNI OS/HANNI OS.exe'
    executable.parent.mkdir(parents=True); executable.write_bytes(b'fixture-not-executed')
    script = ROOT / 'scripts/install_desktop_shortcuts.ps1'
    args = ['-Startup', '-OnlyStartup', '-StartupFolder', startup, '-RepositoryRoot', repo]
    for _ in range(2):
        result = powershell(script, *args); assert result.returncode == 0, result.stderr
    assert [p.name for p in startup.iterdir()] == ['HANNI OS.lnk']
    executable.unlink()
    relocated = tmp_path / 'new work laptop install'; relocated_exe = relocated / 'dist/HANNI OS/HANNI OS.exe'
    relocated_exe.parent.mkdir(parents=True); relocated_exe.write_bytes(b'fixture-not-executed')
    result = powershell(script, '-Startup', '-OnlyStartup', '-StartupFolder', startup, '-RepositoryRoot', relocated)
    assert result.returncode == 0 and 'Repairing' in result.stdout, result.stderr
    inspect = tmp_path / 'inspect.ps1'
    inspect.write_text('param([string]$Path)\n$s=New-Object -ComObject WScript.Shell\n$l=$s.CreateShortcut($Path)\n@{target=$l.TargetPath;cwd=$l.WorkingDirectory;args=$l.Arguments}|ConvertTo-Json -Compress\n')
    metadata = json.loads(powershell(inspect, '-Path', startup / 'HANNI OS.lnk').stdout)
    assert metadata['target'] == str(relocated_exe) and metadata['cwd'] == str(relocated)
    assert metadata['args'] == '--repo-root "' + str(relocated) + '"'

if os.name != "nt": raise SystemExit("Run this isolated shortcut check on Windows.")
with tempfile.TemporaryDirectory(prefix="hanni-startup-review-") as scratch:
    test_startup_shortcut_is_idempotent_and_repairs_a_stale_installation(Path(scratch))
print({"isolated_startup_shortcut_valid":True,"idempotent":True,"stale_target_repaired":True,"real_startup_folder_changed":False})
