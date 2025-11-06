# Install Allied Telesis Backup as Windows Service
# Run this script as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Allied Telesis Backup Service Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "Step 1: Installing required Python packages..." -ForegroundColor Yellow
pip install pywin32

Write-Host "Running pywin32 post-install script..." -ForegroundColor Yellow
python -c "import sys; from pathlib import Path; scripts = Path(sys.executable).parent / 'Scripts'; postinstall = scripts / 'pywin32_postinstall.py'; print(f'Post-install script: {postinstall}'); exec(open(postinstall).read() if postinstall.exists() else 'print(\"Post-install script not found\")')" -install 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Note: Post-install script may require manual run with admin privileges" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Step 2: Setting up master passphrase..." -ForegroundColor Yellow
Write-Host "Enter the master passphrase for credential encryption:" -ForegroundColor White
Write-Host "(This will be stored securely for the service to use)" -ForegroundColor Gray
$securePassphrase = Read-Host -AsSecureString
$passphrase = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassphrase))

if ($passphrase.Length -lt 8) {
    Write-Host "ERROR: Passphrase must be at least 8 characters long!" -ForegroundColor Red
    pause
    exit 1
}

# Save passphrase to secure location
$dataDir = "data"
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}

$passphraseFile = Join-Path $dataDir ".service_passphrase"
$passphrase | Out-File -FilePath $passphraseFile -Encoding UTF8 -NoNewline

# Set file permissions to restrict access
$acl = Get-Acl $passphraseFile
$acl.SetAccessRuleProtection($true, $false)
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("SYSTEM", "FullControl", "Allow")
$acl.AddAccessRule($rule)
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule($env:USERNAME, "FullControl", "Allow")
$acl.AddAccessRule($rule)
Set-Acl $passphraseFile $acl

Write-Host "Passphrase saved securely" -ForegroundColor Green

Write-Host ""
Write-Host "Step 3: Installing Windows Service..." -ForegroundColor Yellow

# Install the service
python app\windows_service.py install

if ($LASTEXITCODE -eq 0) {
    Write-Host "Service installed successfully!" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "Step 4: Configuring service startup..." -ForegroundColor Yellow
    
    # Set service to automatic startup
    Set-Service -Name "AlliedTelesisBackup" -StartupType Automatic
    
    Write-Host ""
    Write-Host "Would you like to start the service now? (Y/N)" -ForegroundColor Yellow
    $response = Read-Host
    
    if ($response -eq "Y" -or $response -eq "y") {
        Write-Host "Starting service..." -ForegroundColor Yellow
        Start-Service -Name "AlliedTelesisBackup"
        Start-Sleep -Seconds 2
        
        $service = Get-Service -Name "AlliedTelesisBackup"
        if ($service.Status -eq "Running") {
            Write-Host "Service started successfully!" -ForegroundColor Green
        } else {
            Write-Host "Service failed to start. Check logs in the 'logs' directory." -ForegroundColor Red
        }
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Installation Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "The service is now configured to start automatically with Windows." -ForegroundColor White
    Write-Host ""
    Write-Host "Service Management Commands:" -ForegroundColor Yellow
    Write-Host "  Start:   Start-Service -Name 'AlliedTelesisBackup'" -ForegroundColor Gray
    Write-Host "  Stop:    Stop-Service -Name 'AlliedTelesisBackup'" -ForegroundColor Gray
    Write-Host "  Status:  Get-Service -Name 'AlliedTelesisBackup'" -ForegroundColor Gray
    Write-Host "  Uninstall: .\uninstall_service.ps1" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Note: The GUI application can still be run separately for manual management." -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "ERROR: Service installation failed!" -ForegroundColor Red
    Write-Host "Check the error messages above for details." -ForegroundColor Yellow
}

pause
