# Run this script as Administrator to set up auto-start for the Discord bot

$taskName = "WSL Discord Bot"
$batPath = "E:\discord-bot\start-wsl-bot.bat"

# Remove existing task if present
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Create trigger for system startup
$trigger = New-ScheduledTaskTrigger -AtStartup

# Create action to run the batch file
$action = New-ScheduledTaskAction -Execute $batPath

# Create principal to run as SYSTEM with highest privileges
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Create settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register the task
Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Action $action -Principal $principal -Settings $settings -Description "Starts Discord bot in WSL Debian at system startup"

Write-Host "Task '$taskName' created successfully!" -ForegroundColor Green
Write-Host "The bot will now start automatically when Windows boots." -ForegroundColor Cyan
