# WompBot - Discord Bot

A Discord bot powered by OpenRouter LLMs (Hermes/Dolphin models) with conversation memory, web search, claims tracking, user behavior analysis, and iRacing integration.

## Features

### 🤖 Core Features
- **Conversational AI**: Context-aware responses with a professional and helpful personality
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

### 📈 Chat Statistics
- **Network Graphs**: `/stats_server [days]` - Who interacts with whom
- **Topic Trends**: `/stats_topics [days]` - Trending keywords using TF-IDF
- **Prime Time**: `/stats_primetime [@user] [days]` - Activity heatmaps by hour/day
- **Engagement**: `/stats_engagement [@user] [days]` - Response times, patterns
- **Zero Cost**: Uses machine learning, no LLM needed
- **Background Updates**: Auto-refreshes every hour

### 🔥 Hot Takes Leaderboard
- **Auto Detection**: Identifies controversial claims using pattern matching
- **Community Tracking**: Monitors reactions and replies automatically
- **Multiple Leaderboards**: Controversial, Vindicated, Worst, Community Favorites, Combined
- **Vindication System**: Track which hot takes aged well or poorly
- **User Stats**: `/mystats_hottakes` - Your personal controversy metrics
- **Smart Hybrid**: Three-stage system keeps costs under $1/month
- **Track Record**: See who has the best/worst prediction accuracy

### ⏰ Context-Aware Reminders
- **Natural Language**: "in 5 minutes", "tomorrow at 3pm", "next Monday"
- **Context Links**: Jump back to original message
- **Flexible Delivery**: DM or channel mention
- **Recurring Support**: Daily, weekly, or custom intervals
- **Zero Cost**: Pure time parsing, no LLM needed
- **Background Checker**: Runs every minute for precise delivery

### 📅 Event Scheduling
- **Scheduled Events**: Create events with automatic periodic reminders
- **Natural Language**: "Friday at 8pm", "in 3 days", "next Monday at 7pm", "october 20"
- **Periodic Reminders**: Configurable intervals (default: 1 week, 1 day, 1 hour before)
- **Channel Announcements**: Public event notifications with Discord timestamps
- **Event Management**: List upcoming events, cancel events by ID
- **Zero Cost**: No LLM needed, pure time parsing
- **Background Checker**: Runs every 5 minutes for reminder delivery

### 📊 Yearly Wrapped (NEW!)
- **Year-End Summary**: Spotify-style statistics for your Discord activity
- **Comprehensive Stats**: Messages, social network, claims, quotes, personality insights
- **Achievements**: Earn badges like Night Owl, Early Bird, Debate Champion, Quote Machine
- **Compare Years**: View any year (2020-present) or compare users
- **Beautiful Embeds**: Gold-themed cards with your profile picture
- **Zero Cost**: Pure database queries, no LLM needed

### 🏆 Quote of the Day (NEW!)
- **Featured Quotes**: Highlight the best quotes from your server
- **Multiple Modes**: Daily, Weekly, Monthly, All-Time Greats, or Random
- **Smart Selection**: Top quotes by reaction count from each time period
- **Beautiful Display**: Purple embeds with context, attribution, and category badges
- **Zero Cost**: Pure database queries, no LLM needed

### ⚔️ Debate Scorekeeper (NEW!)
- **Track Debates**: Start/end debates with `/debate_start` and `/debate_end`
- **LLM Analysis**: Automatic scoring of arguments and detection of logical fallacies
- **Winner Determination**: AI judges declare winners and explain why
- **Individual Scores**: Each participant gets scored 0-10 on argument quality
- **Fallacy Detection**: Identifies ad hominem, strawman, and other logical fallacies
- **Debate History**: Track your wins, losses, average score, and favorite topics
- **Leaderboards**: See who the best debaters are by wins and scores
- **Low Cost**: Only uses LLM when debate ends (typically $0.01-0.05 per debate)

### 🏁 iRacing Integration (NEW!)
- **Driver Profiles**: View any iRacing driver's stats across all license categories
- **Driver Comparison**: Side-by-side comparison charts with license ratings and career stats
- **Rating History**: Track iRating and Safety Rating progression over time
- **Server Leaderboards**: See who's the fastest in your Discord server by category
- **Meta Analysis**: View best cars for any series with performance statistics
- **Account Linking**: Link your Discord account to your iRacing profile
- **Race Schedule**: View upcoming official races across all series
- **Series Information**: Browse all active iRacing series and seasons with autocomplete
- **Recent Results**: Check recent race results and performance
- **Smart Search**: Automatically finds drivers by name
- **Category Autocomplete**: Easy selection of Oval, Sports Car, Formula Car, Dirt Oval, Dirt Road
- **Professional Visualizations**: Charts matching iRacing Reports style
- **Live Data**: Direct integration with iRacing's official API
- **Response Caching**: Intelligent caching to minimize API requests
- **Optional Feature**: Only enabled if credentials are provided
- **Zero Cost**: No LLM usage, pure API calls

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

