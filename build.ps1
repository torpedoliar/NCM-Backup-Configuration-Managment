# PyInstaller build script for Windows
# Allied Telesis Backup Configuration Management v1.0

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Allied Telesis Backup Configuration Management" -ForegroundColor Green
Write-Host "Building Windows Executable..." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if PyInstaller is installed
Write-Host "Checking dependencies..." -ForegroundColor Yellow
$pyinstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyinstaller) {
    Write-Host "PyInstaller not found. Installing..." -ForegroundColor Yellow
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install PyInstaller!" -ForegroundColor Red
        exit 1
    }
}

# Clean previous builds
Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "*.spec") { Remove-Item -Force "*.spec" }

# Create deployment directory
$deployDir = "deployment"
if (Test-Path $deployDir) { Remove-Item -Recurse -Force $deployDir }
New-Item -ItemType Directory -Path $deployDir | Out-Null

# Build executable
Write-Host ""
Write-Host "Building executable (this may take a few minutes)..." -ForegroundColor Yellow
pyinstaller --onefile `
    --windowed `
    --name "AlliedTelesisBackup" `
    --icon NONE `
    --add-data "app/config;app/config" `
    --hidden-import "ttkbootstrap" `
    --hidden-import "paramiko" `
    --hidden-import "telnetlib3" `
    --hidden-import "apscheduler" `
    --hidden-import "sqlalchemy" `
    --hidden-import "cryptography" `
    --hidden-import "yaml" `
    --hidden-import "ntplib" `
    --collect-all ttkbootstrap `
    --collect-all sqlalchemy `
    app/main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

# Copy executable to deployment folder
Write-Host ""
Write-Host "Creating deployment package..." -ForegroundColor Yellow
Copy-Item "dist\AlliedTelesisBackup.exe" $deployDir

# Create required directories
New-Item -ItemType Directory -Path "$deployDir\data" -Force | Out-Null
New-Item -ItemType Directory -Path "$deployDir\backups" -Force | Out-Null
New-Item -ItemType Directory -Path "$deployDir\logs" -Force | Out-Null

# Copy documentation
Copy-Item "README.md" $deployDir -ErrorAction SilentlyContinue
Copy-Item "IMPLEMENTATION_GUIDE.md" $deployDir -ErrorAction SilentlyContinue

# Create version file
$versionInfo = @"
Allied Telesis Backup Configuration Management
Version: 3.5.5
Build Date: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Created by: Yohanes Octavian Rizky

System Requirements:
- Windows 10 or later
- Network connectivity to switches
- Administrator privileges (for some features)

Quick Start:
1. Run AlliedTelesisBackup.exe
2. Set master password on first run
3. Add credentials in Credentials tab
4. Add switches in Inventory tab
5. Start backing up!

Support:
- Check IMPLEMENTATION_GUIDE.md for detailed documentation
- Logs are stored in the 'logs' folder
- Backup configurations are stored in 'backups' folder
"@

$versionInfo | Out-File "$deployDir\VERSION.txt" -Encoding UTF8

# Create startup script
$startupScript = @"
@echo off
echo ========================================
echo Allied Telesis Backup Configuration Management
echo Version 3.5.5
echo ========================================
echo.
echo Starting application...
echo.
start "" "%~dp0AlliedTelesisBackup.exe"
"@

$startupScript | Out-File "$deployDir\Start.bat" -Encoding ASCII

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "BUILD SUCCESSFUL!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Deployment package created in: $deployDir" -ForegroundColor Cyan
Write-Host ""
Write-Host "Package contents:" -ForegroundColor Yellow
Write-Host "  - AlliedTelesisBackup.exe (main application)" -ForegroundColor White
Write-Host "  - Start.bat (quick launcher)" -ForegroundColor White
Write-Host "  - VERSION.txt (version information)" -ForegroundColor White
Write-Host "  - data/ (database folder)" -ForegroundColor White
Write-Host "  - backups/ (backup storage)" -ForegroundColor White
Write-Host "  - logs/ (application logs)" -ForegroundColor White
Write-Host "  - Documentation files" -ForegroundColor White
Write-Host ""
Write-Host "To distribute:" -ForegroundColor Yellow
Write-Host "  1. Zip the '$deployDir' folder" -ForegroundColor White
Write-Host "  2. Share with users" -ForegroundColor White
Write-Host "  3. Users extract and run Start.bat or AlliedTelesisBackup.exe" -ForegroundColor White
Write-Host ""
Write-Host "Executable size: $((Get-Item "dist\AlliedTelesisBackup.exe").Length / 1MB) MB" -ForegroundColor Cyan
Write-Host ""
