# Discord Bot - Development Export Package

## Contents
- `export_dump.dump` - PostgreSQL database dump (pg_restore format)
- `.env` - Environment configuration with API keys
- Full source code (git repository)

## Setup on New Machine

### Prerequisites
- Docker & Docker Compose installed
- Git installed

### Steps

1. **Copy/clone the repo to the new machine:**
   ```bash
   # Either extract the zip, or clone from git:
   git clone <your-repo-url> discord-bot
   cd discord-bot
   ```

2. **Copy the .env file** into the project root (if not already present).

3. **Copy `export_dump.dump`** into the `backups/` directory:
   ```bash
   cp export_dump.dump backups/
   ```

4. **Start the database first:**
   ```bash
   docker-compose up -d postgres redis
   # Wait for postgres to be healthy
   docker-compose ps
   ```

5. **Restore the database:**
   ```bash
   # Wait ~10 seconds for postgres to initialize, then restore:
   docker exec -i discord_bot_db pg_restore -U botuser -d discord_bot --clean --if-exists /backups/export_dump.dump
   ```
   If you see "errors" about objects not existing during `--clean`, that's normal on first restore.

6. **Start the bot:**
   ```bash
   docker-compose up -d
   ```

7. **Verify everything is running:**
   ```bash
   docker-compose ps
   docker logs discord_bot --tail 20
   ```

### Notes
- The `.env` file contains sensitive API keys - keep it secure
- Database dump includes all tables, message history, user data, embeddings, etc.
- Redis data is ephemeral cache and does not need to be migrated
- The `data/` directory is currently empty (.gitkeep only)
- Resource limits in `docker-compose.yml` may need adjustment for your dev machine
