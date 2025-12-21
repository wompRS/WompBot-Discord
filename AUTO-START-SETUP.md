# Discord Bot Auto-Start Setup

## Overview

The Discord bot is configured to automatically start when Windows boots and monitor its own health.

## Components

### 1. Docker Restart Policy
- **File**: `docker-compose.yml`
- **Setting**: `restart: unless-stopped`
- All containers (postgres, bot, backup) will automatically restart if they crash

### 2. WSL Systemd Service
- **File**: `/etc/systemd/system/discord-bot.service`
- **Script**: `E:\discord-bot\start-bot.sh`
- Automatically starts Docker containers when WSL boots
- Enabled with: `systemctl enable discord-bot.service`

### 3. Health Monitoring (Cron)
- **File**: `E:\discord-bot\monitor-bot.sh`
- **Schedule**: Every 5 minutes
- **Cron Job**: `*/5 * * * * /mnt/e/discord-bot/monitor-bot.sh`
- Checks if containers are running and restarts them if needed
- Logs errors and restart attempts

### 4. Windows Auto-Start (Task Scheduler)
- **Setup Script**: `E:\discord-bot\setup-wsl-autostart.ps1`
- **Task Name**: `WSL-Discord-Bot-AutoStart`
- Starts WSL when Windows boots
- Triggers: System startup (30s delay) + User logon (15s delay)

## Setup Instructions

### Initial Setup (Run Once)

1. **Run PowerShell as Administrator**
   - Right-click PowerShell
   - Select "Run as Administrator"

2. **Execute the setup script**
   ```powershell
   cd E:\discord-bot
   .\setup-wsl-autostart.ps1
   ```

3. **Verify the task was created**
   ```powershell
   Get-ScheduledTask -TaskName "WSL-Discord-Bot-AutoStart"
   ```

### Testing

1. **Test the startup script manually**
   ```bash
   wsl -e bash -c "/mnt/e/discord-bot/start-bot.sh"
   ```

2. **Test the monitoring script manually**
   ```bash
   wsl -e bash -c "/mnt/e/discord-bot/monitor-bot.sh"
   ```

3. **Test the Windows Task Scheduler task**
   ```powershell
   Start-ScheduledTask -TaskName "WSL-Discord-Bot-AutoStart"
   ```

4. **Check if containers are running**
   ```bash
   wsl -e bash -c "cd /mnt/e/discord-bot && docker compose ps"
   ```

## Logs

### Startup Logs
- **Location**: `E:\discord-bot\startup.log`
- **Contains**: Boot-time container startup attempts and results

### Health Monitoring Logs
- **Location**: `E:\discord-bot\monitor.log`
- **Contains**: Periodic health checks and auto-restart actions
- **Cleanup**: Automatically keeps last 1000 lines

### Cron Logs
- **Location**: `E:\discord-bot\cron.log`
- **Contains**: Cron job execution logs

### Docker Container Logs
```bash
# View bot logs
wsl -e bash -c "cd /mnt/e/discord-bot && docker compose logs bot --tail=50"

# View all container logs
wsl -e bash -c "cd /mnt/e/discord-bot && docker compose logs --tail=50"

# Follow bot logs in real-time
wsl -e bash -c "cd /mnt/e/discord-bot && docker compose logs -f bot"
```

## Management Commands

### Start/Stop Bot Manually
```bash
# Start all containers
wsl -e bash -c "cd /mnt/e/discord-bot && docker compose up -d"

# Stop all containers
wsl -e bash -c "cd /mnt/e/discord-bot && docker compose down"

# Restart bot only
wsl -e bash -c "cd /mnt/e/discord-bot && docker compose restart bot"
```

### Check Status
```bash
# Check container status
wsl -e bash -c "cd /mnt/e/discord-bot && docker compose ps"

# Check systemd service status
wsl -e bash -c "sudo systemctl status discord-bot.service"

# Check cron job
wsl -e bash -c "crontab -l"
```

### View Recent Monitoring Activity
```bash
# Last 20 lines of monitoring log
wsl -e bash -c "tail -20 /mnt/e/discord-bot/monitor.log"

# Last 20 lines of startup log
wsl -e bash -c "tail -20 /mnt/e/discord-bot/startup.log"
```

### Disable Auto-Start (if needed)
```powershell
# Disable Windows Task Scheduler task
Disable-ScheduledTask -TaskName "WSL-Discord-Bot-AutoStart"

# Or remove it completely
Unregister-ScheduledTask -TaskName "WSL-Discord-Bot-AutoStart" -Confirm:$false
```

```bash
# Disable WSL systemd service
wsl -e bash -c "sudo systemctl disable discord-bot.service"

# Remove cron job
wsl -e bash -c "crontab -r"
```

## Troubleshooting

### Bot doesn't start on Windows boot
1. Check Task Scheduler: Open Task Scheduler → Find "WSL-Discord-Bot-AutoStart"
2. Check last run result (should be 0x0 for success)
3. Check startup log: `type E:\discord-bot\startup.log`

### Bot crashes and doesn't restart
1. Check monitoring log: `wsl -e bash -c "tail -50 /mnt/e/discord-bot/monitor.log"`
2. Check Docker status: `wsl -e bash -c "docker ps -a"`
3. Check bot logs: `wsl -e bash -c "cd /mnt/e/discord-bot && docker compose logs bot --tail=100"`

### Cron job not running
1. Verify cron is enabled: `wsl -e bash -c "sudo systemctl status cron"`
2. Check cron log: `type E:\discord-bot\cron.log`
3. Test script manually: `wsl -e bash -c "/mnt/e/discord-bot/monitor-bot.sh"`

### WSL doesn't start automatically
1. Check if WSL is set to start: `wsl --status`
2. Reinstall Task Scheduler task: Run `setup-wsl-autostart.ps1` again
3. Check Windows Event Viewer for Task Scheduler errors

## Architecture

```
Windows Boot
    ↓
Windows Task Scheduler (30s delay)
    ↓
WSL Starts
    ↓
Systemd starts docker.service
    ↓
Systemd runs discord-bot.service
    ↓
start-bot.sh executes
    ↓
docker compose up -d
    ↓
Containers start with restart: unless-stopped
    ↓
Cron job monitors every 5 minutes
    ↓
monitor-bot.sh checks and restarts if needed
```

## Notes

- The bot will survive system reboots, WSL restarts, and container crashes
- Health checks run every 5 minutes to ensure uptime
- Logs are automatically trimmed to prevent disk space issues
- All scripts are in `/mnt/e/discord-bot/` for easy access from both Windows and WSL
