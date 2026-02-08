# WompBot - Discord Bot

A Discord bot powered by DeepSeek through OpenRouter, featuring intelligent conversation memory (RAG), media analysis (images, GIFs, YouTube transcripts, video transcription), 26 LLM tools, web search integration, claims tracking, user behavior analysis, and iRacing integration.

## Core Features

### Conversational AI

**AI Architecture**
- General Chat: DeepSeek for high-quality conversational responses
- Configurable model via MODEL_NAME environment variable

**Three Personality Modes**
- Default: Conversational and helpful, provides detailed responses with personality
- Concise: Brief and direct, gets straight to the point without elaboration
- Bogan: Full Australian slang mode for casual pub-style conversations

**Smart Context Management**
- Professional conversation memory that remembers your preferences and past discussions
- LLMLingua compression reduces token usage by 50-80%, allowing much longer conversations
- Only responds when mentioned, tagged, or when you use "wompbot" or "!wb"
- Proper Discord mention support works both ways

**Web Search Integration**
- Automatic Tavily API search when the bot needs current information
- Rate-limited to prevent abuse: 5 per hour, 20 per day per user

**Guild Data Isolation**
- Complete separation of data between Discord servers
- 18 tables use guild_id filtering for privacy and performance
- Composite indexes make queries 10x faster than separate databases

**Automated Backups**
- Daily, weekly, and monthly database backups with configurable retention
- Centralized logging with file rotation and error tracking

**Comprehensive Rate Limiting**
- Multi-layer protection prevents abuse and controls costs
- Token limits: 1,000 per request, 10,000 per hour per user
- Message frequency controls: 3-second cooldown, max 10 per minute
- Feature-specific limits for fact-checks, searches, and expensive commands
- Concurrent request limiting: 3 simultaneous requests maximum
- Cost tracking with configurable spending alerts (COST_ALERT_THRESHOLD, default $1) sent via DM

### RAG - Intelligent Memory System

The bot uses Retrieval Augmented Generation to remember conversations more efficiently than just keeping everything in context.

**How it works:**
- Semantic search using vector embeddings finds relevant past conversations by meaning, not keywords
- Hybrid memory combines recent messages (working memory) with long-term retrieval
- Learns your preferences, projects, and skills automatically
- Background processing generates embeddings every 5 minutes
- AI-generated conversation summaries provide broader context
- pgvector integration enables fast similarity search in PostgreSQL

**Benefits:**
- 40% token reduction compared to keeping full conversation history
- Access to full message database without bloating context
- Smarter context assembly means better responses

### Media Analysis

WompBot can analyze images, GIFs, YouTube videos, and video attachments using vision AI and audio transcription.

**Supported Media:**
- **Images:** PNG, JPG, WebP - describes content, reads text, identifies memes
- **Animated GIFs:** Extracts 6 frames to capture full animation
- **YouTube Videos:** Transcript-first approach - fetches captions instantly without downloading
- **Video Attachments:** Transcribes audio using OpenAI Whisper API

**How It Works:**
- Share media with WompBot and ask "what's this?" or "what's happening?"
- YouTube transcripts are fetched instantly via API (no video download required)
- Video attachments are transcribed with timestamps
- Falls back to visual frame extraction if no transcript available

**Example Usage:**
```
@WompBot what's happening in this video?
[YouTube link or video attachment]

@WompBot describe this meme
[Image attachment]
```

### LLM Tools (26 Available)

WompBot can automatically invoke tools to provide real-time information:

**Weather & Science:**
- `get_weather` - Current weather conditions
- `get_weather_forecast` - 5-day weather forecast
- `wolfram_query` - Math, science, conversions, historical weather data

**Search & Information:**
- `web_search` - Current events and news
- `wikipedia` - Factual information
- `define_word` - Dictionary definitions
- `url_preview` - Summarize webpages

**Time, Translation & Currency:**
- `get_time` - Current time in any timezone
- `translate` - Translate between languages
- `currency_convert` - Convert currencies (supports 30+ currencies and natural language like "100 bucks to euros")

**Entertainment & Media:**
- `youtube_search` - Search YouTube videos
- `movie_info` - Movie/TV ratings and info
- `stock_price` - Stock and crypto prices
- `stock_history` - Historical stock price charts with technical analysis
- `sports_scores` - Live sports scores and schedules
- `image_search` - Search for images on the web

**Utility:**
- `random_choice` - Dice rolls, coin flips, random picks
- `create_reminder` - Set reminders

**Visualization:**
- `create_bar_chart`, `create_line_chart`, `create_pie_chart`, `create_table`, `create_comparison_chart`
- Natural language: "show me a chart of who talks the most"

### Weather and Computational Tools

The bot can invoke tools through LLM function calling to create visualizations and fetch data.

