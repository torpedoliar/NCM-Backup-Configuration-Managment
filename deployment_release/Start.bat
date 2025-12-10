@echo off
title Allied Telesis Backup Manager

echo ========================================
echo Allied Telesis Backup Configuration Manager v3.5.5
echo ========================================
echo.
echo Build Date: 2025-11-21 07:52:14
echo.
echo Starting application...
echo.
if not exist "%~dp0AlliedTelesisBackup.exe" (
    echo ERROR: AlliedTelesisBackup.exe not found!
    echo Please ensure you extracted all files correctly.
    pause
    exit /b 1
)

if not exist "%~dp0data" mkdir "%~dp0data"
if not exist "%~dp0backups" mkdir "%~dp0backups"
if not exist "%~dp0logs" mkdir "%~dp0logs"

start "" "%~dp0AlliedTelesisBackup.exe"

timeout /t 2 /nobreak >nul
exit /b 0
