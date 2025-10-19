# 📊 Chat Statistics Feature

Comprehensive analytics for your Discord server with **zero LLM costs** using machine learning and graph analysis.

## Overview

The Chat Statistics feature provides deep insights into server activity, trending topics, user interactions, and engagement patterns. Unlike other bot features that rely on expensive LLM APIs, chat statistics uses **TF-IDF keyword extraction** and **network graph analysis** for completely free, fast analytics.

### Key Features
- 🕸️ **Network Graphs** - Visualize who talks to whom
- 🔥 **Topic Trends** - Track trending keywords over time
- ⏰ **Prime Time Analysis** - Activity heatmaps by hour/day
- 📈 **Engagement Metrics** - Response times, message patterns, conversation depth

### Technologies Used
- **TF-IDF** (Term Frequency-Inverse Document Frequency) - Keyword extraction
- **NetworkX** - Graph analysis for user interactions
- **scikit-learn** - Machine learning for topic modeling
- **PostgreSQL** - Caching and data storage
- **Pandas** - Data manipulation and analysis

### Cost & Performance
- **API Cost**: $0.00 (no LLM usage)
- **Computation Time**: 3-10 seconds depending on message volume
- **Update Frequency**: Configurable (15 min to 6 hours)
- **Cache Duration**: 1-6 hours (configurable)

---

## Commands

### `/stats_server [days|date_range]`
Shows server-wide network statistics and interaction graph.

**Examples:**
```
/stats_server 7
/stats_server 30
/stats_server 01/15/2024-02/15/2024
```

**Output:**
- Most connected users (by replies, mentions, conversation proximity)
- Total messages analyzed
- Network degree (connection count) per user
- ASCII table formatted for Discord

---

### `/stats_topics [days|date_range]`
Shows trending keywords using TF-IDF analysis.

**Examples:**
```
/stats_topics 7
/stats_topics 30
/stats_topics 01/01/2024-02/01/2024
```

**Output:**
- Top 15 keywords ranked by relevance
- Message count per keyword
- Visual relevance bars
- No LLM needed - pure machine learning

---

### `/stats_primetime [@user] [days|date_range]`
Shows activity patterns with hourly and daily breakdowns.

**Examples:**
```
/stats_primetime
/stats_primetime @username 7
/stats_primetime 30
/stats_primetime @username 01/15/2024-02/15/2024
```

**Output:**
- 24-hour activity heatmap
- Day of week breakdown (Mon-Sun)
- Peak hour and peak day
- Total message count
- Works for individual users or server-wide

---

### `/stats_engagement [@user] [days|date_range]`
Shows engagement metrics and conversation patterns.

**Examples:**
```
/stats_engagement
/stats_engagement @username 7
/stats_engagement 30
```

**Output:**
- Total messages and unique users
- Average message length
- Messages per user
- Top responders (users who reply quickly)

---

### `!refreshstats` (Admin Only)
Manually triggers background stats computation immediately.

**Usage:**
```
!refreshstats
```

Forces a cache refresh for all stats types and time ranges.

---

## How It Works

### 1. TF-IDF Topic Extraction

**What is TF-IDF?**
Term Frequency-Inverse Document Frequency is a statistical method that identifies important words in a collection of documents.

- **TF (Term Frequency)**: How often a word appears in messages
- **IDF (Inverse Document Frequency)**: How unique the word is across all messages
- **Score**: TF × IDF = relevance score

**Why TF-IDF?**
- No LLM needed (free, fast)
- Automatically filters out common words ("the", "a", "is")
- Identifies truly meaningful keywords
- Works for any language

**Implementation:**
```python
from sklearn.feature_extraction.text import TfidfVectorizer

vectorizer = TfidfVectorizer(
    max_features=20,          # Top 20 keywords
    stop_words='english',     # Remove common words
    ngram_range=(1, 2),       # Single words + 2-word phrases
    min_df=2,                 # Must appear in 2+ messages
    max_df=0.7                # Ignore if in >70% of messages
)

topics = vectorizer.fit_transform(messages)
```

**Custom Stopwords:**
The bot filters out Discord-specific jargon like "lol", "lmao", "tbh", "imo" to surface real topics.

---

### 2. Network Graph Analysis

**How it works:**
Uses NetworkX to build a directed graph of user interactions based on:
- **Direct @mentions** (weight: 1.0)
- **Conversation proximity** - Replying within 3 messages in same channel (weight: 0.5)

