@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%bootstrap_remote_test_windows.ps1"

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

if not exist "%PS_SCRIPT%" (
    echo PowerShell script not found:
    echo %PS_SCRIPT%
    pause
    exit /b 1
)

echo Running WSL SSH bootstrap...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Bootstrap failed with exit code %EXIT_CODE%.
) else (
    echo.
    echo Bootstrap completed successfully.
)

pause
exit /b %EXIT_CODE%