**Weather Features:**
- Beautiful weather cards with dual-unit display (Fahrenheit primary, Celsius secondary)
- Smart US location parsing: "spokane wa", "spokane, wa", "New York, NY" all work
- Save your default location with !weatherset
- 5-day forecasts available
- Just say "wompbot weather" after setting your preference

**Wolfram Alpha Integration:**
- Mathematical calculations and unit conversions
- Factual queries about math, science, geography
- Free tier: 2,000 queries per month

**Data Visualizations:**
- Bar charts, line charts, pie charts, tables, comparison charts
- Natural language requests: "show me a chart of who talks the most"
- Colorblind-friendly Okabe-Ito palette (enable with VIZ_COLORBLIND_MODE=true)
- Zero LLM cost - tool outputs speak for themselves

### Claims and Accountability

The bot automatically detects when people make bold predictions, factual claims, or guarantees.

**Features:**
- LLM-powered claim detection
- Edit tracking preserves original text
- Deletion tracking saves deleted claims
- Contradiction detection identifies when users contradict previous claims
- Use !receipts to view tracked claims for any user (alias: !claims)
- Verify claims as true/false/mixed with !verify

### Quotes System

React with a cloud emoji to any message to save it as a memorable quote.

**Commands:**
- !quotes to view saved quotes for a user
- Tracks reaction counts and timestamps
- Auto-categorizes quotes by context

### Fact-Check Feature

React with a warning emoji to trigger an automated fact-check.

**How it works:**
- Uses DeepSeek for high accuracy
- Automatically searches 5 web sources using Tavily
- Requires at least 2 sources to corroborate claims
- Strict anti-hallucination prompts
- Provides numbered source references with links
- Verdict system: True, False, Mixed, Misleading, or Unverifiable
- Rate limited: 5-minute cooldown, 10 per day per user

### User Analytics

Track behavior patterns and participation across your server.

**Available Stats:**
- Behavior analysis: profanity scores, tone, honesty patterns
- Leaderboards: messages, questions, profanity usage
- User-specific statistics with /stats
- GDPR-compliant opt-out system

### Chat Statistics

Zero-cost machine learning analytics for your server.

**Features:**
- Network graphs showing interaction patterns
- Topic trends using TF-IDF analysis
- Activity heatmaps by hour and day
- Engagement metrics and response time analysis
- Background updates every hour
- Commands: /stats_server, /stats_topics, /stats_primetime, /stats_engagement

### Hot Takes Leaderboard

Tracks controversial claims and monitors how they age.

**Features:**
- Automatic detection using pattern matching
- Community tracking via reactions and replies
- Multiple leaderboard types: Controversial, Vindicated, Worst, Community Favorites, Combined
- Vindication system tracks which predictions aged well or poorly
- Three-stage hybrid system keeps costs under $1/month
- View your personal stats with !myht

### Context-Aware Reminders

Natural language reminders that link back to the original conversation.

**Features:**
- Natural language parsing: "in 5 minutes", "tomorrow at 3pm", "next Monday"
- Context links jump back to the original message
- Delivery options: DM or channel mention
- Recurring support: daily, weekly, or custom intervals (fixed: calculates from last_trigger + interval)
- Guild-level timezone support via /set_timezone
- Better error messages for past times and unparseable inputs
- Zero LLM cost - pure time parsing
- Background checker runs every minute

### Event Scheduling

Schedule events with automatic periodic reminders.

**Features:**
- Natural language time input: "Friday at 8pm", "in 3 days", "October 20"
- Configurable reminder intervals (default: 1 week, 1 day, 1 hour before)
- Public channel announcements with Discord timestamps
- Event management: list upcoming events, cancel by ID (creator permission required)
- Guild-level timezone support via /set_timezone
- Better error messages for invalid dates (e.g., "Feb 30")
- Zero LLM cost
- Background checker runs every 5 minutes

### Yearly Wrapped

Spotify-style statistics for Discord activity.

**Features:**
- Year-end summary of messages, social network, claims, quotes
- Personality insights based on your activity
- Achievement badges: Night Owl, Early Bird, Debate Champion, Quote Machine
- Compare any year from 2020 to present
- Gold-themed embeds with profile pictures
- Uses DENSE_RANK() for proper tie handling
- Zero LLM cost - pure database queries

### Quote of the Day

Highlight the best quotes from your server.

**Modes:**
- Daily, Weekly, Monthly, All-Time Greats, or Random
- Smart selection based on reaction counts, all-time weighted by freshness
- Calendar day boundary for daily mode
- Beautiful purple embeds with context and attribution
- Zero LLM cost

### Debate Scorekeeper

Track and analyze debates with LLM judging.

**Features:**
- Start/end debates with commands
- Automatic scoring of arguments (0-10 scale)
- Logical fallacy detection: ad hominem, strawman, etc.
- Winner determination with explanations
- Debate history and leaderboards
- Personal stats: wins, losses, average score
- Sessions persist to database (survive bot restarts)
- Prompt injection defense on transcripts (XML-wrapped)
- Cost: $0.01-0.05 per debate (only when ending)

