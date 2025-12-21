#!/bin/bash
# Discord Bot Health Monitor and Auto-Restart Script
# This script checks if the bot containers are running and starts them if needed

BOT_DIR="/mnt/e/discord-bot"
LOG_FILE="/mnt/e/discord-bot/monitor.log"
CONTAINERS=("discord_bot" "discord_bot_db" "discord_bot_backup")

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Change to bot directory
cd "$BOT_DIR" || {
    log "ERROR: Could not change to $BOT_DIR"
    exit 1
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    log "ERROR: Docker is not running"
    exit 1
fi

# Check each container
ALL_RUNNING=true
for container in "${CONTAINERS[@]}"; do
    if ! docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        log "WARNING: Container $container is not running"
        ALL_RUNNING=false
    fi
done

# If any container is down, restart all
if [ "$ALL_RUNNING" = false ]; then
    log "Starting containers with docker compose up -d..."

    # Start containers
    if docker compose up -d; then
        log "SUCCESS: Containers started successfully"

        # Wait a bit and verify bot is actually running
        sleep 10

        if docker ps --format '{{.Names}}' | grep -q "^discord_bot$"; then
            # Check bot logs for any immediate errors
            BOT_LOGS=$(docker compose logs --tail=20 bot 2>&1 | grep -i "error\|exception\|failed" | head -5)
            if [ -n "$BOT_LOGS" ]; then
                log "WARNING: Bot started but errors detected in logs:"
                echo "$BOT_LOGS" >> "$LOG_FILE"
            else
                log "SUCCESS: Bot is running and healthy"
            fi
        else
            log "ERROR: Bot container failed to start"
        fi
    else
        log "ERROR: Failed to start containers"
        exit 1
    fi
else
    log "OK: All containers are running"
fi

# Clean up old log entries (keep last 1000 lines)
if [ -f "$LOG_FILE" ]; then
    tail -1000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
fi
