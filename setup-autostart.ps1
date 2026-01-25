# Run this script as Administrator to set up auto-start for the Discord bot
# Uses Docker Desktop (WSL2 backend) instead of Docker in WSL

$taskName = "Discord Bot Autostart"
$batPath = "E:\discord-bot\start-bot.bat"

# Remove existing tasks if present
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "WSL Discord Bot" -Confirm:$false -ErrorAction SilentlyContinue

# Create trigger for user logon (Docker Desktop runs as user, not SYSTEM)
$trigger = New-ScheduledTaskTrigger -AtLogon

# Create action to run the batch file
$action = New-ScheduledTaskAction -Execute $batPath -WorkingDirectory "E:\discord-bot"

# Create settings - with delay to let Docker Desktop start first
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

# Register the task for current user
Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Settings $settings -Description "Starts Discord bot containers after Docker Desktop is ready"

Write-Host ""
Write-Host "Task '$taskName' created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Auto-start flow:" -ForegroundColor Cyan
Write-Host "  1. Windows boots" -ForegroundColor White
Write-Host "  2. Docker Desktop starts (AutoStart enabled)" -ForegroundColor White
Write-Host "  3. Task runs start-bot.bat at logon" -ForegroundColor White
Write-Host "  4. Script waits for Docker to be ready, then starts containers" -ForegroundColor White
Write-Host ""
