-- Migration 16: New feature tables
-- Includes: user_topic_expertise, polls, poll_votes, active_who_said_it,
--           active_devils_advocate, active_jeopardy, scheduled_messages,
--           rss_feeds, github_watches, watchlists

-- ===== Feature 4: Topic Expertise Tracking =====
CREATE TABLE IF NOT EXISTS user_topic_expertise (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    topic VARCHAR(100) NOT NULL,
    message_count INT DEFAULT 0,
    quality_score FLOAT DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, guild_id, topic)
);
CREATE INDEX IF NOT EXISTS idx_expertise_user_guild ON user_topic_expertise (user_id, guild_id);
CREATE INDEX IF NOT EXISTS idx_expertise_topic ON user_topic_expertise (guild_id, topic);
