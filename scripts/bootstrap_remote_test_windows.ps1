$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Distro = if ($env:NCN_WSL_DISTRO) { $env:NCN_WSL_DISTRO } else { "Ubuntu" }
$ListenPort = if ($env:NCN_WSL_SSH_PORT) { [int]$env:NCN_WSL_SSH_PORT } else { 22 }
$ServicePort = if ($env:NCN_WSL_SERVICE_PORT) { [int]$env:NCN_WSL_SERVICE_PORT } else { 8018 }
$FirewallName = "NCN WSL SSH"
$ServiceFirewallName = "NCN WSL Service 8018"
$PublicKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICVtzWODnSjGyz0IS8NnsgVy+GWO0s+MUBmo5R0XD9aO cnstock-artx@ArtX Macbook Air"

function Test-SshBanner {
    param(
        [Parameter(Mandatory = $true)] [string] $ComputerName,
        [Parameter(Mandatory = $true)] [int] $Port,
        [int] $TimeoutMilliseconds = 5000
    )

    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect($ComputerName, $Port, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne($TimeoutMilliseconds)) {
            throw "Timed out connecting to $ComputerName`:$Port."
        }
        $client.EndConnect($connect)
        $stream = $client.GetStream()
        $stream.ReadTimeout = $TimeoutMilliseconds
        $buffer = New-Object byte[] 256
        $count = $stream.Read($buffer, 0, $buffer.Length)
        $banner = [Text.Encoding]::ASCII.GetString($buffer, 0, $count).Trim()
        if (-not $banner.StartsWith("SSH-")) {
            throw "Expected SSH banner from $ComputerName`:$Port, received '$banner'."
        }
        return $banner
    } finally {
        $client.Close()
    }
}

function Get-PortListeners {
    param([Parameter(Mandatory = $true)] [int] $Port)

    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            $processName = try { (Get-Process -Id $_.OwningProcess -ErrorAction Stop).ProcessName } catch { "unknown" }
            [PSCustomObject]@{
                LocalAddress = $_.LocalAddress
                LocalPort = $_.LocalPort
                OwningProcess = $_.OwningProcess
                ProcessName = $processName
            }
        }
}

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($currentIdentity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated Administrator PowerShell window."
}

$distros = @(wsl.exe --list --quiet | ForEach-Object { $_.Trim("`0", " ", "`t", "`r", "`n") } | Where-Object { $_ })
if ($Distro -notin $distros) {
    throw "WSL distribution '$Distro' was not found. Available distributions: $($distros -join ', ')"
}

$WslUser = if ($env:NCN_WSL_USER) {
    $env:NCN_WSL_USER
} else {
    (wsl.exe -d $Distro -- bash -lc 'id -un').Trim()
}
if (-not $WslUser) {
    throw "Could not determine the default WSL user for '$Distro'. Set NCN_WSL_USER explicitly."
}

wsl.exe -d $Distro -u root -- id $WslUser | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "WSL user '$WslUser' does not exist in '$Distro'."
}

$WslHome = (wsl.exe -d $Distro -u $WslUser -- bash -lc 'printf %s "$HOME"').Trim()
$WslUid = (wsl.exe -d $Distro -u $WslUser -- bash -lc 'id -u').Trim()
$WslGid = (wsl.exe -d $Distro -u $WslUser -- bash -lc 'id -g').Trim()
if (-not $WslHome -or -not $WslUid -or -not $WslGid) {
    throw "Could not determine WSL account details for '$WslUser'."
}

$PublicKeyBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($PublicKey))
$WslHomeBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($WslHome))

$bootstrapTemplate = @'
set -Eeuo pipefail
trap 'echo "WSL bootstrap failed at line $LINENO: $BASH_COMMAND" >&2' ERR
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y openssh-server python3 python3-venv python3-dev build-essential rsync iproute2 procps dbus-x11
PUBLIC_KEY="$(printf '%s' '__PUBLIC_KEY_B64__' | base64 -d)"
WSL_HOME="$(printf '%s' '__WSL_HOME_B64__' | base64 -d)"
WSL_UID='__WSL_UID__'
WSL_GID='__WSL_GID__'
install -d -m 700 -o "$WSL_UID" -g "$WSL_GID" "$WSL_HOME/.ssh"
touch "$WSL_HOME/.ssh/authorized_keys"
grep -qxF "$PUBLIC_KEY" "$WSL_HOME/.ssh/authorized_keys" || printf '%s\n' "$PUBLIC_KEY" >> "$WSL_HOME/.ssh/authorized_keys"
chown "$WSL_UID:$WSL_GID" "$WSL_HOME/.ssh/authorized_keys"
chmod 600 "$WSL_HOME/.ssh/authorized_keys"
mkdir -p /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/99-ncn-wsl.conf <<'EOF'
PubkeyAuthentication yes
PasswordAuthentication no
PermitRootLogin no
EOF
mkdir -p /run/sshd
ssh-keygen -A
/usr/sbin/sshd -t
if ! service ssh restart; then
  pkill -x sshd 2>/dev/null || true
  /usr/sbin/sshd
