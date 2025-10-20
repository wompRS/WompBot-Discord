-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT UNIQUE NOT NULL,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_name VARCHAR(255),
    content TEXT,
    timestamp TIMESTAMP NOT NULL,
    opted_out BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User profiles table
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    total_messages INT DEFAULT 0,
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL,
    opted_out BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User behavior analysis table
CREATE TABLE IF NOT EXISTS user_behavior (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    analysis_period_start TIMESTAMP NOT NULL,
    analysis_period_end TIMESTAMP NOT NULL,
    profanity_score INT DEFAULT 0,
    message_count INT DEFAULT 0,
    tone_analysis TEXT,
    honesty_patterns TEXT,
    conversation_style TEXT,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);

-- Search logs table
CREATE TABLE IF NOT EXISTS search_logs (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    results_count INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    triggered_by_user_id BIGINT,
    channel_id BIGINT
);

-- Claims table
CREATE TABLE IF NOT EXISTS claims (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    message_id BIGINT UNIQUE NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_name VARCHAR(255),
    claim_text TEXT NOT NULL,
    claim_type VARCHAR(50), -- 'prediction', 'fact', 'opinion', 'guarantee'
    confidence_level VARCHAR(20), -- 'certain', 'probable', 'uncertain'
    context TEXT, -- surrounding conversation for context
    timestamp TIMESTAMP NOT NULL,
    is_edited BOOLEAN DEFAULT FALSE,
    original_text TEXT, -- original claim before edits
    edit_history JSONB, -- array of {text, timestamp}
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    deleted_text TEXT, -- preserved text after deletion
    verification_status VARCHAR(20) DEFAULT 'unverified', -- 'unverified', 'true', 'false', 'mixed', 'outdated'
    verification_date TIMESTAMP,
    verification_sources TEXT,
    verification_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Hot takes table (controversial claims with community tracking)
CREATE TABLE IF NOT EXISTS hot_takes (
    id SERIAL PRIMARY KEY,
    claim_id INT UNIQUE REFERENCES claims(id) ON DELETE CASCADE,
    controversy_score FLOAT DEFAULT 0.0, -- LLM-scored 0-10 (only for high-engagement)
    community_score FLOAT DEFAULT 0.0, -- Reaction-based 0-10
    total_reactions INT DEFAULT 0,
    reaction_diversity FLOAT DEFAULT 0.0, -- Mix of different reactions 0-1
    reply_count INT DEFAULT 0,
    vindication_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'won', 'lost', 'mixed'
    vindication_date TIMESTAMP,
    vindication_notes TEXT,
    age_score FLOAT, -- How well it aged: 10.0 (won), 5.0 (mixed), 0.0 (lost)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Quotes table
CREATE TABLE IF NOT EXISTS quotes (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    message_id BIGINT UNIQUE NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_name VARCHAR(255),
    quote_text TEXT NOT NULL,
    context TEXT, -- few messages before/after for context
    timestamp TIMESTAMP NOT NULL,
    added_by_user_id BIGINT, -- who added the quote
    added_by_username VARCHAR(255),
    category VARCHAR(50), -- 'funny', 'crazy', 'wise', 'wtf', 'savage'
    reaction_count INT DEFAULT 1, -- how many cloud reacts it got
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Claim contradictions table (track when users contradict themselves)
CREATE TABLE IF NOT EXISTS claim_contradictions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    claim_id_1 INT REFERENCES claims(id) ON DELETE CASCADE,
    claim_id_2 INT REFERENCES claims(id) ON DELETE CASCADE,
    contradiction_explanation TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fact-checks table (emoji react triggered fact-checks)
CREATE TABLE IF NOT EXISTS fact_checks (
    id SERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    channel_id BIGINT NOT NULL,
    claim_text TEXT NOT NULL,
    fact_check_result TEXT NOT NULL,
    search_results JSONB,
    requested_by_user_id BIGINT NOT NULL,
    requested_by_username VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stats cache table (for pre-computed statistics)
CREATE TABLE IF NOT EXISTS stats_cache (
    id SERIAL PRIMARY KEY,
    stat_type VARCHAR(50) NOT NULL, -- 'primetime', 'topics', 'network', 'engagement', 'channel'
    scope VARCHAR(100) NOT NULL, -- 'server', 'channel:123', 'user:456'
    time_range_days INT, -- NULL for custom ranges
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP NOT NULL,
    results JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Message interactions table (for network graphs)
CREATE TABLE IF NOT EXISTS message_interactions (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL, -- who sent the message
    replied_to_user_id BIGINT, -- who they replied to
    replied_to_message_id BIGINT, -- which message they replied to
    mentioned_user_ids BIGINT[], -- array of mentioned user IDs
    channel_id BIGINT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Topic tracking table (for trending topics over time)
CREATE TABLE IF NOT EXISTS topic_snapshots (
    id SERIAL PRIMARY KEY,
    snapshot_date TIMESTAMP NOT NULL,
    time_range_days INT NOT NULL, -- 7, 30, etc.
    channel_id BIGINT, -- NULL for server-wide
    topics JSONB NOT NULL, -- [{keyword: 'bitcoin', count: 45, score: 0.87}, ...]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Reminders table (context-aware reminder system)
CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    channel_id BIGINT NOT NULL,
    message_id BIGINT, -- Original message for context
    reminder_text TEXT NOT NULL,
    time_string VARCHAR(255) NOT NULL, -- Original input: "in 5 minutes", "tomorrow at 3pm"
    remind_at TIMESTAMP NOT NULL,
    recurring BOOLEAN DEFAULT FALSE,
    recurring_interval VARCHAR(255), -- "daily", "weekly", "in 1 hour"
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Events table (scheduled events with periodic reminders)
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    event_name VARCHAR(255) NOT NULL,
    description TEXT,
    event_date TIMESTAMP NOT NULL,
    created_by_user_id BIGINT NOT NULL,
    created_by_username VARCHAR(255) NOT NULL,
    channel_id BIGINT NOT NULL, -- Where to announce reminders
    guild_id BIGINT NOT NULL, -- Discord server ID
    reminder_intervals JSONB DEFAULT '["1 week", "1 day", "1 hour"]'::JSONB, -- When to send reminders
    last_reminder_sent VARCHAR(50), -- Track last sent reminder interval
    notify_role_id BIGINT, -- Optional: role to ping for this event
    cancelled BOOLEAN DEFAULT FALSE,
    cancelled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Debates table (tracked debates with LLM analysis)
CREATE TABLE IF NOT EXISTS debates (
    id SERIAL PRIMARY KEY,
    topic VARCHAR(255) NOT NULL,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    started_by_user_id BIGINT NOT NULL,
    started_by_username VARCHAR(255) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP NOT NULL,
    participant_count INT DEFAULT 0,
    message_count INT DEFAULT 0,
    transcript JSONB, -- Full debate messages
    analysis JSONB, -- LLM analysis results
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Debate participants table (individual participant records)
CREATE TABLE IF NOT EXISTS debate_participants (
    id SERIAL PRIMARY KEY,
    debate_id INT REFERENCES debates(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    message_count INT DEFAULT 0,
    score FLOAT, -- LLM-assigned score 0-10
    is_winner BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_channel_id ON messages(channel_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_user_behavior_user_id ON user_behavior(user_id);
CREATE INDEX IF NOT EXISTS idx_search_logs_timestamp ON search_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_claims_user_id ON claims(user_id);
CREATE INDEX IF NOT EXISTS idx_claims_timestamp ON claims(timestamp);
CREATE INDEX IF NOT EXISTS idx_claims_verification_status ON claims(verification_status);
CREATE INDEX IF NOT EXISTS idx_quotes_user_id ON quotes(user_id);
CREATE INDEX IF NOT EXISTS idx_quotes_timestamp ON quotes(timestamp);
CREATE INDEX IF NOT EXISTS idx_quotes_category ON quotes(category);
CREATE INDEX IF NOT EXISTS idx_fact_checks_message_id ON fact_checks(message_id);
CREATE INDEX IF NOT EXISTS idx_fact_checks_user_id ON fact_checks(user_id);

-- Indexes for new stats tables
CREATE INDEX IF NOT EXISTS idx_stats_cache_type_scope ON stats_cache(stat_type, scope);
CREATE INDEX IF NOT EXISTS idx_stats_cache_valid_until ON stats_cache(valid_until);
CREATE INDEX IF NOT EXISTS idx_message_interactions_user_id ON message_interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_message_interactions_replied_to ON message_interactions(replied_to_user_id);
CREATE INDEX IF NOT EXISTS idx_message_interactions_timestamp ON message_interactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_topic_snapshots_date ON topic_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_topic_snapshots_channel ON topic_snapshots(channel_id);

-- Indexes for hot takes
CREATE INDEX IF NOT EXISTS idx_hot_takes_claim_id ON hot_takes(claim_id);
CREATE INDEX IF NOT EXISTS idx_hot_takes_controversy ON hot_takes(controversy_score);
CREATE INDEX IF NOT EXISTS idx_hot_takes_community ON hot_takes(community_score);
CREATE INDEX IF NOT EXISTS idx_hot_takes_vindication ON hot_takes(vindication_status);
CREATE INDEX IF NOT EXISTS idx_hot_takes_created_at ON hot_takes(created_at);

-- Indexes for reminders
CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_remind_at ON reminders(remind_at);
CREATE INDEX IF NOT EXISTS idx_reminders_completed ON reminders(completed);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(remind_at, completed) WHERE completed = FALSE;

-- Indexes for events
CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_channel_id ON events(channel_id);
CREATE INDEX IF NOT EXISTS idx_events_guild_id ON events(guild_id);
CREATE INDEX IF NOT EXISTS idx_events_cancelled ON events(cancelled);
CREATE INDEX IF NOT EXISTS idx_events_upcoming ON events(event_date, cancelled) WHERE cancelled = FALSE;

-- Indexes for debates
CREATE INDEX IF NOT EXISTS idx_debates_guild_id ON debates(guild_id);
CREATE INDEX IF NOT EXISTS idx_debates_channel_id ON debates(channel_id);
CREATE INDEX IF NOT EXISTS idx_debates_started_at ON debates(started_at);
CREATE INDEX IF NOT EXISTS idx_debate_participants_debate_id ON debate_participants(debate_id);
CREATE INDEX IF NOT EXISTS idx_debate_participants_user_id ON debate_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_debate_participants_winner ON debate_participants(is_winner);
