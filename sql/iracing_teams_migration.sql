-- iRacing Team Scheduling & Management System
-- Adds support for team management, event scheduling, and driver rotations

-- Teams table
CREATE TABLE IF NOT EXISTS iracing_teams (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,  -- Discord server ID
    team_name VARCHAR(100) NOT NULL,
    team_tag VARCHAR(10),  -- Optional team tag/abbreviation
    created_by BIGINT NOT NULL,  -- Discord user ID of creator
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(guild_id, team_name)
);

-- Team members with roles
CREATE TABLE IF NOT EXISTS iracing_team_members (
    id SERIAL PRIMARY KEY,
    team_id INT NOT NULL REFERENCES iracing_teams(id) ON DELETE CASCADE,
    discord_user_id BIGINT NOT NULL,
    role VARCHAR(50) DEFAULT 'driver',  -- driver, crew_chief, spotter, manager
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    UNIQUE(team_id, discord_user_id)
);

-- Team events (practices, races, endurance events)
CREATE TABLE IF NOT EXISTS iracing_team_events (
    id SERIAL PRIMARY KEY,
    team_id INT NOT NULL REFERENCES iracing_teams(id) ON DELETE CASCADE,
    guild_id BIGINT NOT NULL,
    event_name VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- practice, qualifying, race, endurance
    series_name VARCHAR(255),
    track_name VARCHAR(255),
    event_start TIMESTAMP NOT NULL,
    event_duration_minutes INT,  -- For endurance races
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reminder_sent BOOLEAN DEFAULT FALSE,
    is_cancelled BOOLEAN DEFAULT FALSE,
    notes TEXT
);

-- Driver availability for events
CREATE TABLE IF NOT EXISTS iracing_driver_availability (
    id SERIAL PRIMARY KEY,
    event_id INT NOT NULL REFERENCES iracing_team_events(id) ON DELETE CASCADE,
    discord_user_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL,  -- available, unavailable, maybe, confirmed
    available_from TIMESTAMP,  -- For partial availability in endurance races
    available_until TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    UNIQUE(event_id, discord_user_id)
);

-- Driver stint schedule for endurance events
CREATE TABLE IF NOT EXISTS iracing_stint_schedule (
    id SERIAL PRIMARY KEY,
    event_id INT NOT NULL REFERENCES iracing_team_events(id) ON DELETE CASCADE,
    discord_user_id BIGINT NOT NULL,
    stint_number INT NOT NULL,
    stint_start TIMESTAMP NOT NULL,
    stint_duration_minutes INT NOT NULL,
    role VARCHAR(20) DEFAULT 'driver',  -- driver, relief, backup
    notes TEXT,
    UNIQUE(event_id, stint_number, discord_user_id)
);

-- Track special events (Daytona 24, Le Mans, etc.)
CREATE TABLE IF NOT EXISTS iracing_special_events (
    id SERIAL PRIMARY KEY,
    series_id INT NOT NULL,
    season_id INT NOT NULL,
    event_name VARCHAR(255) NOT NULL,
    track_name VARCHAR(255),
    event_start TIMESTAMP NOT NULL,
    event_duration_minutes INT,
    registration_opens TIMESTAMP,
    registration_closes TIMESTAMP,
    min_team_size INT,
    max_team_size INT,
    is_endurance BOOLEAN DEFAULT FALSE,
    requirements TEXT,  -- JSON with license/iRating requirements
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(series_id, season_id, event_start)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_iracing_teams_guild ON iracing_teams(guild_id);
CREATE INDEX IF NOT EXISTS idx_team_members_team ON iracing_team_members(team_id);
CREATE INDEX IF NOT EXISTS idx_team_members_user ON iracing_team_members(discord_user_id);
CREATE INDEX IF NOT EXISTS idx_team_events_team ON iracing_team_events(team_id);
CREATE INDEX IF NOT EXISTS idx_team_events_start ON iracing_team_events(event_start);
CREATE INDEX IF NOT EXISTS idx_driver_availability_event ON iracing_driver_availability(event_id);
CREATE INDEX IF NOT EXISTS idx_driver_availability_user ON iracing_driver_availability(discord_user_id);
CREATE INDEX IF NOT EXISTS idx_stint_schedule_event ON iracing_stint_schedule(event_id);
CREATE INDEX IF NOT EXISTS idx_special_events_start ON iracing_special_events(event_start);
