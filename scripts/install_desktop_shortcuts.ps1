[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$executable = Join-Path $repoRoot 'dist\HANNI OS\HANNI OS.exe'
if (-not (Test-Path -LiteralPath $executable)) { throw 'Build the desktop application before installing shortcuts.' }
$shell = New-Object -ComObject WScript.Shell
$startMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'HANNI'
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
$destinations = @((Join-Path $startMenu 'HANNI OS.lnk'), (Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'HANNI OS.lnk'))
foreach ($destination in $destinations) {
    $shortcut = $shell.CreateShortcut($destination)
    if ((Test-Path -LiteralPath $destination) -and $shortcut.TargetPath -ne $executable) {
        Write-Warning "A different application owns $destination; it was retained."
        continue
    }
    $shortcut.TargetPath = $executable
    $shortcut.WorkingDirectory = $repoRoot
    $shortcut.Arguments = '--repo-root "' + $repoRoot + '"'
    $shortcut.IconLocation = $executable + ',0'
    $shortcut.Description = 'HANNI assistant with background tasks and desktop notifications'
    $shortcut.Save()
    Write-Host "Installed $destination"
}