### iRacing Integration

Comprehensive iRacing stats and team management.

**Driver Stats:**
- View any driver's profile across all license categories
- Side-by-side driver comparisons with charts
- Performance dashboard: rating trends, wins, podiums, top series
- Server leaderboards showing fastest drivers by category
- Smart driver search by name
- Account linking between Discord and iRacing

**Series Analytics:**
- Series popularity charts: season, yearly, all-time
- Meta analysis showing best cars for any series
- Win rate analysis per car
- Schedule visualization with current week highlighted
- Timeslot viewer for race sessions

**Team Management:**
- Create racing teams with custom names and tags
- Role management: manager, driver, crew chief, spotter
- Event scheduling with natural language times
- Driver availability tracking: available, unavailable, maybe, confirmed
- Team rosters with iRacing profile integration
- Event calendar with Discord timestamps
- Server-specific teams (multi-guild support)

**Technical Details:**
- Professional visualizations using matplotlib with dark mode theme
- Live data with background caching (bounded TTLCache: maxsize=50, ttl=7 days)
- Parallel subsession fetching (semaphore-limited, 10 concurrent) for meta analysis
- Adaptive rate limiting with tenacity retry/backoff (exponential + jitter)
- Team query optimization: JOIN + GROUP BY (was COUNT subquery)
- Team menu pagination for lists > 25 items
- Optional feature - only enabled if credentials provided
- Zero LLM cost - pure API calls
- Encrypted credential storage using Fernet

## Setup Instructions

### 1. Install Dependencies (WSL2 Debian)

Already done if you followed the initial setup.

### 2. Configure Environment

Edit your .env file:

```bash
nano .env
```

**Required Settings:**
- DISCORD_TOKEN: Your Discord bot token
- OPENROUTER_API_KEY: Your OpenRouter API key
- TAVILY_API_KEY: Your Tavily search API key
- MODEL_NAME: LLM model for chat (recommended: deepseek/deepseek-chat)
- POSTGRES_PASSWORD: Choose a secure database password

**Optional Rate Limiting:**
- MAX_TOKENS_PER_REQUEST: Max tokens per request (default: 1000)
- HOURLY_TOKEN_LIMIT: Max tokens per user per hour (default: 10000)
- MAX_CONTEXT_TOKENS: Max context size (default: 4000)
- MAX_CONCURRENT_REQUESTS: Simultaneous requests per user (default: 3)
- MESSAGE_COOLDOWN: Seconds between messages (default: 3)
- MAX_MESSAGES_PER_MINUTE: Messages per minute per user (default: 10)
- MAX_INPUT_LENGTH: Max message length in characters (default: 2000)
- FACT_CHECK_COOLDOWN: Seconds between fact-checks (default: 300)
- FACT_CHECK_DAILY_LIMIT: Fact-checks per day per user (default: 10)
- SEARCH_HOURLY_LIMIT: Web searches per hour (default: 5)
- SEARCH_DAILY_LIMIT: Web searches per day (default: 20)

**Optional Cost & Display:**
- COST_ALERT_THRESHOLD: Monthly cost alert threshold in dollars (default: 1.00)
- VIZ_COLORBLIND_MODE: Enable Okabe-Ito colorblind-friendly palette (default: false)

**Optional iRacing Integration:**

To enable iRacing features with encrypted credentials:

1. See [CREDENTIALS_SETUP.md](docs/guides/CREDENTIALS_SETUP.md) for detailed instructions
2. Quick start:
   ```bash
   docker-compose build bot
   docker-compose run --rm bot python encrypt_credentials.py
   docker-compose up -d bot
   ```

Credentials are encrypted using Fernet symmetric encryption and never stored in plaintext.

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

- Mention @WompBot, say "wompbot", or use "!wb" to chat with the bot
- !ping: Check bot latency
- !wompbot help or /help: Show all commands
- Share images, GIFs, or videos and ask "what's this?" for analysis

### AI Tools (via natural language or prefix commands)

Natural language (mention wompbot):
- "wompbot convert 100 USD to EUR": Currency conversion
- "wompbot what time is it in Tokyo?": Timezone lookup
- "wompbot define serendipity": Dictionary definitions
- "wompbot roll a d20": Random dice/coin
- "wompbot what's the weather?": Weather lookup
- "wompbot translate hello to Spanish": Translation

Prefix commands (faster, no LLM cost):
- `!convert 100 USD EUR`: Currency conversion
- `!define serendipity`: Dictionary definition
- `!weather London`: Current weather
- `!time Tokyo`: Time in timezone
- `!roll d20` or `!roll coin`: Dice/coin
- `!movie Inception`: Movie/TV info
- `!stock AAPL` or `!stock Microsoft`: Stock/crypto price
- `!translate es Hello`: Translate text

