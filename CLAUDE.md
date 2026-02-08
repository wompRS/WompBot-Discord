# WompBot - Project Memory

## What This Is
WompBot is a conversational Discord bot built with Python 3.11, discord.py 2.6.4, PostgreSQL 15 (pgvector), Redis 7, deployed via Docker Compose.

## Quick Architecture

```
Discord message → on_message (events.py) → handle_bot_mention (conversations.py)
  → rate limit check → media extraction (media_processor.py)
  → get conversation context (database.py + rag.py)
  → compress history if needed (compression.py / LLMLingua)
  → should_search? (llm.py) → web search if yes (search.py)
  → select tools by intent (_select_tools_for_message)
  → call LLM via OpenRouter (llm.py)
  → execute tool calls if any (tool_executor.py)
  → synthesis pass for charts (always add text with viz)
  → send response → track claims → generate embeddings (background)
```

## Key Files & What They Do

### Core Pipeline (edit these carefully)
- `bot/handlers/conversations.py` — Main message handler, tool selection, synthesis logic, placeholder management; extracted `_execute_tool_calls()` and `_synthesize_tool_response()` helpers (~1200 lines)
- `bot/llm.py` — LLMClient class: system prompt loading, should_search(), generate_response(), simple_completion(), compression (~800 lines)
- `bot/llm_tools.py` — 26 tool definitions (ALL_TOOLS, COMPUTATIONAL_TOOLS lists), DataRetriever class (~850 lines)
- `bot/tool_executor.py` — ToolExecutor: dict registry pattern for tool dispatch, Redis caching for all external APIs, 30s tool timeout (~1800 lines)
- `bot/database.py` — PostgreSQL connection pool, all queries, get_conversation_context() (~1550 lines)
- `bot/constants.py` — Centralized constants: TIMEZONE_ALIASES, LANGUAGE_CODES, STOCK_TICKERS, CRYPTO_TICKERS, SELF_CONTAINED_TOOLS

### Core Support Modules
- `bot/rag.py` — RAG system: embeddings via OpenAI text-embedding-3-small, pgvector similarity search (threshold: 0.55)
- `bot/search.py` — Tavily/Google search, format_results_for_llm() (max 5 results, 200 char snippets)
- `bot/compression.py` — LLMLingua conversation compression (keep_recent=8, min_messages=10)
- `bot/plotly_charts.py` — **Primary chart engine**: Plotly-based charts (bar, line, pie, table, comparison, radar, sankey, heatmap) with premium dark theme, exported via Kaleido
- `bot/card_base.py` — Shared PIL card primitives: draw_rounded_rect, draw_progress_bar, draw_glow_circle, draw_gradient_bg, load_fonts, theme colors. Used by feature-specific card generators.
- `bot/debate_card.py` — PIL-based debate argumentation profile card (purple theme, radar chart, rhetorical breakdown). Uses `card_base.py`.
- `bot/mystats_card.py` — PIL-based personal analytics card (teal/emerald theme, stat badges, progress bars, achievements). Uses `card_base.py`.
- `bot/viz_tools.py` — **Legacy/fallback** matplotlib charts + weather card (PIL-based, kept for weather display)
- `bot/media_processor.py` — Image/video/YouTube frame extraction and analysis
- `bot/cost_tracker.py` — Per-request API cost tracking, configurable threshold via COST_ALERT_THRESHOLD env var
- `bot/weather.py` — OpenWeatherMap integration
- `bot/wolfram.py` — Wolfram Alpha integration
- `bot/self_knowledge.py` — Bot self-awareness responses
- `bot/data_retriever.py` — Database query engine for visualization tools