fi
ss -lntp | grep -E '(^|[[:space:]])[^[:space:]]*:22[[:space:]]' >/dev/null
'@

$bootstrap = $bootstrapTemplate.Replace("__PUBLIC_KEY_B64__", $PublicKeyBase64)
$bootstrap = $bootstrap.Replace("__WSL_HOME_B64__", $WslHomeBase64)
$bootstrap = $bootstrap.Replace("__WSL_UID__", $WslUid)
$bootstrap = $bootstrap.Replace("__WSL_GID__", $WslGid)

$bootstrap | wsl.exe -d $Distro -u root -- bash -se
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install or start OpenSSH inside WSL."
}

$WslIp = (wsl.exe -d $Distro -- bash -lc "hostname -I | tr ' ' '\n' | grep -m1 -E '^[0-9]+(\.[0-9]+){3}$'").Trim()
$parsedWslIp = $null
if (-not [System.Net.IPAddress]::TryParse($WslIp, [ref]$parsedWslIp)) {
    throw "Could not determine a valid WSL IPv4 address. Received: '$WslIp'"
}

Set-Service -Name iphlpsvc -StartupType Automatic
Start-Service -Name iphlpsvc

$WindowsAddresses = @(
    Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object {
            $_.IPAddress -ne "127.0.0.1" -and
            $_.IPAddress -notlike "169.254*" -and
            $_.PrefixOrigin -ne "WellKnown"
        } |
        Select-Object -ExpandProperty IPAddress
)
$conflictingListeners = @(
    Get-PortListeners -Port $ListenPort |
        Where-Object { $_.LocalAddress -notin @("127.0.0.1", "::1") } |
        Where-Object { $_.ProcessName -ne "svchost" }
)
if ($conflictingListeners.Count -gt 0) {
    $details = ($conflictingListeners | ForEach-Object { "$($_.LocalAddress):$($_.LocalPort) pid=$($_.OwningProcess) process=$($_.ProcessName)" }) -join "; "
    throw "TCP port $ListenPort is already owned on a non-localhost address by a non-portproxy process: $details. Stop or move that service before using Windows-to-WSL portproxy."
}

netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=$ListenPort | Out-Null
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=$ListenPort connectaddress=$WslIp connectport=22 | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to configure Windows portproxy for SSH TCP $ListenPort."
}

netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=$ServicePort | Out-Null
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=$ServicePort connectaddress=$WslIp connectport=$ServicePort | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Failed to configure Windows portproxy for service TCP $ServicePort."
}

Get-NetFirewallRule -DisplayName $FirewallName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule `
    -DisplayName $FirewallName `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort $ListenPort `
    -Action Allow `
    -Profile Any `
    -RemoteAddress LocalSubnet | Out-Null

Get-NetFirewallRule -DisplayName $ServiceFirewallName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule `
    -DisplayName $ServiceFirewallName `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort $ServicePort `
    -Action Allow `
    -Profile Any `
    -RemoteAddress LocalSubnet | Out-Null

$localCheck = Test-NetConnection -ComputerName 127.0.0.1 -Port $ListenPort -WarningAction SilentlyContinue
if (-not $localCheck.TcpTestSucceeded) {
    throw "Windows port $ListenPort is not forwarding to WSL SSH."
}

$LocalSshBanner = Test-SshBanner -ComputerName "127.0.0.1" -Port $ListenPort
$AddressBanners = foreach ($address in $WindowsAddresses) {
    try {
        "$address => $(Test-SshBanner -ComputerName $address -Port $ListenPort)"
    } catch {
        "$address => ERROR: $($_.Exception.Message)"
    }
}

Write-Host "NCN remote test bootstrap completed."
Write-Host "Distribution: $Distro"
Write-Host "WSL user:     $WslUser"
Write-Host "WSL home:     $WslHome"
Write-Host "WSL address:  $WslIp"
Write-Host "SSH endpoint: $env:COMPUTERNAME`:$ListenPort"
Write-Host "Service endpoint: $env:COMPUTERNAME`:$ServicePort"
Write-Host "Local SSH banner: $LocalSshBanner"
Write-Host "Windows IPv4 addresses for Mac SSH: $($WindowsAddresses -join ', ')"
Write-Host "Windows address SSH banners:"
foreach ($banner in $AddressBanners) {
    Write-Host "  $banner"
}
Write-Host "The Mac public key is installed; no Windows or WSL password is stored."
Write-Host "Windows portproxy rules:"
netsh interface portproxy show v4tov4
