# 📋 Claims & Accountability Feature

Track predictions, facts, and bold statements automatically with LLM-powered claim detection.

## Overview

The Claims Tracking feature automatically detects and stores trackable claims from user messages, preserving them even if edited or deleted. It also detects contradictions when users make conflicting statements.

### Key Features
- 🔍 **Auto Detection** - LLM analyzes messages for trackable claims
- ✏️ **Edit Tracking** - Preserves original text when claims are edited
- 🗑️ **Deletion Tracking** - Saves deleted messages with claims
- 🚨 **Contradiction Detection** - Identifies conflicting statements (shown only to Wompie__)
- 📋 **Receipts Command** - View user's claim history

### Technologies
- OpenRouter LLM (configurable via MODEL_NAME) - Claim detection & classification
- PostgreSQL - Claim storage with edit history (JSONB)
- JSON parsing - Robust response handling

---

## Commands

### `/receipts [@user] [keyword]`
View tracked claims for a user.

**Examples:**
```
/receipts                           # Your own claims
/receipts @username                 # Someone else's claims
/receipts @username bitcoin         # Filter by keyword
```

**Output:**
- List of claims with timestamps
- Claim type (prediction, fact, opinion, guarantee)
- Verification status (✅ ✓ ❌ 🔀 📅)
- Edit markers (✏️) if claim was edited

---

### `/verify_claim <id> <status> [notes]` (Admin Only)
Manually verify or fact-check a claim.

**Status options:**
- `true` - Claim verified as accurate
- `false` - Claim proven false
- `mixed` - Partially true
- `outdated` - Was true, no longer valid

**Examples:**
```
/verify_claim 42 true Bitcoin did reach $100k
/verify_claim 15 false No evidence found
/verify_claim 23 mixed Partially accurate with caveats
```

---

## How It Works

### 1. Automatic Claim Detection

**Trigger:** Every message >20 characters (except bot conversations)

**LLM Prompt:**
```
Analyze this message and determine if it contains a trackable claim.

A trackable claim is:
- A factual assertion that can be verified (e.g., "Trump always spits when talking")
- A strong prediction (e.g., "Bitcoin will hit 100k by next year")
- A guarantee or absolute statement (e.g., "I will never eat pineapple pizza")
- A bold opinion stated as fact (e.g., "EVs are always worse for the environment")

NOT trackable:
- Casual conversation (e.g., "I don't always agree with you")
- Questions
- Obvious jokes or sarcasm
- Vague statements without specifics
- Simple preferences (e.g., "I like pizza")
```

**Response Format:**
```json
{
    "is_trackable": true,
    "claim_text": "Bitcoin will hit $100k by the end of 2025",
    "claim_type": "prediction",
    "confidence_level": "certain",
    "reasoning": "Specific prediction with timeframe"
}
```

---

### 2. Edit Tracking

**When a message with a claim is edited:**

1. Original text is preserved in `original_text` column
2. Edit history stored as JSONB array:
   ```json
   [
     {"text": "Bitcoin will hit $100k", "timestamp": "2024-01-15T10:30:00"},
     {"text": "Bitcoin will hit $150k", "timestamp": "2024-01-15T12:00:00"}
   ]
   ```
3. Claim marked with `is_edited = TRUE`
4. `claim_text` updated to latest version

**Users can't hide their original claims by editing!**

---

### 3. Deletion Tracking

**When a message with a claim is deleted:**

1. Claim remains in database
2. Marked with `is_deleted = TRUE`
3. Text preserved in `deleted_text` column
4. Deletion timestamp recorded

**Deleted claims still show in `/receipts` unless `include_deleted=False`**

---

### 4. Contradiction Detection

**Process:**
1. New claim detected
2. Bot fetches user's last 10 claims
3. LLM compares new claim to past claims
4. If contradiction found, alert sent

**Example:**
```
🚨 Contradiction Detected

New Claim: "I love pineapple pizza"
Contradicts Previous Claim (2024-01-10): "I will never eat pineapple pizza"
Explanation: Direct contradiction of previous statement
```

**Privacy:** Only visible to user "Wompie__" (configured in `main.py:31`)

---

## Configuration

### Claim Detection Sensitivity

**File:** `bot/features/claims.py:60`

**Adjust LLM temperature:**
```python
payload = {
    "model": self.llm.model,
    "messages": [...],
    "max_tokens": 300,
    "temperature": 0.2  # Lower = stricter, Higher = more lenient
}
```