### Weather and Computational

- "wompbot weather [location]": Get weather with visualization
- "wompbot forecast [location]": Get 5-day forecast
- !weatherset <location> [units]: Set your default location
- !weatherclear: Clear saved weather preference
- "wompbot [math question]": Ask Wolfram Alpha
- "wompbot show me a chart of...": Create visualizations

### Claims and Receipts

- !receipts [@user] [keyword]: View tracked claims (alias: !claims)
- !verify <id> <status> [notes]: Verify a claim

### Quotes

- React with cloud emoji to save a quote
- !quotes [@user]: View saved quotes

### Fact-Checking

- React with warning emoji to trigger fact-check

### Chat Statistics

- /stats_server [days|date_range]: Network graph and interaction stats
- /stats_topics [days|date_range]: Trending keywords
- /stats_primetime [@user] [days|date_range]: Activity heatmaps
- /stats_engagement [@user] [days|date_range]: Engagement metrics
- !refreshstats: (Admin) Manually refresh cache

### Hot Takes

- !hottakes [type] [days]: View leaderboards (alias: !ht)
- !myht: Your personal hot takes stats
- !vindicate <id> <status> [notes]: (Admin) Mark vindication status

### Reminders

- !remind <time> <message> [recurring]: Set reminder
- !reminders: View active reminders
- !cancelremind <id>: Cancel a reminder

### Events

- !event <name> <date> [description] [reminders]: Schedule event
- !events [limit]: View upcoming events
- !cancelevent <id>: Cancel event

### Yearly Wrapped

- /wrapped [year] [user]: View yearly summary

### Quote of the Day

- !qotd [mode]: View featured quotes

### Debate Scorekeeper

- /debate_start <topic>: Start tracking debate
- !debate_end: End debate and show analysis (alias: !de)
- !debate_stats [user]: View debate statistics (alias: !ds)
- !debate_lb: Top debaters (alias: !dlb)
- !debate_review <file>: Analyze uploaded transcript (alias: !dr)
- !debate_profile [@user]: View argumentation profile card (alias: !dp)

### Utility

- !whoami: Show your Discord information
- !personality <mode>: Change bot personality (default/concise/bogan) - Admin only
- /set_timezone <timezone>: Set guild-level timezone for reminders and events

### iRacing Integration

**Driver Stats:**
- /iracing_link <name>: Link Discord to iRacing account
- /iracing_profile [name]: View driver profile
- /iracing_compare_drivers <driver1> <driver2> [category]: Compare drivers
- /iracing_history [name] [category] [days]: Rating progression
- /iracing_server_leaderboard [category]: Server rankings
- /iracing_results [name]: Recent race results

**Series and Schedule:**
- /iracing_meta <series> [season] [week] [track]: Best cars for series
- /iracing_win_rate <series> [season]: Win rates by car
- /iracing_schedule [series] [category] [week]: View schedules
- /iracing_series_popularity [time_range]: Popular series charts
- /iracing_season_schedule <series> [season]: Full season rotation
- /iracing_timeslots <series> [week]: Race session times
- /iracing_upcoming_races [hours] [category]: Upcoming races

**Team Management:**
- /iracing_team_create <name> <tag> [description]: Create team
- /iracing_team_invite <team_id> <member> [role]: Invite member
- /iracing_team_leave <team_id>: Leave team
- /iracing_team_info <team_id>: View team details
- /iracing_team_list: List all teams
- /iracing_my_teams: Your teams
- /iracing_event_create <team_id> <name> <type> <time> [duration] [series] [track]: Schedule event
- /iracing_team_events <team_id>: View events
- /iracing_event_availability <event_id> <status> [notes]: Mark availability
- /iracing_event_roster <event_id>: View driver availability

Note: The iRacing client uses adaptive rate limiting with gentle retries after 429 responses while keeping commands snappy at full speed within API limits.

For pre-caching before broadcasts or league nights, run:
```bash
docker-compose exec bot python -m bot.scripts.warm_iracing_cache
```
Add --limit N to test with a subset or --sleep 1.0 to slow requests.

### User Analytics

- !stats [@user]: View user statistics
- !search <query>: Manual web search
- !analyze [days]: (Admin) Analyze behavior patterns
- !refreshstats: (Admin) Refresh stats cache

### Tool Prefix Commands

These commands work without LLM processing (faster and zero token cost):

