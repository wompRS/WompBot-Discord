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
MODEL_NAME=anthropic/claude-3.7-sonnet           # High-quality model for general chat
FACT_CHECK_MODEL=anthropic/claude-3.5-sonnet   # High-accuracy model for fact-checking

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
- Claude 3.7 Sonnet: ~$3 input / $15 output per 1M tokens
- Pay only for what you use
- Expected: ~$20-30/month for active Discord server

---

### Model Selection

**Dual-Model Architecture:**

WompBot uses two models optimized for different tasks:
1. **General Chat Model** (`MODEL_NAME`) - Fast, conversational
2. **Fact-Check Model** (`FACT_CHECK_MODEL`) - Slow, highly accurate

```bash
# General Chat - Recommended (high quality, accurate)
MODEL_NAME=anthropic/claude-3.7-sonnet

# Fact-Checking - High accuracy (critical for zero hallucination)
FACT_CHECK_MODEL=anthropic/claude-3.5-sonnet
```

**Alternative General Chat Models:**

```bash
# High quality alternatives
MODEL_NAME=anthropic/claude-3.5-sonnet  # Previous generation
MODEL_NAME=deepseek/deepseek-chat-v3.1  # Cheaper, very good

# Budget options
MODEL_NAME=google/gemini-2.5-flash      # Very cheap
MODEL_NAME=deepseek/deepseek-r1-distill-qwen-32b  # Reasoning model
```

**Alternative Fact-Check Models:**

```bash
# High accuracy (recommended, slower but reliable)
FACT_CHECK_MODEL=anthropic/claude-3.5-sonnet

# Medium accuracy (cheaper but more hallucination)
FACT_CHECK_MODEL=meta-llama/llama-3.1-70b-instruct

# Low accuracy (not recommended for fact-checking)
FACT_CHECK_MODEL=nousresearch/hermes-3-llama-3.1-70b
```

**Browse models:** [OpenRouter Models](https://openrouter.ai/models)

**Filters:**
- General chat: Look for "Uncensored" or "Dolphin" for no content filtering
- Fact-checking: Look for high accuracy models (Claude, GPT-4, etc.)
- Check pricing ($/1M tokens)
- Check context length (longer = more conversation memory)

---

### Context Window

**Controls how many recent messages the bot sees:**

```bash
# Default: 6 messages
CONTEXT_WINDOW_MESSAGES=6

# More context (better conversations, higher cost)
CONTEXT_WINDOW_MESSAGES=10

# Less context (cheaper, may miss context)
CONTEXT_WINDOW_MESSAGES=3
```

**Trade-off:**
- More messages = better understanding of conversation
- More messages = more tokens = higher cost
- Recommended: 5-10 messages

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
MODEL_NAME=nousresearch/hermes-3-llama-3.1-70b

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
