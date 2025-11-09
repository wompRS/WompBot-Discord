-- Rate limiting table for tracking token usage per user
CREATE TABLE IF NOT EXISTS rate_limits (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    tokens_used INT NOT NULL,
    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for efficient hourly lookups
CREATE INDEX IF NOT EXISTS idx_rate_limits_user_timestamp ON rate_limits(user_id, request_timestamp);
CREATE INDEX IF NOT EXISTS idx_rate_limits_timestamp ON rate_limits(request_timestamp);

-- Clean up old rate limit records (older than 1 hour)
CREATE OR REPLACE FUNCTION cleanup_old_rate_limits() RETURNS void AS $$
BEGIN
    DELETE FROM rate_limits WHERE request_timestamp < NOW() - INTERVAL '1 hour';
END;
$$ LANGUAGE plpgsql;
