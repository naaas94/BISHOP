# Register (or remove) a Windows Scheduled Task that runs the Bishop
# host-side SQLite integrity-gated snapshot script on a fixed interval.
param(
    [string]$TaskName = "BishopSqliteSnapshot",
    [int]$IntervalMinutes = 30,
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$scriptPath = Join-Path $repoRoot "scripts\sqlite_snapshot.py"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "required command not found: python"
    exit 1
}
$python = (Get-Command python).Source

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Unregistered scheduled task: $TaskName"
    exit 0
}

if (-not (Test-Path -LiteralPath $scriptPath)) {
    Write-Error "snapshot script not found: $scriptPath"
    exit 1
}

$action = New-ScheduledTaskAction -Execute $python -Argument "`"$scriptPath`""
$interval = New-TimeSpan -Minutes $IntervalMinutes
# Task Scheduler rejects [TimeSpan]::MaxValue on some hosts; ~10 years is "indefinite".
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval $interval -RepetitionDuration ([TimeSpan]::FromDays(3650))

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Description "Bishop integrity-gated SQLite snapshot (host-side, read-only backup API)." `
    -Force | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Write-Host "  user:     $env:USERNAME"
Write-Host "  python:   $python"
Write-Host "  script:   $scriptPath"
Write-Host "  interval: every $IntervalMinutes minutes"
