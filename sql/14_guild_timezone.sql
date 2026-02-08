-- Guild-level timezone support
-- Creates guild_config table if it doesn't exist, adds timezone column

CREATE TABLE IF NOT EXISTS guild_config (
    guild_id BIGINT PRIMARY KEY,
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- If table already existed without timezone column, add it
ALTER TABLE guild_config ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';

-- Add comment for documentation
COMMENT ON COLUMN guild_config.timezone IS 'IANA timezone identifier (e.g. America/New_York, Europe/London)';
