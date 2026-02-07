-- Server Admins Migration
-- Allows per-server bot admin configuration

-- Table to store server-specific bot admins
CREATE TABLE IF NOT EXISTS server_admins (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    added_by BIGINT NOT NULL,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(guild_id, user_id)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_server_admins_guild ON server_admins(guild_id);
CREATE INDEX IF NOT EXISTS idx_server_admins_user ON server_admins(user_id);

-- Global super admins (can manage admins in any server)
-- These are set via environment variable SUPER_ADMIN_IDS
-- No table needed - they're checked from env

COMMENT ON TABLE server_admins IS 'Per-server bot administrator configuration';
COMMENT ON COLUMN server_admins.guild_id IS 'Discord server/guild ID';
COMMENT ON COLUMN server_admins.user_id IS 'Discord user ID of the admin';
COMMENT ON COLUMN server_admins.added_by IS 'User ID who added this admin';