- `!convert <amount> <from> <to>`: Currency conversion (e.g., `!convert 100 USD EUR`)
- `!define <word>`: Dictionary definition (e.g., `!define serendipity`)
- `!weather [location]`: Current weather (e.g., `!weather London`, `!weather spokane wa`)
- `!time [timezone]`: Current time (e.g., `!time Tokyo`, `!time EST`)
- `!roll <dice>`: Roll dice (e.g., `!roll d20`, `!roll 2d6+5`, `!roll coin`)
- `!movie <title>`: Movie/TV info (e.g., `!movie Inception`)
- `!stock <symbol or name>`: Stock/crypto price with history charts (e.g., `!stock AAPL`, `!stock TSLA 1 year`, `!stock NVDA 3m candle`)
- `!translate <lang> <text>`: Translate text (e.g., `!translate es Hello`, `!translate en Bonjour`, `!translate fi-en moi`)
- `!wiki <topic>`: Wikipedia summary (e.g., `!wiki Albert Einstein`)
- `!wa <query>`: Wolfram Alpha calculations and queries (e.g., `!wa 2+2`, `!wa convert 100 F to C`)
- `!yt <query>`: YouTube search (e.g., `!yt rickroll`)

## Privacy Features

GDPR-compliant privacy controls using an opt-out model.

**Legal Basis:**

Data processing operates under Legitimate Interest (GDPR Art. 6.1.f). WompBot collects data by default to provide conversational AI with context awareness and personalization. Users can opt out at any time.

**Default Behavior:**

All users are opted-in by default for:
- Message history storage
- Behavioral profiling (tone, style, profanity levels)
- Personalized responses based on context
- Full access to all bot features

**User Privacy Commands:**

- /wompbot_optout: Opt out of data collection
- /download_my_data: Export all your data (GDPR Art. 15)
- /delete_my_data: Request deletion with 30-day grace period (GDPR Art. 17), includes cancel option
  - Warning: Currently deletes messages, claims, quotes, reminders, events - does not delete user_behavior, search_logs, or debate records

**Compliance Status:**

See [GDPR Compliance Manual](docs/compliance/GDPR_COMPLIANCE.md) for full details on implemented controls and known gaps.

**When Opted Out:**

- Message content and usernames are redacted before storage
- Messages flagged as opted-out
- Excluded from behavioral profiling
- Not included in conversation context or LLM prompts
- Bot still responds but without personalization

**Background Jobs:**

Background tasks respect opt-out status and rate limits. Scheduled tasks persist their last successful run in job_last_run table. On startup, each loop checks the stored timestamp and skips work until the interval elapses. This prevents duplicate GDPR cleanup or iRacing snapshots after restarts while keeping schedules predictable.

New members automatically receive a welcome DM outlining privacy commands and opt-out options. Set PRIVACY_DM_NEW_MEMBERS=0 to disable.

## Behavior Analysis

Weekly or on-demand analysis tracks profanity frequency, conversational tone, honesty patterns, and communication style. Use the !analyze command to run analysis.

## Documentation

Comprehensive guides are available in the docs directory.

**Feature Documentation:**
- [Conversational AI](docs/features/CONVERSATIONAL_AI.md) - Personality modes, LLM configuration
- [Media Analysis](docs/features/MEDIA_ANALYSIS.md) - Images, GIFs, YouTube, video transcription
- [LLM Tools](docs/features/LLM_TOOLS.md) - 26 available tools, currency conversion, weather
- [Claims Tracking](docs/features/CLAIMS_TRACKING.md) - Auto-detection, edit tracking
- [Fact-Checking](docs/features/FACT_CHECK.md) - Web search, verdict system
- [Quotes System](docs/features/QUOTES.md) - Emoji reactions, context
- [User Analytics](docs/features/USER_ANALYTICS.md) - Behavior analysis
- [Chat Statistics](docs/features/CHAT_STATISTICS.md) - Network graphs, topics
- [Hot Takes Leaderboard](docs/features/HOT_TAKES.md) - Controversy tracking
- [Reminders](docs/features/REMINDERS.md) - Natural language parsing
- [Event Scheduling](docs/features/EVENTS.md) - Scheduled events
- [iRacing Integration](docs/features/IRACING.md) - Driver stats, teams
- [RAG System](docs/features/RAG_SYSTEM.md) - Memory architecture
- [Trivia System](docs/features/TRIVIA.md) - LLM-powered quiz games
- [Debate Scorekeeper](docs/features/DEBATE.md) - Debate analysis and scoring
- [Bug Tracking](docs/features/BUG_TRACKING.md) - Admin bug tracking system

**Configuration and Development:**
- [Configuration Guide](docs/CONFIGURATION.md) - All settings and variables
- [Development Guide](docs/DEVELOPMENT.md) - Adding features, migrations
- [Cost Optimization](docs/COST_OPTIMIZATION.md) - Hybrid detection

**Guides:**
- [Encrypted Credentials Setup](docs/guides/CREDENTIALS_SETUP.md) - Secure workflow
- [iRacing Testing Checklist](docs/guides/IRACING_TESTING.md) - Validation steps