### Features (bot/features/)
- `claims.py` — 2-stage claim detection (fast pattern → LLM verify)
- `claim_detector.py` — Fast keyword pre-filter for claims
- `fact_check.py` — Emoji-triggered fact checking (requires 2+ sources)
- `hot_takes.py` — 3-stage controversy scoring (pattern → engagement → LLM)
- `chat_stats.py` — Network graphs, topic trends, primetime analysis
- `help_system.py` — Command documentation system (~1570 lines)
- `gdpr_privacy.py` — GDPR compliance: opt-out, data export, deletion requests (simplified: 3 commands, breach/policy versioning removed)
- `reminders.py` — Natural language reminders with context links, guild timezone support via zoneinfo
- `events.py` — Event scheduling with periodic reminders, guild timezone support, creator-only cancellation
- `debate_scorekeeper.py` — Debate tracking with LLM judging, sessions persist to DB (survive restarts)
- `trivia.py` — LLM-powered trivia games, sessions persist to DB (survive restarts)
- `dashboard.py` — Server health dashboard with Plotly charts
- `polls.py` — Poll system with button voting, single/multi-choice, auto-close
- `who_said_it.py` — "Who Said It?" game using real server quotes, GDPR-safe
- `devils_advocate.py` — Devil's advocate debate mode with LLM counter-arguments
- `jeopardy.py` — Channel Jeopardy with server-inspired categories, LLM-generated clues
- `message_scheduler.py` — Message scheduling with abuse prevention limits
- `rss_monitor.py` — RSS feed monitoring with feedparser, admin only
- `github_monitor.py` — GitHub repo monitoring for releases/issues/PRs, admin only
- `watchlists.py` — Shared price watchlists with alerts, admin only
- `yearly_wrapped.py` — Spotify-style yearly summaries
- `quote_of_the_day.py` — Featured quote selection
- `admin_utils.py` — Admin permission utilities
- `iracing.py` — iRacing driver stats and comparisons
- `iracing_teams.py` — iRacing team management
- `iracing_meta.py` — iRacing meta analysis (best cars/tracks), parallel subsession fetching
- `team_menu.py` — Team menu with pagination for lists > 25 items

### Commands
- `bot/commands/slash_commands.py` — All slash commands (~1500 lines)
- `bot/commands/prefix_commands.py` — !stats, !analyze, !search, !refreshstats

### Prompts (gitignored - live config only)
- `bot/prompts/system_prompt.txt` — Default personality (has chart guardrails)
- `bot/prompts/system_prompt_sample.txt` — Template/feyd personality
- `bot/prompts/system_prompt_bogan.txt` — Australian personality
- `bot/prompts/system_prompt_concise.txt` — Brief response mode

### Infrastructure
- `bot/main.py` — Bot initialization, module registration
- `bot/redis_cache.py` — Redis caching with graceful fallback
- `bot/tasks/background_jobs.py` — Scheduled jobs (embedding generation, cleanup)
- `bot/logging_config.py` — Logging setup
- `docker-compose.yml` — 5 services: bot, postgres, redis, postgres-backup, portainer
- `sql/` — 16 SQL files (init.sql + 15 migrations including indexes, rate limiting, GDPR, iRacing, GDPR trim, guild timezone, session persistence)
- `bot/migrations/` — 3 iRacing-specific migration files

### iRacing Subsystem (bot/ root level)
- `bot/iracing_client.py` — iRacing API client with tenacity retry/backoff
- `bot/iracing_viz.py` — iRacing visualizations
- `bot/iracing_graphics.py` — iRacing chart generation
- `bot/iracing_event_commands.py` — Event slash commands
- `bot/iracing_team_commands.py` — Team slash commands
- Features in `bot/features/`: `iracing.py`, `iracing_teams.py`, `iracing_meta.py`, `team_menu.py`

## Tool Architecture

Tools are split into two groups in `llm_tools.py`:
- **COMPUTATIONAL_TOOLS** — Non-visual tools (search, weather, wolfram, stocks, etc.)
- **ALL_TOOLS** — Computational + visualization tools (charts, tables)

`_select_tools_for_message()` in conversations.py only passes visualization tools when the message contains viz-intent keywords (chart, graph, plot, visualize, etc.). This prevents the LLM from generating charts for knowledge questions.

**Tool dispatch** uses a dict registry pattern in `tool_executor.py` (replaced the previous if-elif chain). Tool execution has a 30-second timeout via `asyncio.wait_for`.

**simple_completion()** in `LLMClient` provides a lightweight method for single-prompt LLM calls — used by `claims.py` and `fact_check.py` instead of raw `requests.post()`.

**Self-contained tools** are tracked in `bot/constants.py` via the `SELF_CONTAINED_TOOLS` set.

## Environment Variables (Key Ones)

