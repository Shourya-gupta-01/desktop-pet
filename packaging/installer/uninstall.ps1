# ==============================================================================
# Desktop Pet Uninstaller for Windows
# ==============================================================================

$InstallDir = "$env:LOCALAPPDATA\desktop-pet"
$StartupShortcut = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Desktop Pet.lnk"
$DesktopShortcut = "$([Environment]::GetFolderPath("Desktop"))\Desktop Pet.lnk"

Write-Host "Uninstalling Desktop Pet..." -ForegroundColor Yellow

if (Test-Path $StartupShortcut) {
    Remove-Item -Force $StartupShortcut
}
if (Test-Path $DesktopShortcut) {
    Remove-Item -Force $DesktopShortcut
}
if (Test-Path $InstallDir) {
    Remove-Item -Recurse -Force $InstallDir
}

Write-Host "Desktop Pet uninstalled successfully." -ForegroundColor Green