**Optional - iRacing Integration:**
To enable iRacing features securely with encrypted credentials:
1. See **[CREDENTIALS_SETUP.md](CREDENTIALS_SETUP.md)** for detailed instructions
2. Quick start:
   ```bash
   docker-compose build bot  # Install encryption library
   docker-compose run --rm bot python encrypt_credentials.py  # Encrypt credentials
   docker-compose up -d bot  # Restart with encrypted credentials
   ```

**Note**: Credentials are encrypted using Fernet symmetric encryption and never stored in plaintext.

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
- **!ping**: Check bot latency
- **!wompbot help** or **/help**: Show all available commands

### Claims & Receipts
- **/receipts [@user] [keyword]**: View tracked claims for a user
- **/verify_claim <id> <status> [notes]**: (Admin) Verify a claim as true/false/mixed/outdated

### Quotes
- **☁️ React**: React to any message with ☁️ emoji to save as quote
- **/quotes [@user]**: View saved quotes for a user

### Fact-Checking
- **⚠️ React**: React to any message with ⚠️ emoji to trigger fact-check
- Bot will search web and analyze claim accuracy

### Chat Statistics
- **/stats_server [days|date_range]**: Network graph and interaction stats
- **/stats_topics [days|date_range]**: Trending keywords (TF-IDF)
- **/stats_primetime [@user] [days|date_range]**: Activity heatmaps
- **/stats_engagement [@user] [days|date_range]**: Engagement metrics
- **!refreshstats**: (Admin) Manually refresh stats cache

### Hot Takes Leaderboard
- **/hottakes [type] [days]**: View hot takes leaderboards (controversial/vindicated/worst/community/combined)
- **/mystats_hottakes**: View your personal hot takes statistics
- **/vindicate <id> <status> [notes]**: (Admin) Mark a hot take as vindicated/proven wrong

### Reminders
- **/remind <time> <message> [recurring]**: Set a reminder with natural language time
- **/reminders**: View all your active reminders
- **/cancel_reminder <id>**: Cancel one of your reminders

### Event Scheduling
- **/schedule_event <name> <date> [description] [reminders]**: Schedule an event with automatic reminders
- **/events [limit]**: View upcoming scheduled events
- **/cancel_event <id>**: Cancel a scheduled event

### Yearly Wrapped
- **/wrapped [year] [user]**: View your yearly activity summary (Spotify Wrapped for Discord!)

### Quote of the Day
- **/qotd [mode]**: View featured quotes (daily/weekly/monthly/alltime/random)

### Debate Scorekeeper
- **/debate_start <topic>**: Start tracking a debate in the current channel
- **/debate_end**: End debate and show LLM analysis with scores and fallacies
- **/debate_stats [user]**: View debate statistics and win/loss record
- **/debate_leaderboard**: Top debaters by wins and average score

### iRacing Integration
- **/iracing_link <iracing_name>**: Link your Discord account to your iRacing account
- **/iracing_profile [driver_name]**: View iRacing driver profile (uses linked account if no name provided)
- **/iracing_compare_drivers <driver1> <driver2> [category]**: Compare two drivers side-by-side with charts
- **/iracing_history [driver_name] [category] [days]**: View rating progression chart (default: 30 days)
- **/iracing_server_leaderboard [category]**: Show iRating rankings for linked Discord members
- **/iracing_meta <series> [season] [week] [track]**: View meta analysis showing best cars for a series
- **/iracing_schedule [series] [hours]**: View upcoming race schedule (default: next 24 hours)
- **/iracing_series**: List all active iRacing series and seasons
- **/iracing_results [driver_name]**: View recent race results (uses linked account if no name provided)

### User Analytics & Leaderboards
- **!stats [@user]**: View user statistics and behavior analysis
- **!leaderboard <type> [days]**: Show leaderboards (messages/questions/profanity)
- **!search <query>**: Manually search the web
- **!analyze [days]**: (Admin) Analyze user behavior patterns

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

## Documentation

📚 **Comprehensive guides available:**

