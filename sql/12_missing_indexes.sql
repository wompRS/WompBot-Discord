-- Migration 12: Add missing indexes for query performance
-- These indexes were identified as missing during code audit

-- Compound index for guild + timestamp filtering (used by get_message_stats and many other queries)
CREATE INDEX IF NOT EXISTS idx_messages_guild_timestamp ON messages(guild_id, timestamp DESC);

-- feature_rate_limits indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_feature_rate_limits_user_feature ON feature_rate_limits(user_id, feature_type, request_timestamp);
CREATE INDEX IF NOT EXISTS idx_feature_rate_limits_timestamp ON feature_rate_limits(request_timestamp);

-- Compound index for claims queries by user + time (used by behavior analysis)
CREATE INDEX IF NOT EXISTS idx_claims_user_timestamp ON claims(user_id, timestamp DESC);

-- Index for cache cleanup queries on iracing_meta_cache
CREATE INDEX IF NOT EXISTS idx_iracing_meta_cache_expires ON iracing_meta_cache(expires_at);

-- Index for guild isolation on messages (many queries filter by guild_id alone)
CREATE INDEX IF NOT EXISTS idx_messages_guild_id ON messages(guild_id);

-- embedding_queue already has priority_idx on (priority, created_at) - no additional index needed

-- Composite index for get_recent_messages (hottest query path - called on every bot response)
CREATE INDEX IF NOT EXISTS idx_messages_channel_timestamp ON messages(channel_id, timestamp DESC);

-- Composite index for check_repeated_messages (spam detection on every bot mention)
CREATE INDEX IF NOT EXISTS idx_messages_user_timestamp ON messages(user_id, timestamp DESC);

-- Composite index for stats_cache lookups
CREATE INDEX IF NOT EXISTS idx_stats_cache_lookup ON stats_cache(stat_type, scope, start_date, end_date);

-- Composite index for hot_takes community reaction tracking
CREATE INDEX IF NOT EXISTS idx_messages_channel_id_timestamp ON messages(channel_id, timestamp);
