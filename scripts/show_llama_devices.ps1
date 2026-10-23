<#
.SYNOPSIS
    Show the GPUs visible to H.A.N.N.I.'s llama.cpp runtime.
#>
[CmdletBinding()]
param()

$server = Get-Command llama-server -ErrorAction SilentlyContinue
$llama = Get-Command llama -ErrorAction SilentlyContinue
$winGetBase = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe'
$winGetServer = Join-Path $winGetBase 'llama-server.exe'
$winGetLlama = Join-Path $winGetBase 'llama.exe'
if (-not $server -and (Test-Path $winGetServer)) { $server = @{ Source = $winGetServer } }
if (-not $llama -and (Test-Path $winGetLlama)) { $llama = @{ Source = $winGetLlama } }

if ($server) {
    & $server.Source --list-devices
    exit $LASTEXITCODE
}
if ($llama) {
    & $llama.Source cli --list-devices
    exit $LASTEXITCODE
}
throw "llama.cpp not found. Run SETUP_HANNI.cmd first."
