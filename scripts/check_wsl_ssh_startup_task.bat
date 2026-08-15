@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS_SCRIPT=%SCRIPT_DIR%check_wsl_ssh_startup_task.ps1"
set "LOG_FILE=%SCRIPT_DIR%wsl-ssh-diagnostics.log"

if not exist "%PS_SCRIPT%" (
    echo PowerShell script not found:
    echo %PS_SCRIPT%
    pause
    exit /b 1
)

echo Running WSL SSH startup diagnostics...
echo Output will be written to:
echo %LOG_FILE%
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" > "%LOG_FILE%" 2>&1
set "EXIT_CODE=%errorlevel%"

echo Diagnostics exited with code %EXIT_CODE%.
echo Diagnostics log:
echo %LOG_FILE%
echo.
echo Last 20 lines:
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path -LiteralPath '%LOG_FILE%') { Get-Content -LiteralPath '%LOG_FILE%' -Tail 20 }"

pause
exit /b %EXIT_CODE%
