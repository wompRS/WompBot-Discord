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
