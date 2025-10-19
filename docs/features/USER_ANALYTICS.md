# 📊 User Analytics & Leaderboards

Behavior analysis, profanity scoring, and activity leaderboards.

## Overview

The User Analytics feature tracks user behavior patterns, message activity, and generates leaderboards. Uses LLM analysis for profanity scoring and tone detection.

### Key Features
- 📈 **User Stats** - Message counts, activity timeline
- 🔥 **Profanity Scoring** - 0-10 scale profanity detection
- 💬 **Tone Analysis** - Conversational style and patterns
- 🏆 **Leaderboards** - Messages, questions, profanity rankings
- 🔒 **Privacy Controls** - Role-based opt-out system

---

## Commands

### `!stats [@user]` or `/stats [@user]`
View detailed statistics for a user.

**Examples:**
```
!stats                    # Your own stats
!stats @username          # Someone else's stats
```

**Output:**
```
📊 Stats for username

Total Messages: 1,523
First Seen: 2024-01-01
Last Seen: 2024-10-19

Profanity Score: 7/10
Tone: Casual, humorous, occasionally sarcastic
Style: Direct communicator, uses slang frequently, engages in debates
```

---

### `!leaderboard <type> [days]`
Show top users by various metrics.

**Types:**
- `messages` - Most active users
- `questions` - Most inquisitive users
- `profanity` - Saltiest users

**Examples:**
```
!leaderboard messages               # Last 7 days (default)
!leaderboard messages 30            # Last 30 days
!leaderboard questions 7            # Most questions last week
!leaderboard profanity 30           # Saltiest users last month
```

**Output Example (messages):**
```
📊 Top Users by Messages
Last 30 days

🥇 Username1: 1,523 messages (28 active days)
🥈 Username2: 987 messages (25 active days)
🥉 Username3: 654 messages (20 active days)
4. Username4: 432 messages (18 active days)
5. Username5: 321 messages (15 active days)
...
```

---

### `!analyze [days]` (Admin Only)
Trigger behavior analysis for active users.

**Examples:**
```
!analyze           # Last 7 days (default)
!analyze 30        # Last 30 days
```

**Process:**
1. Finds top 10 most active users
2. Analyzes their messages with LLM
3. Generates profanity score (0-10)
4. Analyzes tone and conversation style
5. Stores results in database

**Output:**
```
🔍 Analyzing user behavior from the last 7 days...

Analyzing Username1...
Analyzing Username2...
...

✅ Analysis complete!

**Username1**: Profanity 7/10, 234 messages
**Username2**: Profanity 3/10, 189 messages
...
```

---

### Natural Language Leaderboard (via @mention)

**Examples:**
```
@WompBot who talks the most?
@WompBot who asks the most questions?
@WompBot who swears the most?
@WompBot who is the saltiest?
```

Bot detects leaderboard triggers and shows appropriate leaderboard.

---

## How It Works

### 1. Message Tracking

Every message is stored in the `messages` table:
- User ID, username
- Channel, timestamp
- Message content
- Opted-out flag

**Automatic profile creation:**
When a user sends their first message, a profile is created in `user_profiles` table.

---

### 2. Behavior Analysis (LLM)

**Triggered by:** `!analyze` command (admin only)

**Process:**
1. Get user's recent messages (last N days)
2. Send to LLM for analysis
3. Extract:
   - Profanity score (0-10)
   - Tone analysis (casual, formal, sarcastic, etc.)
   - Honesty patterns (fact-based, exaggeration, etc.)
   - Conversation style

**LLM Prompt:** `bot/llm.py:analyze_user_behavior()`

**Example analysis:**
```json
{
    "profanity_score": 7,
    "message_count": 234,
    "tone_analysis": "Casual, humorous, occasionally sarcastic",
    "honesty_patterns": "Generally straightforward, occasional hyperbole",
    "conversation_style": "Direct, engages in debates, uses slang"
}
```

---

### 3. Question Detection (LLM)

**For questions leaderboard:**

**Process:**
1. Get all messages from last N days
2. Batch messages by user
3. Send to LLM for classification
4. LLM identifies which messages are questions
5. Count questions per user

