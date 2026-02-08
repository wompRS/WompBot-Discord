# ☁️ Quotes System

Save memorable messages with emoji reactions.

## Overview

The Quotes system allows users to save memorable messages by reacting with a ☁️ (cloud) emoji. Quotes are stored with context and can be retrieved later.

### Key Features
- ☁️ **Emoji Saving** - React to save quotes instantly
- 📝 **Context Preservation** - Saves surrounding messages for context
- ⭐ **Reaction Counting** - Tracks how many times quote was saved
- 📋 **Quotes Command** - View all quotes from a user
- 🔍 **Searchable** - Stored in database for easy retrieval

---

## Usage

### Save a Quote

1. Find a memorable message
2. React with ☁️ emoji (`:cloud:`)
3. Bot confirms with ✅ reaction
4. Quote is saved to database

**Note:** Same message can be saved multiple times (reaction count increments)

---

### View Quotes

**Command:** `!quotes [@user]`

**Examples:**
```
!quotes                    # Your saved quotes
!quotes @username          # Someone's quotes
```

**Output:**
```
☁️ Quotes by username

1. 2024-01-15 (⭐ 3)
"This is the most quotable thing ever said in this server"

2. 2024-01-10 (⭐ 1)
"I can't believe you've done this"

3. 2024-01-05 (⭐ 5)
"To be or not to be, that is the question... of whether pineapple belongs on pizza"

Showing 10 of 15 quotes
```

---

## How It Works

### 1. Emoji Detection

**Supported formats:**
- Unicode: `☁️`
- Discord name: `:cloud:`
- Variations: `☁` (without variation selector)

**Code:** `main.py:225-230`

```python
is_cloud = (
    str(reaction.emoji) == "☁️" or
    (hasattr(reaction.emoji, 'name') and reaction.emoji.name == 'cloud') or
    str(reaction.emoji) == ":cloud:"
)
```

---

### 2. Context Capture

When a quote is saved, the bot captures:
- **The quoted message** (main content)
- **2 messages before** (leading context)
- **2 messages after** (trailing context)
- **Channel information**
- **Timestamp**
- **Who saved it**

**Context example:**
```
User1: What do you think about pineapple pizza?
User2: I think it's controversial
User3: "Pineapple pizza is a gift from the gods" ← QUOTED
User1: Wow hot take
User2: I disagree strongly
```

Context stored: All 5 messages

---

### 3. Duplicate Handling

**If quote already exists:**
- Don't create duplicate entry
- Increment `reaction_count` instead
- Update to latest reactor

**SQL:**
```sql
INSERT INTO quotes (...)
ON CONFLICT (message_id)
DO UPDATE SET reaction_count = quotes.reaction_count + 1
```

---

### 4. Storage

All quotes stored in PostgreSQL with:
- Full message text
- Surrounding context
- Reaction count
- Attribution (who said it, who saved it)
- Timestamps

---

## Configuration

### Context Window Size

**File:** `bot/features/claims.py:296-306`

**Adjust context capture:**
```python
# Current: 2 messages before, 2 after
all_messages = self.db.get_recent_messages(message.channel.id, limit=10)

# Find the quoted message
quote_index = next((i for i, m in enumerate(all_messages)
                   if m.get('message_id') == message.id), None)

# Capture context
start = max(0, quote_index - 2)  # Change 2 to adjust
end = min(len(all_messages), quote_index + 3)  # Change 3 to adjust
```

**More context = better understanding, but larger storage**

---

### Quotes Display Limit

**File:** `main.py:670`

**Number of quotes shown:**
```python
quotes = claims_tracker.get_user_quotes(target.id, limit=10)

# Show more quotes
quotes = claims_tracker.get_user_quotes(target.id, limit=25)
```

---

### Auto-Categorization (Future)

**File:** `sql/init.sql:91`

**Category field exists but not used yet:**
```sql
category VARCHAR(50),  -- 'funny', 'crazy', 'wise', 'wtf', 'savage'
```

**To enable:** Add LLM classification in `claims.py:~334`

---

## Database Schema

```sql
CREATE TABLE quotes (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,          -- Who said the quote
    username VARCHAR(255) NOT NULL,
    message_id BIGINT UNIQUE NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_name VARCHAR(255),
    quote_text TEXT NOT NULL,
    context TEXT,                      -- Surrounding messages
    timestamp TIMESTAMP NOT NULL,
    added_by_user_id BIGINT,          -- Who saved it
    added_by_username VARCHAR(255),
    category VARCHAR(50),              -- Future: 'funny', 'wise', etc.
    reaction_count INT DEFAULT 1,      -- How many ☁️ reactions
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quotes_user_id ON quotes(user_id);
CREATE INDEX idx_quotes_timestamp ON quotes(timestamp);
CREATE INDEX idx_quotes_category ON quotes(category);
```

---

## Example Queries

### Most Popular Quotes (by reactions)
```sql
SELECT username, quote_text, reaction_count
FROM quotes
ORDER BY reaction_count DESC
LIMIT 10;
```

### Recent Quotes
```sql
SELECT username, quote_text, timestamp
FROM quotes
ORDER BY timestamp DESC
LIMIT 10;
```

