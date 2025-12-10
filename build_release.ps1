# Allied Telesis Backup Manager - Simplified Release Build Script
# Based on build_production.ps1, but ASCII-only and reduced complexity

param(
    [switch]$SkipTests,
    [switch]$SkipClean,
    [string]$Version = "3.5.5",
    [string]$IconPath = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Configuration
$AppName = "AlliedTelesisBackup"
$BuildDate = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$DeploymentDir = "deployment_release"
$DistDir = "dist"
$BuildDir = "build"

# Helper functions
function Write-Step {
    param([string]$Message)
    Write-Host "" 
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Yellow
    Write-Host "==================================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "  $Message" -ForegroundColor White
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-ErrorCustom {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Test-Command {
    param([string]$Command)
    return ($null -ne (Get-Command $Command -ErrorAction SilentlyContinue))
}

Write-Host "" 
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host " Allied Telesis Backup - Release Build" -ForegroundColor Green
Write-Host " Version: $Version" -ForegroundColor Green
Write-Host " Build Date: $BuildDate" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# STEP 1: PRE-BUILD VALIDATION
Write-Step "STEP 1: Pre-Build Validation"

# Check Python
Write-Info "Checking Python installation..."
if (-not (Test-Command python)) {
    Write-ErrorCustom "Python not found in PATH!"
    exit 1
}
$pythonVersion = python --version 2>&1
Write-Success "Python found: $pythonVersion"

# Check pip
Write-Info "Checking pip..."
if (-not (Test-Command pip)) {
    Write-ErrorCustom "pip not found!"
    exit 1
}
Write-Success "pip is available"

# Check required files
Write-Info "Checking required files..."
$requiredFiles = @(
    "app/main.py",
    "app/config/appsettings.yaml",
    "requirements.txt"
)

foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-ErrorCustom "Required file missing: $file"
        exit 1
    }
}
Write-Success "All required files present"

# Check Python dependencies
Write-Info "Checking Python dependencies..."
$requiredPackages = @(
    "ttkbootstrap",
    "paramiko",
    "sqlalchemy",
    "cryptography",
    "apscheduler",
    "pyinstaller",
    "pillow"
)

$pipList = pip list --format=freeze
$missingPackages = @()
foreach ($package in $requiredPackages) {
    if ($pipList -notmatch "^$package=") {
        $missingPackages += $package
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Warning "Missing packages: $($missingPackages -join ', ')"
    Write-Info "Installing packages from requirements.txt..."
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorCustom "Failed to install dependencies!"
        exit 1
    }
    Write-Success "Dependencies installed"
} else {
    Write-Success "All required Python dependencies are installed"
}

# STEP 2: OPTIONAL CODE VALIDATION
if (-not $SkipTests) {
    Write-Step "STEP 2: Code Validation"
    Write-Info "Running Python syntax check (py_compile)..."
    python -m py_compile app/main.py
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorCustom "Syntax errors found in app/main.py"
        exit 1
    }
    Write-Success "Python syntax validation passed"
} else {
    Write-Warning "Skipping code validation (--SkipTests specified)"
}

# STEP 3: CLEAN PREVIOUS BUILDS
Write-Step "STEP 3: Clean Previous Builds"

if (-not $SkipClean) {
    $cleanDirs = @($BuildDir, $DistDir, $DeploymentDir)
    foreach ($dir in $cleanDirs) {
        if (Test-Path $dir) {
            Write-Info "Removing $dir..."
            Remove-Item -Recurse -Force $dir
        }
    }
    Get-ChildItem -Filter "*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Success "Cleanup complete"
} else {
    Write-Warning "Skipping cleanup (--SkipClean specified)"
}

# STEP 4: BUILD EXECUTABLE WITH PYINSTALLER
Write-Step "STEP 4: Build Executable (PyInstaller)"

# Determine icon argument
$iconArgument = "NONE"
if ($IconPath -and $IconPath.Trim() -ne "") {
    if (Test-Path $IconPath) {
        $resolvedIcon = (Resolve-Path $IconPath).Path
        $iconArgument = $resolvedIcon
        Write-Success "Using application icon: $resolvedIcon"
    } else {
        Write-Warning "Icon file not found: $IconPath. Using default icon."
    }
}

Write-Info "Starting PyInstaller build (this may take several minutes)..."
$buildStartTime = Get-Date

$pyinstallerArgs = @(
    "--onefile",
    "--windowed",
    "--name", $AppName,
    "--icon", $iconArgument,
    "--add-data", "app/config;app/config",
    "--hidden-import", "ttkbootstrap",
    "--hidden-import", "paramiko",
    "--hidden-import", "telnetlib3",
    "--hidden-import", "apscheduler",
    "--hidden-import", "sqlalchemy",
    "--hidden-import", "cryptography",
    "--hidden-import", "yaml",
    "--hidden-import", "ntplib",
    "--collect-all", "ttkbootstrap",
    "--collect-all", "sqlalchemy",
    "app/main.py"
)

