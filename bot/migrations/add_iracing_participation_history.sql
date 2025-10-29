-- Migration: Add iRacing series participation history tracking
-- This table stores daily snapshots of series participation for historical analysis

CREATE TABLE IF NOT EXISTS iracing_participation_history (
    id SERIAL PRIMARY KEY,
    series_name VARCHAR(255) NOT NULL,
    series_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    season_year INTEGER NOT NULL,
    season_quarter INTEGER NOT NULL,
    participant_count INTEGER NOT NULL,
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure we only have one entry per series per day
    UNIQUE(series_name, season_id, snapshot_date)
);

-- Index for fast lookups by date range
CREATE INDEX IF NOT EXISTS idx_participation_snapshot_date ON iracing_participation_history(snapshot_date);

-- Index for fast lookups by season
CREATE INDEX IF NOT EXISTS idx_participation_season ON iracing_participation_history(season_id);

-- Index for fast lookups by quarter and year
CREATE INDEX IF NOT EXISTS idx_participation_quarter_year ON iracing_participation_history(season_year, season_quarter);

-- Comments for documentation
COMMENT ON TABLE iracing_participation_history IS 'Daily snapshots of iRacing series participation data for historical tracking';
COMMENT ON COLUMN iracing_participation_history.series_name IS 'Display name of the series (e.g., "Global Mazda MX-5 Cup")';
COMMENT ON COLUMN iracing_participation_history.series_id IS 'iRacing series ID';
COMMENT ON COLUMN iracing_participation_history.season_id IS 'iRacing season ID (unique per quarter)';
COMMENT ON COLUMN iracing_participation_history.season_year IS 'Year of the season (e.g., 2025)';
COMMENT ON COLUMN iracing_participation_history.season_quarter IS 'Quarter of the season (1-4)';
COMMENT ON COLUMN iracing_participation_history.participant_count IS 'Number of unique participants in this series/season';
COMMENT ON COLUMN iracing_participation_history.snapshot_date IS 'Date when this snapshot was taken';
