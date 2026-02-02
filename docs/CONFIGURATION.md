# ⚙️ Configuration Guide

Complete guide to configuring WompBot.

## Environment Variables (.env)

All bot configuration is done through the `.env` file in the project root.

### Creating .env File

**Location:** `/discord-bot/.env`

**Template:**
```bash
# Discord Bot Token
DISCORD_TOKEN=your_discord_bot_token_here

# OpenRouter API (for LLM)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Tavily API (for web search)
TAVILY_API_KEY=your_tavily_api_key_here

# Model Selection
MODEL_NAME=deepseek/deepseek-chat              # Cost-effective model for general chat
FACT_CHECK_MODEL=deepseek/deepseek-chat        # Model for fact-checking

# Conversation Context
CONTEXT_WINDOW_MESSAGES=6

# Rate Limiting (prevents abuse)
MAX_TOKENS_PER_REQUEST=1000  # Maximum tokens per single request
HOURLY_TOKEN_LIMIT=10000     # Maximum tokens per user per hour

# Privacy
OPT_OUT_ROLE_NAME=NoDataCollection

# Database (auto-configured by Docker)
POSTGRES_PASSWORD=secure_random_password_here
```

---

## Discord Configuration

### Bot Token

**Get token:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create new application or select existing
3. Go to "Bot" section
4. Click "Reset Token" and copy
5. Add to `.env`:
   ```bash
   DISCORD_TOKEN=MTIwNjA3OTkzNjMzMTI1OTk1NA.GvXxxx.xxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

### Bot Permissions

**Required permissions:**
- Read Messages/View Channels
- Send Messages
- Send Messages in Threads
- Embed Links
- Attach Files
- Read Message History
- Add Reactions
- Use Slash Commands

**Permission integer:** `414464723008`

**Invite link format:**
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=414464723008&scope=bot%20applications.commands
```

---

## LLM Configuration

### OpenRouter API Key

