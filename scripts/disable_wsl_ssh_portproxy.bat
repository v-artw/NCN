@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%disable_wsl_ssh_portproxy.ps1"

if not exist "%PS_SCRIPT%" (
    echo ERROR: PowerShell script not found:
    echo %PS_SCRIPT%
    pause
    exit /b 1
)

net session >nul 2>&1
if errorlevel 1 (
    echo Requesting Administrator privileges...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
        "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
    exit /b %errorlevel%
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo SSH portproxy rollback failed. Exit code: %EXIT_CODE%
) else (
    echo.
    echo SSH portproxy startup configuration removed.
)

pause
exit /b %EXIT_CODE%
