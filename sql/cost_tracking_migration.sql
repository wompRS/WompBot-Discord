-- Cost tracking table for monitoring LLM spending
CREATE TABLE IF NOT EXISTS api_costs (
    id SERIAL PRIMARY KEY,
    model VARCHAR(255) NOT NULL,
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    cost_usd DECIMAL(10, 6) NOT NULL,
    request_type VARCHAR(50),  -- 'chat', 'fact_check', 'analysis', etc.
    user_id BIGINT,
    username VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Cost alerts tracking (to avoid duplicate alerts)
CREATE TABLE IF NOT EXISTS cost_alerts (
    id SERIAL PRIMARY KEY,
    threshold_usd DECIMAL(10, 2) NOT NULL,
    alert_sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_cost_usd DECIMAL(10, 6) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_api_costs_timestamp ON api_costs(timestamp);
CREATE INDEX IF NOT EXISTS idx_api_costs_model ON api_costs(model);
CREATE INDEX IF NOT EXISTS idx_api_costs_request_type ON api_costs(request_type);
CREATE INDEX IF NOT EXISTS idx_cost_alerts_threshold ON cost_alerts(threshold_usd);
