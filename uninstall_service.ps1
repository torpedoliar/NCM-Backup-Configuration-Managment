# Uninstall Allied Telesis Backup Windows Service
# Run this script as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Allied Telesis Backup Service Uninstaller" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Requesting Administrator privileges..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$((Get-Location).Path)\uninstall_service.ps1`"" -Verb RunAs
    exit
}

Write-Host "This will uninstall the Allied Telesis Backup Windows Service." -ForegroundColor Yellow
Write-Host "Are you sure you want to continue? (Y/N)" -ForegroundColor Yellow
$response = Read-Host

if ($response -ne "Y" -and $response -ne "y") {
    Write-Host "Uninstall cancelled." -ForegroundColor Gray
    pause
    exit 0
}

Write-Host ""
Write-Host "Step 1: Stopping service..." -ForegroundColor Yellow

# Stop the service if running
$service = Get-Service -Name "AlliedTelesisBackup" -ErrorAction SilentlyContinue
if ($service) {
    if ($service.Status -eq "Running") {
        Stop-Service -Name "AlliedTelesisBackup" -Force
        Start-Sleep -Seconds 2
        Write-Host "Service stopped" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Step 2: Uninstalling service..." -ForegroundColor Yellow

# Uninstall the service
python app\windows_service.py remove

if ($LASTEXITCODE -eq 0) {
    Write-Host "Service uninstalled successfully!" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "Step 3: Cleaning up..." -ForegroundColor Yellow
    
    # Ask if user wants to delete passphrase file
    Write-Host "Do you want to delete the stored passphrase file? (Y/N)" -ForegroundColor Yellow
    $response = Read-Host
    
    if ($response -eq "Y" -or $response -eq "y") {
        $passphraseFile = "data\.service_passphrase"
        if (Test-Path $passphraseFile) {
            Remove-Item $passphraseFile -Force
            Write-Host "Passphrase file deleted" -ForegroundColor Green
        }
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Uninstall Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "The Windows Service has been removed." -ForegroundColor White
    Write-Host "You can still use the GUI application for manual backups." -ForegroundColor Cyan
    Write-Host ""
}
else {
    Write-Host "ERROR: Service uninstall failed!" -ForegroundColor Red
    Write-Host "The service may not be installed or there was an error." -ForegroundColor Yellow
}

pause
