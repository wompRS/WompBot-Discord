# GitHub Issues to Create

These issues track the remaining TODO items from the code review. Create them on GitHub to track future performance optimizations.

---

## Issue 1: Optimize iRacing season schedule data fetching with caching

**Labels:** `enhancement`, `performance`, `iracing`
**Priority:** Low

### Description

**Location:** `bot/main.py:5870`

**Current Issue:**
The iRacing schedule commands fetch all season data on every request, which is inefficient when only needing a subset of the data.

**Proposed Solution:**
Implement caching for season schedule data with TTL of 1 hour to reduce API calls and improve response times.

**Benefits:**
- Reduced iRacing API load
- Faster command responses
- Lower rate limit pressure

**Implementation Ideas:**
- Add in-memory or database cache for season schedules
- Set 1-hour TTL for schedule data
- Invalidate cache on demand if needed

**Affected Commands:** `/iracing_schedule`, `/iracing_season_schedule`

**Code Location:**
```python
# bot/main.py:5870
# TODO: Optimize by caching season schedule data (TTL: 1 hour) to reduce
```

---

## Issue 2: Add get_season_by_id() helper method to avoid fetching all seasons

**Labels:** `enhancement`, `performance`, `iracing`
**Priority:** Low

### Description

**Location:** `bot/main.py:5881`

**Current Issue:**
When needing data for a single season, the code currently fetches all 147+ seasons then filters, which is wasteful.

**Proposed Solution:**
Add a `get_season_by_id(season_id)` helper method to the iRacing client to fetch only the requested season.

**Benefits:**
- Reduced data transfer
- Faster response times
- More efficient API usage

**Implementation:**
```python
async def get_season_by_id(self, season_id: int) -> Optional[dict]:
    """Fetch a single season by ID without fetching all seasons"""
    # Check cache first
    if cached := self._get_cached_season(season_id):
        return cached

    # Fetch from API
    # ... implementation
```

**Affected Commands:** `/iracing_season_schedule`, `/iracing_meta`

**Code Location:**
```python
# bot/main.py:5881
# TODO: Cache this or add get_season_by_id() to avoid fetching all 147 seasons
```

---

## How to Create These Issues

### Via GitHub Web UI:
1. Go to https://github.com/wompRS/WompBot-Discord/issues/new
2. Copy/paste the title and description for each issue
3. Add the labels: `enhancement`, `performance`, `iracing`
4. Set milestone (optional): "Performance Optimizations"

### Via GitHub CLI (if available):
```bash
gh issue create \
  --title "Optimize iRacing season schedule data fetching with caching" \
  --body-file issue1.md \
  --label "enhancement,performance,iracing"

gh issue create \
  --title "Add get_season_by_id() helper method to avoid fetching all seasons" \
  --body-file issue2.md \
  --label "enhancement,performance,iracing"
```

---

**Note:** These are performance optimizations identified during code review. They're not urgent but would improve efficiency of iRacing commands.