**Graph Metrics:**
- **Degree**: Number of connections a user has
- **Edges**: Weighted connections between users
- **Nodes**: Users with metadata (username, message count)

**Implementation:**
```python
import networkx as nx

G = nx.DiGraph()
# Add edges for mentions
G.add_edge(user_a, user_b, weight=1.0)
# Add edges for conversation proximity
G.add_edge(user_a, prev_user, weight=0.5)

# Calculate most connected users
top_users = sorted(G.degree(), key=lambda x: x[1], reverse=True)
```

---

### 3. Caching System

**Why Caching?**
- Avoids re-computing same stats repeatedly
- Instant response for users
- Reduces database load

**Cache Strategy:**
- Results stored in `stats_cache` table as JSONB
- Cache key: `{stat_type}:{scope}:{start_date}:{end_date}`
- Default validity: 2-6 hours (configurable)
- Automatic invalidation on expiry

**Cache Hit Rate:**
For hourly updates, expect ~95%+ cache hit rate during normal usage.

---

### 4. Background Computation

**How it works:**
A background task runs on a schedule to pre-compute common statistics before users request them.

**What gets pre-computed:**
- Last 7 days: network, topics, primetime, engagement
- Last 30 days: network, topics, primetime, engagement

**Schedule:**
Default: Every 1 hour (configurable)

**Database Storage:**
Each cache entry is ~5-10 KB, totaling ~200 KB per update cycle.

---

## Configuration

### Update Frequency

**File:** `bot/main.py:36`

**Change background task interval:**

```python
# Current: Every hour
@tasks.loop(hours=1)
async def precompute_stats():
    ...

# Every 30 minutes (recommended for active servers)
@tasks.loop(minutes=30)

# Every 15 minutes (maximum freshness)
@tasks.loop(minutes=15)

# Every 6 hours (lighter load)
@tasks.loop(hours=6)
```

**Recommendation by server size:**
- Small (<100 msgs/day): `hours=1` or `hours=6`
- Medium (100-1000 msgs/day): `minutes=30` or `hours=1`
- Large (1000+ msgs/day): `minutes=15` or `minutes=30`

---

### Time Ranges

**File:** `bot/main.py:46`

**Which time ranges to pre-compute:**

```python
# Current: 7 and 30 days
time_ranges = [7, 30]

# Add more options
time_ranges = [1, 7, 30, 90]  # Yesterday, week, month, quarter

# Minimal (fastest)
time_ranges = [7]  # Just last week

# Custom ranges
time_ranges = [3, 14, 60]  # Last 3 days, 2 weeks, 2 months
```

**Note:** More time ranges = more computation time but better coverage.

---

### Cache Duration

**File:** `bot/main.py:64, 74, 83, 92`

**How long to cache results:**

```python
# Current: 2 hours
chat_stats.cache_stats('network', scope, start_date, end_date, network, cache_hours=2)

# Longer cache (less computation)
cache_hours=6

# Shorter cache (fresher data)
cache_hours=1
```

**Trade-off:**
- Longer cache = Less computation, slightly stale data
- Shorter cache = More computation, fresher data
- **Cost is always $0**, so you can use short cache durations freely

---

### Date Format

**American Standard:** MM/DD/YYYY

**Valid formats:**
- Days: `7`, `30`, `90`
- Date ranges: `01/15/2024-02/15/2024`

**Examples:**
```
/stats_topics 30                          ✅ Last 30 days
/stats_topics 01/01/2024-01/31/2024      ✅ January 2024
/stats_primetime @user 12/25/2024-12/31/2024  ✅ Holiday week
```

**Invalid:**
```
/stats_topics 2024-01-15 to 2024-02-15   ❌ Wrong format
/stats_topics 15/01/2024-15/02/2024      ❌ Day/Month/Year not supported
```

---

## Performance & Cost Analysis

### Computation Time by Server Size

| Messages | Network | Topics | Primetime | Engagement | Total |
|----------|---------|--------|-----------|------------|-------|
| 100      | ~1s     | ~1s    | ~0.5s     | ~0.5s      | ~3s   |
| 1,000    | ~2s     | ~2s    | ~0.5s     | ~0.5s      | ~5s   |
| 10,000   | ~3s     | ~5s    | ~1s       | ~1s        | ~10s  |
| 100,000  | ~10s    | ~15s   | ~2s       | ~2s        | ~29s  |

### Cost Breakdown

