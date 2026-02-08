-- Session persistence for trivia and debates
-- Allows active sessions to survive bot restarts

CREATE TABLE IF NOT EXISTS active_trivia_sessions (
    id SERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    started_by BIGINT NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    session_state JSONB NOT NULL,  -- Full session state: questions, scores, current_index, etc.
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trivia_sessions_active ON active_trivia_sessions (channel_id, is_active) WHERE is_active = TRUE;

CREATE TABLE IF NOT EXISTS active_debates (
    id SERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    topic TEXT NOT NULL,
    started_by BIGINT NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    debate_state JSONB NOT NULL,  -- Full debate state: participants, messages, scores, etc.
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_debates_active ON active_debates (channel_id, is_active) WHERE is_active = TRUE;
