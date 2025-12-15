# Quick Start: Auto-Start on Boot

Set up your Discord bot to automatically start when Windows boots.

## One-Command Setup

**Option 1: Automatic Setup (Easiest)**
```powershell
# Run PowerShell as Administrator, then:
cd E:\discord-bot
.\setup-autostart.ps1
```

This will:
- ✅ Check prerequisites (WSL, Docker)
- ✅ Create scheduled task automatically
- ✅ Test the task
- ✅ Done!

---

**Option 2: Manual Import**

1. Open Task Scheduler (`Win + R` → `taskschd.msc`)
2. Click "Import Task..."
3. Select `E:\discord-bot\discord-bot-autostart-task.xml`
4. Enter your Windows password when prompted
5. Done!

---

## Verify It Works

**Test the task:**
```powershell
# Run the task manually
Get-ScheduledTask "Discord Bot Auto-Start" | Start-ScheduledTask

# Wait 30 seconds, then check status
wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose ps"
```

**Expected output:**
```
NAME                STATUS
discord_bot         Up X minutes
discord_bot_db      Up X minutes (healthy)
```

---

## Restart to Test

1. Restart your computer
2. Wait 1-2 minutes after boot
3. Check if bot is running:
   ```powershell
   wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose ps"
   ```

---

## Troubleshooting

**Bot not starting?**

Check Task Scheduler history:
1. Open Task Scheduler
2. Find "Discord Bot Auto-Start"
3. Click "History" tab
4. Look for errors

**View startup logs:**
```powershell
wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose logs --tail=50 bot"
```

**Common fixes:**
- Increase startup delay (Task Scheduler → Triggers → 60 seconds delay)
- Check network is ready before task runs
- Ensure WSL Debian has Docker installed

---

## Disable Auto-Start

**Temporary:**
```powershell
wsl -d Debian bash -c "cd /mnt/e/discord-bot && docker-compose down"
```

**Permanent:**
1. Open Task Scheduler
2. Right-click "Discord Bot Auto-Start"
3. Select "Disable" or "Delete"

---

## Full Documentation

See **[AUTOSTART_SETUP.md](AUTOSTART_SETUP.md)** for complete setup guide and advanced configuration.
