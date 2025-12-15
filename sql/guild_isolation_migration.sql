-- Guild Isolation Migration
-- Adds guild_id to all tables for proper server data separation
-- This ensures each Discord server's data is logically isolated

BEGIN;

-- Add guild_id to messages table (most critical)
ALTER TABLE messages ADD COLUMN IF NOT EXISTS guild_id BIGINT;

-- Add guild_id to user-related tables
ALTER TABLE user_behavior ADD COLUMN IF NOT EXISTS guild_id BIGINT;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS guild_id BIGINT;
ALTER TABLE user_facts ADD COLUMN IF NOT EXISTS guild_id BIGINT;
ALTER TABLE user_consent ADD COLUMN IF NOT EXISTS guild_id BIGINT;

-- Add guild_id to content tables
ALTER TABLE claims ADD COLUMN IF NOT EXISTS guild_id BIGINT;
ALTER TABLE hot_takes ADD COLUMN IF NOT EXISTS guild_id BIGINT;
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS guild_id BIGINT;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS guild_id BIGINT;
ALTER TABLE conversation_summaries ADD COLUMN IF NOT EXISTS guild_id BIGINT;
ALTER TABLE stats_cache ADD COLUMN IF NOT EXISTS guild_id BIGINT;

-- Add guild_id to interaction tables
ALTER TABLE message_interactions ADD COLUMN IF NOT EXISTS guild_id BIGINT;
ALTER TABLE claim_contradictions ADD COLUMN IF NOT EXISTS guild_id BIGINT;
ALTER TABLE fact_checks ADD COLUMN IF NOT EXISTS guild_id BIGINT;

-- Add guild_id to debate tables
-- (debates and debate_participants already have guild_id via events)

-- Create indexes for performance (CRITICAL for query speed)
CREATE INDEX IF NOT EXISTS idx_messages_guild_id ON messages(guild_id);
CREATE INDEX IF NOT EXISTS idx_user_behavior_guild_id ON user_behavior(guild_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_guild_id ON user_profiles(guild_id);
CREATE INDEX IF NOT EXISTS idx_user_facts_guild_id ON user_facts(guild_id);
CREATE INDEX IF NOT EXISTS idx_claims_guild_id ON claims(guild_id);
CREATE INDEX IF NOT EXISTS idx_hot_takes_guild_id ON hot_takes(guild_id);
CREATE INDEX IF NOT EXISTS idx_quotes_guild_id ON quotes(guild_id);
CREATE INDEX IF NOT EXISTS idx_reminders_guild_id ON reminders(guild_id);
CREATE INDEX IF NOT EXISTS idx_conversation_summaries_guild_id ON conversation_summaries(guild_id);
CREATE INDEX IF NOT EXISTS idx_stats_cache_guild_id ON stats_cache(guild_id);
CREATE INDEX IF NOT EXISTS idx_message_interactions_guild_id ON message_interactions(guild_id);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_messages_guild_channel ON messages(guild_id, channel_id);
CREATE INDEX IF NOT EXISTS idx_messages_guild_user ON messages(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_messages_guild_timestamp ON messages(guild_id, timestamp);

-- Note: Existing data will have NULL guild_id
-- The bot will populate guild_id for new messages automatically
-- Old data can be updated manually if needed

COMMIT;

-- Verification query
SELECT
    'Migration complete. Tables with guild_id:' as status,
    COUNT(*) as table_count
FROM information_schema.columns
WHERE table_schema = 'public'
  AND column_name = 'guild_id';
