[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('personal','school')][string]$Account,
    [Parameter(Mandatory=$true)][string]$Email,
    [Parameter(Mandatory=$true)][string]$ClientSecrets,
    [string[]]$Calendar = @('primary'),
    [switch]$Replace,
    [switch]$SkipInstall
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$clientPath = (Resolve-Path -LiteralPath $ClientSecrets).Path
$repoRoot = Get-HanniRepoRoot
$python = Initialize-HanniEnvironment -RepoRoot $repoRoot -SkipInstall
if (-not $SkipInstall) {
    & $python -m pip install -e '.[google]'
    if ($LASTEXITCODE -ne 0) { throw 'Google dependency installation failed.' }
}
$googleArgs = @('-m','hanni.tools.google_auth','connect','--account',$Account,'--email',$Email,'--client-secrets',$clientPath)
foreach ($id in $Calendar) { $googleArgs += @('--calendar',$id) }
if ($Replace) { $googleArgs += '--replace' }
& $python @googleArgs
if ($LASTEXITCODE -ne 0) { throw 'Google connection failed; see the message above.' }
