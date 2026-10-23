[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$DashboardOnly,
    [switch]$ReuseModel,
    [switch]$NoBrowser,
    [switch]$Desktop,
    [switch]$Text,
    [int]$Port = 8765,
    [int]$DesktopOwnerPid = 0,
    [string]$Device = '',
    [string]$ModelFile = ''
)
. (Join-Path $PSScriptRoot '_common.ps1')
$repoRoot = Get-HanniRepoRoot
$python = Initialize-HanniEnvironment -RepoRoot $repoRoot -SkipInstall
if (-not $SkipInstall) {
    $needed = @('hanni', 'huggingface_hub')
    if (-not $DashboardOnly -and -not $Text) {
        $needed += @('sounddevice', 'faster_whisper', 'silero_vad', 'onnxruntime', 'kokoro_onnx')
    }
    $moduleList = $needed -join ','
    & $python -c "import importlib.util, pathlib, sys; modules = '$moduleList'.split(','); spec = importlib.util.find_spec('hanni'); expected = pathlib.Path(r'$repoRoot') / 'src' / 'hanni' / '__init__.py'; installed = spec is not None and pathlib.Path(spec.origin).resolve() == expected.resolve(); sys.exit(0 if installed and all(importlib.util.find_spec(name) for name in modules) else 1)"
    if ($LASTEXITCODE -ne 0) {
        $extras = '.'
        if (-not $DashboardOnly -and -not $Text) { $extras = '.[speech,voice]' }
        Write-Host "Installing missing HANNI dependencies ..."
        & $python -m pip install -e $extras --quiet
        if ($LASTEXITCODE -ne 0) { throw 'HANNI dependency installation failed.' }
    } else {
        Write-Host "HANNI dependencies already installed."
    }
}
$launchArgs = @('-m', 'hanni.dashboard.launcher', '--port', [string]$Port)
if ($DashboardOnly) { $launchArgs += '--dashboard-only' }
if ($ReuseModel) { $launchArgs += '--reuse-model' }
if ($NoBrowser) { $launchArgs += '--no-browser' }
if ($Desktop -and -not $NoBrowser) { $launchArgs += '--desktop' }
if ($DesktopOwnerPid -gt 0) { $launchArgs += @('--desktop-owner-pid', [string]$DesktopOwnerPid) }
if ($Text) { $launchArgs += '--text' }
if ($Device) { $launchArgs += @('--device', $Device) }
if ($ModelFile) { $launchArgs += @('--model-file', $ModelFile) }
& $python @launchArgs
exit $LASTEXITCODE
