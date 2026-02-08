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

-- ===== Feature 8: Polls =====
CREATE TABLE IF NOT EXISTS polls (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,
    question TEXT NOT NULL,
    poll_type VARCHAR(20) DEFAULT 'single',  -- single, multi, ranked
    options JSONB NOT NULL,  -- ["Option A", "Option B", ...]
    anonymous BOOLEAN DEFAULT FALSE,
    duration_minutes INT,
    closes_at TIMESTAMP,
    is_closed BOOLEAN DEFAULT FALSE,
    message_id BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS poll_votes (
    id SERIAL PRIMARY KEY,
    poll_id INT REFERENCES polls(id),
    user_id BIGINT NOT NULL,
    option_index INT NOT NULL,
    rank_position INT,  -- for ranked choice
    voted_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(poll_id, user_id, option_index)
);
CREATE INDEX IF NOT EXISTS idx_poll_votes_poll ON poll_votes (poll_id);
CREATE INDEX IF NOT EXISTS idx_polls_guild ON polls (guild_id, is_closed);
