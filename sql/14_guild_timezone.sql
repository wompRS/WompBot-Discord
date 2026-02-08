-- Guild-level timezone support
-- Adds timezone column to guild_config for per-server timezone settings

ALTER TABLE guild_config ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'UTC';

-- Add comment for documentation
COMMENT ON COLUMN guild_config.timezone IS 'IANA timezone identifier (e.g. America/New_York, Europe/London)';
