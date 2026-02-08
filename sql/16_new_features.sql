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

-- ===== Feature 9: Who Said It? =====
CREATE TABLE IF NOT EXISTS active_who_said_it (
    id SERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    started_by BIGINT NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    session_state JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wsi_active ON active_who_said_it (channel_id, is_active) WHERE is_active = TRUE;

-- ===== Feature 10: Devil's Advocate =====
CREATE TABLE IF NOT EXISTS active_devils_advocate (
    id SERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    topic TEXT NOT NULL,
    started_by BIGINT NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    session_state JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_da_active ON active_devils_advocate (channel_id, is_active) WHERE is_active = TRUE;

-- ===== Feature 11: Channel Jeopardy =====
CREATE TABLE IF NOT EXISTS active_jeopardy (
    id SERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    started_by BIGINT NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    session_state JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_jeopardy_active ON active_jeopardy (channel_id, is_active) WHERE is_active = TRUE;

-- ===== Feature 12: Message Scheduling =====
CREATE TABLE IF NOT EXISTS scheduled_messages (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    send_at TIMESTAMP NOT NULL,
    sent BOOLEAN DEFAULT FALSE,
    cancelled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_scheduled_pending ON scheduled_messages (send_at, sent, cancelled) WHERE sent = FALSE AND cancelled = FALSE;

-- ===== Feature 13: RSS Feeds =====
CREATE TABLE IF NOT EXISTS rss_feeds (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    feed_url TEXT NOT NULL,
    feed_title VARCHAR(255),
    added_by BIGINT NOT NULL,
    last_checked TIMESTAMP,
    last_entry_id TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(guild_id, feed_url)
);

-- ===== Feature 14: GitHub Watches =====
CREATE TABLE IF NOT EXISTS github_watches (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    repo_full_name VARCHAR(255) NOT NULL,
    watch_type VARCHAR(50) DEFAULT 'releases',
    added_by BIGINT NOT NULL,
    last_checked TIMESTAMP,
    last_event_id TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(guild_id, repo_full_name, watch_type)
);

-- ===== Feature 15: Watchlists =====
CREATE TABLE IF NOT EXISTS watchlists (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    symbol_type VARCHAR(10) NOT NULL,
    added_by BIGINT NOT NULL,
    alert_threshold FLOAT DEFAULT 5.0,
    last_price FLOAT,
    last_alert_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(guild_id, symbol)
);
