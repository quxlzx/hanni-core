# Shared PowerShell helpers for the H.A.N.N.I. start scripts (Milestone 0).
# Dot-source this file; do not run it directly.

$ErrorActionPreference = "Stop"

function Get-HanniRepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Initialize-HanniEnvironment {
    param(
        [string]$RepoRoot,
        [switch]$SkipInstall
    )
    Set-Location $RepoRoot

    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Host "Creating virtual environment in .venv ..."
        
        # The launcher default can be an older Python even when 3.12 is installed.
        $created = $false
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3.12 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                & py -3.12 -m venv .venv
                if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
                $created = $true
            }
        }

        if (-not $created) {
            $pythonExe = $null
            $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
            if ($pythonCommand) {
                & $pythonCommand.Source -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" 2>$null
                if ($LASTEXITCODE -eq 0) { $pythonExe = $pythonCommand.Source }
            }
            $searchPaths = @(
                "C:\Program Files\Python*\python.exe",
                "C:\Program Files (x86)\Python*\python.exe",
                "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe"
            )
            if (-not $pythonExe) {
                foreach ($pattern in $searchPaths) {
                    foreach ($found in @(Get-Item $pattern -ErrorAction SilentlyContinue)) {
                        & $found.FullName -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" 2>$null
                        if ($LASTEXITCODE -eq 0) { $pythonExe = $found.FullName; break }
                    }
                    if ($pythonExe) { break }
                }
            }
            if (-not $pythonExe) {
                throw "Python 3.12+ not found. Install it from python.org and re-run SETUP_HANNI.cmd."
            }
            & $pythonExe -m venv .venv
            if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
        }
    }

    if (-not $SkipInstall) {
        Write-Host "Installing H.A.N.N.I. (editable) and dev dependencies ..."
        & $venvPython -m pip install --upgrade pip --quiet
        if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
        & $venvPython -m pip install -e "." --quiet
        if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
    }

    if (-not (Test-Path (Join-Path $RepoRoot ".env"))) {
        Write-Host "No .env file (none needed in V1; see .env.example for optional overrides)."
    }

    $env:PATH = "$(Split-Path $venvPython -Parent)$([IO.Path]::PathSeparator)$env:PATH"
    return $venvPython
}
