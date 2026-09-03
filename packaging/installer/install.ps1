# ==============================================================================
# Desktop Pet Automated Installer for Windows 10/11
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "     Desktop Pet Automated Installer (Windows)       " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

$InstallDir = "$env:LOCALAPPDATA\desktop-pet"
$StartupDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1. Check Python
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Python 3 is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3 from https://www.python.org/downloads/ (check Add to PATH)" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Python detected: $(python --version)" -ForegroundColor Green

# 2. Check Ollama
Write-Host "[2/5] Verifying Ollama AI engine..." -ForegroundColor Yellow
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "  ✓ Ollama CLI detected." -ForegroundColor Green
    $models = ollama list 2>$null
    if ($models -match "qwen2.5vl:7b") {
        Write-Host "  ✓ Vision AI model (qwen2.5vl:7b) is already downloaded." -ForegroundColor Green
    } else {
        Write-Host "  ! Model qwen2.5vl:7b not found." -ForegroundColor Yellow
        $pull = Read-Host "  Would you like to pull qwen2.5vl:7b now? (Y/N)"
        if ($pull -match "^[Yy]?$") {
            ollama pull qwen2.5vl:7b
        }
    }
} else {
    Write-Host "  ! Ollama is not installed. (You can still use Google Gemini API in .env)" -ForegroundColor Yellow
}

# 3. Create target directories
Write-Host "[3/5] Setting up target directory at $InstallDir..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$InstallDir\bin" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\assets\sprites" | Out-Null
New-Item -ItemType Directory -Force -Path "$InstallDir\pet-brain" | Out-Null

# 4. Copy Binaries & Assets
Write-Host "[4/5] Copying binaries, assets, and AI modules..." -ForegroundColor Yellow
if (Test-Path "$ScriptDir\bin") {
    Copy-Item -Recurse -Force "$ScriptDir\bin\*" "$InstallDir\bin\"
    Copy-Item -Recurse -Force "$ScriptDir\assets\sprites\*" "$InstallDir\assets\sprites\"
    Copy-Item -Recurse -Force "$ScriptDir\pet-brain\*" "$InstallDir\pet-brain\"
} else {
    if (Test-Path "$ScriptDir\..\..\pet-shell\target\release\pet-shell.exe") {
        Copy-Item -Force "$ScriptDir\..\..\pet-shell\target\release\pet-shell.exe" "$InstallDir\bin\pet-shell.exe"
    } elseif (Test-Path "$ScriptDir\..\pet-shell\target\release\pet-shell.exe") {
        Copy-Item -Force "$ScriptDir\..\pet-shell\target\release\pet-shell.exe" "$InstallDir\bin\pet-shell.exe"
    }
    Copy-Item -Recurse -Force "$ScriptDir\..\..\assets\sprites\*" "$InstallDir\assets\sprites\" -ErrorAction SilentlyContinue
    Copy-Item -Recurse -Force "$ScriptDir\..\..\pet-brain\core" "$InstallDir\pet-brain\" -ErrorAction SilentlyContinue
    Copy-Item -Recurse -Force "$ScriptDir\..\..\pet-brain\plugins" "$InstallDir\pet-brain\" -ErrorAction SilentlyContinue
    Copy-Item -Recurse -Force "$ScriptDir\..\..\pet-brain\scripts" "$InstallDir\pet-brain\" -ErrorAction SilentlyContinue
    Copy-Item -Force "$ScriptDir\..\..\pet-brain\main.py" "$InstallDir\pet-brain\" -ErrorAction SilentlyContinue
    Copy-Item -Force "$ScriptDir\..\..\pet-brain\pet_pb2.py" "$InstallDir\pet-brain\" -ErrorAction SilentlyContinue
    Copy-Item -Force "$ScriptDir\..\..\pet-brain\requirements.txt" "$InstallDir\pet-brain\" -ErrorAction SilentlyContinue
    Copy-Item -Force "$ScriptDir\..\..\pet-brain\.env.example" "$InstallDir\pet-brain\" -ErrorAction SilentlyContinue
}

# Setup Python Virtual Environment
Write-Host "[5/5] Configuring Python environment and shortcuts..." -ForegroundColor Yellow
Set-Location "$InstallDir\pet-brain"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& "$InstallDir\pet-brain\.venv\Scripts\python.exe" -m pip install --upgrade pip -q
& "$InstallDir\pet-brain\.venv\Scripts\python.exe" -m pip install -r requirements.txt -q

# Create Windows Launcher Batch Script
$LauncherBat = "$InstallDir\bin\desktop-pet.bat"
$BatContent = @"
@echo off
set DESKTOP_PET_ASSETS_DIR=$InstallDir\assets\sprites
set DESKTOP_PET_BRAIN_BIN=$InstallDir\pet-brain\.venv\Scripts\python.exe $InstallDir\pet-brain\main.py
start "" "$InstallDir\bin\pet-shell.exe" %*
"@
Set-Content -Path $LauncherBat -Value $BatContent

# Create Desktop and Startup Shortcuts via WScript.Shell
$WshShell = New-Object -ComObject WScript.Shell

# Desktop Shortcut
$DesktopShortcut = $WshShell.CreateShortcut("$DesktopDir\Desktop Pet.lnk")
$DesktopShortcut.TargetPath = "$InstallDir\bin\pet-shell.exe"
$DesktopShortcut.WorkingDirectory = "$InstallDir"
$DesktopShortcut.Description = "Interactive Multimodal Desktop AI Companion"
$DesktopShortcut.Save()

# Startup Shortcut
$StartupShortcut = $WshShell.CreateShortcut("$StartupDir\Desktop Pet.lnk")
$StartupShortcut.TargetPath = "$InstallDir\bin\pet-shell.exe"
$StartupShortcut.WorkingDirectory = "$InstallDir"
$StartupShortcut.Description = "Interactive Multimodal Desktop AI Companion"
$StartupShortcut.Save()

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  🎉 Desktop Pet Installed Successfully on Windows!  " -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Installed To  : $InstallDir"
Write-Host "Desktop Icon  : $DesktopDir\Desktop Pet.lnk"
Write-Host "Autostart     : Configured in Windows Startup"
Write-Host ""
Write-Host "You can launch Desktop Pet now from your Desktop shortcut!" -ForegroundColor Cyan