**Batch size:** Processes efficiently in batches

---

### 4. Privacy System

**Opt-out role:** `NoDataCollection` (configurable)

**What opt-out does:**
- Messages still logged (for context) but flagged
- **Excluded from:**
  - Behavior analysis
  - Leaderboards
  - Conversation context for bot
  - All statistics

**Check opt-out:**
```python
opted_out = user_has_opted_out(message.author)
db.store_message(message, opted_out=opted_out)
```

---

## Configuration

### Opt-Out Role Name

**File:** `.env`

```bash
OPT_OUT_ROLE_NAME=NoDataCollection
```

**Change to:**
```bash
OPT_OUT_ROLE_NAME=PrivacyMode
# or
OPT_OUT_ROLE_NAME=NoTracking
```

---

### Analysis Batch Size

**File:** `bot/main.py:524`

**How many users to analyze:**
```python
for user in active_users[:10]:  # Limit to 10 users
    ...

# Analyze more users
for user in active_users[:20]:
```

**Warning:** More users = higher LLM costs

---

### Minimum Messages for Analysis

**File:** `bot/main.py:527`

**Skip users with too few messages:**
```python
if len(messages) < 5:  # Skip users with <5 messages
    continue

# More strict
if len(messages) < 20:
```

---

### Profanity Scoring Scale

**File:** `bot/llm.py` (analyze_user_behavior prompt)

**Current scale:** 0-10
- 0 = No profanity, clean language
- 5 = Moderate, occasional swearing
- 10 = Extremely profane, every other word

**To adjust:** Modify LLM prompt to use different scale (e.g., 0-100)

---

## Database Schema

### user_profiles
```sql
CREATE TABLE user_profiles (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    total_messages INT DEFAULT 0,
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL,
    opted_out BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### user_behavior
```sql
CREATE TABLE user_behavior (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    analysis_period_start TIMESTAMP NOT NULL,
    analysis_period_end TIMESTAMP NOT NULL,
    profanity_score INT DEFAULT 0,
    message_count INT DEFAULT 0,
    tone_analysis TEXT,
    honesty_patterns TEXT,
    conversation_style TEXT,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id) ON DELETE CASCADE
);
```

### messages
```sql
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT UNIQUE NOT NULL,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_name VARCHAR(255),
    content TEXT,
    timestamp TIMESTAMP NOT NULL,
    opted_out BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Cost Analysis

### Behavior Analysis
**Per user analyzed:**
- Tokens: ~2000 (varies by message count)
- Cost: ~$0.002 per user
- Time: ~3-5 seconds per user

**For 10 users:**
- Cost: ~$0.02
- Time: ~30-50 seconds

### Question Classification
**Per batch (all users):**
- Tokens: ~500 per user
- Cost: ~$0.015 for entire server
- Time: ~10-20 seconds

### Monthly Estimate
**Running `!analyze` weekly:**
- 4 analyses/month × 10 users × $0.002 = **$0.08/month**

**Questions leaderboard (on-demand):**
- ~$0.015 per request
- Used 10 times/month = **$0.15/month**

**Total: ~$0.25/month for analytics**

---

## Leaderboard Types

### 1. Messages Leaderboard
**Metric:** Total message count
**Query:** Pure SQL (fast, free)
**Shows:**
- Username
- Message count
- Active days count

---

### 2. Questions Leaderboard
**Metric:** Questions asked (% of messages)
**Query:** LLM classification (slower, costs money)
**Shows:**
- Username
- Question count
- Percentage of messages that are questions
- Total messages

**Use sparingly:** Each request costs ~$0.015

---

### 3. Profanity Leaderboard
**Metric:** Profanity score (0-10)
**Requires:** `!analyze` must be run first
**Shows:**
- Username
- Profanity score
- Based on most recent analysis

---

## Troubleshooting

### "No behavior analysis available yet"

**Cause:** `!analyze` hasn't been run

**Fix:**
```
!analyze 30
```

Wait for completion, then try `!stats` or `!leaderboard profanity` again

---

### Opted-Out User Still Appears