**Compliance and Security:**
- [GDPR Compliance Manual](docs/compliance/GDPR_COMPLIANCE.md) - Data rights and flows
- [GDPR Self-Attestation](docs/compliance/GDPR_SELF_ATTESTATION.md) - Server admin statement
- [Security and GDPR Release Notes](docs/compliance/SECURITY_AND_GDPR_UPDATE.md) - Hardening release
- [Security Audit 2025](docs/compliance/SECURITY_AUDIT_2025.md) - Findings and remediation

## Database Schema

**Core Tables:**
- messages: All Discord messages with opt-out flags and guild_id
- user_profiles: User metadata and message counts (global)
- user_behavior: Analysis results with guild_id
- search_logs: Web search history
- job_last_run: Background job timestamps
- claims: Tracked claims with edit/delete history and guild_id
- hot_takes: Controversial claims with vindication and guild_id
- quotes: Saved quotes with reaction counts and guild_id
- claim_contradictions: Detected contradictions with guild_id
- fact_checks: Fact-check results with sources and guild_id
- reminders: Context-aware reminders with guild_id
- events: Scheduled events with guild_id
- debates: Tracked debates with guild_id
- debate_participants: Individual participant records

**Analytics Tables:**
- stats_cache: Pre-computed statistics with guild_id
- message_interactions: Network graph data with guild_id
- message_embeddings: RAG vector embeddings
- embedding_queue: Background processing queue
- conversation_summaries: AI-generated summaries with guild_id
- user_facts: Learned facts about users with guild_id
- topic_snapshots: Trending topics over time

**Integration Tables:**
- weather_preferences: User weather locations
- iracing_links: Discord to iRacing mappings
- iracing_teams: Racing team metadata with guild_id
- iracing_team_members: Team rosters with roles
- iracing_team_events: Scheduled team events with guild_id
- iracing_driver_availability: Driver availability per event
- iracing_stint_schedule: Driver stint rotations
- iracing_participation_history: Daily participation snapshots

**Privacy and Compliance Tables:**
- user_consent: GDPR consent tracking with guild_id
- data_audit_log: Complete audit trail (7-year retention)
- data_export_requests: Data export tracking
- data_deletion_requests: Deletion with 30-day grace period
- data_retention_config: Configurable retention policies

**Session Persistence Tables:**
- active_trivia_sessions: Trivia game state (survives bot restarts)
- active_debates: Debate session state (survives bot restarts)

**Guild Configuration Tables:**
- guild_config: Guild-level settings (timezone, etc.)

**Rate Limiting and Cost Tables:**
- rate_limits: Token usage tracking (1-hour rolling window)
- api_costs: LLM API cost tracking with model breakdowns
- cost_alerts: $1 spending alert tracking
- feature_rate_limits: Feature-specific usage tracking

**Guild Isolation:**

18 tables have guild_id columns with composite indexes for 10x faster queries. See [Guild Isolation Documentation](docs/GUILD_ISOLATION.md) for technical details.

## Costs

### Model Pricing

**DeepSeek Chat:**
- Very cost-effective compared to other models
- Roughly $0.001-0.005 per message depending on length
- Excellent quality/cost ratio

**Search (Tavily):**
- Free up to 1,000 searches per month
- About $0.001 per search if exceeded
- Rate limited: 5 per hour, 20 per day per user

**Total Monthly Estimate (with rate limits):**
- Light usage: $5-10/month
- Moderate usage: $15-25/month
- Heavy usage: $30-50/month

### Cost Tracking and Alerts

**Automatic Cost Monitoring:**
- Real-time token usage tracking from API responses
- Model-specific pricing calculations (updated for current models)
- Configurable spending alerts sent via direct message (COST_ALERT_THRESHOLD env var, default $1)
- Beautiful embeds with cost breakdown by model
- Database tracking in api_costs and cost_alerts tables

**Cost Control Features:**
- Token limits prevent runaway spending
- Feature-specific rate limits for expensive operations
- Command cooldowns on costly commands
- Concurrent request limiting
- Context token hard cap (4000 tokens max)
- Message frequency controls

### Other Features

**Zero-Cost Features:**
- Event Scheduling and Reminders (pure time parsing)
- Quote of the Day (database queries)
- Yearly Wrapped (database aggregation)
- Chat Statistics (network graphs, TF-IDF)
- iRacing Integration (API calls only)
- Currency Conversion (Frankfurter API - free)
- YouTube Transcripts (YouTube API - free)

**Media Analysis Costs:**
- Images: Vision model tokens only (~$0.001-0.005 per image)
- GIFs: Vision model tokens only
- YouTube with transcript: Vision tokens + transcript (nearly free)
- Video attachments: Whisper API (~$0.006/minute of audio) + vision tokens

**Variable Cost Features:**
- Debate Analysis: $0.01-0.05 per debate
- Hot Takes Scoring: $0.005 per analysis (only high-engagement claims)
- User Behavior Analysis: $0.005 per user

