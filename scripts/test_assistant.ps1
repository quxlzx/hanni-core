[CmdletBinding()]
param([switch]$SkipInstall, [switch]$FullSuite)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
$python = Initialize-HanniEnvironment -RepoRoot (Get-HanniRepoRoot) -SkipInstall:$SkipInstall
if ($FullSuite) { & $python -m pytest -ra }
else { & $python -m pytest tests/unit/test_model_first.py tests/unit/test_google_access.py tests/unit/test_task_tools.py tests/unit/test_source_export.py -ra }
if ($LASTEXITCODE -ne 0) { throw 'Assistant regression failed.' }
& $python scripts/capability_routing_check.py --strict
if ($LASTEXITCODE -ne 0) { throw 'Routing regression failed.' }
& $python scripts/capability_safety_check.py
if ($LASTEXITCODE -ne 0) { throw 'Capability safety failed.' }
& $python scripts/capability_matrix.py --check
if ($LASTEXITCODE -ne 0) { throw 'Capability documentation is stale.' }
& $python -m compileall -q src scripts
if ($LASTEXITCODE -ne 0) { throw 'Python syntax validation failed.' }
& $python -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency failed.' }
$badScripts = @()
Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1' | ForEach-Object {
    $tokens = $null
    $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors.Count -gt 0) { $badScripts += $_.Name; $parseErrors | ForEach-Object { Write-Host $_.Message } }
}
if ($badScripts.Count -gt 0) { throw "PowerShell syntax errors: $($badScripts -join ', ')" }
Write-Host 'PASS: automated assistant checks. Live voice/model/Google acceptance is separate.' -ForegroundColor Green
