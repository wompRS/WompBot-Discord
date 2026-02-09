-- Performance indexes for hot path queries
-- Compound index for get_recent_messages() which filters by channel_id + guild_id + timestamp
CREATE INDEX IF NOT EXISTS idx_messages_channel_guild_timestamp
ON messages (channel_id, guild_id, timestamp DESC);

-- Index for server_personality lookups (called every bot mention, now cached but still needs fast first-load)
CREATE INDEX IF NOT EXISTS idx_server_personality_server_id
ON server_personality (server_id);

-- Remove the cleanup query from record_feature_usage by adding an index that makes periodic cleanup fast
CREATE INDEX IF NOT EXISTS idx_feature_rate_limits_timestamp
ON feature_rate_limits (request_timestamp);
