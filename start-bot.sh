#!/bin/bash
# Discord Bot Auto-Start Script
# This script starts the bot containers when WSL boots

BOT_DIR="/mnt/e/discord-bot"
LOG_FILE="/mnt/e/discord-bot/startup.log"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Bot Auto-Start Script Triggered ==="

# Wait for Docker to be ready
MAX_WAIT=30
WAIT_COUNT=0
while ! docker info > /dev/null 2>&1; do
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        log "ERROR: Docker failed to start within ${MAX_WAIT} seconds"
        exit 1
    fi
    log "Waiting for Docker to be ready... ($WAIT_COUNT/$MAX_WAIT)"
    sleep 1
    ((WAIT_COUNT++))
done

log "Docker is ready"

# Change to bot directory
cd "$BOT_DIR" || {
    log "ERROR: Could not change to $BOT_DIR"
    exit 1
}

# Start containers
log "Starting bot containers..."
if docker compose up -d; then
    log "SUCCESS: Containers started"

    # Wait and verify
    sleep 10

    # Check if bot is running
    if docker ps --format '{{.Names}}' | grep -q "^discord_bot$"; then
        log "SUCCESS: Bot container is running"

        # Check for immediate errors
        BOT_LOGS=$(docker compose logs --tail=20 bot 2>&1 | grep -i "error\|exception\|failed" | head -5)
        if [ -n "$BOT_LOGS" ]; then
            log "WARNING: Errors detected in bot logs:"
            echo "$BOT_LOGS" >> "$LOG_FILE"
        fi
    else
        log "ERROR: Bot container is not running"
        docker compose logs --tail=50 bot >> "$LOG_FILE"
    fi
else
    log "ERROR: Failed to start containers"
    exit 1
fi

log "=== Auto-Start Script Complete ==="
