-- Migration: Add iRacing meta analysis cache table
-- This stores pre-computed meta analysis results to avoid re-analyzing races

CREATE TABLE IF NOT EXISTS iracing_meta_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(255) UNIQUE NOT NULL,
    series_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    week_num INTEGER NOT NULL,
    track_id INTEGER,

    -- Meta analysis results stored as JSON
    meta_data JSONB NOT NULL,

    -- Cache metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_meta_cache_key ON iracing_meta_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_meta_cache_series ON iracing_meta_cache(series_id, season_id, week_num);
CREATE INDEX IF NOT EXISTS idx_meta_cache_expires ON iracing_meta_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_meta_cache_expired ON iracing_meta_cache(expires_at) WHERE expires_at < NOW();

-- Add comments
COMMENT ON TABLE iracing_meta_cache IS 'Cached meta analysis results for iRacing series to avoid re-processing races';
COMMENT ON COLUMN iracing_meta_cache.cache_key IS 'Format: meta_{series_id}_{season_id}_{week_num}[_track_{track_id}]';
COMMENT ON COLUMN iracing_meta_cache.meta_data IS 'Full meta analysis results including car stats, lap times, iRatings, etc.';
COMMENT ON COLUMN iracing_meta_cache.expires_at IS 'When this cache entry expires (typically 6-24 hours for active series)';
