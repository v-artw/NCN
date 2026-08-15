@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%register_wsl_ssh_startup_task.ps1"

if not exist "%PS_SCRIPT%" (
    echo PowerShell script not found:
    echo %PS_SCRIPT%
    pause
    exit /b 1
)

echo Enabling WSL SSH autostart...
echo This must be run as Administrator.
echo You will be prompted for the Windows account password used by Task Scheduler.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Failed to enable WSL SSH autostart. Exit code: %EXIT_CODE%
) else (
    echo.
    echo WSL SSH autostart enabled successfully.
    echo TCP 22 and 8018 are being configured now.
    echo Check the task log at:
    echo   C:\ProgramData\NCN\wsl-ssh-bootstrap.log
)

pause
exit /b %EXIT_CODE%
