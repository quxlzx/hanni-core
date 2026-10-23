[CmdletBinding()]
param(
    [ValidateSet('text','voice')][string]$Mode = 'text',
    [string]$ModelId = 'supervisor',
    [string]$Device = '',
    [switch]$NoTts
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$python = Initialize-HanniEnvironment -RepoRoot (Get-HanniRepoRoot) -SkipInstall
& $python -m hanni.cli health --no-file-log
if ($LASTEXITCODE -ne 0) { throw 'Foundation health failed.' }
& $python -m hanni.cli model-health --model-id $ModelId
if ($LASTEXITCODE -ne 0) { throw 'Start the configured local model server, then retry.' }
$command = 'text'
if ($Mode -eq 'voice') { $command = 'attend' }
$runArgs = @('-m','hanni.cli',$command,'--model-id',$ModelId)
if ($Mode -eq 'voice') {
    if ($Device) { $runArgs += @('--device',$Device) }
    if ($NoTts) { $runArgs += '--no-tts' }
}
& $python @runArgs
if ($LASTEXITCODE -ne 0) { throw 'Assistant exited with an error.' }