### Cost Optimization Strategy

- Dual-model architecture: cheap model for chat, expensive only for fact-checking
- Hot Takes use hybrid detection (pattern matching first, LLM only for high engagement)
- Debate Scorekeeper only uses LLM when ending debates
- Background stat updates use zero LLM (pure SQL and TF-IDF)

## Troubleshooting

**Bot not responding:**
```bash
docker-compose logs bot
```

**Database connection issues:**
```bash
docker-compose restart postgres
docker-compose logs postgres
```

**Reset everything:**
```bash
docker-compose down -v
docker-compose up -d
```

## Model Configuration

WompBot uses DeepSeek via OpenRouter for high-quality conversational AI:

```env
# General chat - Fast, high-quality responses
MODEL_NAME=deepseek/deepseek-chat
```

### Why DeepSeek?

- Excellent quality/cost ratio
- Fast, accurate, conversational responses
- Very cost-effective for high-volume usage

### Alternative Models (via OpenRouter)

- deepseek/deepseek-chat (Default - excellent balance)
- anthropic/claude-3.5-sonnet (Higher accuracy, more expensive)
- anthropic/claude-3-haiku (Fast, economical)
- google/gemini-2.0-flash-exp (Fast alternative)
- anthropic/claude-3-opus (Maximum accuracy, expensive)
- Other models not recommended for fact-checking

## Personality System

WompBot has three personality modes available via the !personality command (admin only).

**Default (Conversational):**
- Conversational and helpful responses
- Provides detailed information with personality
- Balanced tone suitable for most interactions
- Responds with 2-4 sentences typically
- Adapts to user's communication style

**Concise (Brief):**
- Very brief responses (1-2 sentences maximum)
- Gets straight to the point without elaboration
- Simple acknowledgments for statements
- No unnecessary explanations or context
- Ideal for quick information or when you prefer minimal text
- Example responses: "Yep.", "4", "Trump won the 2024 election.", "docker restart container_name"

**Bogan (Australian):**
- Full Australian slang and casual language
- Working-class Aussie dialect and expressions
- Laid-back, friendly tone like chatting at the pub
- Uses terms like "yeah nah", "mate", "she'll be right"
- Still helpful and informative, just with personality
- Natural variation in greetings and responses to sound authentic

The personality setting is per-server and persists in the database.

### Trivia Games

LLM-powered trivia with multiple categories and difficulty levels.

**Commands:**
- `/trivia_start [category] [difficulty] [questions]`: Start a trivia game
- `!triviastop`: End current trivia session
- `!triviastats [user]`: View your trivia statistics
- `!trivialeaderboard [days]`: Server trivia rankings (alias: `!tlb`)

**Features:**
- 20+ categories: Science, History, Geography, Sports, Entertainment, etc.
- Three difficulty levels: Easy, Medium, Hard
- Point system with streaks and bonuses
- Configurable question count (5-20 per session)
- 30-second timer per question with early answer bonus
- Server-specific leaderboards
- Sessions persist to database (survive bot restarts)

### Bug Tracking

Report and track bugs with an integrated bug tracking system.

**Commands:**
- `!bug <description>`: Report a new bug
- `!bugfix <bug_id> [resolution]`: Mark bug as resolved
- `!bugs [status]`: List all bugs (all/open/resolved)

### User Facts (Remember This)

- `!myfacts`: View all stored facts about you
- `!forget <id>`: Delete a specific stored fact
- Or say "@WompBot remember that I prefer Python" to store a fact

### Polls

- `/poll`: Create a poll with button voting (single or multi-choice)
- `!pollresults <id>`: View poll results card
- `!pollclose <id>`: Close a poll (creator only)

### Who Said It? Game

- `!whosaidit [rounds]`: Start a "Who Said It?" game with real server quotes
- `!wsisskip`: Skip current round and reveal answer
- `!wsisend`: End game early and show scores

### Devil's Advocate

- `!da [topic]`: Start a devil's advocate debate session
- `!daend`: End the session and show exchange count

### Channel Jeopardy

- `!jeopardy [categories] [clues_per]`: Start Jeopardy with server-inspired categories
- `!jpick [category] [value]`: Select a clue from the board
- `!jpass`: Skip current clue and reveal answer
- `!jend`: End game early and show final scores

### Message Scheduling

- `!schedule <message> <minutes/hours/days>`: Schedule a message to be sent later
- `!scheduled`: View your pending scheduled messages
- `!cancelschedule <id>`: Cancel a scheduled message (creator only)

### RSS Feed Monitoring (Admin Only)

- `!feedadd <url> <channel>`: Add an RSS feed to monitor
- `!feedremove <id>`: Remove a feed
- `!feeds`: List all monitored feeds

### GitHub Monitoring (Admin Only)

