# Register a Windows scheduled task that opens the review dialog every day.
# Run once:  powershell -ExecutionPolicy Bypass -File tools\install-daily-review.ps1
# Remove:    Unregister-ScheduledTask -TaskName "MultiVoice Daily Review" -Confirm:$false

param(
    [string]$At = "09:00"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonw = "D:\Local Repositories\_venvs\MultiVoice-Summary-Suit\Scripts\pythonw.exe"

if (-not (Test-Path $pythonw)) {
    throw "pythonw not found: $pythonw"
}

$action = New-ScheduledTaskAction `
    -Execute $pythonw `
    -Argument "-m multivoice.ui.tray --review" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Daily -At $At

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName "MultiVoice Daily Review" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Open the MultiVoice pending-term review dialog once a day" `
    -Force | Out-Null

Write-Host "Registered 'MultiVoice Daily Review' at $At" -ForegroundColor Green
Write-Host "Note: the task starts the tray app in review mode; if it is already"
Write-Host "running, the running instance keeps its own daily timer."
