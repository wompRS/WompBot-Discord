-- Advanced rate limiting for specific features
CREATE TABLE IF NOT EXISTS feature_rate_limits (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    feature_type VARCHAR(50) NOT NULL,  -- 'fact_check', 'search', 'command', etc.
    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_feature_rate_limits_user_feature ON feature_rate_limits(user_id, feature_type, request_timestamp);
CREATE INDEX IF NOT EXISTS idx_feature_rate_limits_timestamp ON feature_rate_limits(request_timestamp);