```
# Required
DISCORD_TOKEN, OPENROUTER_API_KEY, POSTGRES_PASSWORD

# LLM (all via OpenRouter)
MODEL_NAME=deepseek/deepseek-chat          # Primary chat model
VISION_MODEL=openai/gpt-4o-mini            # Image analysis
FACT_CHECK_MODEL=deepseek/deepseek-chat    # Fact checking

# Search
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=...

# Embeddings
OPENAI_API_KEY=...  # For text-embedding-3-small

# Database
DB_HOST=postgres  DB_PORT=5432  DB_NAME=discord_bot
DB_USER=botuser   DB_POOL_MAX=25

# Admin
WOMPIE_USER_ID=...  SUPER_ADMIN_IDS=...  BOT_ADMIN_IDS=...

# Cost & Display
COST_ALERT_THRESHOLD=1.00       # Monthly cost alert threshold in dollars
VIZ_COLORBLIND_MODE=false       # Enable Okabe-Ito colorblind-friendly palette
```

## Database (30+ tables)

Key tables: `messages`, `user_profiles`, `claims`, `fact_checks`, `hot_takes`, `quotes`, `message_embeddings` (vector), `conversation_summaries`, `api_costs`, `rate_limits`, `reminders`, `events`, `iracing_teams`, `gdpr_deletion_requests`, `opt_outs`, `guild_config`, `server_admins`, `stats_cache`, `active_trivia_sessions`, `active_debates`, `user_topic_expertise`

Dropped tables (GDPR trim): `data_breach_log`, `privacy_policy_versions`

Indexes: 11 composite indexes added in `sql/12_missing_indexes.sql`

Migrations:
- `sql/13_gdpr_trim.sql` — Drops 7 GDPR slash commands, removes `data_breach_log` and `privacy_policy_versions` tables
- `sql/14_guild_timezone.sql` — Creates `guild_config` table for guild-level timezone support
- `sql/15_session_persistence.sql` — Creates `active_trivia_sessions` and `active_debates` tables for session persistence across restarts
- `sql/16_new_features.sql` — Creates tables for new features: `user_topic_expertise`, polls, games, scheduling, monitoring

## Important Design Decisions

1. **Intent-based tool filtering** — Viz tools only passed when message has chart keywords. Prevents "what is X" → bar chart bug.
2. **Mandatory chart synthesis** — Charts always get a follow-up LLM call to generate accompanying text.
3. **Self-contained tools** — Most text tools skip synthesis (defined in `SELF_CONTAINED_TOOLS` in `bot/constants.py`). Their output IS the answer.
4. **Search negative filter** — `no_search_patterns` in should_search() blocks web search for conversational/definitional questions the LLM can answer from training data.
5. **Channel semaphore** — asyncio.Semaphore(3) per channel, not a global lock.
6. **HTTP session reuse** — requests.Session() for connection pooling in API clients. Weather and Wolfram use HTTPS.
7. **Truncation notice** — When messages are removed from context, a note is inserted so the LLM knows history was trimmed.
8. **GDPR simplified** — 3 commands only (/wompbot_optout, /download_my_data, /delete_my_data with cancel folded in). Breach logging and policy versioning removed.
9. **Cost tracking** — Every API call tracked with model, tokens, cost. Alert threshold configurable via COST_ALERT_THRESHOLD env var (default $1/month).
10. **Claim detection** — 2-stage: fast regex/keyword filter → LLM verification via `simple_completion()` (saves cost).
11. **Fact-check** — Requires minimum 2 corroborating sources before rendering verdict. Uses `simple_completion()`.
12. **Dict registry for tool dispatch** — `tool_executor.py` maps tool names to handler functions via a dict instead of if-elif chain.
13. **Token estimation** — Uses tiktoken (optional dependency) with fallback to `len/4` (was `len/3.5`). Image tokens estimated at 170 (was 1000).
14. **Tool execution timeout** — 30-second timeout per tool call via `asyncio.wait_for`.
15. **SQL injection prevention** — DataRetriever INTERVAL queries use parameterized `INTERVAL '1 day' * %s` pattern.
16. **Prompt injection defense** — Debate transcripts wrapped in XML tags to prevent prompt injection.
17. **Session persistence** — Trivia and debate sessions persist to database tables, surviving bot restarts.
18. **Guild timezone support** — `/set_timezone` command stores timezone per guild; reminders and events use guild timezone via `zoneinfo`.
19. **Dual chart engine** — Primary: Plotly + Kaleido (premium charts, requires chromium). Fallback: matplotlib (if Plotly fails). Weather card stays PIL-based. Configured in `conversations.py` `get_visualizer()`.
20. **Shared card primitives** — `card_base.py` provides composable PIL drawing utilities (rounded rects, progress bars, glow effects, gradients, fonts). Feature-specific cards import from here rather than duplicating code.

