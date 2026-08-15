$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$TaskName = if ($env:NCN_WSL_SSH_TASK_NAME) { $env:NCN_WSL_SSH_TASK_NAME } else { "NCN WSL SSH Bootstrap" }
$SourceBootstrapScript = if ($env:NCN_WSL_SSH_BOOTSTRAP) {
    $env:NCN_WSL_SSH_BOOTSTRAP
} else {
    Join-Path $PSScriptRoot "bootstrap_remote_test_windows.ps1"
}
$SourceRunnerScript = if ($env:NCN_WSL_SSH_RUNNER) {
    $env:NCN_WSL_SSH_RUNNER
} else {
    Join-Path $PSScriptRoot "start_wsl_then_bootstrap_remote_test_windows.ps1"
}
$InstallDir = if ($env:NCN_WSL_SSH_INSTALL_DIR) {
    $env:NCN_WSL_SSH_INSTALL_DIR
} else {
    Join-Path $env:ProgramData "NCN"
}
$InstalledBootstrapScript = Join-Path $InstallDir "bootstrap_remote_test_windows.ps1"
$InstalledRunnerScript = Join-Path $InstallDir "start_wsl_then_bootstrap_remote_test_windows.ps1"
$LogPath = Join-Path $InstallDir "wsl-ssh-bootstrap.log"
$RunUser = if ($env:NCN_WSL_SSH_RUN_USER) { $env:NCN_WSL_SSH_RUN_USER } else { "$env:USERDOMAIN\$env:USERNAME" }

$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($currentIdentity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated Administrator PowerShell window."
}

if (-not (Test-Path -LiteralPath $SourceBootstrapScript -PathType Leaf)) {
    throw "Bootstrap script was not found: $SourceBootstrapScript"
}
if (-not (Test-Path -LiteralPath $SourceRunnerScript -PathType Leaf)) {
    throw "Runner script was not found: $SourceRunnerScript"
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -LiteralPath $SourceBootstrapScript -Destination $InstalledBootstrapScript -Force
Copy-Item -LiteralPath $SourceRunnerScript -Destination $InstalledRunnerScript -Force
"[$(Get-Date -Format o)] Installed runner and bootstrap from $PSScriptRoot" | Out-File -LiteralPath $LogPath -Encoding UTF8 -Append

$encodedCommandText = @"
try {
    & '$($InstalledRunnerScript.Replace("'", "''"))' *>&1 | Out-File -LiteralPath '$($LogPath.Replace("'", "''"))' -Encoding UTF8 -Append
    exit `$LASTEXITCODE
} catch {
    "TASK FAILED: `$(`$_.Exception.Message)" | Out-File -LiteralPath '$($LogPath.Replace("'", "''"))' -Encoding UTF8 -Append
    "`$(`$_.ScriptStackTrace)" | Out-File -LiteralPath '$($LogPath.Replace("'", "''"))' -Encoding UTF8 -Append
    exit 1
}
"@
$encodedCommand = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($encodedCommandText))
$actionArgument = "-NoProfile -ExecutionPolicy Bypass -EncodedCommand $encodedCommand"

Write-Host "This will register a Windows startup task that can run before interactive login."
Write-Host "Windows stores the task credential using Task Scheduler. The password is not written to repo files or logs."
Write-Host "Run user: $RunUser"
$credential = Get-Credential -UserName $RunUser -Message "Enter the Windows password for the account that owns the WSL distro."

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArgument
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -User $credential.UserName `
    -Password $credential.GetNetworkCredential().Password `
    -RunLevel Highest `
    -Description "Refresh WSL OpenSSH, Windows portproxy, and firewall for NCN remote access at Windows startup before interactive login." `
    -Force | Out-Null

Write-Host "Scheduled task registered: $TaskName"
Write-Host "Trigger: At Windows startup"
Write-Host "Run mode: Whether user is logged on or not"
Write-Host "Run level: Highest"
Write-Host "Run user: $($credential.UserName)"
Write-Host "Installed runner: $InstalledRunnerScript"
Write-Host "Installed bootstrap: $InstalledBootstrapScript"
Write-Host "Log: $LogPath"
Write-Host "Starting the task now to apply the current WSL IP and portproxy rules."
Start-ScheduledTask -TaskName $TaskName
Write-Host "Task started. Check status with: Get-ScheduledTaskInfo -TaskName '$TaskName'"