### User's Most Popular Quote
```sql
SELECT quote_text, reaction_count
FROM quotes
WHERE user_id = YOUR_USER_ID
ORDER BY reaction_count DESC
LIMIT 1;
```

---

## Troubleshooting

### Cloud Emoji Not Working

**Check:**
1. Emoji is exactly ☁️ (cloud)
2. Not ⛅ (cloud with sun) or 🌤️ (sun behind cloud)
3. Bot has "Read Message History" permission
4. Bot has "Add Reactions" permission

**Test:**
React with ☁️ to any message, bot should react with ✅

---

### Quotes Not Saving

**Possible causes:**
1. Database connection issue
2. Message already quoted (check reaction count)
3. Error in context retrieval

**Check logs:**
```bash
docker-compose logs bot | grep "Quote"
```

Should see: `☁️ Quote #X saved from username`

---

### Context Missing

**Cause:** Message is at the start/end of channel

**Fix:** Normal behavior - bot can only capture available messages

---

## Privacy

- **Opted-out users**: Quotes ARE saved (quotes feature exempt from opt-out)
- **Public visibility**: Anyone can view quotes with `!quotes`
- **No deletion**: Quotes persist even if original message deleted
- **Attribution**: Shows who said it and who saved it

**Rationale:** Quotes are meant to be public memories

---

## Quote of the Day Selection

### Daily Mode: Calendar Day Boundary

The Quote of the Day feature uses a **calendar day boundary** (midnight) to determine when a new quote should be selected, rather than a rolling 24-hour window. This means:
- A new quote is selected once per calendar day, at midnight
- All users in the server see the same quote throughout the day
- The quote does not change mid-day even if the feature was triggered 23 hours ago

### All-Time Selection: Freshness-Weighted Scoring

When selecting from all-time quotes, the system uses a **freshness-weighted scoring** formula to balance popularity with recency:

```
score = reaction_count + 30 / (days_old + 30)
```

**How it works:**
- `reaction_count` is the total number of cloud emoji reactions the quote received
- `30 / (days_old + 30)` is the freshness bonus, which gives newer quotes a slight boost
- A brand new quote (0 days old) gets a freshness bonus of +1.0
- A 30-day-old quote gets a freshness bonus of +0.5
- A 90-day-old quote gets a freshness bonus of +0.25
- Very old quotes still surface if they have high reaction counts

This prevents the same popular old quotes from dominating forever and gives newer well-received quotes a fair chance at being featured.

## Future Enhancements

1. **Categories** - Auto-classify as funny, wise, savage, etc.
2. **Quote search** - `!quotes @user keyword` or `!searchquotes keyword`
3. ~~**Quote of the Day** - Daily random quote feature~~ (Implemented with calendar day boundary and freshness-weighted scoring)
4. **Ranking** - Leaderboard of most quoted users
5. **Export** - Download all quotes as JSON/CSV
6. **Quote walls** - Special channel for displaying quotes
7. **Reactions on quotes** - Let users react to quote embeds

---

## Advanced: Quote Categorization

**Add LLM-based categorization:**

**File:** `bot/features/claims.py:~334` (after storing quote)

```python
async def store_quote(self, message, added_by_user):
    """Store a quote when someone reacts with cloud emoji"""
    try:
        # ... existing code ...

        # NEW: Categorize quote with LLM
        category = await self.categorize_quote(message.content)

        with self.db.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO quotes
                (user_id, username, message_id, channel_id, channel_name,
                 quote_text, context, timestamp, added_by_user_id,
                 added_by_username, category)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ...
            """, (..., category))

async def categorize_quote(self, quote_text):
    """Categorize quote as funny, wise, savage, etc."""
    prompt = f"""Categorize this quote into ONE category:
    - funny: Humorous, makes people laugh
    - wise: Insightful, thought-provoking
    - savage: Brutal, roast, comeback
    - wholesome: Heartwarming, kind
    - wtf: Bizarre, confusing, absurd

    Quote: "{quote_text}"

    Respond with ONLY the category name."""

    # Call LLM...
    return category  # Return string: "funny", "wise", etc.
```

**Cost:** ~$0.0001 per quote (negligible)

---

## API Reference

### Get User Quotes

**Function:** `claims_tracker.get_user_quotes(user_id, limit=None)`

**Returns:**
```python
[
    {
        'id': 1,
        'quote_text': 'Memorable quote here',
        'timestamp': datetime(2024, 1, 15),
        'reaction_count': 3,
        'channel_name': 'general',
        'message_id': 123456789,
        'context': 'User1: ...\nUser2: quote\nUser3: ...'
    },
    ...
]
```

---

## Support

**View all quotes:**
```sql
SELECT * FROM quotes ORDER BY created_at DESC LIMIT 10;
```

**Delete specific quote:**
```sql
DELETE FROM quotes WHERE id = QUOTE_ID;
```

**Reset reaction counts:**
```sql
UPDATE quotes SET reaction_count = 1;
```

**Find most quoted user:**
```sql
SELECT username, COUNT(*) as quote_count
FROM quotes
GROUP BY username
ORDER BY quote_count DESC;
```