| Component | Technology | Cost |
|-----------|-----------|------|
| Topic Extraction | TF-IDF (scikit-learn) | $0.00 |
| Network Analysis | NetworkX | $0.00 |
| Primetime Calc | SQL Aggregation | $0.00 |
| Engagement Calc | SQL + Python | $0.00 |
| **Total** | **No LLM needed** | **$0.00** |

### Monthly Resource Usage

**For hourly updates (24 cycles/day):**
- Computation cycles: ~720/month
- Database growth: ~35 MB/month
- CPU usage: <1% average
- **API costs: $0.00**

**For 15-minute updates (96 cycles/day):**
- Computation cycles: ~2,880/month
- Database growth: ~140 MB/month
- CPU usage: <2% average
- **API costs: $0.00**

---

## Customization Examples

### Example 1: Real-Time Stats (15-min updates)

**Goal:** Always have fresh stats, updated every 15 minutes.

**Configuration:**
```python
# bot/main.py:36
@tasks.loop(minutes=15)  # Run every 15 minutes

# bot/main.py:46
time_ranges = [1, 7]  # Yesterday + last week (faster computation)

# bot/main.py:64
cache_hours=1  # Cache for 1 hour
```

**Result:** Stats are never older than 15 minutes, still costs $0.

---

### Example 2: Extended History

**Goal:** Track stats for longer periods (90 days, 1 year).

**Configuration:**
```python
# bot/main.py:46
time_ranges = [7, 30, 90, 365]  # Week, month, quarter, year

# bot/main.py:36
@tasks.loop(hours=2)  # Run every 2 hours (more data = slower)

# bot/main.py:64
cache_hours=4  # Longer cache for large datasets
```

**Note:** Year-long stats may take 30-60 seconds to compute for active servers.

---

### Example 3: Custom Stopwords

**Goal:** Filter out server-specific jargon from topic trends.

**File:** `bot/features/chat_stats.py:89-101`

**Add custom stopwords:**
```python
custom_stopwords = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
    # ... existing stopwords ...

    # Add your server-specific words to ignore
    'poggers', 'kekw', 'copium', 'hopium',
    'gm', 'gn', 'lfg', 'fr', 'ngl',
    # Add more as needed
}
```

---

### Example 4: Adjust TF-IDF Parameters

**Goal:** Get more specific/different keyword results.

**File:** `bot/features/chat_stats.py:103-110`

**Modify vectorizer settings:**
```python
vectorizer = TfidfVectorizer(
    max_features=30,         # Get more keywords (was 20)
    ngram_range=(1, 3),      # Include 3-word phrases (was 1-2)
    min_df=1,                # Allow single-mention words (was 2)
    max_df=0.5,              # Stricter uniqueness (was 0.7)
    token_pattern=r'(?u)\b[a-zA-Z][a-zA-Z]+\b'
)
```

**Effects:**
- `max_features`: More keywords in results
- `ngram_range`: Longer phrase detection
- `min_df`: Lower = more rare words, Higher = only common words
- `max_df`: Lower = more unique words, Higher = allows common words

---

## Troubleshooting

### Stats Not Updating

**Symptom:** Stats show old data even after hours.

**Check:**
1. Is background task running?
   ```bash
   docker-compose logs bot | grep "Background stats"
   ```
   Should see: `🔄 Starting background stats computation...`

2. Check cache validity:
   ```sql
   SELECT stat_type, scope, valid_until
   FROM stats_cache
   WHERE valid_until > NOW();
   ```

**Fix:**
- Manually refresh: `!refreshstats`
- Restart bot: `docker-compose restart bot`
- Clear cache: `DELETE FROM stats_cache;`

---

### Performance Issues

**Symptom:** Stats commands take >30 seconds.

**Possible causes:**
1. **Too many messages**: 100,000+ messages in time range
2. **Large time range**: Requesting 1 year of data
3. **No cache**: First request or cache expired

**Solutions:**
1. Reduce time range: Use 7 or 30 days instead of custom ranges
2. Enable background computation: Ensures cache is always fresh
3. Optimize database:
   ```sql
   VACUUM ANALYZE messages;
   REINDEX TABLE messages;
   ```

---

### TF-IDF Returns Gibberish

**Symptom:** Topic keywords are random letters or emoji.

**Cause:** Token pattern doesn't filter non-words.

**Fix:** Adjust `token_pattern` in `chat_stats.py:110`:
```python
token_pattern=r'(?u)\b[a-zA-Z]{3,}\b'  # At least 3 letters
```

---

### Memory Usage High

