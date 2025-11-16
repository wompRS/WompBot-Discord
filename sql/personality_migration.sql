-- Personality System Migration
-- Enables admin-controlled personality switching per server

-- Server personality settings table
CREATE TABLE IF NOT EXISTS server_personality (
    server_id BIGINT PRIMARY KEY,
    personality VARCHAR(50) NOT NULL DEFAULT 'default',  -- 'default' or 'feyd'
    enabled_by BIGINT,  -- User ID who enabled it
    enabled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast personality lookups
CREATE INDEX IF NOT EXISTS server_personality_lookup_idx
ON server_personality(server_id, personality);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_personality_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_server_personality_updated_at ON server_personality;
CREATE TRIGGER update_server_personality_updated_at
    BEFORE UPDATE ON server_personality
    FOR EACH ROW
    EXECUTE FUNCTION update_personality_updated_at();

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE server_personality TO botuser;

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✅ Personality system table created successfully';
    RAISE NOTICE '   - server_personality: Tracks personality mode per server';
    RAISE NOTICE '   - Supported modes: default (professional) and feyd (Feyd-Rautha)';
END $$;
