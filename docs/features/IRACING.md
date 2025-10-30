# iRacing Integration

Complete integration with iRacing's official API for driver stats, race schedules, meta analysis, and more.

## Features Overview

### 🏁 Core Features
- **Driver Profiles** - View detailed stats across all license categories
- **Driver Comparison** - Side-by-side visual comparisons with professional charts
- **Performance Dashboard** - Analyze rating trends, per-race deltas, wins/podiums, and incident averages over selectable timeframes
- **Series Popularity Analytics** - Daily participation snapshots power season/year/all-time trends
- **Server Leaderboards** - Rankings for Discord server members by category
- **Meta Analysis** - Best car performance data for any series/track combination
- **Schedule Visualizations** - Season tables highlight the current week, display UTC open times, and include season date ranges
- **Account Linking** - Connect Discord accounts to iRacing profiles
### 🎨 Professional Visualizations
- Charts styled after iRacing Reports
- Dark theme with gold accents
- Category-specific color coding
- License class badges (Rookie through Pro)
- High-resolution PNG exports (150 DPI)

## Commands

### `/iracing_link <iracing_name>`
Link your Discord account to your iRacing profile.

**Parameters:**
- `iracing_name` - Your iRacing display name

**Example:**
```
/iracing_link John Smith
```

**Notes:**
- Only needs to be done once
- Allows using commands without specifying driver name
- Stored securely in database

---

### `/iracing_profile [driver_name]`
View comprehensive iRacing driver profile.

**Parameters:**
- `driver_name` (optional) - Driver's iRacing name (uses linked account if omitted)

**Example:**
```
/iracing_profile
/iracing_profile Blair Winters
```

**Shows:**
- All license categories (Oval, Sports Car, Formula Car, Dirt Oval, Dirt Road)
- iRating and TT Rating for each category
- Safety Rating and License Class
- Career statistics (starts, wins, top 5s, etc.)

---

### `/iracing_compare_drivers <driver1> <driver2> [category]`
Generate side-by-side comparison chart for two drivers.

**Parameters:**
- `driver1` - First driver name or customer ID
- `driver2` - Second driver name or customer ID
- `category` (optional) - License category (default: sports_car_road)
  - Use autocomplete: Oval, Sports Car (Road), Formula Car (Road), Dirt Oval, Dirt Road

**Example:**
```
/iracing_compare_drivers "Rinde Andrew" "Blair Winters"
/iracing_compare_drivers 118800 1294605 oval
```

**Chart Includes:**
- License ratings for all 5 categories
- iRating, TT Rating, Safety Rating, License Class
- Career statistics (starts, wins, podiums, poles, avg finish, avg incidents, win rate)
- Professional visualization with column banding

**Features:**
- Compact layout (16x9.5)
- Alternating row backgrounds with rounded corners
- Consistent corner radius (0.08)
- License classes color-coded by iRacing standard:
  - Rookie: Red
  - D-Class: Orange
  - C-Class: Yellow/Gold
  - B-Class: Green
  - A-Class: Blue
  - Pro: Lighter Blue

---

### `/iracing_history [driver_name] [timeframe]`
Unified performance dashboard showing rating trends, per-race deltas, and usage breakdowns.

**Parameters:**
- `driver_name` (optional) - Driver name (uses linked account if omitted)
- `timeframe` (optional) - One of `day`, `week`, `month`, `season`, `year`, `all` (defaults to `week`)

**Example:**
```
/iracing_history
/iracing_history "Blair Winters" timeframe:month
/iracing_history timeframe:season
```

**Dashboard Includes:**
- Dual-axis chart with iRating (left) and Safety Rating (right)
- Period change summary showing total and per-race IR/SR deltas
- Wins, podiums, average finish, and average incidents for the selected window
- Bar charts highlighting the most-used series and cars
- Friendly message when insufficient data exists for the timeframe

**Notes:**
- Pulls up to the most recent 200 races before timeframe filtering
- Automatically uses linked account if `driver_name` omitted
- Caches API requests to avoid hitting the adaptive rate limiter

---

### `/iracing_server_leaderboard [category]`
Show iRating rankings for Discord server members who have linked accounts.

**Parameters:**
- `category` (optional) - License category (default: sports_car_road)
  - Use autocomplete: Oval, Sports Car (Road), Formula Car (Road), Dirt Oval, Dirt Road

**Example:**
```
/iracing_server_leaderboard
/iracing_server_leaderboard oval
```

**Shows:**
- Discord username and iRacing name
- iRating for selected category
- Safety Rating
- License Class
- Sorted by iRating (highest first)