**Symptom:** Bot using 500+ MB RAM.

**Cause:** Too many stats cached or large datasets.

**Solutions:**
1. Clear old cache entries:
   ```sql
   DELETE FROM stats_cache WHERE valid_until < NOW();
   ```

2. Reduce cache retention:
   ```python
   cache_hours=1  # Instead of 6
   ```

3. Limit time ranges:
   ```python
   time_ranges = [7]  # Only last week
   ```

---

## Database Schema

### stats_cache Table

```sql
CREATE TABLE stats_cache (
    id SERIAL PRIMARY KEY,
    stat_type VARCHAR(50) NOT NULL,        -- 'network', 'topics', 'primetime', 'engagement'
    scope VARCHAR(100) NOT NULL,            -- 'server:123', 'user:456'
    time_range_days INT,                    -- NULL for custom date ranges
    start_date TIMESTAMP,                   -- Query start date
    end_date TIMESTAMP,                     -- Query end date
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_until TIMESTAMP NOT NULL,         -- Cache expiry
    results JSONB NOT NULL,                 -- Cached results
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookups
CREATE INDEX idx_stats_cache_type_scope ON stats_cache(stat_type, scope);
CREATE INDEX idx_stats_cache_valid_until ON stats_cache(valid_until);
```

### Example Cache Entry

```json
{
  "stat_type": "topics",
  "scope": "server:1206079936331259954",
  "start_date": "2024-10-12 00:00:00",
  "end_date": "2024-10-19 23:59:59",
  "results": [
    {"keyword": "bitcoin", "score": 0.87, "count": 45},
    {"keyword": "crypto market", "score": 0.65, "count": 23},
    {"keyword": "ethereum", "score": 0.54, "count": 18}
  ]
}
```

---

## Technical Details

### Dependencies

```python
# requirements.txt
scikit-learn==1.3.2  # TF-IDF vectorization
networkx==3.2.1       # Graph analysis
pandas==2.1.4         # Data manipulation
numpy==1.26.2         # Linear algebra for scikit-learn
```

### Module Structure

```
bot/features/chat_stats.py
├── ChatStatistics class
│   ├── parse_date_range()        # Parse user input
│   ├── get_cached_stats()        # Retrieve from cache
│   ├── cache_stats()             # Store in cache
│   ├── get_messages_for_analysis() # Query messages
│   ├── extract_topics_tfidf()    # TF-IDF topic extraction
│   ├── build_network_graph()     # NetworkX graph building
│   ├── calculate_primetime()     # Activity heatmaps
│   ├── calculate_engagement()    # Engagement metrics
│   └── format_as_discord_table() # ASCII table formatting
```

### Algorithm Complexity

| Operation | Time Complexity | Space Complexity |
|-----------|----------------|------------------|
| TF-IDF | O(n × m) | O(m × v) |
| Network Graph | O(n²) | O(n) |
| Primetime | O(n) | O(1) |
| Engagement | O(n) | O(n) |

Where:
- n = number of messages
- m = average message length
- v = vocabulary size
- Worst case for network: O(n²) when everyone talks to everyone

---

## Privacy Considerations

**Opted-Out Users:**
Users with the `NoDataCollection` role are **completely excluded** from all statistics:
- Not counted in totals
- Not shown in network graphs
- Not included in topic analysis
- Not listed in engagement metrics

**Code:**
```python
# All queries exclude opted-out users
messages = chat_stats.get_messages_for_analysis(
    channel_id=None,
    start_date=start_date,
    end_date=end_date,
    exclude_opted_out=True  # Privacy enforcement
)
```

---

## Future Enhancements

Potential additions to this feature:

1. **Channel Comparison** - Compare activity across different channels
2. **Sentiment Analysis** - Track positive/negative tone over time
3. **Export to CSV** - Download stats as spreadsheet
4. **Custom Visualizations** - Generate PNG charts (requires matplotlib)
5. **Emoji Statistics** - Most used emoji, emoji trends
6. **Thread Analysis** - Track conversation thread depth
7. **Time Series** - Show topic trends over time (week-over-week)

---

## Support

**Issues?**
1. Check logs: `docker-compose logs bot | grep stats`
2. Verify database: `docker-compose exec postgres psql -U botuser -d discord_bot`
3. Manual refresh: `!refreshstats`
4. Restart bot: `docker-compose restart bot`

**Still stuck?**
Check [docs/CONFIGURATION.md](../CONFIGURATION.md) for bot-wide settings.
