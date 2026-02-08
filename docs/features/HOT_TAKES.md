# 🔥 Hot Takes Leaderboard

The Hot Takes Leaderboard tracks controversial claims and community reactions, creating competitive leaderboards while keeping costs under $1/month through a smart three-stage hybrid system.

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Three-Stage Detection System](#three-stage-detection-system)
- [Leaderboard Types](#leaderboard-types)
- [Commands](#commands)
- [Cost Analysis](#cost-analysis)
- [Configuration](#configuration)
- [Database Schema](#database-schema)
- [Troubleshooting](#troubleshooting)

## Overview

**What makes a "hot take"?**

A hot take is a claim that is:
1. **Controversial** - Uses provocative language or makes bold comparisons
2. **Engaging** - Gets community reactions (likes, replies, diverse emoji responses)
3. **Trackable** - Can be vindicated or proven wrong over time

Unlike regular claims tracking, hot takes focus on **controversial opinions** and track how they **age over time**.

## How It Works

### Automatic Detection

When a user sends a message:
1. **Claims detector** checks if it's trackable (see [Claims Tracking](CLAIMS_TRACKING.md))
2. **Hot takes detector** checks if it's controversial (pattern matching)
3. If both pass → Creates hot take entry linked to the claim
4. Community reactions are tracked automatically
5. High-engagement hot takes get LLM controversy scoring (5+ reactions or 3+ replies)

### Vindication Tracking

Admins can mark hot takes as:
- **Won** (✅) - Proven right, aged like fine wine (score: 10.0)
- **Lost** (❌) - Proven wrong, aged like milk (score: 0.0)
- **Mixed** (🔀) - Partially correct (score: 5.0)
- **Pending** (⏳) - Still waiting to be proven

Users build a **track record** based on vindication rate.

## Three-Stage Detection System

### Stage 1: Controversy Pattern Detection (FREE)

Fast regex/keyword matching for controversial language:

**Explicit Indicators:**
- "hot take", "unpopular opinion", "controversial", "fight me"
- "change my mind", "prove me wrong"
- "everyone is wrong", "y'all are wrong"

**Strong Judgments:**
- "overrated", "underrated", "overhyped"
- "trash", "garbage", "peak", "goat", "mid"
- "cope", "seethe", "based", "cringe"

**Comparisons:**
- "X is better than Y"
- "X > Y" or "X < Y" with context
- "objectively better/worse"

**Sensitive Topics:**
- Pineapple on pizza debates
- GIF vs JIF pronunciation
- Tabs vs spaces
- Vim vs Emacs vs VSCode
- iPhone vs Android
- Star Wars vs Star Trek

**Threshold:** Confidence ≥ 0.3 to qualify as controversial

**Cost:** $0 (pure regex)

### Stage 2: Community Reaction Tracking (FREE)

Tracks Discord engagement metrics:
- **Total reactions** - How many emoji reactions
- **Reaction diversity** - Mix of different emojis (👍 vs 👎 = high diversity)
- **Reply count** - Responses within 1 hour
- **Community score** - Formula: `min((reactions × diversity) × 2, 10)`

**Threshold for Stage 3:** 5+ reactions OR 3+ replies

**Cost:** $0 (Discord API)

### Stage 3: LLM Controversy Scoring (CHEAP)

Only for high-engagement claims (top ~5-10%):

LLM rates controversy on 0-10 scale:
- **0-2:** Bland, universally accepted
- **3-4:** Mildly spicy, some disagreement
- **5-6:** Polarizing, strong opinions on both sides
- **7-8:** Very controversial, heated debate
- **9-10:** Nuclear-level hot take, extremely divisive

**Cost:** ~$0.001-0.002 per analysis, runs on 5-10% of claims only

## Leaderboard Types

### 1. Most Controversial 🔥
**Command:** `/hottakes controversial [days]`

Ranks by LLM-scored controversy (0-10 scale).

**Example:**
```
#1 - Wompie__
> Pineapple on pizza is objectively superior to any other topping combination.
🔥 Controversy: 8.5/10
```

### 2. Best Vindicated ✅
**Command:** `/hottakes vindicated [days]`

Shows hot takes that **aged well** (marked as "won").

Tracks users with the best **track record** of being right.

**Example:**
```
#1 - TechGuru
> Bitcoin will hit $100k by end of 2024
✅ Aged like fine wine: 10.0/10
```

### 3. Worst Takes ❌
**Command:** `/hottakes worst [days]`

Shows hot takes that **aged poorly** (marked as "lost").

Hall of shame for terrible predictions.

**Example:**
```
#1 - BadTakes
> AI will never be able to write code
❌ Aged like milk: 0.0/10
```

### 4. Community Favorites ⭐
**Command:** `/hottakes community [days]`

Ranks by community engagement (reactions + replies).

Doesn't require LLM scoring - pure community metrics.

**Example:**
```
#1 - PopularGuy
> Tabs are objectively better than spaces. Fight me.
⭐ Community: 9.2/10 | 👍 47 reactions
```

### 5. Hot Take Kings 👑
**Command:** `/hottakes combined [days]`

Combined score: `controversy_score × age_score`

Rewards controversial takes that were proven right.

**Example:**
```
#1 - Prophet
> Dune Part 2 will be the highest-rated sci-fi movie of the decade
👑 Combined: 90.0 | 🔥 9.0 | ✅ 10.0
```

## Commands

### User Commands

#### `/hottakes [leaderboard_type] [days]`
View hot takes leaderboards.

**Parameters:**
- `leaderboard_type` (optional): Choose from dropdown
  - Most Controversial
  - Best Vindicated
  - Worst Takes
  - Community Favorite
  - Hot Take Kings
- `days` (optional, default: 30): Lookback period

**Example:**
```
/hottakes controversial 7
```
Shows most controversial hot takes from last 7 days.

#### `/mystats_hottakes`
View your personal hot takes statistics.

**Shows:**
- Total hot takes made
- Spiciest take (highest controversy score)
- Average controversy rating
- Vindication count (✅ won, ❌ lost)
- Average community score
- Win rate percentage

**Example Output:**
```
🔥 YourName's Hot Takes Stats

Total Hot Takes: 12
Spiciest Take: 8.5/10
Avg Controversy: 6.2/10
Vindicated: ✅ 7
Proven Wrong: ❌ 2
Avg Community Score: 7.1/10
Win Rate: 77.8%
```

### Admin Commands

#### `/vindicate <hot_take_id> <status> [notes]`
Mark a hot take as vindicated or proven wrong (admin only).

**Parameters:**
- `hot_take_id` (required): ID of the hot take (shown in logs)
- `status` (required): Choose from dropdown
  - Won (Proven Right)
  - Lost (Proven Wrong)
  - Mixed (Partially Right)
  - Pending
- `notes` (optional): Explanation or evidence

**Example:**
```
/vindicate 42 won This prediction came true on 3/15/2024
```

**How to find hot take IDs:**
Check bot logs when hot takes are detected:
```
🔥 Hot take detected! ID: 42, Confidence: 0.65
```

Or query database:
```sql
SELECT ht.id, c.claim_text, c.username
FROM hot_takes ht
JOIN claims c ON c.id = ht.claim_id
ORDER BY ht.created_at DESC
LIMIT 20;
```

## Cost Analysis

### Before Optimization (Theoretical)
**If every message was LLM-scored for controversy:**
- 1,000 msgs/day × $0.002 = $2/day
- **Monthly cost:** ~$60/month ❌

### With Three-Stage System (Actual)
**Stage 1:** Free keyword detection (filters 80-90%)
**Stage 2:** Free community tracking (filters another 80-90% of remainder)
**Stage 3:** LLM scoring only top ~5-10% with high engagement

**Breakdown for 1,000 msgs/day server:**
- Stage 1 matches: ~20% (200 msgs) - controversial patterns detected
- Stage 2 threshold: ~10% of those (20 msgs) - high engagement
- Stage 3 LLM calls: 20 msgs/day × $0.002 = $0.04/day

**Monthly cost:** ~$0.50-1.00/month ✅

**Cost reduction:** 98-99% savings vs naive approach

### Scalability

| Server Size | Msgs/Day | Stage 3 LLM Calls | Monthly Cost |
|-------------|----------|-------------------|--------------|
| Small | 100 | ~2/day | $0.10 |
| Medium | 1,000 | ~20/day | $0.50-1.00 |
| Large | 5,000 | ~100/day | $3-6 |
| Huge | 10,000 | ~200/day | $10-15 |

**Note:** Even for massive servers, costs remain low because:
1. Most messages aren't claims (pre-filtered by claims detector)
2. Most claims aren't controversial (Stage 1 filter)
3. Most controversial claims don't get engagement (Stage 2 filter)

## Configuration

### Controversy Patterns

Edit patterns in `bot/features/hot_takes.py`:

```python
class HotTakesTracker:
    def __init__(self, db, llm):
        self.controversy_patterns = [
            r'\b(hot take|unpopular opinion)\b',
            # Add your custom patterns here
        ]

        self.sensitive_topics = [
            r'\b(pineapple.*pizza|pizza.*pineapple)\b',
            # Add community-specific triggers
        ]
```

**Tips for custom patterns:**
- Use `\b` for word boundaries to avoid partial matches
- Test patterns with sample messages before deploying
- Add lowercase patterns (matching is case-insensitive)

### Stage 1 Threshold

Adjust confidence threshold for controversy detection:

```python
def detect_controversy_patterns(self, message_content: str) -> dict:
    # ...
    is_controversial = confidence >= 0.3  # Lower = more permissive
```

**Default:** 0.3 (balanced)
**More strict:** 0.5 (fewer false positives, might miss some)
**More permissive:** 0.2 (catches more, but more false positives)

### Stage 2 Threshold

Adjust engagement threshold for LLM scoring:

```python
async def check_and_score_high_engagement(self, hot_take_id: int, message):
    # Check threshold
    if (total_reactions >= 5 or reply_count >= 3) and current_score == 0.0:
        # Send to LLM
```

**Default:** 5+ reactions OR 3+ replies
**More strict:** 10+ reactions OR 5+ replies (lower costs)
**More permissive:** 3+ reactions OR 2+ replies (higher costs, more coverage)

### LLM Model

Uses same model as claims tracking (configured in `.env`):
```env
MODEL_NAME=deepseek/deepseek-chat  # Recommended
```

**Alternative cheaper models for Stage 3:**
- `mistralai/mixtral-8x7b-instruct` - Faster, slightly less accurate
- `meta-llama/llama-3-8b-instruct` - Cheapest option

Change in `hot_takes.py` if you want a separate model:
```python
payload = {
    "model": "mistralai/mixtral-8x7b-instruct",  # Override here
    # ...
}
```

## Database Schema

### `hot_takes` Table

```sql
CREATE TABLE hot_takes (
    id SERIAL PRIMARY KEY,
    claim_id INT UNIQUE REFERENCES claims(id) ON DELETE CASCADE,
    controversy_score FLOAT DEFAULT 0.0,        -- LLM-scored 0-10
    community_score FLOAT DEFAULT 0.0,          -- Reaction-based 0-10
    total_reactions INT DEFAULT 0,
    reaction_diversity FLOAT DEFAULT 0.0,       -- 0-1 (mix of reactions)
    reply_count INT DEFAULT 0,
    vindication_status VARCHAR(20) DEFAULT 'pending',
    vindication_date TIMESTAMP,
    vindication_notes TEXT,
    age_score FLOAT,                            -- 10.0 (won), 5.0 (mixed), 0.0 (lost)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
```sql
CREATE INDEX idx_hot_takes_claim_id ON hot_takes(claim_id);
CREATE INDEX idx_hot_takes_controversy ON hot_takes(controversy_score);
CREATE INDEX idx_hot_takes_community ON hot_takes(community_score);
CREATE INDEX idx_hot_takes_vindication ON hot_takes(vindication_status);
CREATE INDEX idx_hot_takes_created_at ON hot_takes(created_at);
```

### Relationships

```
messages (Discord) → claims (tracked) → hot_takes (controversial)
```

**One-to-one:** Each claim can have at most one hot take entry.

**Cascade deletion:** If a claim is deleted, its hot take is also deleted.

## Troubleshooting

### Hot Takes Not Being Detected

**Check logs for claim detection:**
```
✅ Trackable claim detected: Bitcoin will hit $100k
```

If claims aren't being detected, hot takes won't work either. See [Claims Tracking](CLAIMS_TRACKING.md).

**Check controversy pattern matching:**
```
🔥 Hot take detected! ID: 42, Confidence: 0.65
```

If not appearing, your message might not match controversy patterns.

**Test patterns manually:**
```python
# In Python console
from features.hot_takes import HotTakesTracker
tracker = HotTakesTracker(None, None)
result = tracker.detect_controversy_patterns("Your message here")
print(result)
```

### LLM Not Scoring Hot Takes

**Check if meeting engagement threshold:**
```
🎯 Hot take #42 meets threshold - sending to LLM for scoring
```

**Default threshold:** 5+ reactions OR 3+ replies

**Check LLM logs:**
```
🔥 LLM controversy score: 7.5/10 - Uses inflammatory comparison and absolutist language
```

**Common issues:**
- Hot take just created (reactions come later)
- API key issues (check `.env` file)
- Not enough engagement to trigger Stage 3

### Leaderboards Empty

**Check database:**
```sql
-- Count hot takes
SELECT COUNT(*) FROM hot_takes;

-- Check controversy scores
SELECT id, controversy_score, community_score, vindication_status
FROM hot_takes
WHERE created_at > NOW() - INTERVAL '30 days'
ORDER BY controversy_score DESC;
```

**Common reasons:**
- No hot takes detected yet (need controversial claims)
- Hot takes too old (check `days` parameter)
- Filtering by vindication status (only shows won/lost, not pending)

### Reaction Tracking Not Updating

**Verify intents enabled:**

In `main.py`:
```python
intents.reactions = True  # Must be enabled!
```

In Discord Developer Portal:
- Go to your application
- Bot section → Privileged Gateway Intents
- Enable "Message Content Intent"
- Enable "Guild Message Reactions"

**Check event handlers:**
```python
@bot.event
async def on_reaction_add(reaction, user):
    # Should see this in logs
    print(f"Reaction added: {reaction.emoji}")
```

### Database Migration Issues

**Create table manually if needed:**
```bash
docker-compose exec -T postgres psql -U botuser -d discord_bot << 'EOF'
CREATE TABLE IF NOT EXISTS hot_takes (
    id SERIAL PRIMARY KEY,
    claim_id INT UNIQUE REFERENCES claims(id) ON DELETE CASCADE,
    controversy_score FLOAT DEFAULT 0.0,
    community_score FLOAT DEFAULT 0.0,
    total_reactions INT DEFAULT 0,
    reaction_diversity FLOAT DEFAULT 0.0,
    reply_count INT DEFAULT 0,
    vindication_status VARCHAR(20) DEFAULT 'pending',
    vindication_date TIMESTAMP,
    vindication_notes TEXT,
    age_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_hot_takes_claim_id ON hot_takes(claim_id);
CREATE INDEX idx_hot_takes_controversy ON hot_takes(controversy_score);
CREATE INDEX idx_hot_takes_community ON hot_takes(community_score);
CREATE INDEX idx_hot_takes_vindication ON hot_takes(vindication_status);
CREATE INDEX idx_hot_takes_created_at ON hot_takes(created_at);
EOF
```

## Best Practices

### For Users

1. **Be specific in hot takes** - Vague opinions won't trigger detection
2. **Use bold language** - "X is better than Y" triggers detection
3. **Engage with others' hot takes** - React and reply to boost community scores
4. **Track your win rate** - Use `/mystats_hottakes` to see your record

### For Admins

1. **Vindicate regularly** - Mark outcomes when evidence appears
2. **Add evidence in notes** - Help users understand why it won/lost
3. **Review logs** - Check for false positives/negatives
4. **Tune thresholds** - Adjust if too many/too few hot takes
5. **Monitor costs** - Check Stage 3 LLM usage if scaling

### For Developers

1. **Add community-specific patterns** - Tailor to your server's debates
2. **Test before deploying** - Use test cases to validate patterns
3. **Monitor performance** - Track detection rates and LLM usage
4. **Backup database** - Hot takes become valuable community history
5. **Document vindications** - Keep notes on why takes won/lost

## Future Enhancements

Potential improvements (not yet implemented):

- **Auto-vindication for predictions** - Check dates and auto-resolve
- **User challenges** - Users can dispute vindication status
- **Monthly recap** - Automated summary of spiciest takes
- **Hot take badges** - Roles for top performers
- **Cross-server leaderboards** - Compare controversy across servers
- **Trending hot takes** - Real-time feed of spicy discussions
- **Hot take notifications** - Alert users when their take is vindicated

---

**Related Documentation:**
- [Claims Tracking](CLAIMS_TRACKING.md) - Understanding the base claims system
- [Cost Optimization](../COST_OPTIMIZATION.md) - Two-stage hybrid detection
- [Configuration Guide](../CONFIGURATION.md) - Environment variables and settings