pyinstaller @pyinstallerArgs

if ($LASTEXITCODE -ne 0) {
    Write-ErrorCustom "PyInstaller build failed!"
    exit 1
}

$buildEndTime = Get-Date
$buildDuration = ($buildEndTime - $buildStartTime).TotalSeconds

# Verify executable
if (-not (Test-Path "$DistDir\$AppName.exe")) {
    Write-ErrorCustom "Executable not found after build (expected: $DistDir\$AppName.exe)"
    exit 1
}

$exeItem = Get-Item "$DistDir\$AppName.exe"
$exeSizeMB = [math]::Round(($exeItem.Length / 1MB), 2)
Write-Success "Build completed in $([math]::Round($buildDuration, 1)) seconds"
Write-Info "Executable size: $exeSizeMB MB"

# STEP 5: CREATE DEPLOYMENT STRUCTURE
Write-Step "STEP 5: Create Deployment Package"

New-Item -ItemType Directory -Path $DeploymentDir -Force | Out-Null
New-Item -ItemType Directory -Path "$DeploymentDir\data" -Force | Out-Null
New-Item -ItemType Directory -Path "$DeploymentDir\backups" -Force | Out-Null
New-Item -ItemType Directory -Path "$DeploymentDir\logs" -Force | Out-Null
New-Item -ItemType Directory -Path "$DeploymentDir\docs" -Force | Out-Null

# Copy executable
Write-Info "Copying executable to deployment folder..."
Copy-Item "$DistDir\$AppName.exe" $DeploymentDir -Force

# Copy documentation (if present)
Write-Info "Copying documentation (if present)..."
$docsToInclude = @(
    "README.md",
    "IMPLEMENTATION_GUIDE.md",
    "DEPLOYMENT_BEST_PRACTICES.md",
    "CODE_REVIEW_SUMMARY.md",
    "TESTING_GUIDE.md",
    "memory.md"
)

foreach ($doc in $docsToInclude) {
    if (Test-Path $doc) {
        Copy-Item $doc "$DeploymentDir\docs\" -Force -ErrorAction SilentlyContinue
    }
}

Write-Success "Deployment structure created"

# STEP 6: GENERATE VERSION.TXT
Write-Step "STEP 6: Generate VERSION.txt and Start.bat"

$versionInfo = @"
Allied Telesis Backup Configuration Manager

Version:        $Version
Build Date:     $BuildDate
Build Type:     Release
Platform:       Windows x64
Executable:     $AppName.exe

Python Version: $pythonVersion
Build Duration: $([math]::Round($buildDuration, 1)) seconds
Executable Size: $exeSizeMB MB
"@

$versionInfo | Out-File "$DeploymentDir\VERSION.txt" -Encoding UTF8
Write-Success "VERSION.txt created"

# Start.bat
$startScript = @"
@echo off
title Allied Telesis Backup Manager

echo ========================================
echo Allied Telesis Backup Configuration Manager v$Version
echo ========================================
echo.
echo Build Date: $BuildDate
echo.
echo Starting application...
echo.
if not exist "%~dp0$AppName.exe" (
    echo ERROR: $AppName.exe not found!
    echo Please ensure you extracted all files correctly.
    pause
    exit /b 1
)

if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0backups" mkdir "%~dp0backups"
if not exist "%~dp0logs" mkdir "%~dp0logs"

start "" "%~dp0$AppName.exe"

timeout /t 2 /nobreak >nul
exit /b 0
"@

$startScript | Out-File "$DeploymentDir\Start.bat" -Encoding ASCII
Write-Success "Start.bat created"

# STEP 7: OPTIONAL MANIFEST AND ZIP PACKAGE
Write-Step "STEP 7: Create Distribution ZIP"

$zipName = "$($AppName)_v$($Version)_$((Get-Date).ToString('yyyyMMdd')).zip"

if (Test-Path $zipName) {
    Remove-Item $zipName -Force
}

Compress-Archive -Path "$DeploymentDir\*" -DestinationPath $zipName -CompressionLevel Optimal

if (Test-Path $zipName) {
    $zipSizeMB = [math]::Round((Get-Item $zipName).Length / 1MB, 2)
    Write-Success "Distribution package created: $zipName ($zipSizeMB MB)"
} else {
    Write-ErrorCustom "Failed to create distribution ZIP package"
    exit 1
}

# FINAL SUMMARY
Write-Host "" 
Write-Host "===============================================" -ForegroundColor Green
Write-Host " RELEASE BUILD SUCCESSFUL" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
Write-Info "Version:        $Version"
Write-Info "Build Date:     $BuildDate"
Write-Info "Build Duration: $([math]::Round($buildDuration, 1)) seconds"
Write-Info "Executable:     $DistDir\$AppName.exe ($exeSizeMB MB)"
Write-Info "Deployment:     $DeploymentDir\"
Write-Info "ZIP Package:    $zipName"
Write-Host ""
