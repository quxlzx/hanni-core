[CmdletBinding()]
param([switch]$Startup, [switch]$OnlyStartup, [string]$StartupFolder, [string]$RepositoryRoot)
$ErrorActionPreference = 'Stop'
$repoRoot = if ($RepositoryRoot) { (Resolve-Path -LiteralPath $RepositoryRoot).Path } else { Split-Path -Parent $PSScriptRoot }
$executable = Join-Path $repoRoot 'dist\HANNI OS\HANNI OS.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw 'Build the desktop application before installing shortcuts.' }
$shell = New-Object -ComObject WScript.Shell
$destinations = @()
if (-not $OnlyStartup) {
    $startMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'HANNI'
    New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
    $destinations += @((Join-Path $startMenu 'HANNI OS.lnk'), (Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'HANNI OS.lnk'))
}
if ($Startup) {
    $loginFolder = if ($StartupFolder) { [System.IO.Path]::GetFullPath($StartupFolder) } else { [Environment]::GetFolderPath('Startup') }
    if (-not $loginFolder) { throw 'Windows did not provide a Startup folder for this account.' }
    New-Item -ItemType Directory -Path $loginFolder -Force | Out-Null
    $destinations += (Join-Path $loginFolder 'HANNI OS.lnk')
}
foreach ($destination in $destinations) {
    $shortcut = $shell.CreateShortcut($destination)
    if ((Test-Path -LiteralPath $destination) -and $shortcut.TargetPath -ne $executable) {
        $ownedHanni = ([System.IO.Path]::GetFileName($shortcut.TargetPath) -eq 'HANNI OS.exe') -and ($shortcut.Description -like 'HANNI*')
        if ($ownedHanni) {
            Write-Host 'Repairing the HANNI shortcut to use this installation.'
        } elseif ($Startup -and $destination -eq (Join-Path $loginFolder 'HANNI OS.lnk')) {
            throw 'Another application owns the HANNI OS startup shortcut. It was not overwritten.'
        } else {
            Write-Warning "A different application owns $destination; it was retained."
            continue
        }
    }
    $shortcut.TargetPath = $executable
    $shortcut.WorkingDirectory = $repoRoot
    $shortcut.Arguments = '--repo-root "' + $repoRoot + '"'
    $shortcut.IconLocation = $executable + ',0'
    $shortcut.Description = 'HANNI assistant with background tasks and desktop notifications'
    $shortcut.Save()
    $saved = $shell.CreateShortcut($destination)
    if ($saved.TargetPath -ne $executable -or $saved.WorkingDirectory -ne $repoRoot) { throw 'Windows did not save a valid HANNI shortcut.' }
    Write-Host "Installed $destination"
}
if ($Startup) { Write-Host 'Windows startup: HANNI OS is registered for this account at sign-in (no administrator rights required).' }
