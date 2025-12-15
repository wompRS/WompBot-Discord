-- Weather location preferences migration
-- Allows users to save a default location for quick weather checks

CREATE TABLE IF NOT EXISTS weather_preferences (
    user_id BIGINT PRIMARY KEY,
    location TEXT NOT NULL,
    units TEXT DEFAULT 'metric' CHECK (units IN ('metric', 'imperial')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_weather_prefs_user ON weather_preferences(user_id);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_weather_prefs_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER weather_prefs_update_timestamp
    BEFORE UPDATE ON weather_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_weather_prefs_timestamp();
