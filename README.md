# WompBot - Discord Bot

A Discord bot powered by DeepSeek through OpenRouter, featuring intelligent conversation memory (RAG), media analysis (images, GIFs, YouTube transcripts, video transcription), 18 LLM tools, web search integration, claims tracking, user behavior analysis, and iRacing integration.

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
- Cost tracking with $1 spending alerts sent via DM

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

### LLM Tools (18 Available)

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

**Utility:**
- `random_choice` - Dice rolls, coin flips, random picks
- `create_reminder` - Set reminders

**Visualization:**
- `create_bar_chart`, `create_line_chart`, `create_pie_chart`, `create_table`
- Natural language: "show me a chart of who talks the most"

### Weather and Computational Tools

The bot can invoke tools through LLM function calling to create visualizations and fetch data.

**Weather Features:**
- Beautiful weather cards with dual-unit display (Celsius/Fahrenheit)
- Save your default location with /weather_set
- 5-day forecasts available
- Just say "wompbot weather" after setting your preference

**Wolfram Alpha Integration:**
- Mathematical calculations and unit conversions
- Factual queries about math, science, geography
- Free tier: 2,000 queries per month

**Data Visualizations:**
- Bar charts, line charts, pie charts, tables, comparison charts
- Natural language requests: "show me a chart of who talks the most"
- Zero LLM cost - tool outputs speak for themselves

### Claims and Accountability

The bot automatically detects when people make bold predictions, factual claims, or guarantees.

**Features:**
- LLM-powered claim detection
- Edit tracking preserves original text
- Deletion tracking saves deleted claims
- Contradiction detection identifies when users contradict previous claims
- Use /receipts to view tracked claims for any user
- Verify claims as true/false/mixed with /verify_claim

### Quotes System

React with a cloud emoji to any message to save it as a memorable quote.

**Commands:**
- /quotes to view saved quotes for a user
- Tracks reaction counts and timestamps
- Auto-categorizes quotes by context

### Fact-Check Feature

React with a warning emoji to trigger an automated fact-check.

**How it works:**
- Uses DeepSeek for high accuracy
- Automatically searches 7 web sources using Tavily
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
- View your personal stats with /mystats_hottakes

### Context-Aware Reminders

Natural language reminders that link back to the original conversation.

**Features:**
- Natural language parsing: "in 5 minutes", "tomorrow at 3pm", "next Monday"
- Context links jump back to the original message
- Delivery options: DM or channel mention
- Recurring support: daily, weekly, or custom intervals
- Zero LLM cost - pure time parsing
- Background checker runs every minute

### Event Scheduling

Schedule events with automatic periodic reminders.

**Features:**
- Natural language time input: "Friday at 8pm", "in 3 days", "October 20"
- Configurable reminder intervals (default: 1 week, 1 day, 1 hour before)
- Public channel announcements with Discord timestamps
- Event management: list upcoming events, cancel by ID
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
- Zero LLM cost - pure database queries

### Quote of the Day

Highlight the best quotes from your server.

**Modes:**
- Daily, Weekly, Monthly, All-Time Greats, or Random
- Smart selection based on reaction counts
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
- Live data with background caching for performance
- Adaptive rate limiting with gentle retries
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
- MODEL_NAME: LLM model for chat (default: anthropic/claude-3.7-sonnet)
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
- /weather_set <location> [units]: Set your default location
- /weather_clear: Clear saved weather preference
- /weather_info: View current preference
- "wompbot [math question]": Ask Wolfram Alpha
- "wompbot show me a chart of...": Create visualizations

### Claims and Receipts

- /receipts [@user] [keyword]: View tracked claims
- /verify_claim <id> <status> [notes]: Verify a claim

### Quotes

- React with cloud emoji to save a quote
- /quotes [@user]: View saved quotes

### Fact-Checking

- React with warning emoji to trigger fact-check

### Chat Statistics

- /stats_server [days|date_range]: Network graph and interaction stats
- /stats_topics [days|date_range]: Trending keywords
- /stats_primetime [@user] [days|date_range]: Activity heatmaps
- /stats_engagement [@user] [days|date_range]: Engagement metrics
- !refreshstats: (Admin) Manually refresh cache

### Hot Takes

- /hottakes [type] [days]: View leaderboards
- /mystats_hottakes: Your personal stats
- /vindicate <id> <status> [notes]: (Admin) Mark vindication status

### Reminders