**Requirements:**
- Users must link accounts with `/iracing_link`
- Only shows members in current server
- Caches profile data to minimize API calls

---

### `/iracing_meta <series> [season] [week] [track]`
View meta analysis showing best performing cars for a series.

**Parameters:**
- `series` - Series name (autocomplete available)
- `season` (optional) - Season ID (autocomplete available, defaults to current)
- `week` (optional) - Week number (autocomplete available, defaults to current)
- `track` (optional) - Track name (autocomplete available, analyzes all if omitted)

**Example:**
```
/iracing_meta "IMSA Michelin Pilot Challenge"
/iracing_meta "GT3 Sprint Series" track:"Watkins Glen International"
```

**Analysis Includes:**
- Best average lap times by car
- Average iRating of drivers using each car
- Win rate percentage
- Podium rate percentage
- Total races analyzed
- Unique drivers count
- Professional chart with car logos (when available)

**Features:**
- Autocomplete for series, season, week, and track
- Can analyze specific week or entire season
- Can filter by specific track or analyze all tracks
- Performance analysis waits up to 60 seconds for complete data
- Charts styled like iRacing Reports

**Notes:**
- Analysis can take 30-60 seconds for large datasets
- Shows "analyzing race data" message while processing
- Caches series data for 5 minutes to improve autocomplete performance

---

### `/iracing_schedule [series] [category] [week]`
Render race schedules as a polished table image.

**Parameters:**
- `series` (optional) - Series name (partial match supported, takes priority over category)
- `category` (optional) - Show current-week highlights for Oval, Sports Car, Formula Car, Dirt Oval, or Dirt Road
- `week` (optional) - `current`, `upcoming`, or `full` (default) to control how many weeks are shown

**Examples:**
```
/iracing_schedule series:"IMSA Michelin Pilot Challenge"
/iracing_schedule category:oval week:current
/iracing_schedule week:upcoming
```

**Output:**
- High-resolution PNG table with week number, UTC open time, and full track layout
- Current week highlighted with a blue accent box
- Season date range and weekly reset note displayed above the table
- Category view highlights every active series for the selected discipline
- Intelligent fallback when the race guide lacks complete historical data

---

---

### `/iracing_series_popularity [time_range]`
Show the most popular series by unique participants, backed by daily snapshots.

**Parameters:**
- `time_range` (optional) - `season` (default), `yearly`, or `all_time`

**Examples:**
```
/iracing_series_popularity
/iracing_series_popularity time_range:yearly
```

**How it works:**
- Season view requires at least **7 days** of data for the current quarter
- Yearly view unlocks after **30 days** of snapshots
- All-time view unlocks after **90 days** of snapshots
- Falls back to the current season with a friendly notice until thresholds are met
- Outputs an analytics-style chart ranked by participant counts

---

### `/iracing_season_schedule <series_name> [season]`
View the full season track rotation for a series.

**Parameters:**
- `series_name` - Series name (partial match supported)
- `season` (optional) - Specific season in `YYYY S#` format (defaults to current)

**Examples:**
```
/iracing_season_schedule "GT3 Sprint Series"
/iracing_season_schedule "IMSA Michelin Pilot Challenge" season:"2025 S1"
```

**Output:**
- Embed plus attached PNG table highlighting the current week
- Season date range, weekly reset note, and total weeks displayed in the header
- Track column widened to reduce truncation and show configuration names
- Adaptive fallback to text-based embeds if the visualizer is unavailable

---

---

### `/iracing_results [driver_name]`
View recent race results and performance.

**Parameters:**
- `driver_name` (optional) - Driver name (uses linked account if omitted)

**Example:**
```
/iracing_results
/iracing_results "Rinde Andrew"
```

## Historical Participation Tracking & Caching

- **Daily snapshots** store participant counts for every active series in `iracing_participation_history`.
- **Weekly cache refreshes** pre-compute popularity rankings for season, yearly, and all-time views.
- Commands automatically fall back to live API data until enough history is collected.
- Keep the bot running to accumulate data; the longer it runs, the richer the analytics become.
- Snapshot tasks respect rate limits by sampling up to 100 active series per day.

---

## License Categories

iRacing has 5 distinct license categories:

| Category | Key | Description |
|----------|-----|-------------|
| **Oval** | `oval` | Traditional oval racing |
| **Sports Car** | `sports_car_road` | GT3, GTE, and sports car road racing |
| **Formula Car** | `formula_car_road` | Open-wheel road racing |
| **Dirt Oval** | `dirt_oval` | Dirt track oval racing |
| **Dirt Road** | `dirt_road` | Rallycross and dirt road racing |

