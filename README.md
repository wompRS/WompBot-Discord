# WompBot - Discord Bot with Feyd-Rautha Persona

A Discord bot powered by OpenRouter LLMs (Hermes/Dolphin models) with conversation memory, web search, claims tracking, and user behavior analysis. Embodies the persona of Feyd-Rautha Harkonnen from Dune.

## Features

### 🤖 Core Features
- **Conversational AI**: Context-aware responses with Feyd-Rautha's cunning personality
- **Smart Response Detection**: Only responds when "wompbot" mentioned or @tagged
- **Web Search Integration**: Automatic Tavily API search when facts are needed
- **Message Storage**: PostgreSQL database tracks all conversations

### 📋 Claims & Accountability
- **Auto Claims Detection**: LLM detects bold predictions, facts, and guarantees
- **Edit Tracking**: Preserves original text when claims are edited
- **Deletion Tracking**: Saves deleted messages with claims
- **Contradiction Detection**: Identifies when users contradict previous claims
- **Receipts Command**: `/receipts [@user] [keyword]` - View tracked claims

### ☁️ Quotes System
- **Save Quotes**: React with ☁️ emoji to save memorable quotes
- **Quotes Command**: `/quotes [@user]` - View saved quotes with context
- **Auto-Categorization**: Tracks reaction counts and timestamps

### ⚠️ Fact-Check Feature (NEW!)
- **Emoji Triggered**: React with ⚠️ to any message to trigger fact-check
- **Web Search**: Automatically searches for evidence using Tavily
- **LLM Analysis**: Analyzes claim accuracy with verdict and explanation
- **Source Citations**: Includes links to top 3 sources
- **Verdict System**: ✅ True, ❌ False, 🔀 Mixed, ⚠️ Misleading, ❓ Unverifiable

### 📊 User Analytics
- **Behavior Analysis**: Profanity scores, tone, honesty patterns
- **Leaderboards**: `/leaderboard <type> [days]` - messages, questions, profanity
- **User Stats**: `/stats [@user]` - View detailed user statistics
- **Privacy Opt-Out**: Role-based exclusion from data collection

## Setup Instructions

### 1. Install Dependencies (WSL2 Debian)

Already done if you followed the setup commands.

### 2. Configure Environment

Edit `.env` file and fill in your API keys:

```bash
nano .env
```

Replace these values:
- `DISCORD_TOKEN`: Your Discord bot token
- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `TAVILY_API_KEY`: Your Tavily API key
- `POSTGRES_PASSWORD`: Choose a secure password

### 3. Start the Bot

```bash
cd /mnt/e/discord-bot
docker-compose up -d
```

### 4. View Logs

```bash
docker-compose logs -f bot
```

### 5. Stop the Bot

```bash
docker-compose down
```

## Commands

### Conversation
- **@WompBot** or **"wompbot"**: Chat with the bot (Feyd-Rautha persona)
- **/ping**: Check bot latency
- **/help_bot**: Show all available commands

### Claims & Receipts
- **/receipts [@user] [keyword]**: View tracked claims for a user
- **/verify_claim <id> <status> [notes]**: (Admin) Verify a claim as true/false/mixed/outdated

### Quotes
- **☁️ React**: React to any message with ☁️ emoji to save as quote
- **/quotes [@user]**: View saved quotes for a user

### Fact-Checking
- **⚠️ React**: React to any message with ⚠️ emoji to trigger fact-check
- Bot will search web and analyze claim accuracy

### Statistics & Leaderboards
- **/stats [@user]**: View user statistics and behavior analysis
- **/leaderboard <type> [days]**: Show leaderboards (messages/questions/profanity)
- **/search <query>**: Manually search the web
- **/analyze [days]**: (Admin) Analyze user behavior patterns

## Privacy Features

Create a Discord role called `NoDataCollection` (or customize in .env).

Users with this role:
- Messages are still logged but flagged as opted-out
- Excluded from behavior analysis
- Not included in conversation context

## Behavior Analysis

Weekly or on-demand analysis tracks:
- Profanity frequency (0-10 scale)
- Conversational tone
- Honesty patterns (fact-based vs exaggeration)
- Communication style

Use `/analyze` command to run analysis.

## Database Schema

**Tables:**
- `messages`: All Discord messages with opt-out flags
- `user_profiles`: User metadata and message counts
- `user_behavior`: Analysis results (profanity, tone, patterns)
- `search_logs`: Web search history
- `claims`: Tracked claims with edit/delete history
- `quotes`: Saved quotes with reaction counts
- `claim_contradictions`: Detected contradictions
- `fact_checks`: Fact-check results with sources

## Costs

- **OpenRouter (Dolphin 70B)**: ~$10-15/month for moderate usage
- **Tavily Search**: Free up to 1000 searches/month
- **Server**: Free (local Docker)

## Troubleshooting

### Bot not responding
```bash
docker-compose logs bot
```

### Database connection issues
```bash
docker-compose restart postgres
docker-compose logs postgres
```

### Reset everything
```bash
docker-compose down -v
docker-compose up -d
```

## Model Configuration

Change model in `.env`:
```
MODEL_NAME=nousresearch/hermes-3-llama-3.1-70b
```

Available uncensored models on OpenRouter:
- `nousresearch/hermes-3-llama-3.1-70b` (Recommended)
- `cognitivecomputations/dolphin-2.9.2-qwen-110b` (70B)
- `cognitivecomputations/dolphin-mixtral-8x7b`
- `mistralai/mixtral-8x22b-instruct`

## Personality System

WompBot embodies **Feyd-Rautha Harkonnen** from Dune:
- Cunning, calculating, and sharp-tongued
- Dismissive of weakness and logical fallacies
- Eloquent but menacing speech style
- Enjoys intellectual dominance and verbal sparring
- No customer service energy - direct and brutal
- Occasional Dune references (spice, Houses, desert power)

## Upcoming Features

- 🎭 **Roast Mode**: `/roast` command with personality-based roasts
- ⚔️ **Debate Scorekeeper**: Auto-detect debates, score arguments, track fallacies
- 🔥 **Hot Takes Leaderboard**: Track controversial opinions and vindication rate
- 📈 **Chat Statistics**: Network graphs, prime time analysis, topic trends
- 🏆 **Quote of the Day**: `/qotd` command for daily/weekly/monthly quotes
- 📅 **Yearly Wrapped**: End-of-year statistics summary
- ⏰ **Reminders**: Context-aware reminder system

## Development

Edit bot code:
```bash
nano bot/main.py
```

Restart bot:
```bash
docker-compose restart bot
```

View logs:
```bash
docker-compose logs -f bot
```

## File Structure

```
discord-bot/
├── bot/
│   ├── main.py              # Main bot logic, event handlers, commands
│   ├── llm.py               # OpenRouter LLM client
│   ├── database.py          # PostgreSQL interface
│   ├── search.py            # Tavily web search
│   └── features/
│       ├── claims.py        # Claims tracking system
│       └── fact_check.py    # Fact-check feature
├── sql/
│   └── init.sql             # Database schema
├── docker-compose.yml       # Docker configuration
├── Dockerfile               # Bot container setup
└── .env                     # Environment variables (API keys)
```

## Support

Check logs for errors:
```bash
docker-compose logs -f
```
