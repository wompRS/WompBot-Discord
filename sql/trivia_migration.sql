-- Trivia System Migration
-- Adds tables for trivia sessions, questions, answers, and statistics

-- Trivia sessions table
CREATE TABLE IF NOT EXISTS trivia_sessions (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    topic VARCHAR(255) NOT NULL,
    difficulty VARCHAR(20) NOT NULL,  -- 'easy', 'medium', 'hard'
    question_count INT NOT NULL,
    time_per_question INT NOT NULL,  -- seconds
    started_by_user_id BIGINT NOT NULL,
    started_by_username VARCHAR(255) NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'completed', 'abandoned'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Questions asked during sessions (for history/stats)
CREATE TABLE IF NOT EXISTS trivia_questions (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES trivia_sessions(id) ON DELETE CASCADE,
    question_number INT NOT NULL,
    question_text TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    acceptable_answers TEXT[],  -- PostgreSQL array for alternative answers
    difficulty VARCHAR(20) NOT NULL,
    asked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, question_number)
);

-- Individual answer submissions
CREATE TABLE IF NOT EXISTS trivia_answers (
    id SERIAL PRIMARY KEY,
    session_id INT REFERENCES trivia_sessions(id) ON DELETE CASCADE,
    question_id INT REFERENCES trivia_questions(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    answer_text TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    similarity_score FLOAT,  -- 0.0-1.0 fuzzy match score
    time_taken FLOAT NOT NULL,  -- seconds from question asked to answer
    points_earned INT NOT NULL,
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Aggregated user statistics per server
CREATE TABLE IF NOT EXISTS trivia_stats (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    total_sessions INT DEFAULT 0,
    total_questions_answered INT DEFAULT 0,
    total_correct INT DEFAULT 0,
    total_points INT DEFAULT 0,
    avg_time_per_question FLOAT DEFAULT 0.0,
    best_streak INT DEFAULT 0,
    favorite_topic VARCHAR(255),
    wins INT DEFAULT 0,  -- First place finishes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(guild_id, user_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_trivia_sessions_guild ON trivia_sessions(guild_id);
CREATE INDEX IF NOT EXISTS idx_trivia_sessions_channel ON trivia_sessions(channel_id);
CREATE INDEX IF NOT EXISTS idx_trivia_sessions_status ON trivia_sessions(status);
CREATE INDEX IF NOT EXISTS idx_trivia_questions_session ON trivia_questions(session_id);
CREATE INDEX IF NOT EXISTS idx_trivia_answers_session ON trivia_answers(session_id);
CREATE INDEX IF NOT EXISTS idx_trivia_answers_user ON trivia_answers(user_id);
CREATE INDEX IF NOT EXISTS idx_trivia_stats_guild_user ON trivia_stats(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_trivia_stats_leaderboard ON trivia_stats(guild_id, total_points DESC);

-- Trigger for auto-updating updated_at
CREATE OR REPLACE FUNCTION update_trivia_stats_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_trivia_stats_updated_at
    BEFORE UPDATE ON trivia_stats
    FOR EACH ROW
    EXECUTE FUNCTION update_trivia_stats_updated_at();

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE trivia_sessions TO botuser;
GRANT ALL PRIVILEGES ON TABLE trivia_questions TO botuser;
GRANT ALL PRIVILEGES ON TABLE trivia_answers TO botuser;
GRANT ALL PRIVILEGES ON TABLE trivia_stats TO botuser;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO botuser;
