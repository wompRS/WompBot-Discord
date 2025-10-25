# iRacing Integration

Complete integration with iRacing's official API for driver stats, race schedules, meta analysis, and more.

## Features Overview

### 🏁 Core Features
- **Driver Profiles** - View detailed stats across all license categories
- **Driver Comparison** - Side-by-side visual comparisons with professional charts
- **Rating History** - Track iRating and Safety Rating progression over time
- **Server Leaderboards** - Rankings for Discord server members by category
- **Meta Analysis** - Best car performance data for any series/track combination
- **Race Schedules** - Upcoming official races with series filtering
- **Account Linking** - Connect Discord accounts to iRacing profiles
- **Recent Results** - View latest race performance

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

### `/iracing_history [driver_name] [category] [days]`
View rating progression chart showing iRating and Safety Rating history.

**Parameters:**
- `driver_name` (optional) - Driver name (uses linked account if omitted)
- `category` (optional) - License category (default: sports_car_road)
  - Use autocomplete: Oval, Sports Car (Road), Formula Car (Road), Dirt Oval, Dirt Road
- `days` (optional) - Number of days of history (default: 30)

**Example:**
```
/iracing_history
/iracing_history "Blair Winters" sports_car_road 90
/iracing_history category:oval days:60
```

**Chart Features:**
- Dual y-axis (iRating on left, Safety Rating on right)
- Line plots with markers and filled areas
- Period change summary showing gains/losses
- Professional dark theme with gold accents

**Notes:**
- Shows "not enough data" if fewer than 2 data points
- Filters by specific category (e.g., oval, sports_car_road)
- Debug logging available if category filtering issues occur

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

### `/iracing_schedule [series] [hours]`
View upcoming official race schedule.

**Parameters:**
- `series` (optional) - Filter by series name
- `hours` (optional) - How many hours ahead to show (default: 24)

**Example:**
```
/iracing_schedule
/iracing_schedule "GT3 Sprint Series"
/iracing_schedule hours:48
```

---

### `/iracing_series`
List all active iRacing series and seasons.

**Example:**
```
/iracing_series
```

**Shows:**
- Series names
- Current season information
- Available categories

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
- Intelligent caching minimizes API calls
- Pre-warms series cache on bot startup
- Background task loads series data
- Avoids redundant profile lookups within same command

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