## Build & Deploy

```bash
docker compose up -d --build     # Build and deploy
docker compose logs -f bot       # Watch logs
docker compose restart bot       # Restart bot only
```

## Common Patterns When Editing

- **Adding a new tool**: Define in `llm_tools.py` (add to ALL_TOOLS or COMPUTATIONAL_TOOLS), add handler to dict registry in `tool_executor.py`, add to `SELF_CONTAINED_TOOLS` in `bot/constants.py` if the tool output is the final answer, add to system prompts if needed
- **Changing LLM behavior**: Edit `llm.py` for search/compression logic, `conversations.py` for tool selection/synthesis
- **New slash command**: Add to `commands/slash_commands.py`, register in `main.py`
- **Database changes**: Create new migration file in `sql/`, update `database.py`
- **Prompt changes**: Edit files in `bot/prompts/` (gitignored, only on server)

## Recent Fixes (Session ec0b354)

- Chart-for-knowledge-question bug fixed (3-layer defense: prompt guardrails + intent filtering + mandatory synthesis)
- Search over-triggering fixed (negative pattern filter)
- Chart readability improved (value labels, sizing, multi-color, smart rotation)
- RAG similarity threshold lowered 0.7 → 0.55
- Search result verbosity reduced (5 results, 200 char snippets)
- DataRetriever error handling improved
- Placeholder message flicker fixed (edit instead of delete+create)
- Compression settings tuned (keep_recent=8, min_messages=10)
- Context truncation notice added

## Comprehensive Refactoring (Session 62a1b5e)

### Security
- Weather and Wolfram APIs upgraded to HTTPS
- SQL injection fixed in DataRetriever INTERVAL queries (now uses `INTERVAL '1 day' * %s` parameterized pattern)
- Prompt injection defense added to debate transcripts (wrapped in XML tags)
- Event cancellation requires creator permission (`AND created_by = %s`)

### Bug Fixes
- Hot takes diversity formula fixed (was `/min(total,10)`, now `/max(total,1)`)
- Compression `keep_recent` default fixed: 3 → 8
- Quote of the day uses calendar day boundary, all-time selection weighted by freshness
- Search fetches 5 results (was 7, matched to `format_results_for_llm`)
- Cost tracker pricing updated (removed obsolete models, added current ones, configurable threshold via `COST_ALERT_THRESHOLD` env var)
- Yearly wrapped uses `DENSE_RANK()` for ties
- Recurring reminders fixed: calculate from `last_trigger + interval`, not `now() + interval`

### Architecture
- New `bot/constants.py` centralizes: TIMEZONE_ALIASES, LANGUAGE_CODES, STOCK_TICKERS, CRYPTO_TICKERS, SELF_CONTAINED_TOOLS
- `LLMClient.simple_completion()` — lightweight method used by `claims.py` and `fact_check.py` instead of raw `requests.post()`
- `conversations.py` deduplicated: extracted `_execute_tool_calls()` and `_synthesize_tool_response()` helpers
- `tool_executor.py` uses dict registry pattern instead of if-elif chain
- SHA-256 for cache keys (was MD5)
- Token estimation uses tiktoken (optional) with fallback to `len/4` (was `len/3.5`), image tokens 1000 → 170
- Tool execution has 30s timeout via `asyncio.wait_for`

### GDPR Trim
- Removed 7 commands: /cancel_deletion, /privacy_settings, /privacy_audit, /my_privacy_status, /privacy_policy, /privacy_support, /tos
- Kept 3 commands: /wompbot_optout, /download_my_data, /delete_my_data (with cancel folded in)
- Dropped tables: `data_breach_log`, `privacy_policy_versions`
- Simplified `gdpr_privacy.py` (removed breach logging, policy versioning methods)

### New Features
- Guild-level timezone support: `/set_timezone` command, `guild_config` table, reminders/events use guild timezone via `zoneinfo`
- Trivia and debate sessions persist to database (survive bot restarts) via `active_trivia_sessions` and `active_debates` tables
- Better error messages for reminders (past time, unparseable) and events (invalid dates like "Feb 30")
- Colorblind-friendly viz palette (Okabe-Ito, enabled via `VIZ_COLORBLIND_MODE=true` env var)
- Team menu pagination for lists > 25 items