**Note:** "Road" category was deprecated and split into Sports Car and Formula Car categories to match iRacing's official classification.

## License Classes

| Class | Color | iRating Range |
|-------|-------|---------------|
| **Rookie** | Red (#fc0706) | New drivers |
| **D-Class** | Orange (#ff8c00) | Learning fundamentals |
| **C-Class** | Yellow/Gold (#ffd700) | Intermediate |
| **B-Class** | Green (#22c55e) | Advanced |
| **A-Class** | Blue (#0153db) | Expert |
| **Pro** | Lighter Blue (#3b82f6) | Professional |

## Rating Types

### iRating
- **Official Race Rating** - Skill-based rating from official races
- Increases with good finishes, decreases with poor finishes
- Separate iRating for each license category
- Displayed as integer (e.g., 1,852)

### TT Rating (Time Trial)
- **Time Trial Rating** - Skill-based rating from time trials
- Available for drivers who participate in time trial events
- Separate from official race iRating
- Displayed when iRating is 0 or as secondary metric

### Safety Rating
- **Incident-based Rating** - Measures clean driving
- Scale: 0.00 to 4.99
- Higher is better (fewer incidents)
- Required minimums for license promotions
- Displayed as decimal (e.g., 3.25)

## API Integration

### Authentication
- Uses encrypted credentials (Fernet symmetric encryption)
- Credentials stored in `.iracing_credentials` (encrypted)
- Encryption key in `.encryption_key` (both gitignored)
- Set up with `python encrypt_credentials.py`

### Endpoints Used
- `/data/member/get` - Driver profiles and licenses
- `/data/stats/member_recent_races` - Recent race results
- `/data/stats/member_yearly` - Career statistics
- `/data/member/chart_data` - Rating history
- `/data/lookup/drivers` - Driver search
- `/data/series/get` - Series information
- `/data/series/seasons` - Season data
- `/data/season/race_guide` - Race schedules
- Result analysis endpoints for meta charts

### Caching Strategy
- **Series Data**: 5-minute cache for autocomplete performance
- **Profile Data**: Cached per request to minimize duplicate API calls
- **Race Guide**: Cached for schedule lookups
- Response caching prevents rate limiting

### Rate Limiting
- Shared asyncio lock serializes outbound requests per process
- 429 responses respect the API-provided `Retry-After` header before retrying
- Standard requests fire without delay once the lock releases
- Existing caching strategy still pre-warms series data and avoids duplicate profile lookups

## Database Schema

### `iracing_links` Table
```sql
CREATE TABLE iracing_links (
    discord_id BIGINT PRIMARY KEY,
    iracing_cust_id INTEGER NOT NULL,
    iracing_name TEXT NOT NULL,
    linked_at TIMESTAMP DEFAULT NOW()
);
```

Stores Discord → iRacing account mappings for linked users.

## Visualization Details

### Color Scheme
- **Background Dark**: #0f172a
- **Background Card**: #1e293b
- **Text White**: #ffffff
- **Text Gray**: #94a3b8
- **Accent Blue**: #3b82f6 (iRating)
- **Accent Green**: #22c55e (Safety Rating)
- **Accent Yellow**: #eab308 (TT Rating)
- **Accent Gold**: #fbbf24 (Headers)

### Chart Specifications
- **DPI**: 150-160 for high quality
- **Font**: Sans-serif, sizes 10-28pt
- **Corner Radius**: 0.08 (consistent across all rounded elements)
- **Figure Sizes**:
  - Driver Comparison: 16x9.5 inches
  - Rating History: 16x8 inches
  - Meta Charts: Variable based on data

### Design Elements
- Column banding with alternating row backgrounds
- Rounded corners on row backgrounds (pad=0.04)
- Gold-bordered section headers (linewidth=2.5)
- Horizontal gold separator lines under driver names
- Professional spacing and alignment
- No colored bullet points (removed for cleaner look)

## Cost & Performance

### Zero LLM Cost
- **No AI/LLM usage** - Pure API calls and data processing
- **No per-message fees** - Only API bandwidth
- **Free tier friendly** - Works with basic iRacing account

### Performance Optimizations
- Pre-computed statistics caching
- Background series data loading
- Intelligent request batching
- Minimal redundant API calls
- Fast matplotlib rendering

### Resource Usage
- **API Calls**: ~2-5 per command (with caching)
- **Memory**: Matplotlib charts ~10-20MB per render
- **Disk**: Image cache managed automatically
- **Response Time**: 2-5 seconds typical

## Troubleshooting

### "iRacing integration is not configured"
**Cause**: Encrypted credentials not set up
**Solution**: Run `python encrypt_credentials.py` in bot container

### "Could not find driver"
**Cause**: Incorrect name or driver doesn't exist
**Solution**: Check exact spelling, try customer ID instead

### "Not enough rating history data available"
**Cause**: Fewer than 2 data points for category
**Solutions**:
- Try different category
- Increase days parameter
- Check if driver races in that category

### "Category not found" or data showing wrong category
**Cause**: Category filtering issues in rating history
**Debug**: Check logs for category mapping debug info
**Solution**: Report exact category and driver for investigation

### API Rate Limiting
**Cause**: Too many requests in short time
**Solution**: Wait 1-2 minutes, caching will help reduce future calls

### Helmet Icons Missing
**Note**: iRacing API returns helmet design data (pattern, colors), not images
**Status**: Helmet rendering not implemented (would require complex pattern renderer)
**Workaround**: Not critical for functionality

## Development Notes

### Files
- `bot/features/iracing.py` - Core iRacing API integration
- `bot/iracing_viz.py` - Visualization and charting
- `bot/iracing_graphics.py` - Profile cards (legacy, being phased out)
- `bot/iracing_client.py` - Low-level API client
- `bot/main.py` - Command definitions and autocomplete functions

### Adding New Commands
1. Add autocomplete function if needed (e.g., `category_autocomplete`)
2. Define command with `@bot.tree.command`
3. Add `@app_commands.autocomplete` decorator
4. Implement command logic with error handling
5. Use visualization functions for charts
6. Update documentation

### Testing Checklist
See testing section below for comprehensive test cases.

## Privacy & Security

### Encrypted Credentials
- iRacing credentials encrypted with Fernet
- Keys never stored in plaintext
- Encryption key in gitignored file
- Credentials file also gitignored

### User Data
- Only stores Discord ID → iRacing customer ID mapping
- No sensitive iRacing data cached
- Profile data fetched fresh from API
- Users can unlink with database query

### Optional Feature
- Disabled by default if no credentials
- Users opt-in by linking accounts
- No automatic data collection
- Respects Discord privacy settings

---

## Team Management System

Complete team management and event scheduling system for organizing iRacing teams, practices, and races.

### Features

#### Team Creation & Management
- Create teams with custom names and tags
- Role-based permissions (manager, driver, crew_chief, spotter)
- Multi-guild support (teams are server-specific)
- Team roster with Discord and iRacing profile integration
- Team discovery (list all teams, view team info)

#### Event Scheduling
- Schedule practices, qualifying sessions, races, and endurance events
- Natural language time parsing ("tomorrow 8pm", "next Friday 19:00")
- Discord timestamp integration (shows in user's local timezone)
- Optional series and track information
- Duration tracking for endurance races

#### Driver Availability Tracking
- Four status levels: available, unavailable, maybe, confirmed
- Optional notes for partial availability
- Team roster view showing all driver statuses
- Ready count for quick availability overview

#### Official Race Schedule
- Browse upcoming iRacing official races
- Filter by series name
- Customizable time window (default: 24 hours)

### Team Management Commands

#### `/iracing_team_create <name> <tag> [description]`
Create a new racing team.

**Parameters:**
- `name` - Team name (e.g., "Team Racing Technologies")
- `tag` - Short team abbreviation (e.g., "TRT", max 10 chars)
- `description` (optional) - Team description

**Example:**
```
/iracing_team_create name:"Team Racing Technologies" tag:"TRT" description:"Competitive GT3 racing team"
```

**Result:**
- Team created with you as manager
- Unique team ID assigned
- Ready to invite members

---

#### `/iracing_team_invite <team_id> <member> [role]`
Invite a member to your team.

**Parameters:**
- `team_id` - Your team ID
- `member` - Discord user to invite
- `role` (optional) - Member role (default: driver)
  - `driver` - Team driver
  - `manager` - Team manager (can invite/remove members)
  - `crew_chief` - Race strategist/engineer
  - `spotter` - Race spotter

**Example:**
```
/iracing_team_invite team_id:1 member:@JohnDoe role:driver
```

**Permissions:**
- Only team managers can invite members
- Invited member added immediately

---

#### `/iracing_team_leave <team_id>`
Leave a team.

**Example:**
```
/iracing_team_leave team_id:1
```

---

#### `/iracing_team_info <team_id>`
View detailed team information and roster.

**Example:**
```
/iracing_team_info team_id:1
```

**Shows:**
- Team name and tag
- Description
- Member roster grouped by role
- iRacing names (if linked)
- Total member count
- Creation date

---

#### `/iracing_team_list`
List all teams in your Discord server.

**Example:**
```
/iracing_team_list
```

**Shows:**
- All active teams
- Member counts
- Team IDs for joining

---

#### `/iracing_my_teams`
View teams you're a member of.

**Example:**
```
/iracing_my_teams
```

**Shows:**
- Your teams
- Your role in each team
- Team IDs

---

### Event Scheduling Commands

#### `/iracing_event_create <team_id> <name> <type> <time> [duration] [series] [track] [notes]`
Schedule a team event.

**Parameters:**
- `team_id` - Your team ID
- `name` - Event name
- `type` - Event type (practice, qualifying, race, endurance)
- `time` - Event start time (natural language)
- `duration` (optional) - Duration in minutes (for endurance races)
- `series` (optional) - iRacing series name
- `track` (optional) - Track name
- `notes` (optional) - Additional notes

**Time Examples:**
- "tomorrow 8pm"
- "next Friday 19:00"
- "January 15 2025 7:00pm"
- "2025-01-15 19:00"

**Example:**
```
/iracing_event_create team_id:1 name:"GT3 Practice" type:practice time:"tomorrow 8pm" series:"GT3 Sprint Series" track:"Spa-Francorchamps"
```

---

#### `/iracing_team_events <team_id>`
View upcoming events for a team.

**Example:**
```
/iracing_team_events team_id:1
```

**Shows:**
- Event name and type
- Start time (with Discord timestamp)
- Duration (if applicable)
- Series and track
- Event IDs for availability marking

---

#### `/iracing_event_availability <event_id> <status> [notes]`
Mark your availability for an event.

**Parameters:**
- `event_id` - Event ID
- `status` - Your availability
  - `available` - Available to participate
  - `unavailable` - Cannot participate
  - `maybe` - Tentative
  - `confirmed` - Confirmed participation
- `notes` (optional) - Availability notes (e.g., "Can only do first 2 hours")

**Example:**
```
/iracing_event_availability event_id:5 status:available notes:"Available for full duration"
```

---

#### `/iracing_event_roster <event_id>`
View driver availability for an event.

**Example:**
```
/iracing_event_roster event_id:5
```

**Shows:**
- Drivers grouped by availability status
- iRacing names (if linked)
- Availability notes
- Total driver count

---

#### `/iracing_upcoming_races [hours] [series]`
Browse upcoming official iRacing races.

**Parameters:**
- `hours` (optional) - Hours ahead to search (default: 24)
- `series` (optional) - Filter by series name

**Example:**
```
/iracing_upcoming_races
/iracing_upcoming_races hours:48
/iracing_upcoming_races series:"GT3 Sprint"
```

**Shows:**
- Upcoming official races
- Series names
- Track names
- Start times

---

### Use Cases

#### Practice Sessions
1. Create team event for practice
2. Members mark availability
3. Check roster before session
4. Coordinate on voice chat

#### Race Events
1. Schedule race event with series/track info
2. Set event duration
3. Track confirmed drivers
4. Organize lineup

#### Endurance Races
1. Create endurance event with duration
2. Track availability for full duration
3. Plan driver stints (future feature)
4. Coordinate team strategy

### Integration

**Works with:**
- `/iracing_link` - Links Discord to iRacing profile
- Shows iRacing names in rosters
- Falls back to Discord mentions if not linked
- Compatible with all iRacing API features

**Database:**
- Teams are server-specific
- Events linked to teams
- Availability tracked per event
- Complete audit trail

---

## Future Enhancements

### Potential Features
- [ ] Team/league leaderboards
- [ ] Race result notifications
- [ ] Championship standings tracking
- [ ] Personal best lap times database
- [ ] Series popularity analytics
- [ ] Incident point tracking
- [ ] Multi-driver comparison (3+ drivers)
- [ ] Historical iRating graphs (yearly trends)
- [ ] Safety Rating progression tracking
- [ ] License promotion predictions

### Known Limitations
- Helmet icons not rendered (API only provides design data)
- Meta analysis limited to available race results
- Rating history requires multiple race data points
- Series autocomplete cache: 5-minute TTL

## Support

For issues or questions:
1. Check bot logs: `docker-compose logs bot`
2. Verify credentials: Files exist and not corrupted
3. Test API access: Profile command should work
4. Check iRacing API status
5. Review error messages for specific issues
