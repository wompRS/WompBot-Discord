# PowerShell script to create a Windows Task Scheduler task for WSL auto-start
# Run this script as Administrator

$TaskName = "WSL-Discord-Bot-AutoStart"
$TaskDescription = "Automatically start WSL and Discord bot on Windows startup"

# Check if running as admin
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Remove existing task if it exists
Write-Host "Checking for existing task..." -ForegroundColor Cyan
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the action (start WSL and run the startup script)
Write-Host "Creating scheduled task..." -ForegroundColor Cyan
$Action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-e bash -c '/mnt/e/discord-bot/start-bot.sh'"

# Create the trigger (at system startup, with a 30 second delay to let services start)
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Trigger.Delay = "PT30S"

# Create additional trigger for when user logs on (backup)
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn
$TriggerLogon.Delay = "PT15S"

# Set the principal (run with highest privileges as SYSTEM)
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Set the settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

# Register the task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Description $TaskDescription `
    -Action $Action `
    -Trigger @($Trigger, $TriggerLogon) `
    -Principal $Principal `
    -Settings $Settings

Write-Host "`nSUCCESS: Task created successfully!" -ForegroundColor Green
Write-Host "`nTask Details:" -ForegroundColor Cyan
Write-Host "  Name: $TaskName"
Write-Host "  Triggers:"
Write-Host "    - At system startup (30 second delay)"
Write-Host "    - At user logon (15 second delay)"
Write-Host "  Action: Start WSL and run Discord bot startup script"
Write-Host "  User: SYSTEM (highest privileges)"
Write-Host "`nThe Discord bot will now automatically start when Windows boots!" -ForegroundColor Green
Write-Host "`nTo test the task now, run:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "`nTo view task logs:" -ForegroundColor Yellow
Write-Host "  Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
Write-Host "`nBot logs are stored in:" -ForegroundColor Yellow
Write-Host "  E:\discord-bot\startup.log (startup)"
Write-Host "  E:\discord-bot\monitor.log (health checks)"
Write-Host "  E:\discord-bot\cron.log (cron jobs)"