### iRacing
- Parallel subsession fetching (semaphore-limited, 10 concurrent) in `iracing_meta.py`
- Bounded `TTLCache(maxsize=50, ttl=7 days)` replaces unbounded dict (via cachetools)
- Team query optimization: COUNT subquery → JOIN + GROUP BY
- tenacity for retry/backoff (exponential + jitter)

### New Dependencies
- `cachetools` (iRacing cache)
- `tenacity` (iRacing retries)
- `tiktoken` (optional, token counting)
- `plotly` (primary chart engine, replaces matplotlib for data charts)
- `kaleido` (static image export for Plotly, requires chromium in Docker)
- `feedparser` (RSS feed parsing for feed monitoring feature)

### New Migrations
- `sql/13_gdpr_trim.sql`
- `sql/14_guild_timezone.sql` (creates `guild_config` table)
- `sql/15_session_persistence.sql` (`active_trivia_sessions`, `active_debates`)

### New Environment Variables
- `COST_ALERT_THRESHOLD` (default: 1.00) — Monthly cost alert threshold in dollars
- `VIZ_COLORBLIND_MODE` (default: false) — Enable Okabe-Ito colorblind-friendly palette

## Cost & Performance Optimizations

- **Behavior analysis**: Reduced from hourly to every 6 hours (saves ~$80/mo in LLM costs)
- **Redis caching layer** in `tool_executor.py` for all external API results:
  - Web search: 2-hour TTL
  - Wolfram Alpha: 1-hour TTL
  - Weather (current + forecast): 30-min TTL
  - Wikipedia: 1-hour TTL
  - Stock/crypto prices: 5-min TTL
  - Sports scores: 5-min TTL
  - Movie info: 24-hour TTL
  - Dictionary definitions: 24-hour TTL
  - Currency conversion: 30-min TTL
- **User context caching** in `conversations.py`: DB lookup cached in Redis for 1 hour
- Cache key generation via `_cache_key()` helper with SHA-256 (was MD5)
- All caching gracefully degrades if Redis is unavailable (existing RedisCache pattern)
- **iRacing parallel fetch**: Subsession data fetched with asyncio.Semaphore(10) concurrency in `iracing_meta.py`
- **iRacing bounded cache**: `TTLCache(maxsize=50, ttl=7 days)` via cachetools replaces unbounded dict
- **iRacing retries**: tenacity for exponential backoff with jitter on API failures

## Documentation Sync (Session 7192e61)

- All docs updated to match actual codebase: model references, tool counts, file structure
- Outdated "Hermes 70B" and "Claude 3.7 Sonnet" references replaced with configurable MODEL_NAME
- PERFORMANCE_AUDIT.md and CODE_ANALYSIS_REPORT.md have inline fix status markers
- CONVERSATIONAL_AI.md has Performance Architecture section documenting all optimizations

## Tool Response Fixes