**Temperature effects:**
- `0.1` - Very strict, only obvious claims
- `0.2` - Default, balanced
- `0.3` - More lenient, catches subtle claims

---

### Minimum Message Length

**File:** `bot/main.py:164`

**Change minimum length for analysis:**
```python
# Current: 20 characters
if not opted_out and len(message.content) > 20 and not is_addressing_bot:
    claim_data = await claims_tracker.analyze_message_for_claim(message)

# More strict (30 characters)
if ... and len(message.content) > 30 ...

# Less strict (10 characters)
if ... and len(message.content) > 10 ...
```

---

### Contradiction Check Scope

**File:** `bot/features/claims.py:221`

**How many past claims to check:**
```python
# Current: Last 10 claims
for i, c in enumerate(past_claims[:10]):

# Check more history (slower)
for i, c in enumerate(past_claims[:20]):

# Check less (faster)
for i, c in enumerate(past_claims[:5]):
```

---

### Contradiction Visibility

**File:** `bot/main.py:31`

**Who can see contradiction alerts:**
```python
WOMPIE_USERNAME = "Wompie__"  # Change to your username

# Or make public to everyone:
# Remove the check on line 174:
# if str(message.author) == WOMPIE_USERNAME:
```

---

## Database Schema

```sql
CREATE TABLE claims (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    message_id BIGINT UNIQUE NOT NULL,
    channel_id BIGINT NOT NULL,
    channel_name VARCHAR(255),
    claim_text TEXT NOT NULL,
    claim_type VARCHAR(50),          -- 'prediction', 'fact', 'opinion', 'guarantee'
    confidence_level VARCHAR(20),     -- 'certain', 'probable', 'uncertain'
    context TEXT,                     -- Surrounding conversation
    timestamp TIMESTAMP NOT NULL,

    -- Edit tracking
    is_edited BOOLEAN DEFAULT FALSE,
    original_text TEXT,
    edit_history JSONB,               -- Array of {text, timestamp}

    -- Deletion tracking
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    deleted_text TEXT,

    -- Verification
    verification_status VARCHAR(20) DEFAULT 'unverified',
    verification_date TIMESTAMP,
    verification_sources TEXT,
    verification_notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Cost Analysis

### Per Message Analyzed
- **Tokens**: ~300 (prompt + response)
- **Cost**: ~$0.0003 per message (varies by model)
- **Time**: ~1-2 seconds

### Monthly Estimate
For a server with 1000 messages/day:
- Messages analyzed: ~30,000/month
- **Cost**: ~$9-12/month
- Successful claims detected: ~100-500/month (3-15%)

### Cost Optimization
- Already skips messages <20 chars
- Skips bot conversations
- Skips opted-out users
- Only analyzes once per message

---

## Troubleshooting

### Claims Not Being Detected

**Check:**
1. Message length >20 characters
2. User hasn't opted out
3. Not a direct bot conversation (doesn't track "@WompBot" messages)

**Test:**
Post a very obvious claim like: "Bitcoin will definitely hit $1 million by 2025"

---

### False Positives (Non-claims tracked)

**Solution:** Increase temperature strictness
```python
"temperature": 0.1  # Stricter
```

Or add explicit filtering in `claims.py:84-88`

---

### Contradictions Not Showing

**Check:**
1. Your username matches `WOMPIE_USERNAME` in `main.py:31`
2. User has at least 2 claims in database
3. Claims actually contradict (LLM must detect it)

---

## Privacy

- Opted-out users: Claims NOT tracked
- Edit history: Permanently stored
- Deleted claims: Preserved in database
- Contradictions: Only visible to configured user

---

## Future Enhancements

1. **Auto-verification** - Web search to verify claims automatically
2. **Vindication rate** - Track % of predictions that came true
3. **Claim expiry** - Mark time-bound predictions as outdated automatically
4. **Public leaderboard** - Most accurate predictors
5. **Claim categories** - Tag claims by topic (crypto, politics, etc.)

---

## Support

**Check claim detection logs:**
```bash
docker-compose logs bot | grep "Trackable claim"
```

**View claims in database:**
```sql
SELECT id, username, claim_text, claim_type, is_edited
FROM claims
WHERE user_id = YOUR_USER_ID
ORDER BY timestamp DESC
LIMIT 10;
```
