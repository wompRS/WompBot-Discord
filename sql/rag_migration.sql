-- RAG (Retrieval Augmented Generation) System Migration
-- Enables semantic search and intelligent context retrieval

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Message embeddings table
-- Stores vector embeddings for semantic search
CREATE TABLE IF NOT EXISTS message_embeddings (
    id SERIAL PRIMARY KEY,
    message_id BIGINT UNIQUE REFERENCES messages(message_id) ON DELETE CASCADE,
    embedding vector(1536),  -- OpenAI text-embedding-3-small dimension
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for fast vector similarity search
CREATE INDEX IF NOT EXISTS message_embeddings_vector_idx
ON message_embeddings USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Conversation summaries table
-- Stores AI-generated summaries of conversation segments
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id SERIAL PRIMARY KEY,
    channel_id BIGINT NOT NULL,
    user_id BIGINT,  -- NULL for channel-wide summaries
    summary TEXT NOT NULL,
    message_count INTEGER NOT NULL,  -- How many messages were summarized
    start_timestamp TIMESTAMP NOT NULL,
    end_timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(channel_id, user_id, start_timestamp, end_timestamp)
);

-- Index for fast summary retrieval
CREATE INDEX IF NOT EXISTS conversation_summaries_channel_user_idx
ON conversation_summaries(channel_id, user_id);

CREATE INDEX IF NOT EXISTS conversation_summaries_timestamp_idx
ON conversation_summaries(start_timestamp, end_timestamp);

-- User facts table
-- Stores extracted facts about users for compact context
CREATE TABLE IF NOT EXISTS user_facts (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    fact_type VARCHAR(50) NOT NULL,  -- 'preference', 'technical_skill', 'project', 'issue', etc.
    fact TEXT NOT NULL,
    confidence DECIMAL(3,2) DEFAULT 0.80,  -- 0.00 to 1.00
    source_message_id BIGINT REFERENCES messages(message_id) ON DELETE SET NULL,
    first_mentioned TIMESTAMP NOT NULL,
    last_confirmed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mention_count INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast fact retrieval
CREATE INDEX IF NOT EXISTS user_facts_user_id_idx
ON user_facts(user_id);

CREATE INDEX IF NOT EXISTS user_facts_type_idx
ON user_facts(fact_type);

CREATE INDEX IF NOT EXISTS user_facts_confidence_idx
ON user_facts(confidence);

-- Embedding generation queue
-- Tracks which messages need embeddings generated
CREATE TABLE IF NOT EXISTS embedding_queue (
    id SERIAL PRIMARY KEY,
    message_id BIGINT REFERENCES messages(message_id) ON DELETE CASCADE,
    priority INTEGER DEFAULT 5,  -- 1 (highest) to 10 (lowest)
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(message_id)
);

CREATE INDEX IF NOT EXISTS embedding_queue_priority_idx
ON embedding_queue(priority, created_at);

-- Function to automatically queue new messages for embedding
CREATE OR REPLACE FUNCTION queue_message_for_embedding()
RETURNS TRIGGER AS $$
BEGIN
    -- Only queue messages with content (not empty/null)
    IF NEW.content IS NOT NULL AND LENGTH(TRIM(NEW.content)) > 0 THEN
        INSERT INTO embedding_queue (message_id, priority)
        VALUES (NEW.message_id, 5)
        ON CONFLICT (message_id) DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to queue messages for embedding on insert
DROP TRIGGER IF EXISTS trigger_queue_message_embedding ON messages;
CREATE TRIGGER trigger_queue_message_embedding
    AFTER INSERT ON messages
    FOR EACH ROW
    EXECUTE FUNCTION queue_message_for_embedding();

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_message_embeddings_updated_at ON message_embeddings;
CREATE TRIGGER update_message_embeddings_updated_at
    BEFORE UPDATE ON message_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_user_facts_updated_at ON user_facts;
CREATE TRIGGER update_user_facts_updated_at
    BEFORE UPDATE ON user_facts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE message_embeddings TO botuser;
GRANT ALL PRIVILEGES ON TABLE conversation_summaries TO botuser;
GRANT ALL PRIVILEGES ON TABLE user_facts TO botuser;
GRANT ALL PRIVILEGES ON TABLE embedding_queue TO botuser;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO botuser;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ RAG system tables created successfully';
    RAISE NOTICE '   - message_embeddings: Vector storage for semantic search';
    RAISE NOTICE '   - conversation_summaries: AI-generated conversation summaries';
    RAISE NOTICE '   - user_facts: Extracted user facts and preferences';
    RAISE NOTICE '   - embedding_queue: Automatic embedding generation queue';
END $$;
