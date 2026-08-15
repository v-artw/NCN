@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%register_wsl_ssh_startup_task.ps1"

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

echo Registering startup task to start WSL first, then refresh WSL SSH...
echo You will be prompted for the Windows account password used by Task Scheduler.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Registration failed with exit code %EXIT_CODE%.
) else (
    echo.
    echo Registration completed successfully.
    echo You can test it with:
    echo   Start-ScheduledTask -TaskName "NCN WSL SSH Bootstrap"
)

pause
exit /b %EXIT_CODE%