**Get API key:**
1. Sign up at [OpenRouter.ai](https://openrouter.ai/)
2. Go to [Keys](https://openrouter.ai/keys)
3. Create new key
4. Add to `.env`:
   ```bash
   OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

**Costs:**
- DeepSeek: Very cost-effective per 1M tokens
- Pay only for what you use
- Expected: ~$5-15/month for active Discord server

---

### Model Selection

**Model Configuration:**

WompBot uses configurable models via OpenRouter:

```bash
# General Chat - Recommended (cost-effective, high quality)
MODEL_NAME=deepseek/deepseek-chat

# Fact-Checking
FACT_CHECK_MODEL=deepseek/deepseek-chat
```

**Alternative Models:**

```bash
# High quality alternatives
MODEL_NAME=anthropic/claude-3.5-sonnet  # More expensive, very accurate
MODEL_NAME=google/gemini-2.0-flash-exp  # Fast alternative

# Budget options
MODEL_NAME=google/gemini-2.5-flash      # Very cheap
```

**Browse models:** [OpenRouter Models](https://openrouter.ai/models)

**Filters:**
- General chat: Look for "Uncensored" or "Dolphin" for no content filtering
- Check pricing ($/1M tokens)
- Check context length (longer = more conversation memory)

---

### Context Window

**Controls how many recent messages the bot sees:**

```bash
# Default: 50 messages (with compression)
CONTEXT_WINDOW_MESSAGES=50

# More context (extended conversations with compression)
CONTEXT_WINDOW_MESSAGES=100

# Less context (for testing or minimal conversations)
CONTEXT_WINDOW_MESSAGES=20
```

**With LLMLingua Compression:**
- Compression reduces token usage by 50-80% on conversation history
- Allows 3-4x more messages than without compression
- Default 50 messages = ~10-15 message equivalent in token cost
- Older messages compressed, last 3 kept verbatim
- Activates automatically when 8+ messages in history
- Recommended: 50-100 messages (with compression enabled)

---

### Conversation Compression (LLMLingua)

**Semantic compression for longer conversations:**

```bash
# Enable/disable compression
ENABLE_COMPRESSION=true

# Target compression rate (0.5 = 50% token reduction)
COMPRESSION_RATE=0.5

# Minimum messages before compression activates
MIN_MESSAGES_TO_COMPRESS=8

# Compression model (default: llmlingua-2-bert-base-multilingual-cased)
COMPRESSION_MODEL=microsoft/llmlingua-2-bert-base-multilingual-cased
```

**How compression works:**
- Uses LLMLingua to remove less important tokens while preserving meaning
- Compresses older messages, keeps last 3 verbatim for context freshness
- 50-80% token reduction on compressed messages
- Model downloads once (~500MB) then caches locally
- CPU-only operation (no GPU required)
- Graceful fallback to uncompressed if model fails

**Benefits:**
- 3-4x longer conversation history within same token budget
- Significant cost savings on conversations
- No visible impact to users
- Automatic activation (no user action needed)

**Compression rate:**
```bash
# Aggressive compression (more savings, may lose nuance)
COMPRESSION_RATE=0.3  # 70% reduction

# Balanced (default)
COMPRESSION_RATE=0.5  # 50% reduction

# Conservative (less savings, preserves more detail)
COMPRESSION_RATE=0.7  # 30% reduction
```

**Activation threshold:**
```bash
# Compress sooner (more savings)
MIN_MESSAGES_TO_COMPRESS=5

# Default (balanced)
MIN_MESSAGES_TO_COMPRESS=8

# Compress later (only very long conversations)
MIN_MESSAGES_TO_COMPRESS=15
```

**Disabling compression:**
```bash
# Disable if having issues or prefer uncompressed
ENABLE_COMPRESSION=false
```

**Console output:**
```
📦 Compression initialized (enabled: True, rate: 0.5)
📦 Compressed 12 messages: 450 → 180 tokens (60% savings)
```

---

## Web Search Configuration

### Tavily API Key

**Get API key:**
1. Sign up at [Tavily](https://tavily.com/)
2. Get API key from dashboard
3. Add to `.env`:
   ```bash
   TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

**Free tier:** 1,000 searches/month

**Costs:**
- Free: 1,000 searches/month
- Pro: $30/month for 30,000 searches
- Enterprise: Custom pricing

---

## Privacy Configuration

### Opt-Out Role

**Role name for users who want to opt out:**

```bash
# Default
OPT_OUT_ROLE_NAME=NoDataCollection

# Alternative names
OPT_OUT_ROLE_NAME=PrivacyMode
OPT_OUT_ROLE_NAME=NoTracking
OPT_OUT_ROLE_NAME=DoNotTrack
```

**What opt-out does:**
- Excludes user from behavior analysis
- Excludes from leaderboards
- Messages flagged but not used for bot context
- Claims/quotes still tracked (feature-specific opt-out not available)

**Create role in Discord:**
1. Server Settings → Roles
2. Create new role with exact name from `.env`
3. Assign to users who want privacy

---

## Rate Limiting Configuration

### Token Limits

**Prevents abuse and controls costs:**

```bash
# Per-request limit (prevents single massive response)
MAX_TOKENS_PER_REQUEST=1000

# Hourly limit per user (prevents spam)
HOURLY_TOKEN_LIMIT=10000
```

**What this means:**
- **Per-request limit**: Maximum tokens the bot can generate in a single response
  - 1000 tokens ≈ 750 words ≈ 2-3 Discord messages
  - Prevents users from requesting extremely long responses

- **Hourly limit**: Maximum tokens a user can consume per hour
  - 10000 tokens ≈ 5-10 average conversations
  - Resets on rolling 1-hour window
  - Tracked per user in database

**When limit is reached:**
```
⏱️ Token limit reached! You've used 10,250/10,000 tokens this hour.
Reset in 42m 15s.
```

**Adjusting limits:**
```bash
# More generous (higher costs)
MAX_TOKENS_PER_REQUEST=2000
HOURLY_TOKEN_LIMIT=20000

# More restrictive (lower costs, fewer abuse issues)
MAX_TOKENS_PER_REQUEST=500
HOURLY_TOKEN_LIMIT=5000

# No limits (not recommended - abuse risk)
MAX_TOKENS_PER_REQUEST=4096
HOURLY_TOKEN_LIMIT=999999
```

**How tokens are counted:**
- Input tokens: User's message + conversation history
- Output tokens: Bot's response
- Estimated at ~4 characters per token
- Actual token usage tracked in `rate_limits` table

**Database cleanup:**
- Automatic cleanup of records older than 1 hour
- Runs on every request
- No manual maintenance required

---

### Context Token Limits

**Hard cap on conversation context size:**

```bash
# Maximum tokens in conversation context
MAX_CONTEXT_TOKENS=4000
```

**What this means:**
- Prevents runaway context costs from long conversations
- Automatically truncates oldest messages when limit exceeded
- ~1 token per 3.5 characters estimation
- Preserves system prompt and most recent messages

**How it works:**
```
Long conversation with 5000 tokens:
→ Oldest messages removed until ≤ 4000 tokens
→ System prompt always preserved
→ Most recent user message always included
→ Context stays focused and affordable
```

**Adjusting limits:**
```bash
# Larger context (higher quality, higher cost)
MAX_CONTEXT_TOKENS=8000

# Smaller context (lower cost, less history)
MAX_CONTEXT_TOKENS=2000

# Default (balanced)
MAX_CONTEXT_TOKENS=4000
```

---

### Feature-Specific Rate Limits

**Fact-Check Limits:**

```bash
# Cooldown between fact-checks (seconds)
FACT_CHECK_COOLDOWN=300  # 5 minutes

# Daily limit per user
FACT_CHECK_DAILY_LIMIT=10
```

**Why limit fact-checks:**
- Web search costs (7 sources per check)
- Without limits: costs can add up quickly

**User feedback:**
```
⏱️ Fact-check cooldown! Wait 4m 32s before requesting another.
📊 Daily limit reached! You've used 10/10 fact-checks today.
```

**Web Search Limits:**

```bash
# Hourly limit per user
SEARCH_HOURLY_LIMIT=5

# Daily limit per user
SEARCH_DAILY_LIMIT=20
```

**Why limit searches:**
- Tavily API has rate limits
- Can trigger from user messages or LLM requests
- Free tier: 1000 searches/month total
- Prevents exhausting free quota

**User feedback:**
```
⏱️ Search limit reached! You've used 5/5 searches this hour.
📊 Daily search limit reached! You've used 20/20 searches today.
```

---

### Message Frequency Limits

**Anti-spam controls:**

```bash
# Seconds between bot messages per user
MESSAGE_COOLDOWN=3

# Maximum messages per minute per user
MAX_MESSAGES_PER_MINUTE=10

# Maximum input length (characters)
MAX_INPUT_LENGTH=2000
```

**How frequency limits work:**
- **Cooldown**: Silent rejection (no spam messages)
- **Per-minute limit**: "Slow down" warning message
- **Input length**: Automatic truncation with warning

**User feedback:**
```
⏱️ Slow down! You're sending messages too quickly.
⚠️ Message truncated to 2000 characters for processing.
```

**Why these limits matter:**
- Prevents rapid-fire message spam
- Reduces token usage from long inputs
- Protects against DoS-style abuse
- Keeps costs predictable

---

### Concurrent Request Limiting

**Maximum simultaneous LLM calls:**

```bash
# Max concurrent requests per user
MAX_CONCURRENT_REQUESTS=3
```

**Why limit concurrency:**
- Users sending multiple messages before first response completes
- Could cause 10x cost multiplier
- API rate limit issues
- Queue buildup affects all users

**How it works:**
```
User sends 5 rapid messages:
→ First 3 process normally
→ Messages 4-5 get "too many requests" error
→ Counter decrements when requests complete
→ User can send more after responses arrive
```

**User feedback:**
```
⏱️ Too many requests at once! Please wait for your current request to finish.
```

---

### Command Cooldowns

**Expensive operations:**

```bash
# Wrapped command cooldown (seconds)
WRAPPED_COOLDOWN=60

# Server leaderboard cooldown (seconds)
IRACING_LEADERBOARD_COOLDOWN=60
```

**Why cooldown commands:**
- `/wrapped`: Expensive database aggregation queries
- `/iracing_server_leaderboard`: Fetches all server members' iRacing data
- Visualization generation overhead
- Multiple API calls

**Which commands have cooldowns:**
- `/wrapped`: Year-end statistics summary
- `/iracing_server_leaderboard`: Server-wide iRating rankings

**User feedback:**
```
⏱️ Wrapped cooldown! Please wait 42 seconds before generating another wrapped.
⏱️ Leaderboard cooldown! Please wait 35 seconds before requesting another leaderboard.
```

---

### Cost Tracking & Alerts

**Automatic spending monitoring:**

Cost tracking is **always enabled** and requires no configuration.

**What gets tracked:**
- Real-time token usage from API responses
- Model-specific pricing
- Input tokens vs. output tokens
- Request type (chat, fact-check, etc.)
- Per-user attribution

**Alert system:**
- DMs bot owner (user: `wompie__`) when spending crosses each $1 threshold
- Beautiful embed with cost breakdown by model
- Prevents duplicate alerts (tracks in `cost_alerts` table)

**Alert example:**
```
💸 Cost Alert: $3.00 Spent

Your bot has spent $3.00 total on LLM API calls.

DeepSeek: $3.00 (100%)

This is an automatic alert sent every $1.
```

**Database tables:**
- `api_costs`: Individual API call costs with token counts
- `cost_alerts`: Alert history (prevents duplicates)
- `rate_limits`: Token usage per user
- `feature_rate_limits`: Feature-specific usage tracking

**Monitoring queries:**
```bash
# Total spending
docker-compose exec postgres psql -U botuser -d discord_bot \
  -c "SELECT SUM(cost_usd) FROM api_costs;"

# Cost by model
docker-compose exec postgres psql -U botuser -d discord_bot \
  -c "SELECT model, SUM(cost_usd) FROM api_costs GROUP BY model;"

# Top users by cost
docker-compose exec postgres psql -U botuser -d discord_bot \
  -c "SELECT username, SUM(cost_usd) FROM api_costs GROUP BY username ORDER BY SUM(cost_usd) DESC LIMIT 10;"
```

---

### Complete Rate Limiting Configuration

**Full .env example:**

```bash
# Core Token Limits
MAX_TOKENS_PER_REQUEST=1000      # Tokens per single response
HOURLY_TOKEN_LIMIT=10000         # Tokens per user per hour
MAX_CONTEXT_TOKENS=4000          # Context size hard cap

# Feature-Specific Limits
FACT_CHECK_COOLDOWN=300          # 5 minutes between fact-checks
FACT_CHECK_DAILY_LIMIT=10        # 10 fact-checks per day per user
SEARCH_HOURLY_LIMIT=5            # 5 searches per hour per user
SEARCH_DAILY_LIMIT=20            # 20 searches per day per user

# Anti-Spam Controls
MESSAGE_COOLDOWN=3               # 3 seconds between messages
MAX_MESSAGES_PER_MINUTE=10       # 10 messages per minute per user
MAX_INPUT_LENGTH=2000            # 2000 character max input
MAX_CONCURRENT_REQUESTS=3        # 3 simultaneous requests max

# Command Cooldowns
WRAPPED_COOLDOWN=60              # 60 seconds between /wrapped
IRACING_LEADERBOARD_COOLDOWN=60  # 60 seconds between leaderboards
```

**Cost impact:**

| Limit Type | Without Limits | With Limits | Savings |
|------------|---------------|-------------|---------|
| Token limits | $100+/day | $2-10/day | 90-98% |
| Context limits | $1/msg | $0.03/msg | 97% |
| Concurrent | 10x cost | 1x cost | 90% |
| Feature limits | $50/day | $5/day | 90% |

**Result**: Predictable monthly costs ($10-50) vs. unpredictable ($100-1000+)

---

## Database Configuration

### PostgreSQL Password

**Set a secure password:**

```bash
POSTGRES_PASSWORD=your_secure_password_here_use_random_string
```

**Generate random password:**
```bash
openssl rand -base64 32
```

**Note:** Database is only accessible from Docker network (not exposed externally)

---

### Database Connection

**Automatically configured by Docker:**
```bash
DB_HOST=postgres
DB_PORT=5432
DB_NAME=discord_bot
DB_USER=botuser
DB_PASSWORD=${POSTGRES_PASSWORD}
```

**Do not change these unless modifying docker-compose.yml**

---

## Docker Configuration

### docker-compose.yml

**Location:** `/discord-bot/docker-compose.yml`

**Key settings:**

#### PostgreSQL
```yaml
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: discord_bot
    POSTGRES_USER: botuser
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  ports:
    - "5432:5432"  # Expose port (optional, for external access)
```

**Security note:** Remove port mapping in production:
```yaml
  # ports:
  #   - "5432:5432"  # Commented out - not exposed
```

---

#### Bot Container
```yaml
bot:
  build: ./bot
  environment:
    DISCORD_TOKEN: ${DISCORD_TOKEN}
    OPENROUTER_API_KEY: ${OPENROUTER_API_KEY}
    TAVILY_API_KEY: ${TAVILY_API_KEY}
    MODEL_NAME: ${MODEL_NAME}
    CONTEXT_WINDOW_MESSAGES: ${CONTEXT_WINDOW_MESSAGES}
    OPT_OUT_ROLE_NAME: ${OPT_OUT_ROLE_NAME}
  restart: unless-stopped
  volumes:
    - ./bot:/app  # Hot reload: edit code without rebuild
```

**Hot reload enabled:** Edit Python files and restart bot with `docker-compose restart bot`

---

## Feature-Specific Configuration

### Chat Statistics

**Update frequency:**
- File: `bot/main.py:36`
- Default: Every 1 hour
- Options: 15 min, 30 min, 1 hour, 6 hours

**Time ranges:**
- File: `bot/main.py:46`
- Default: `[7, 30]` (last week and month)
- Options: Add `1` for yesterday, `90` for quarter, etc.

**See:** [docs/features/CHAT_STATISTICS.md](features/CHAT_STATISTICS.md)

---

### Claims Tracking

**Sensitivity:**
- File: `bot/features/claims.py:60`
- Adjust `temperature` parameter (0.1-0.5)

**Minimum message length:**
- File: `bot/main.py:164`
- Default: 20 characters
- Increase to reduce false positives

**See:** [docs/features/CLAIMS_TRACKING.md](features/CLAIMS_TRACKING.md)

---

### Fact-Check

**Search results:**
- File: `bot/search.py`
- Adjust `max_results` (default: 5)

**Timeout:**
- File: `bot/features/fact_check.py:88`
- Default: 60 seconds
- Increase for slow connections

**See:** [docs/features/FACT_CHECK.md](features/FACT_CHECK.md)

---

### User Analytics

**Analysis batch size:**
- File: `bot/main.py:524`
- Default: 10 users per analysis
- Increase for more comprehensive analysis (higher LLM cost)

**Minimum messages:**
- File: `bot/main.py:527`
- Default: 5 messages
- Increase to only analyze active users

**See:** [docs/features/USER_ANALYTICS.md](features/USER_ANALYTICS.md)

---

### Conversational AI

**Personality:**
- File: `bot/llm.py:39-72`
- Modify system prompt entirely

**Temperature:**
- File: `bot/llm.py:93`
- Default: 0.7
- Range: 0.1 (conservative) to 1.5 (creative)

**Max tokens:**
- File: `bot/llm.py:92`
- Default: 500
- Increase for longer responses (higher cost)

**See:** [docs/features/CONVERSATIONAL_AI.md](features/CONVERSATIONAL_AI.md)

---

## Advanced Configuration

### Custom Commands Prefix

**File:** `bot/main.py:20`

```python
# Default: !
bot = commands.Bot(command_prefix='!', intents=intents)

# Change to:
bot = commands.Bot(command_prefix='/', intents=intents)
bot = commands.Bot(command_prefix='>', intents=intents)
```

**Note:** Slash commands (/) are separate and don't use prefix

---

### Logging Level

**File:** `bot/main.py` (add near top)

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Or only warnings/errors
logging.basicConfig(level=logging.WARNING)
```

---

### Timeouts

**LLM timeout:**
- File: `bot/llm.py` (various locations)
- Default: 30 seconds
- Increase for slower connections

**Web search timeout:**
- File: `bot/search.py`
- Default: 10 seconds
- Increase for slower search responses

---

## Performance Tuning

### For Small Servers (<100 users)

```bash
# .env
CONTEXT_WINDOW_MESSAGES=6
MODEL_NAME=deepseek/deepseek-chat

# main.py:36
@tasks.loop(hours=1)  # Hourly stats updates

# main.py:46
time_ranges = [7, 30]  # Week and month only
```

---

### For Large Servers (1000+ users)

```bash
# .env
CONTEXT_WINDOW_MESSAGES=4  # Less context to save tokens
MODEL_NAME=cognitivecomputations/dolphin-mixtral-8x7b  # Cheaper model

# main.py:36
@tasks.loop(hours=6)  # Less frequent stats updates

# main.py:46
time_ranges = [7]  # Only last week

# main.py:524
for user in active_users[:5]:  # Analyze fewer users
```

---

### For Cost Optimization

**Reduce LLM calls:**
1. Lower context window (3-4 messages)
2. Use cheaper model (Mixtral 8x7b)
3. Increase claim detection threshold
4. Reduce analysis frequency

**Reduce search calls:**
1. Disable auto-search triggers
2. Reduce Tavily max_results to 3
3. Cache search results longer

---

## Security Best Practices

### Environment Variables
- ✅ Never commit `.env` to git (already in `.gitignore`)
- ✅ Use strong random passwords
- ✅ Rotate API keys periodically
- ✅ Don't share API keys publicly

### Database
- ✅ Don't expose PostgreSQL port in production
- ✅ Use strong database password
- ✅ Regular backups
- ✅ Keep Docker images updated

### Discord Bot
- ✅ Use minimal required permissions
- ✅ Don't give bot admin permissions
- ✅ Regenerate token if compromised
- ✅ Monitor bot usage/logs

---

## Backup & Restore

### Backup Database

```bash
# Export database
docker-compose exec postgres pg_dump -U botuser discord_bot > backup.sql

# Or with Docker volume
docker run --rm -v discord-bot_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup.tar.gz -C /data .
```

### Restore Database

```bash
# Stop bot first
docker-compose down

# Import database
docker-compose up -d postgres
docker-compose exec -T postgres psql -U botuser discord_bot < backup.sql

# Start bot
docker-compose up -d
```

---

## Troubleshooting

### Bot won't start

**Check:**
1. `.env` exists and has all required variables
2. `DISCORD_TOKEN` is valid
3. Docker is running
4. Ports 5432 not already in use

**Logs:**
```bash
docker-compose logs bot
docker-compose logs postgres
```

---

### Database connection failed

**Check:**
1. PostgreSQL container is running: `docker ps`
2. Password matches in `.env`
3. Wait for health check: `docker-compose logs postgres`

---

### LLM errors

**Check:**
1. OpenRouter API key is valid
2. Model name is correct
3. Account has credits
4. Check [OpenRouter status](https://status.openrouter.ai/)

---

### Search not working

**Check:**
1. Tavily API key is valid
2. Not exceeded free tier (1000/month)
3. Internet connection available
4. Check Tavily dashboard for usage

---

## Support

**Configuration issues:**
- Check all `.env` variables are set
- Verify API keys are valid
- Check Docker logs
- Restart bot after changes: `docker-compose restart bot`

**Need help?**
- Check feature-specific docs in `docs/features/`
- Review logs: `docker-compose logs -f bot`
- Test configuration: `docker-compose config`
