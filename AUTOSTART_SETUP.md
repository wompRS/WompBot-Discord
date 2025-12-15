# Auto-Start Discord Bot on Windows Boot

This guide will set up your Discord bot to automatically start when Windows boots.

## Overview

The auto-start system:
1. Runs on Windows startup (before user login)
2. Starts WSL Debian
3. Starts Docker daemon
4. Launches bot containers via docker-compose
5. Logs output for troubleshooting

## Prerequisites

- ✅ WSL Debian installed
- ✅ Docker installed in WSL Debian
- ✅ Bot already working when started manually
- ✅ Administrator access to create scheduled task

## Setup Instructions

### Method 1: Task Scheduler (Recommended)

**Step 1: Open Task Scheduler**
1. Press `Win + R`
2. Type `taskschd.msc`
3. Press Enter

**Step 2: Create New Task**
1. Click "Create Task" (not "Create Basic Task")
2. Name: `Discord Bot Auto-Start`
3. Description: `Automatically starts Discord bot in WSL on system boot`

**Step 3: Configure General Tab**
- ✅ Check "Run whether user is logged on or not"
- ✅ Check "Run with highest privileges"
- ✅ Check "Hidden" (optional - hides console window)
- Configure for: Windows 10

**Step 4: Configure Triggers Tab**
1. Click "New..."
2. Begin the task: **At startup**
3. Delay task for: **30 seconds** (allows network to initialize)
4. ✅ Check "Enabled"
5. Click OK

**Step 5: Configure Actions Tab**
1. Click "New..."
2. Action: **Start a program**
3. Program/script: `powershell.exe`
4. Add arguments:
   ```
   -ExecutionPolicy Bypass -WindowStyle Hidden -File "E:\discord-bot\start-bot-on-boot.ps1"
   ```
5. Click OK

**Step 6: Configure Conditions Tab**
- ⬜ Uncheck "Start the task only if the computer is on AC power"
- ✅ Check "Start only if the following network connection is available: Any connection"

**Step 7: Configure Settings Tab**
- ✅ Check "Allow task to be run on demand"
- ⬜ Uncheck "Stop the task if it runs longer than"
- If the task fails, restart every: **1 minute**
- Attempt to restart up to: **3 times**

**Step 8: Save Task**
1. Click OK
2. Enter your Windows password when prompted
3. Task is now created

**Step 9: Test the Task**
1. Right-click the task in Task Scheduler
2. Click "Run"
3. Check if bot starts:
   ```powershell
   wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose ps"
   ```

---

### Method 2: Startup Folder (Alternative)

**Create a shortcut in Windows Startup folder:**

1. Create a batch file `E:\discord-bot\start-bot.bat`:
   ```batch
   @echo off
   powershell.exe -ExecutionPolicy Bypass -File "E:\discord-bot\start-bot-on-boot.ps1"
   ```

2. Press `Win + R`, type `shell:startup`, press Enter

3. Create shortcut to `start-bot.bat` in the Startup folder

**Limitations:**
- Only runs when user logs in (not on system boot)
- Shows console window briefly
- Not recommended for servers

---

## Verification

### Test Auto-Start
1. Restart your computer
2. Wait 1-2 minutes after boot
3. Check if containers are running:
   ```powershell
   wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose ps"
   ```

**Expected output:**
```
NAME                    IMAGE                       STATUS
discord_bot             discord-bot-bot             Up 2 minutes
discord_bot_backup      prodrigestivill/postgres... Up 2 minutes
discord_bot_db          pgvector/pgvector:pg15      Up 2 minutes (healthy)
```

### Check Logs
View startup logs:
```powershell
wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose logs --tail=50 bot"
```

### Task Scheduler Logs
1. Open Task Scheduler
2. Find "Discord Bot Auto-Start" task
3. Click "History" tab
4. Check for errors or failures

---

## Troubleshooting

### Bot Not Starting

**Check Task Scheduler History:**
1. Task Scheduler → Discord Bot Auto-Start
2. History tab → Look for errors

**Common Issues:**

**Issue: "WSL not found"**
- Solution: Ensure WSL is in PATH
- Run: `wsl --version` in PowerShell to verify

**Issue: "Docker not running"**
- Solution: Increase startup delay in trigger (try 60 seconds)
- Docker might need more time to initialize

**Issue: "Permission denied"**
- Solution: Ensure task runs with "highest privileges"
- Ensure your user has sudo access in WSL Debian

**Issue: "Network not ready"**
- Solution: Increase network wait time in script (line 14)
- Change `Start-Sleep -Seconds 10` to `Start-Sleep -Seconds 30`

### Manual Start

If auto-start fails, manually run:
```powershell
# Run the PowerShell script
powershell.exe -ExecutionPolicy Bypass -File "E:\discord-bot\start-bot-on-boot.ps1"

# Or start directly in WSL
wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose up -d"
```

### View Script Output

To see what the startup script is doing:
```powershell
# Run with visible console
powershell.exe -ExecutionPolicy Bypass -File "E:\discord-bot\start-bot-on-boot.ps1"
```

---

## Advanced Configuration

### Enable Logging

Modify the task action to log output:
```
powershell.exe -ExecutionPolicy Bypass -Command "& 'E:\discord-bot\start-bot-on-boot.ps1' > 'E:\discord-bot\startup.log' 2>&1"
```

View logs:
```powershell
Get-Content E:\discord-bot\startup.log
```

### Adjust Startup Delay

If containers fail to start:
1. Edit task trigger
2. Increase "Delay task for" to 60-120 seconds
3. Allows more time for network/services to initialize

### Disable Auto-Start

**Temporary (until next boot):**
```powershell
wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose down"
```

**Permanent:**
1. Open Task Scheduler
2. Right-click "Discord Bot Auto-Start"
3. Click "Disable" or "Delete"

---

## Security Notes

- ✅ Script runs with elevated privileges (required for Docker)
- ✅ No credentials stored in script (uses .env file)
- ✅ Task can only be modified by administrators
- ⚠️ Ensure E:\discord-bot\.env has restricted permissions

**Secure .env file:**
```powershell
# Remove inheritance and restrict access
icacls "E:\discord-bot\.env" /inheritance:r
icacls "E:\discord-bot\.env" /grant:r "$env:USERNAME:(R,W)"
```

---

## Uninstall

To remove auto-start:
1. Open Task Scheduler
2. Find "Discord Bot Auto-Start"
3. Right-click → Delete
4. Optionally delete `E:\discord-bot\start-bot-on-boot.ps1`

---

## Support

**Check if task exists:**
```powershell
Get-ScheduledTask | Where-Object {$_.TaskName -eq "Discord Bot Auto-Start"}
```

**View task details:**
```powershell
Get-ScheduledTask -TaskName "Discord Bot Auto-Start" | Get-ScheduledTaskInfo
```

**Test WSL and Docker manually:**
```powershell
# Test WSL
wsl -d Debian echo "WSL works"

# Test Docker
wsl -d Debian sudo service docker status

# Test bot startup
wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose ps"
```