- `!ghwatch <repo> <type> <channel>`: Watch a GitHub repo (releases/issues/prs/all)
- `!ghunwatch <id>`: Stop watching a repo
- `!ghwatches`: List watched repos

### Watchlists (Admin Only)

- `!wladd <symbols> [threshold] [channel]`: Add stock/crypto symbols to watchlist
- `!wlremove <symbol>`: Remove a symbol
- `!watchlist`: View the server's watchlist (alias: `!wl`)

### Admin

- `!setadmin <@user>`: Add a server admin
- `!removeadmin <@user>`: Remove a server admin
- `!admins`: List server admins

## Upcoming Features

- Birthday Tracking: Automatic birthday reminders and celebrations
- Voice Channel Stats: Track time spent in voice channels
- Custom Commands: User-created text commands and responses

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

For detailed development guide, see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

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
│   ├── guides/              # Setup and testing guides
│   ├── compliance/          # GDPR and security docs
│   ├── CONFIGURATION.md     # Configuration guide
│   ├── DEVELOPMENT.md       # Development guide
│   └── COST_OPTIMIZATION.md # Cost optimization strategies
│
├── sql/
│   ├── init.sql             # Database schema
│   ├── 13_gdpr_trim.sql     # GDPR simplification migration
│   ├── 14_guild_timezone.sql # Guild timezone support
│   └── 15_session_persistence.sql # Trivia/debate session persistence
│
└── bot/
    ├── main.py                  # Main bot logic and initialization
    ├── llm.py                   # OpenRouter LLM client with tool calling
    ├── database.py              # PostgreSQL interface with connection pooling
    ├── search.py                # Tavily web search
    ├── rag.py                   # RAG system for intelligent memory
    ├── compression.py           # LLMLingua semantic compression
    ├── cost_tracker.py          # API cost tracking and spending alerts
    ├── backup_manager.py        # Automated database backups
    ├── logging_config.py        # Centralized logging
    ├── weather.py               # OpenWeatherMap API client
    ├── wolfram.py               # Wolfram Alpha API client
    ├── viz_tools.py             # Visualization engine
    ├── tool_executor.py         # LLM tool execution handler (with Redis caching)
    ├── llm_tools.py             # LLM tool definitions
    ├── redis_cache.py           # Redis caching utility with graceful fallback
    ├── constants.py             # Centralized constants (timezones, languages, tickers, self-contained tools)
    ├── data_retriever.py        # Database query engine
    ├── media_processor.py       # Media analysis (images, GIFs, videos, YouTube)
    ├── self_knowledge.py        # Bot self-awareness (reads own docs)
    ├── iracing_client.py        # iRacing API client
    ├── iracing_viz.py           # iRacing visualizations
    ├── iracing_graphics.py      # iRacing chart generation
    ├── requirements.txt         # Python dependencies
    ├── handlers/
    │   ├── conversations.py     # Message handling and LLM conversations
    │   └── events.py            # Discord event handlers
    ├── commands/
    │   ├── prefix_commands.py   # Prefix commands (~55 commands: !ping, !stats, !receipts, !remind, etc.)
    │   └── slash_commands.py    # Slash commands (~43 commands: /help, /wrapped, /stats_*, /iracing_*, etc.)
    ├── features/
    │   ├── claims.py            # Claims tracking system
    │   ├── fact_check.py        # Fact-check feature
    │   ├── chat_stats.py        # Chat statistics
    │   ├── hot_takes.py         # Hot takes leaderboard
    │   ├── reminders.py         # Context-aware reminders
    │   ├── events.py            # Event scheduling
    │   ├── gdpr_privacy.py      # GDPR compliance system
    │   ├── iracing.py           # iRacing integration
    │   ├── iracing_teams.py     # iRacing team management
    │   ├── iracing_meta.py      # iRacing meta analysis (best cars/tracks)
    │   ├── team_menu.py         # Team menu with pagination
    │   ├── yearly_wrapped.py    # Yearly summaries
    │   ├── quote_of_the_day.py  # Featured quotes system
    │   ├── claim_detector.py    # Fast regex pre-filter for claims
    │   ├── trivia.py            # LLM-powered trivia games
    │   ├── help_system.py       # Comprehensive help system
    │   ├── admin_utils.py       # Admin permission utilities
    │   ├── debate_scorekeeper.py # Debate tracking and analysis
    │   └── bug_tracking.py      # Bug reporting system
    ├── prompts/
    │   ├── system_prompt.txt        # Default personality
    │   ├── system_prompt_concise.txt # Concise personality
    │   └── system_prompt_bogan.txt   # Bogan personality
    └── tasks/
        └── background_jobs.py   # Scheduled background tasks
```

## Support

Check logs for errors:
```bash
docker-compose logs -f
```

For issues with specific features, check the relevant documentation in the docs directory.
