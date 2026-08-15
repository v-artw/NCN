param(
    [string]$Distro = "Ubuntu",
    [int]$ListenPort = 22,
    [int]$MaxWaitSeconds = 120,
    [switch]$Install
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$TaskName = "NCN Refresh WSL SSH PortProxy"
$FirewallName = "NCN WSL SSH"
$InstallDirectory = Join-Path $env:ProgramData "NCN"
$InstalledScript = Join-Path $InstallDirectory "enable_wsl_ssh_portproxy.ps1"
$LogPath = Join-Path $InstallDirectory "wsl-ssh-portproxy.log"

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Run this script from an elevated Administrator PowerShell window."
    }
}

function Get-WslIpv4 {
    param(
        [string]$Distribution,
        [int]$WaitSeconds
    )

    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    do {
        $addresses = @()
        try {
            $addresses = (wsl.exe -d $Distribution -- hostname -I 2>$null).Trim().Split(
                ' ', [System.StringSplitOptions]::RemoveEmptyEntries
            )
        } catch {
            $addresses = @()
        }
        foreach ($address in $addresses) {
            $parsed = $null
            if ([System.Net.IPAddress]::TryParse($address, [ref]$parsed) -and
                $parsed.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork) {
                return $address
            }
        }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $deadline)

    throw "WSL distribution '$Distribution' did not provide an IPv4 address within $WaitSeconds seconds."
}

function Set-SshPortProxy {
    param(
        [string]$WslIp,
        [int]$Port
    )

    Set-Service -Name iphlpsvc -StartupType Automatic
    Start-Service -Name iphlpsvc

    netsh interface portproxy delete v4tov4 `
        listenaddress=0.0.0.0 listenport=$Port | Out-Null
    netsh interface portproxy add v4tov4 `
        listenaddress=0.0.0.0 listenport=$Port `
        connectaddress=$WslIp connectport=22 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to configure TCP $Port portproxy to $WslIp`:22."
    }

    Get-NetFirewallRule -DisplayName $FirewallName -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule
    New-NetFirewallRule `
        -DisplayName $FirewallName `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $Port `
        -Action Allow `
        -Profile Any `
        -RemoteAddress LocalSubnet | Out-Null
}

function Start-WslSsh {
    param([string]$Distribution)

    $command = @'
set -Eeuo pipefail
test -x /usr/sbin/sshd
mkdir -p /run/sshd
ssh-keygen -A
/usr/sbin/sshd -t
if ! service ssh restart >/dev/null 2>&1; then
    pkill -x sshd 2>/dev/null || true
    /usr/sbin/sshd
fi
ss -lnt | grep -Eq '(^|[[:space:]])[^[:space:]]*:22[[:space:]]'
'@
    $command | wsl.exe -d $Distribution -u root -- bash -se
    if ($LASTEXITCODE -ne 0) {
        throw "Ubuntu started, but WSL OpenSSH could not be started or is not listening on TCP 22."
    }
}

function Install-StartupTask {
    param(
        [string]$Distribution,
        [int]$Port,
        [int]$WaitSeconds
    )

    New-Item -ItemType Directory -Force -Path $InstallDirectory | Out-Null
    Copy-Item -LiteralPath $PSCommandPath -Destination $InstalledScript -Force

    $runUser = "$env:USERDOMAIN\$env:USERNAME"
    Write-Host "Task Scheduler needs the Windows password for the account that owns '$Distribution'."
    Write-Host "The credential is stored by Windows Task Scheduler and is not written to scripts or logs."
    $credential = Get-Credential -UserName $runUser -Message "Enter the Windows password for the WSL owner account."

    $commandText = @"
try {
    & '$($InstalledScript.Replace("'", "''"))' -Distro '$($Distribution.Replace("'", "''"))' -ListenPort $Port -MaxWaitSeconds $WaitSeconds *>&1 |
        Out-File -LiteralPath '$($LogPath.Replace("'", "''"))' -Encoding UTF8 -Append
    exit `$LASTEXITCODE
} catch {
    "TASK FAILED: `$(`$_.Exception.Message)" |
        Out-File -LiteralPath '$($LogPath.Replace("'", "''"))' -Encoding UTF8 -Append
    exit 1
}
"@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($commandText))
    $action = New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $encoded"
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -User $credential.UserName `
        -Password $credential.GetNetworkCredential().Password `
        -RunLevel Highest `
        -Description "Refresh Windows TCP 22 portproxy after WSL has been started by the existing startup configuration." `
        -Force | Out-Null
}

Assert-Administrator

if ($Install) {
    Install-StartupTask -Distribution $Distro -Port $ListenPort -WaitSeconds $MaxWaitSeconds
}

$wslIp = Get-WslIpv4 -Distribution $Distro -WaitSeconds $MaxWaitSeconds
Start-WslSsh -Distribution $Distro
Set-SshPortProxy -WslIp $wslIp -Port $ListenPort

Write-Host "WSL distribution: $Distro"
Write-Host "Current WSL IPv4: $wslIp"
Write-Host "WSL SSH: listening on TCP 22"
Write-Host "SSH portproxy: 0.0.0.0`:$ListenPort -> $wslIp`:22"
Write-Host "Firewall: $FirewallName, LocalSubnet only"
if ($Install) {
    Write-Host "Startup task installed: $TaskName"
    Write-Host "Installed script: $InstalledScript"
    Write-Host "Task log: $LogPath"
}
netsh interface portproxy show v4tov4
