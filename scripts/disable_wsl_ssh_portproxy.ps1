param(
    [int]$ListenPort = 22
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$TaskName = "NCN Refresh WSL SSH PortProxy"
$FirewallName = "NCN WSL SSH"
$InstallDirectory = Join-Path $env:ProgramData "NCN"
$InstalledScript = Join-Path $InstallDirectory "enable_wsl_ssh_portproxy.ps1"
$LogPath = Join-Path $InstallDirectory "wsl-ssh-portproxy.log"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated Administrator PowerShell window."
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task: $TaskName"
} else {
    Write-Host "Scheduled task already absent: $TaskName"
}

netsh interface portproxy delete v4tov4 `
    listenaddress=0.0.0.0 listenport=$ListenPort | Out-Null
Write-Host "Removed portproxy: 0.0.0.0`:$ListenPort"

$firewall = Get-NetFirewallRule -DisplayName $FirewallName -ErrorAction SilentlyContinue
if ($firewall) {
    $firewall | Remove-NetFirewallRule
    Write-Host "Removed firewall rule: $FirewallName"
} else {
    Write-Host "Firewall rule already absent: $FirewallName"
}

if (Test-Path -LiteralPath $InstalledScript -PathType Leaf) {
    Remove-Item -LiteralPath $InstalledScript -Force
    Write-Host "Removed installed script: $InstalledScript"
}
if (Test-Path -LiteralPath $LogPath -PathType Leaf) {
    Remove-Item -LiteralPath $LogPath -Force
    Write-Host "Removed task log: $LogPath"
}

if (Test-Path -LiteralPath $InstallDirectory -PathType Container) {
    $remaining = @(Get-ChildItem -LiteralPath $InstallDirectory -Force)
    if ($remaining.Count -eq 0) {
        Remove-Item -LiteralPath $InstallDirectory -Force
        Write-Host "Removed empty directory: $InstallDirectory"
    }
}

Write-Host "Rollback completed. WSL and its SSH service were not stopped or modified."
netsh interface portproxy show v4tov4