- **Duplicate response bug fixed**: Most text tools (wikipedia, define_word, movie_info, stock_price, sports_scores, currency_convert, translate, get_time, url_preview, random_choice, stock_history, create_reminder) are now marked self-contained — their output IS the answer, no synthesis LLM call needed. Previously only weather/wolfram were self-contained, causing tools like wikipedia to show raw output + embed + synthesis = triple response.
- **Translation rewrite**: Fixed auto-detection bug (was defaulting source to "en" when target wasn't English). Added 60+ language mappings, display names, email param for higher rate limits. LLM tool definition updated to accept language names (not just codes).

## Feature Expansion (Session 301667e+)

### Visualization Overhaul
- **Plotly + Kaleido** replaces matplotlib as primary chart engine for data charts (bar, line, pie, table, comparison)
- Additional chart types: radar, sankey (flow), heatmap — used by new analytics features
- **card_base.py** shared PIL primitives for feature-specific profile cards
- Chromium added to Docker for Kaleido static image export
- Matplotlib kept as fallback; weather card remains PIL-based

### Explicit User Facts ("Remember This")
- Users say `@bot remember that I prefer Python` and bot stores it as explicit fact
- Uses existing `user_facts` table with `fact_type='explicit'`, `confidence=1.0`
- Pattern detection in `conversations.py` before LLM call (early return, no API cost)
- `/myfacts` — view all stored facts (ephemeral)
- `/forget <id>` — delete a specific fact
- Facts automatically included in LLM context via existing `get_relevant_context()`

### Thread Conversation Continuity
- When bot is mentioned in a thread, it fetches parent channel context around the thread's origin message
- Prepends up to 5 parent messages with a `[Thread context from #parent-channel]` marker
- Uses `database.get_thread_parent_context()` — no new tables needed
- Detects threads via `isinstance(message.channel, discord.Thread)`

### Argumentation Profiles
- `/debate_profile [@user]` — PIL-based profile card aggregating all debate data
- Radar chart for 4 rhetorical dimensions (Logos, Ethos, Pathos, Factual Accuracy)
- Aggregates from `debates.analysis` JSONB: per-dimension averages, fallacy counts, claim verdicts
- Determines argumentation style (Logical Analyst, Authority Builder, Emotional Advocate, etc.)
- Shows best/worst topics, win streak, fact-check accuracy, recent debate results
- Purple-themed card (`debate_card.py`) visually distinct from iRacing blue cards
- No new tables — queries existing `debates` + `debate_participants`

### Topic Expertise Tracking (Silent)
- Silently tracks what topics each user discusses most and most knowledgeably
- No user-facing commands yet — data collection only, used by `/mystats` and future features
- `chat_stats.compute_user_topic_expertise()` — TF-IDF per-user topic extraction with quality scoring
- Quality score combines TF-IDF weight (40%), message count (30%), avg message length (20%), link usage (10%)
- Runs hourly in `precompute_stats` background job (30-day window only, min 5 messages per user)
- `user_topic_expertise` table: `(user_id, guild_id, topic, message_count, quality_score)` with UNIQUE constraint
- Batch upserted via `db.batch_upsert_topic_expertise()` using `psycopg2.extras.execute_values`
- Migration: `sql/16_new_features.sql`

### Conversation Flow Analysis (/flow)
- `/flow [days]` — Sankey diagram of topic transitions + bar chart of topic changers
- `chat_stats.analyze_conversation_flow()` — Splits messages into segments by time gaps (10min default)
- Extracts dominant topic per segment via TF-IDF, builds transition matrix
- Tracks which users most frequently change topics ("topic changers")
- Rendered via Plotly Sankey + horizontal bar chart
- No new tables — computed on-the-fly from messages

### Server Health Dashboard (/dashboard)
- `/dashboard [days]` — Server-wide analytics with Plotly charts (default 7 days, max 90)
- `features/dashboard.py` — `ServerDashboard(db, chat_stats)` class
- Generates 3 Plotly charts: activity trend (line), top messagers (bar), topics (pie)
- Summary embed with: total messages, unique users, avg length, peak hour/day, claims/debates/fact-checks
- Uses `chat_stats` methods: `calculate_primetime()`, `calculate_engagement()`, `extract_topics_tfidf()`
- Results cached via `stats_cache` table for 2 hours
- Queries claims, hot_takes, debates, fact_checks tables for community activity counts

### Polls with Analytics
- `/poll` — Create polls with Discord button voting (single or multi-choice)
- `/poll_results <id>` — View results with PIL card (amber/gold theme, progress bars per option)
- `/poll_close <id>` — Creator-only close with final results card
- `features/polls.py` — `PollSystem(db)` + `PollView(discord.ui.View)` button interactions
- `poll_card.py` — PIL results card with winner highlight, vote bars, voter count
- Tables: `polls` (question, options JSONB, closes_at), `poll_votes` (user_id, option_index)
- Background job: `check_poll_deadlines` (every 1min) auto-closes expired polls and posts results
- Supports: anonymous voting, multi-choice, timed polls (auto-close)

### Who Said It? Game
- `/whosaidit_start [rounds]` — Pulls random anonymous quotes from server history, users guess the author
- `/whosaidit_skip` — Skip current round and reveal answer
- `/whosaidit_end` — End game early and show scores
- `features/who_said_it.py` — `WhoSaidItGame(db)` with in-memory sessions + DB persistence
- Respects GDPR opt-outs, strips @mentions from quotes, min 30 / max 500 chars
- Fuzzy username matching for guesses (case-insensitive, substring match)
- On_message hook in events.py for guess processing (same pattern as trivia)
- Table: `active_who_said_it` with `session_state` JSONB

### Devil's Advocate Mode
- `/devils_advocate [topic]` — Bot argues the opposing side of any topic using LLM counter-arguments
- `/devils_advocate_end` — End the session and show exchange count + duration
- `features/devils_advocate.py` — `DevilsAdvocate(db, llm)` with in-memory sessions + DB persistence
- Only responds to the session starter (other users' messages ignored)
- 30-minute inactivity timeout checked by background task (every 5 min)
- On_message hook in events.py for counter-argument generation
- Table: `active_devils_advocate` with `session_state` JSONB
- System prompt forces LLM to always argue the opposing position

### Channel Jeopardy
- `/jeopardy_start [categories] [clues_per]` — Start Jeopardy with server-inspired categories
- `/jeopardy_pick [category] [value]` — Select a clue from the board
- `/jeopardy_pass` — Skip current clue and reveal answer
- `/jeopardy_board` — Show current board with revealed/available clues
- `/jeopardy_end` — End game early and show final scores
- `features/jeopardy.py` — `JeopardyGame(db, llm, chat_stats)` with LLM-generated boards
- Categories drawn from server's actual discussion topics via TF-IDF + general knowledge
- Correct answer = earn points, wrong answer = lose points (Jeopardy rules)
- Fuzzy answer matching strips "What is..." prefix, checks alternatives
- 15-minute inactivity timeout via background task
- On_message hook in events.py for answer processing
- Table: `active_jeopardy` with `session_state` JSONB

### GitHub Repository Monitoring (Admin Only)
- `/github_watch [repo] [type] [channel]` — Watch a GitHub repo (admin only)
- `/github_unwatch [id]` — Stop watching a repo (admin only)
- `/github_watches` — List watched repos (admin only)
- `features/github_monitor.py` — `GitHubMonitor(db, cache)` with aiohttp
- Watch types: releases, issues, prs, or all
- 5-minute polling via background task, max 3 events per check
- Optional `GITHUB_TOKEN` env var for higher API rate limits
- Color-coded embeds: green (open/release), red (closed), purple (merged PR)
- Table: `github_watches` with `last_event_id` tracking

### Shared Watchlists (Admin Only)
- `/watchlist_add [symbols] [threshold] [channel]` — Add stock/crypto symbols (admin only)
- `/watchlist_remove [symbol]` — Remove a symbol (admin only)
- `/watchlist` — View the server's watchlist (public)
- `features/watchlists.py` — `WatchlistManager(db, cache)` with Finnhub + CoinGecko
- Auto-detects stock vs crypto using `STOCK_TICKERS` and `CRYPTO_TICKERS` from constants.py
- 1-minute alert checking for ±threshold% moves (default 5%, 30-min cooldown between alerts)
- 24-hour daily summary with all symbols and changes
- Table: `watchlists` with `last_price` and `last_alert_at` tracking

### RSS Feed Monitoring (Admin Only)
- `/feed_add [url] [channel]` — Add an RSS feed to monitor (admin only)
- `/feed_remove [id]` — Remove a feed (admin only)
- `/feeds` — List all monitored feeds (admin only)
- `features/rss_monitor.py` — `RSSMonitor(db, cache)` with feedparser
- 5-minute polling via background task, max 3 new entries per check
- Redis caching prevents re-fetching within 5 minutes
- Posts new entries as Discord embeds with title, link, summary
- Table: `rss_feeds` with `last_entry_id` tracking

### Message Scheduling
- `/schedule [message] [minutes/hours/days]` — Schedule a message to be sent later
- `/scheduled` — View your pending scheduled messages (ephemeral)
- `/schedule_cancel [id]` — Cancel a scheduled message (creator only)
- `features/message_scheduler.py` — `MessageScheduler(db)` with abuse prevention
- Limits: max 5 pending per user, no messages within 5 min of each other in same channel, max 30 days out
- Background task checks every 1 minute for due messages
- Table: `scheduled_messages` with `sent` and `cancelled` flags

### Personal Analytics (/mystats)
- `/mystats [@user] [days]` — Unified personal analytics PIL card (teal/emerald theme)
- Aggregates data from: messages, message_interactions, claims, hot_takes, debates, trivia_stats, user_topic_expertise
- Top stats badges: total messages, server rank (DENSE_RANK), active days, peak hour
- Sections: Social (top partner, replies), Claims & Hot Takes, Debates (record, avg score), Topics (quality bars), Trivia (wins, accuracy)
- Achievements strip: Night Owl, Early Bird, Conversationalist, Debate Champion, Trivia Wizard, Topic Expert
- Optional `days` param (1-365) for time-windowed analysis; default is all-time
- Card rendered by `mystats_card.py` using `card_base.py` primitives

## Wishlist / Future Features

- **Cross-channel context awareness** — Opt-in `/link_channels` to pull RAG context from linked channels
