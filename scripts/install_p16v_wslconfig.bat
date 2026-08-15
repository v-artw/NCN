@echo off
setlocal EnableExtensions

set "TARGET=%USERPROFILE%\.wslconfig"

if exist "%TARGET%\NUL" (
    echo ERROR: %TARGET% is a directory, but WSL requires it to be a file.
    echo Remove or rename that directory, then run this installer again.
    pause
    exit /b 1
)

if exist "%TARGET%" (
    for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set "DATESTAMP=%%a%%b%%c"
    set "BACKUP=%TARGET%.backup-%DATESTAMP%-%RANDOM%"
    copy /y "%TARGET%" "%BACKUP%" >nul
    if errorlevel 1 (
        echo ERROR: Failed to back up existing configuration.
        pause
        exit /b 1
    )
    echo Existing configuration backed up to:
    echo %BACKUP%
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "$content = '[wsl2]`r`nmemory=20GB`r`nprocessors=20`r`nswap=4GB`r`nlocalhostForwarding=true`r`n`r`n[experimental]`r`nautoMemoryReclaim=gradual`r`nsparseVhd=true`r`n'; [IO.File]::WriteAllText('%TARGET%', $content, [Text.Encoding]::ASCII)"
if errorlevel 1 (
    echo ERROR: Failed to install %TARGET%
    pause
    exit /b 1
)

echo.
echo Installed WSL configuration:
echo %TARGET%
echo.
type "%TARGET%"
echo.
echo The configuration has NOT been applied yet.
echo Stop the remote study first, then run in PowerShell:
echo   wsl --shutdown
echo Restart Ubuntu and resume the study afterward.
pause
exit /b 0