**Feature Documentation:**
- [🤖 Conversational AI](docs/features/CONVERSATIONAL_AI.md) - Feyd-Rautha personality, LLM configuration
- [📋 Claims Tracking](docs/features/CLAIMS_TRACKING.md) - Auto-detection, edit tracking, contradictions
- [⚠️ Fact-Checking](docs/features/FACT_CHECK.md) - Web search integration, verdict system
- [☁️ Quotes System](docs/features/QUOTES.md) - Emoji reactions, context preservation
- [📊 User Analytics](docs/features/USER_ANALYTICS.md) - Behavior analysis, leaderboards
- [📈 Chat Statistics](docs/features/CHAT_STATISTICS.md) - Network graphs, topics, prime time
- [🔥 Hot Takes Leaderboard](docs/features/HOT_TAKES.md) - Controversy detection, vindication tracking
- [⏰ Reminders](docs/features/REMINDERS.md) - Natural language time parsing, context preservation
- [📅 Event Scheduling](docs/features/EVENTS.md) - Scheduled events with periodic reminders
- [🏁 iRacing Integration](docs/features/IRACING.md) - Driver stats, comparisons, meta analysis, schedules

**Configuration & Development:**
- [⚙️ Configuration Guide](docs/CONFIGURATION.md) - All settings, API keys, environment variables
- [🛠️ Development Guide](docs/DEVELOPMENT.md) - Adding features, database migrations, testing
- [💰 Cost Optimization](docs/COST_OPTIMIZATION.md) - Two-stage hybrid detection for claims

## Database Schema

**Tables:**
- `messages`: All Discord messages with opt-out flags
- `user_profiles`: User metadata and message counts
- `user_behavior`: Analysis results (profanity, tone, patterns)
- `search_logs`: Web search history
- `claims`: Tracked claims with edit/delete history
- `hot_takes`: Controversial claims with community tracking and vindication
- `quotes`: Saved quotes with reaction counts
- `claim_contradictions`: Detected contradictions
- `fact_checks`: Fact-check results with sources
- `reminders`: Context-aware reminders with natural language parsing
- `events`: Scheduled events with periodic reminders and channel notifications
- `debates`: Tracked debates with LLM analysis and scores
- `debate_participants`: Individual debate participant records and statistics
- `stats_cache`: Pre-computed statistics (network, topics, primetime, engagement)
- `message_interactions`: Network graph data
- `topic_snapshots`: Trending topics over time

## Costs

- **OpenRouter (Dolphin 70B)**: ~$10-20/month for moderate usage
  - Conversation AI: ~$0.001-0.005 per message
  - Debate Analysis: ~$0.01-0.05 per debate
  - Hot Takes Scoring: ~$0.005 per analysis (only for high-engagement claims)
- **Tavily Search**: Free up to 1000 searches/month
- **Server**: Free (local Docker)

**Cost Optimization:**
- Hot Takes use hybrid detection (pattern matching first, LLM only for high engagement)
- Debate Scorekeeper only uses LLM when ending debates
- Event Scheduling and Reminders use zero LLM (pure time parsing)
- Quote of the Day uses zero LLM (pure database queries)
- Yearly Wrapped uses zero LLM (pure database aggregation)

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

- 🎲 **Polls & Voting**: Create polls with slash commands and reaction tracking
- 🎂 **Birthday Tracking**: Automatic birthday reminders and celebrations
- 🎮 **Trivia Games**: Quiz system with categories and leaderboards
- 📊 **Voice Channel Stats**: Track time spent in voice channels
- 🎯 **Custom Commands**: User-created text commands and responses

## Development

**Quick reference:**

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

**For detailed development guide, see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)**

## File Structure

```
discord-bot/
├── README.md                # This file
├── .env                     # Environment variables (API keys)
├── docker-compose.yml       # Docker configuration
├── Dockerfile               # Bot container setup
│
├── docs/                    # Documentation
│   ├── features/            # Feature-specific guides
│   │   ├── CHAT_STATISTICS.md
│   │   ├── CLAIMS_TRACKING.md
│   │   ├── CONVERSATIONAL_AI.md
│   │   ├── EVENTS.md
│   │   ├── FACT_CHECK.md
│   │   ├── HOT_TAKES.md
│   │   ├── QUOTES.md
│   │   ├── REMINDERS.md
│   │   └── USER_ANALYTICS.md
│   ├── CONFIGURATION.md     # Configuration guide
│   └── DEVELOPMENT.md       # Development guide
│
├── sql/
│   └── init.sql             # Database schema
│
└── bot/
    ├── main.py              # Main bot logic, event handlers, commands
    ├── llm.py               # OpenRouter LLM client
    ├── database.py          # PostgreSQL interface
    ├── search.py            # Tavily web search
    ├── requirements.txt     # Python dependencies
    └── features/
        ├── claims.py        # Claims tracking system
        ├── fact_check.py    # Fact-check feature
        ├── chat_stats.py    # Chat statistics
        ├── hot_takes.py     # Hot takes leaderboard
        ├── reminders.py     # Context-aware reminders
        └── events.py        # Event scheduling (NEW!)
```

## Support

Check logs for errors:
```bash
docker-compose logs -f
```
