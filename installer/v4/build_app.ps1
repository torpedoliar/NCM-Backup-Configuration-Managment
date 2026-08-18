param(
  [switch]$SkipWebBuild,
  [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $ProjectRoot

Write-Host "==> NCM v4 production build" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

if (-not $SkipWebBuild) {
  Write-Host "==> Building web bundle..." -ForegroundColor Cyan
  & npm --prefix app_v4/web run build
  if ($LASTEXITCODE -ne 0) { throw "npm build failed" }
}

if ($Clean -and (Test-Path "build")) {
  Write-Host "==> Cleaning build/" -ForegroundColor Cyan
  Remove-Item -Recurse -Force "build"
}
if ($Clean -and (Test-Path "dist/ncm-v4-desktop")) {
  Write-Host "==> Cleaning dist/ncm-v4-desktop" -ForegroundColor Cyan
  Remove-Item -Recurse -Force "dist/ncm-v4-desktop"
}

Write-Host "==> Running PyInstaller..." -ForegroundColor Cyan
& python -m PyInstaller "installer/v4/ncm-v4-desktop.spec" --clean --noconfirm
if ($LASTEXITCODE -ne 0) { throw "pyinstaller failed" }

$exePath = Join-Path $ProjectRoot "dist\ncm-v4-desktop\ncm-v4-desktop.exe"
if (-not (Test-Path $exePath)) {
  throw "Executable not produced: $exePath"
}

$size = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
Write-Host ""
Write-Host "==> Build OK" -ForegroundColor Green
Write-Host "Executable: $exePath ($size MB)"
Write-Host "Folder    : $(Split-Path $exePath -Parent)"
Write-Host ""
Write-Host "Run with:  & '$exePath'"
