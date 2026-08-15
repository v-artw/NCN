@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%unregister_wsl_ssh_startup_task.ps1"

if not exist "%PS_SCRIPT%" (
    echo PowerShell script not found:
    echo %PS_SCRIPT%
    pause
    exit /b 1
)

echo Disabling WSL SSH autostart...
echo This must be run as Administrator.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Failed to disable WSL SSH autostart. Exit code: %EXIT_CODE%
) else (
    echo.
    echo WSL SSH autostart disabled successfully.
)

pause
exit /b %EXIT_CODE%
