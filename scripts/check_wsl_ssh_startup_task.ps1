$ErrorActionPreference = "Continue"
Set-StrictMode -Version Latest

$TaskName = if ($env:NCN_WSL_SSH_TASK_NAME) { $env:NCN_WSL_SSH_TASK_NAME } else { "NCN WSL SSH Bootstrap" }
$Distro = if ($env:NCN_WSL_DISTRO) { $env:NCN_WSL_DISTRO } else { "Ubuntu" }
$ListenPort = if ($env:NCN_WSL_SSH_PORT) { [int]$env:NCN_WSL_SSH_PORT } else { 22 }
$LogPath = if ($env:NCN_WSL_SSH_LOG_PATH) { $env:NCN_WSL_SSH_LOG_PATH } else { Join-Path (Join-Path $env:ProgramData "NCN") "wsl-ssh-bootstrap.log" }

function Write-Section {
    param([Parameter(Mandatory = $true)] [string] $Title)
    Write-Host ""
    Write-Host "===== $Title ====="
}

function Test-SshBanner {
    param(
        [Parameter(Mandatory = $true)] [string] $ComputerName,
        [Parameter(Mandatory = $true)] [int] $Port,
        [int] $TimeoutMilliseconds = 3000
    )

    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect($ComputerName, $Port, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne($TimeoutMilliseconds)) {
            Write-Host "BANNER $ComputerName`:$Port = TIMEOUT"
            return
        }
        $client.EndConnect($connect)
        $stream = $client.GetStream()
        $stream.ReadTimeout = $TimeoutMilliseconds
        $buffer = New-Object byte[] 256
        $count = $stream.Read($buffer, 0, $buffer.Length)
        if ($count -le 0) {
            Write-Host "BANNER $ComputerName`:$Port = CLOSED_WITHOUT_BANNER"
            return
        }
        $banner = [Text.Encoding]::ASCII.GetString($buffer, 0, $count).Trim()
        if ($banner) {
            Write-Host "BANNER $ComputerName`:$Port = $banner"
        } else {
            Write-Host "BANNER $ComputerName`:$Port = EMPTY_BANNER"
        }
    } catch {
        Write-Host "BANNER $ComputerName`:$Port = ERROR: $($_.Exception.Message)"
    } finally {
        $client.Close()
    }
}

Write-Host "NCN WSL SSH diagnostics"
Write-Host "TaskName: $TaskName"
Write-Host "Distro: $Distro"
Write-Host "ListenPort: $ListenPort"
Write-Host "LogPath: $LogPath"
Write-Host "User: $env:USERDOMAIN\$env:USERNAME"
Write-Host "Computer: $env:COMPUTERNAME"

Write-Section "Scheduled Task"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    $task | Format-List TaskName, State, Author, Description
    $task.Triggers | Format-List *
    $task.Actions | Format-List *
    try {
        Get-ScheduledTaskInfo -TaskName $TaskName | Format-List LastRunTime, LastTaskResult, NextRunTime, NumberOfMissedRuns
    } catch {
        Write-Host "Get-ScheduledTaskInfo failed: $($_.Exception.Message)"
    }
} else {
    Write-Host "Task not found."
}

Write-Section "Bootstrap Log Tail"
if (Test-Path -LiteralPath $LogPath) {
    Get-Content -LiteralPath $LogPath -Tail 80
} else {
    Write-Host "Log not found: $LogPath"
}

Write-Section "WSL State"
wsl.exe --list --verbose
Write-Host "Default user in distro:"
wsl.exe -d $Distro -- bash -lc 'id -un; printf "home="; printf %s "$HOME"; printf "\n"' 2>&1
Write-Host "WSL IPv4 addresses:"
wsl.exe -d $Distro -- bash -lc 'hostname -I' 2>&1

Write-Section "WSL sshd State"
wsl.exe -d $Distro -u root -- bash -lc "/usr/sbin/sshd -t; echo sshd_config_exit=`$?; service ssh status || true; ss -lntp | awk '`$4 ~ /:22`$/ { print }'; pgrep -a sshd || true; pgrep -af 'dbus-daemon.*session' || echo ncn_wsl_dbus_session=missing; pgrep -af ncn-wsl-keepalive || echo ncn_wsl_keepalive=missing" 2>&1

Write-Section "Windows Portproxy"
netsh interface portproxy show all

Write-Section "Windows Port Listeners"
Get-NetTCPConnection -LocalPort $ListenPort -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
        $processName = try { (Get-Process -Id $_.OwningProcess -ErrorAction Stop).ProcessName } catch { "unknown" }
        [PSCustomObject]@{
            LocalAddress = $_.LocalAddress
            LocalPort = $_.LocalPort
            OwningProcess = $_.OwningProcess
            ProcessName = $processName
        }
    } | Format-Table -AutoSize

Write-Section "Firewall Rule"
Get-NetFirewallRule -DisplayName "NCN WSL SSH" -ErrorAction SilentlyContinue | Format-List DisplayName, Enabled, Direction, Action, Profile
Get-NetFirewallRule -DisplayName "NCN WSL SSH" -ErrorAction SilentlyContinue | Get-NetFirewallPortFilter | Format-List Protocol, LocalPort
Get-NetFirewallRule -DisplayName "NCN WSL SSH" -ErrorAction SilentlyContinue | Get-NetFirewallAddressFilter | Format-List RemoteAddress

Write-Section "Windows IPv4 Addresses"
$WindowsIpRows = @(
    Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object {
            $_.IPAddress -ne "127.0.0.1" -and
            $_.IPAddress -notlike "169.254*" -and
            $_.PrefixOrigin -ne "WellKnown"
        } |
        Select-Object InterfaceAlias, IPAddress, PrefixOrigin
)
$WindowsIpRows | Format-Table -AutoSize

Write-Section "TCP and SSH Banner Checks"
Test-NetConnection -ComputerName 127.0.0.1 -Port $ListenPort -WarningAction SilentlyContinue | Format-List ComputerName, RemotePort, TcpTestSucceeded
Test-SshBanner -ComputerName "127.0.0.1" -Port $ListenPort
foreach ($row in $WindowsIpRows) {
    Test-NetConnection -ComputerName $row.IPAddress -Port $ListenPort -WarningAction SilentlyContinue | Format-List ComputerName, RemotePort, TcpTestSucceeded
    Test-SshBanner -ComputerName $row.IPAddress -Port $ListenPort
}

Write-Host ""
Write-Host "Diagnostics complete. Copy or screenshot the output above."