**Check:**
1. User has exact role name: `NoDataCollection`
2. Role name matches `.env` setting
3. Restart bot after role changes

**Verify:**
```sql
SELECT opted_out FROM messages WHERE user_id = USER_ID LIMIT 1;
```

Should return `true` for opted-out user's messages

---

### Analysis Taking Too Long

**Causes:**
- Too many users (>10)
- Messages per user very high (>500)
- LLM API slow

**Solutions:**
1. Reduce batch size (see Configuration)
2. Reduce days analyzed (`!analyze 7` instead of `!analyze 30`)
3. Increase timeout in `llm.py`

---

### Inaccurate Profanity Scores

**Causes:**
- LLM subjectivity
- Context-dependent language
- Cultural differences

**Solutions:**
1. Run analysis on larger dataset (more days)
2. Adjust LLM temperature in `llm.py`
3. Modify profanity prompt to be more/less strict

---

## Privacy & Ethics

### What is Tracked
✅ All messages (content, timestamp, author)
✅ User activity (first seen, last seen, message count)
✅ Behavior patterns (if analyzed)
✅ Claims, quotes, fact-checks

### What is NOT Tracked for Opted-Out Users
❌ Not included in leaderboards
❌ Not analyzed for behavior
❌ Not used as conversation context
❌ Messages flagged but not analyzed

### Data Retention
- **Messages**: Permanent (for conversation context)
- **Behavior analysis**: Replaced on new analysis
- **User profiles**: Permanent
- **Opted-out status**: Respected in real-time

### Transparency
- Users can see their own stats with `!stats`
- Leaderboards are public
- Profanity scores are visible
- Opt-out role is clearly named

---

## Advanced: Custom Analysis

### Add Custom Metrics

**File:** `bot/llm.py:analyze_user_behavior()`

**Modify LLM prompt to extract more:**
```python
prompt = f"""Analyze this user's behavior...

Provide analysis in JSON format:
{{
    "profanity_score": 0-10,
    "message_count": {len(messages)},
    "tone_analysis": "...",
    "honesty_patterns": "...",
    "conversation_style": "...",

    // NEW METRICS:
    "emoji_usage": "heavy/moderate/minimal",
    "avg_message_length": "short/medium/long",
    "formality": 0-10,
    "positivity": 0-10
}}
"""
```

**Update database schema:**
```sql
ALTER TABLE user_behavior
ADD COLUMN emoji_usage VARCHAR(20),
ADD COLUMN formality INT,
ADD COLUMN positivity INT;
```

---

## Example Queries

### Most Active User All-Time
```sql
SELECT username, total_messages
FROM user_profiles
ORDER BY total_messages DESC
LIMIT 1;
```

### User Activity Timeline
```sql
SELECT DATE(timestamp) as date, COUNT(*) as messages
FROM messages
WHERE user_id = YOUR_USER_ID
GROUP BY DATE(timestamp)
ORDER BY date DESC
LIMIT 30;
```

### Opted-Out Users Count
```sql
SELECT COUNT(DISTINCT user_id)
FROM messages
WHERE opted_out = TRUE;
```

---

## Future Enhancements

1. **Activity graphs** - Visual charts of activity over time
2. **Peak hours** - When each user is most active (already in Chat Stats!)
3. **Streak tracking** - Consecutive days active
4. **Badges** - Achievement system
5. **Comparative stats** - "You're in top 10% of message senders"
6. **Export data** - GDPR-compliant data export for users

---

## Support

**View user profile:**
```sql
SELECT * FROM user_profiles WHERE user_id = YOUR_USER_ID;
```

**View latest behavior analysis:**
```sql
SELECT * FROM user_behavior
WHERE user_id = YOUR_USER_ID
ORDER BY analyzed_at DESC
LIMIT 1;
```

**Reset all analytics:**
```sql
TRUNCATE user_behavior;
```

**Opt-out specific user manually:**
```sql
UPDATE messages SET opted_out = TRUE WHERE user_id = USER_ID;
UPDATE user_profiles SET opted_out = TRUE WHERE user_id = USER_ID;
```