- /remind <time> <message> [recurring]: Set reminder
- /reminders: View active reminders
- /cancel_reminder <id>: Cancel a reminder

### Events

- /schedule_event <name> <date> [description] [reminders]: Schedule event
- /events [limit]: View upcoming events
- /cancel_event <id>: Cancel event

### Yearly Wrapped

- /wrapped [year] [user]: View yearly summary

### Quote of the Day

- /qotd [mode]: View featured quotes

### Debate Scorekeeper

- /debate_start <topic>: Start tracking debate
- /debate_end: End debate and show analysis
- /debate_stats [user]: View debate statistics
- /debate_leaderboard: Top debaters
- /debate_review <file>: Analyze uploaded transcript

### Utility

- /whoami: Show your Discord information
- /personality <mode>: Change bot personality (default/concise/bogan) - Admin only

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

- !convert <amount> <from> <to>: Currency conversion (e.g., `!convert 100 USD EUR`)
- !define <word>: Dictionary definition (e.g., `!define serendipity`)
- !weather [location]: Current weather (e.g., `!weather London`)
- !time [timezone]: Current time (e.g., `!time Tokyo`, `!time EST`)
- !roll <dice>: Roll dice (e.g., `!roll d20`, `!roll 2d6+5`, `!roll coin`)
- !movie <title>: Movie/TV info (e.g., `!movie Inception`)
- !stock <symbol or name>: Stock/crypto price (e.g., `!stock AAPL`, `!stock Microsoft`, `!stock Bitcoin`)
- !translate <lang> <text>: Translate text (e.g., `!translate es Hello world`)

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
- /delete_my_data: Request deletion with 30-day grace period (GDPR Art. 17)
  - Warning: Currently deletes messages, claims, quotes, reminders, events - does not delete user_behavior, search_logs, or debate records
- /my_privacy_status: View current privacy status
- /privacy_policy: View complete privacy policy

**Admin Privacy Commands:**

- /privacy_settings: Live overview of consent counts and stored data
- /privacy_audit: Download JSON report of privacy posture

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

Weekly or on-demand analysis tracks profanity frequency, conversational tone, honesty patterns, and communication style. Use the /analyze command to run analysis.

## Documentation

Comprehensive guides are available in the docs directory.

**Feature Documentation:**
- [Conversational AI](docs/features/CONVERSATIONAL_AI.md) - Personality modes, LLM configuration
- [Media Analysis](docs/features/MEDIA_ANALYSIS.md) - Images, GIFs, YouTube, video transcription
- [LLM Tools](docs/features/LLM_TOOLS.md) - 18 available tools, currency conversion, weather
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
- data_breach_log: Security incident tracking
- privacy_policy_versions: Policy version history

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
- Model-specific pricing calculations
- $1 spending alerts sent via direct message
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

WompBot has three personality modes available via the /personality command (admin only).

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

## Upcoming Features

- Polls and Voting: Create polls with slash commands and reaction tracking
- Birthday Tracking: Automatic birthday reminders and celebrations
- Trivia Games: Quiz system with categories and leaderboards
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
│   └── init.sql             # Database schema
│
└── bot/
    ├── main.py                  # Main bot logic and initialization
    ├── llm.py                   # OpenRouter LLM client with tool calling
    ├── database.py              # PostgreSQL interface with connection pooling
    ├── search.py                # Tavily web search
    ├── rag.py                   # RAG system for intelligent memory
    ├── compression.py           # LLMLingua semantic compression
    ├── backup_manager.py        # Automated database backups
    ├── logging_config.py        # Centralized logging
    ├── weather.py               # OpenWeatherMap API client
    ├── wolfram.py               # Wolfram Alpha API client
    ├── viz_tools.py             # Visualization engine
    ├── tool_executor.py         # LLM tool execution handler
    ├── llm_tools.py             # LLM tool definitions
    ├── data_retriever.py        # Database query engine
    ├── media_processor.py       # Media analysis (images, GIFs, videos, YouTube)
    ├── iracing_client.py        # iRacing API client
    ├── iracing_viz.py           # iRacing visualizations
    ├── requirements.txt         # Python dependencies
    ├── handlers/
    │   ├── conversations.py     # Message handling and LLM conversations
    │   └── events.py            # Discord event handlers
    ├── commands/
    │   ├── prefix_commands.py   # Prefix commands (!ping, !stats)
    │   └── slash_commands.py    # Slash commands (/help, /wrapped)
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
    │   └── yearly_wrapped.py    # Yearly summaries
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
