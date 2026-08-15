$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Distro = if ($env:NCN_WSL_DISTRO) { $env:NCN_WSL_DISTRO } else { "Ubuntu" }
$BootstrapScript = if ($env:NCN_WSL_SSH_BOOTSTRAP) {
    $env:NCN_WSL_SSH_BOOTSTRAP
} else {
    Join-Path $PSScriptRoot "bootstrap_remote_test_windows.ps1"
}
$StartupDelaySeconds = if ($env:NCN_WSL_STARTUP_DELAY_SECONDS) { [int]$env:NCN_WSL_STARTUP_DELAY_SECONDS } else { 3 }
$MaxWaitSeconds = if ($env:NCN_WSL_STARTUP_MAX_WAIT_SECONDS) { [int]$env:NCN_WSL_STARTUP_MAX_WAIT_SECONDS } else { 60 }

if (-not (Test-Path -LiteralPath $BootstrapScript -PathType Leaf)) {
    throw "Bootstrap script was not found: $BootstrapScript"
}

Write-Host "Starting WSL distribution: $Distro"
wsl.exe -d $Distro --exec /bin/sh -lc "exit 0"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start WSL distribution '$Distro'."
}

if ($StartupDelaySeconds -gt 0) {
    Start-Sleep -Seconds $StartupDelaySeconds
}

$deadline = (Get-Date).AddSeconds($MaxWaitSeconds)
$WslIp = ""
do {
    $WslIp = (wsl.exe -d $Distro -- bash -lc "hostname -I | tr ' ' '\n' | grep -m1 -E '^[0-9]+(\.[0-9]+){3}$'").Trim()
    if ($WslIp) {
        break
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

if (-not $WslIp) {
    throw "WSL distribution '$Distro' started, but no IPv4 address was available within $MaxWaitSeconds seconds."
}

Write-Host "WSL distribution is running with IPv4 address: $WslIp"
Write-Host "Starting WSL keepalive process"
wsl.exe -d $Distro -- bash -lc "command -v dbus-launch >/dev/null && dbus-launch true >/tmp/ncn-wsl-dbus-launch.log 2>&1 || true; pgrep -af 'dbus-daemon.*session' >/dev/null || pgrep -f 'ncn-wsl-keepalive' >/dev/null || nohup bash -c 'echo ncn-wsl-keepalive fallback started; while true; do sleep 3600; done' >/tmp/ncn-wsl-keepalive.log 2>&1 &"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start WSL keepalive process in '$Distro'."
}
Write-Host "WSL keepalive process started"
Write-Host "Running bootstrap: $BootstrapScript"
& $BootstrapScript
if ($LASTEXITCODE -ne 0) {
    throw "Bootstrap script failed with exit code $LASTEXITCODE."
}
