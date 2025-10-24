-- Advanced iRacing Features Database Schema
-- Supports: history tracking, personal bests, detailed stats

-- Table for tracking iRating/SR history over time
CREATE TABLE IF NOT EXISTS iracing_rating_history (
    id SERIAL PRIMARY KEY,
    cust_id INTEGER NOT NULL,
    category VARCHAR(50) NOT NULL, -- 'oval', 'road', 'dirt_oval', 'dirt_road', 'formula_car'
    irating INTEGER NOT NULL,
    safety_rating DECIMAL(4,2) NOT NULL,
    license_level INTEGER,
    license_sub_level INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Index for fast lookups
    CONSTRAINT unique_rating_snapshot UNIQUE (cust_id, category, recorded_at)
);

CREATE INDEX IF NOT EXISTS idx_rating_history_cust ON iracing_rating_history(cust_id, category, recorded_at DESC);

-- Table for personal best lap times
CREATE TABLE IF NOT EXISTS iracing_personal_bests (
    id SERIAL PRIMARY KEY,
    cust_id INTEGER NOT NULL,
    track_id INTEGER NOT NULL,
    car_id INTEGER NOT NULL,
    lap_time DECIMAL(10,3) NOT NULL, -- in seconds
    subsession_id BIGINT,
    session_date TIMESTAMP,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_personal_best UNIQUE (cust_id, track_id, car_id)
);

CREATE INDEX IF NOT EXISTS idx_personal_bests_driver ON iracing_personal_bests(cust_id);
CREATE INDEX IF NOT EXISTS idx_personal_bests_track ON iracing_personal_bests(track_id, car_id);

-- Table for detailed race results cache
CREATE TABLE IF NOT EXISTS iracing_race_results_cache (
    subsession_id BIGINT PRIMARY KEY,
    series_id INTEGER,
    season_id INTEGER,
    track_id INTEGER,
    race_week INTEGER,
    session_start TIMESTAMP,

    -- Full race data as JSON
    race_data JSONB NOT NULL,

    -- Metadata
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_race_cache_series ON iracing_race_results_cache(series_id, season_id, race_week);
CREATE INDEX IF NOT EXISTS idx_race_cache_expires ON iracing_race_results_cache(expires_at);

-- Table for tracking series participation trends
CREATE TABLE IF NOT EXISTS iracing_participation_snapshots (
    id SERIAL PRIMARY KEY,
    series_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    week_num INTEGER NOT NULL,
    total_drivers INTEGER,
    total_splits INTEGER,
    avg_sof DECIMAL(10,2), -- Average Strength of Field
    snapshot_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_participation_snapshot UNIQUE (series_id, season_id, week_num, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_participation_series ON iracing_participation_snapshots(series_id, season_id, week_num);

-- Table for track records (fastest laps ever)
CREATE TABLE IF NOT EXISTS iracing_track_records (
    id SERIAL PRIMARY KEY,
    track_id INTEGER NOT NULL,
    car_id INTEGER NOT NULL,
    car_class_id INTEGER,
    cust_id INTEGER NOT NULL,
    driver_name VARCHAR(255),
    lap_time DECIMAL(10,3) NOT NULL,
    subsession_id BIGINT,
    session_date TIMESTAMP,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_track_record UNIQUE (track_id, car_id)
);

CREATE INDEX IF NOT EXISTS idx_track_records_track ON iracing_track_records(track_id);
CREATE INDEX IF NOT EXISTS idx_track_records_car ON iracing_track_records(car_id);

-- Table for caching driver career analysis
CREATE TABLE IF NOT EXISTS iracing_driver_analysis_cache (
    cust_id INTEGER PRIMARY KEY,

    -- Analysis results as JSON
    strengths_weaknesses JSONB, -- Best/worst tracks, car types
    consistency_metrics JSONB,   -- Incident rates, finish consistency
    progression_data JSONB,      -- Improvement trends

    -- Metadata
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_driver_analysis_expires ON iracing_driver_analysis_cache(expires_at);

-- Add comments for documentation
COMMENT ON TABLE iracing_rating_history IS 'Tracks iRating and Safety Rating changes over time for all license categories';
COMMENT ON TABLE iracing_personal_bests IS 'Stores personal best lap times for each driver/track/car combination';
COMMENT ON TABLE iracing_race_results_cache IS 'Caches detailed race result data to avoid repeated API calls';
COMMENT ON TABLE iracing_participation_snapshots IS 'Tracks series participation trends (drivers, splits, SOF) over time';
COMMENT ON TABLE iracing_track_records IS 'Stores the fastest lap times ever recorded at each track/car combination';
COMMENT ON TABLE iracing_driver_analysis_cache IS 'Caches computed driver analysis (strengths, weaknesses, consistency)';
