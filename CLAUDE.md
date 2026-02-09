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
- `bot/commands/slash_commands.py` — Slash commands: help, stats (4), wrapped, debate_start, trivia_start, dashboard, flow, poll, mystats, iRacing (13 incl. history) (~3700 lines, 24 commands)
- `bot/commands/prefix_commands.py` — Prefix command router + built-in commands (search, stock, weather, convert, define, etc.), imports sub-modules for migrated commands
- `bot/commands/prefix_utils.py` — Shared helpers: `is_bot_admin_ctx()`, `parse_choice()` — used by all prefix sub-modules
- `bot/commands/prefix_admin.py` — Admin prefix commands: !whoami, !setadmin, !removeadmin, !admins, !personality (5 commands)
- `bot/commands/prefix_features.py` — Feature prefix commands: !receipts/!claims, !quotes, !verify, !hottakes/!ht, !myht, !vindicate, !remind, !reminders, !cancelremind, !event, !events, !cancelevent, !myfacts, !forget, !qotd, !weatherset, !weatherclear, !schedule, !scheduled, !cancelschedule (20 commands)
- `bot/commands/prefix_games.py` — Game/debate prefix commands: !debate_end/!de, !debate_stats/!ds, !debate_lb/!dlb, !debate_review/!dr, !debate_profile/!dp, !triviastop, !triviastats, !trivialeaderboard/!tlb, !pollresults, !pollclose, !whosaidit, !wsisskip, !wsisend, !da, !daend, !jeopardy, !jpick, !jpass, !jend (19 commands)
- `bot/commands/prefix_monitoring.py` — Monitoring prefix commands: !feedadd, !feedremove, !feeds, !ghwatch, !ghunwatch, !ghwatches, !wladd, !wlremove, !watchlist/!wl (9 commands)

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
- `sql/` — 17 SQL files (init.sql + 16 migrations including indexes, rate limiting, GDPR, iRacing, GDPR trim, guild timezone, session persistence, performance indexes)
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
VISION_MODEL=google/gemini-2.0-flash-lite-001  # Image analysis (cheap: $0.075/M input)
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

Indexes: 11 composite indexes in `sql/12_missing_indexes.sql` + 3 performance indexes in `sql/17_performance_indexes.sql`

Migrations:
- `sql/13_gdpr_trim.sql` — Drops 7 GDPR slash commands, removes `data_breach_log` and `privacy_policy_versions` tables
- `sql/14_guild_timezone.sql` — Creates `guild_config` table for guild-level timezone support
- `sql/15_session_persistence.sql` — Creates `active_trivia_sessions` and `active_debates` tables for session persistence across restarts
- `sql/16_new_features.sql` — Creates tables for new features: `user_topic_expertise`, polls, games, scheduling, monitoring
- `sql/17_performance_indexes.sql` — Compound indexes for hot-path queries: messages(channel_id, guild_id, timestamp DESC), server_personality(server_id), feature_rate_limits(request_timestamp)

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
18. **Guild timezone support** — Guild timezone stored in `guild_config` table; reminders and events use guild timezone via `zoneinfo`.
19. **Dual chart engine** — Primary: Plotly + Kaleido (premium charts, requires chromium). Fallback: matplotlib (if Plotly fails). Weather card stays PIL-based. Configured in `conversations.py` `get_visualizer()`.
20. **Shared card primitives** — `card_base.py` provides composable PIL drawing utilities (rounded rects, progress bars, glow effects, gradients, fonts). Feature-specific cards import from here rather than duplicating code.
21. **Vision cost optimization** — Three layers: (1) `detail: "low"` on all image payloads (~85 tokens vs thousands), (2) images downloaded and resized to max 768px before sending, (3) default vision model switched from gpt-4o-mini ($0.15/M) to Gemini 2.0 Flash Lite ($0.075/M).
22. **3-tier tool selection** — `_select_tools_for_message()` checks `_TOOL_INTENT_KEYWORDS` (~50 keywords). Pure conversation → no tools, viz keywords → all tools, tool keywords → computational only. Prevents Wolfram being called for casual chat.
23. **Background compression model loading** — LLMLingua BERT model loads in a background thread at startup. Requests skip compression while loading (graceful degradation via `_loading` flag with thread lock).
24. **Fire-and-forget claim/hot-take analysis** — Claim detection and hot take scoring moved to `asyncio.create_task()` in events.py, no longer blocking the response pipeline.
25. **Parallel DB context queries** — `get_recent_messages()`, `get_thread_parent_context()`, user context, server personality, RAG, and search all run concurrently via `asyncio.gather()`.
26. **Redis-cached server personality** — `get_server_personality()` cached in Redis with 1hr TTL, avoiding DB hit on every bot mention.
27. **Delta-based token estimation** — Token counts pre-computed per message; truncation loop subtracts removed message's count instead of re-encoding entire list.
28. **Fire-and-forget cost tracking** — `cost_tracker.record_costs_sync()` runs in a daemon thread, not blocking the response.
29. **Parallel media processing** — Images and GIFs processed concurrently via `asyncio.gather()`. YouTube/video remain sequential (dependency on frame extraction).
30. **Fire-and-forget DB logging** — `store_message()`, `record_token_usage()`, and `record_search_log()` all run via `asyncio.create_task(asyncio.to_thread(...))`, not blocking response delivery.
31. **Separated cleanup from insert** — `record_feature_usage()` no longer runs cleanup query on every insert. Cleanup moved to `cleanup_feature_rate_limits()` called once daily in the GDPR cleanup background job.

## Build & Deploy

```bash
docker compose up -d --build     # Build and deploy
docker compose logs -f bot       # Watch logs
docker compose restart bot       # Restart bot only
```

## Common Patterns When Editing

- **Adding a new tool**: Define in `llm_tools.py` (add to ALL_TOOLS or COMPUTATIONAL_TOOLS), add handler to dict registry in `tool_executor.py`, add to `SELF_CONTAINED_TOOLS` in `bot/constants.py` if the tool output is the final answer, add to system prompts if needed
- **Changing LLM behavior**: Edit `llm.py` for search/compression logic, `conversations.py` for tool selection/synthesis
- **New slash command**: Add to `commands/slash_commands.py`, register in `main.py` (use for commands needing Discord UI like modals, autocomplete, buttons)
- **New prefix command**: Add to appropriate `commands/prefix_*.py` sub-module, register in `prefix_commands.py` (use for simple text-in/text-out commands)
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
- Guild-level timezone support: `guild_config` table, reminders/events use guild timezone via `zoneinfo`
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
- `!myfacts` — view all stored facts (ephemeral)
- `!forget <id>` — delete a specific fact
- Facts automatically included in LLM context via existing `get_relevant_context()`

### Thread Conversation Continuity
- When bot is mentioned in a thread, it fetches parent channel context around the thread's origin message
- Prepends up to 5 parent messages with a `[Thread context from #parent-channel]` marker
- Uses `database.get_thread_parent_context()` — no new tables needed
- Detects threads via `isinstance(message.channel, discord.Thread)`

### Argumentation Profiles
- `!debate_profile [@user]` (alias `!dp`) — PIL-based profile card aggregating all debate data
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
- `!pollresults <id>` — View results with PIL card (amber/gold theme, progress bars per option)
- `!pollclose <id>` — Creator-only close with final results card
- `features/polls.py` — `PollSystem(db)` + `PollView(discord.ui.View)` button interactions
- `poll_card.py` — PIL results card with winner highlight, vote bars, voter count
- Tables: `polls` (question, options JSONB, closes_at), `poll_votes` (user_id, option_index)
- Background job: `check_poll_deadlines` (every 1min) auto-closes expired polls and posts results
- Supports: anonymous voting, multi-choice, timed polls (auto-close)

### Who Said It? Game
- `!whosaidit [rounds]` — Pulls random anonymous quotes from server history, users guess the author
- `!wsisskip` — Skip current round and reveal answer
- `!wsisend` — End game early and show scores
- `features/who_said_it.py` — `WhoSaidItGame(db)` with in-memory sessions + DB persistence
- Respects GDPR opt-outs, strips @mentions from quotes, min 30 / max 500 chars
- Fuzzy username matching for guesses (case-insensitive, substring match)
- On_message hook in events.py for guess processing (same pattern as trivia)
- Table: `active_who_said_it` with `session_state` JSONB

### Devil's Advocate Mode
- `!da [topic]` — Bot argues the opposing side of any topic using LLM counter-arguments
- `!daend` — End the session and show exchange count + duration
- `features/devils_advocate.py` — `DevilsAdvocate(db, llm)` with in-memory sessions + DB persistence
- Only responds to the session starter (other users' messages ignored)
- 30-minute inactivity timeout checked by background task (every 5 min)
- On_message hook in events.py for counter-argument generation
- Table: `active_devils_advocate` with `session_state` JSONB
- System prompt forces LLM to always argue the opposing position

### Channel Jeopardy
- `!jeopardy [categories] [clues_per]` — Start Jeopardy with server-inspired categories
- `!jpick [category] [value]` — Select a clue from the board
- `!jpass` — Skip current clue and reveal answer
- `!jend` — End game early and show final scores
- `features/jeopardy.py` — `JeopardyGame(db, llm, chat_stats)` with LLM-generated boards
- Categories drawn from server's actual discussion topics via TF-IDF + general knowledge
- Correct answer = earn points, wrong answer = lose points (Jeopardy rules)
- Fuzzy answer matching strips "What is..." prefix, checks alternatives
- 15-minute inactivity timeout via background task
- On_message hook in events.py for answer processing
- Table: `active_jeopardy` with `session_state` JSONB

### GitHub Repository Monitoring (Admin Only)
- `!ghwatch [repo] [type] [channel]` — Watch a GitHub repo (admin only)
- `!ghunwatch [id]` — Stop watching a repo (admin only)
- `!ghwatches` — List watched repos (admin only)
- `features/github_monitor.py` — `GitHubMonitor(db, cache)` with aiohttp
- Watch types: releases, issues, prs, or all
- 5-minute polling via background task, max 3 events per check
- Optional `GITHUB_TOKEN` env var for higher API rate limits
- Color-coded embeds: green (open/release), red (closed), purple (merged PR)
- Table: `github_watches` with `last_event_id` tracking

### Shared Watchlists (Admin Only)
- `!wladd [symbols] [threshold] [channel]` — Add stock/crypto symbols (admin only)
- `!wlremove [symbol]` — Remove a symbol (admin only)
- `!watchlist` (alias `!wl`) — View the server's watchlist (public)
- `features/watchlists.py` — `WatchlistManager(db, cache)` with Finnhub + CoinGecko
- Auto-detects stock vs crypto using `STOCK_TICKERS` and `CRYPTO_TICKERS` from constants.py
- 1-minute alert checking for ±threshold% moves (default 5%, 30-min cooldown between alerts)
- 24-hour daily summary with all symbols and changes
- Table: `watchlists` with `last_price` and `last_alert_at` tracking

### RSS Feed Monitoring (Admin Only)
- `!feedadd [url] [channel]` — Add an RSS feed to monitor (admin only)
- `!feedremove [id]` — Remove a feed (admin only)
- `!feeds` — List all monitored feeds (admin only)
- `features/rss_monitor.py` — `RSSMonitor(db, cache)` with feedparser
- 5-minute polling via background task, max 3 new entries per check
- Redis caching prevents re-fetching within 5 minutes
- Posts new entries as Discord embeds with title, link, summary
- Table: `rss_feeds` with `last_entry_id` tracking

### Message Scheduling
- `!schedule [message] [minutes/hours/days]` — Schedule a message to be sent later
- `!scheduled` — View your pending scheduled messages (ephemeral)
- `!cancelschedule [id]` — Cancel a scheduled message (creator only)
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

## Slash-to-Prefix Command Migration

Migrated ~55 commands from Discord slash commands (/) to prefix commands (!) to stay under Discord's 100 slash command limit and improve response times. Commands that benefit from Discord's built-in UI (modals, autocomplete, buttons) remain as slash commands (43 total: 24 in slash_commands.py + 12 team + 4 event + 3 GDPR).

### What Stayed as Slash Commands
`/help`, `/stats_server`, `/stats_topics`, `/stats_primetime`, `/stats_engagement`, `/wrapped`, `/debate_start`, `/trivia_start`, `/dashboard`, `/flow`, `/poll`, `/mystats`, all `/iracing_*` commands (13 incl. history + 12 team + 4 event), `/wompbot_optout`, `/download_my_data`, `/delete_my_data`

### Prefix Command Structure
- `prefix_commands.py` — Router + built-in commands (search, stock, weather, convert, define, etc.), imports and calls sub-module registration functions
- `prefix_utils.py` — Shared helpers (`is_bot_admin_ctx`, `parse_choice`) used by all sub-modules
- `prefix_admin.py` — Admin/config commands: whoami, setadmin, removeadmin, admins, personality
- `prefix_features.py` — Feature commands: receipts, quotes, verify, hottakes, myht, vindicate, remind, reminders, cancelremind, event, events, cancelevent, myfacts, forget, qotd, weatherset, weatherclear, schedule, scheduled, cancelschedule
- `prefix_games.py` — Game/debate commands: debate_end, debate_stats, debate_lb, debate_review, debate_profile, triviastop, triviastats, trivialeaderboard, pollresults, pollclose, whosaidit, wsisskip, wsisend, da, daend, jeopardy, jpick, jpass, jend
- `prefix_monitoring.py` — Monitoring commands: feedadd, feedremove, feeds, ghwatch, ghunwatch, ghwatches, wladd, wlremove, watchlist

### Key Command Mappings
| Old Slash | New Prefix | Aliases |
|-----------|-----------|---------|
| `/receipts` | `!receipts` | `!claims` |
| `/quotes` | `!quotes` | |
| `/verify_claim` | `!verify` | |
| `/whoami` | `!whoami` | |
| `/setadmin` | `!setadmin` | |
| `/removeadmin` | `!removeadmin` | |
| `/admins` | `!admins` | |
| `/personality` | `!personality` | |
| `/hottakes` | `!hottakes` | `!ht` |
| `/mystats_hottakes` | `!myht` | |
| `/vindicate` | `!vindicate` | |
| `/remind` | `!remind` | |
| `/reminders` | `!reminders` | |
| `/cancel_reminder` | `!cancelremind` | |
| `/schedule_event` | `!event` | |
| `/events` | `!events` | |
| `/cancel_event` | `!cancelevent` | |
| `/qotd` | `!qotd` | |
| `/debate_end` | `!debate_end` | `!de` |
| `/debate_stats` | `!debate_stats` | `!ds` |
| `/debate_leaderboard` | `!debate_lb` | `!dlb` |
| `/debate_review` | `!debate_review` | `!dr` |
| `/debate_profile` | `!debate_profile` | `!dp` |
| `/weather_set` | `!weatherset` | |
| `/weather_clear` | `!weatherclear` | |
| `/trivia_stop` | `!triviastop` | |
| `/trivia_stats` | `!triviastats` | |
| `/trivia_leaderboard` | `!trivialeaderboard` | `!tlb` |
| `/myfacts` | `!myfacts` | |
| `/forget` | `!forget` | |
| `/poll_results` | `!pollresults` | |
| `/poll_close` | `!pollclose` | |
| `/whosaidit_start` | `!whosaidit` | |
| `/whosaidit_skip` | `!wsisskip` | |
| `/whosaidit_end` | `!wsisend` | |
| `/devils_advocate` | `!da` | |
| `/devils_advocate_end` | `!daend` | |
| `/jeopardy_start` | `!jeopardy` | |
| `/jeopardy_pick` | `!jpick` | |
| `/jeopardy_pass` | `!jpass` | |
| `/jeopardy_end` | `!jend` | |
| `/schedule` | `!schedule` | |
| `/scheduled` | `!scheduled` | |
| `/schedule_cancel` | `!cancelschedule` | |
| `/feed_add` | `!feedadd` | |
| `/feed_remove` | `!feedremove` | |
| `/feeds` | `!feeds` | |
| `/github_watch` | `!ghwatch` | |
| `/github_unwatch` | `!ghunwatch` | |
| `/github_watches` | `!ghwatches` | |
| `/watchlist_add` | `!wladd` | |
| `/watchlist_remove` | `!wlremove` | |
| `/watchlist` | `!watchlist` | `!wl` |

### Removed Commands
- `/jeopardy_board` — removed entirely
- `/bug`, `/bugs`, `/bug_resolve`, `/bug_note` — bug tracker removed entirely
- `/weather_info` — removed entirely

## Wishlist / Future Features

- **Cross-channel context awareness** — Opt-in `/link_channels` to pull RAG context from linked channels. When user asks a question in #general, also search for relevant context in linked channels (e.g. #tech, #gaming). Requires new `linked_channels` table and RAG query expansion.
- **Auto-responses with local LLM** — Use the 8B local model to generate occasional autonomous comments on interesting messages (dropped during planning phase — revisit if local LLM performance improves)
- **Topic expertise leaderboard** — `/experts [topic]` to show who knows most about a topic, using the `user_topic_expertise` table data already being collected
- **Debate tournament mode** — Multi-round debate brackets with seeding based on argumentation profiles
- **Achievement system** — Persistent achievements with Discord role rewards (e.g. "1000 messages", "10 debate wins", "Trivia Champion")

## Performance Latency Audit (Session latest)

### Fixes Applied
1. **Claim/hot-take analysis moved to background** — Was running 2 LLM calls (1-3s each) on EVERY message, blocking response. Now fire-and-forget via `asyncio.create_task()` in events.py
2. **DB context queries parallelized** — `get_recent_messages()`, thread context, user context, personality, RAG, and search all run concurrently via `asyncio.gather()` (was sequential: 300-700ms)
3. **Server personality cached in Redis** — 1hr TTL, avoids DB query on every bot mention
4. **Token estimation uses deltas** — Pre-computes per-message token counts, subtracts on truncation instead of re-encoding entire list in a loop
5. **Cost tracking fire-and-forget** — Runs in daemon thread via `threading.Thread`, doesn't block response
6. **Media processing parallelized** — Images and GIFs processed concurrently via `asyncio.gather()` (YouTube/video remain sequential)
7. **DB logging fire-and-forget** — `store_message()`, `record_token_usage()`, `record_search_log()` all via `asyncio.create_task(asyncio.to_thread(...))`
8. **Cleanup separated from insert** — `record_feature_usage()` no longer runs DELETE query on every insert; cleanup moved to daily background job
9. **3 compound indexes added** — `sql/17_performance_indexes.sql` for hot-path queries (messages, server_personality, feature_rate_limits)
10. **Empty response retry sleep reduced** — 2s → 0.5s

### Other Fixes in Same Session
- **3-tier tool intent filtering** — Prevents computational tools being called for pure conversation (was calling Wolfram on casual chat)
- **LLMLingua model background loading** — BERT model loads in background thread at startup, requests skip compression while loading (was blocking first request for 10+ seconds)
- **Personality prompts rewritten** — Default (more verbose standard LLM), Concise (warm not curt), Bogan (70% English / 30% Aussie, cut from 330 to 75 lines)
- **Vision cost optimization** — detail:low + image resize to 768px + Gemini Flash Lite ($0.075/M vs $0.15/M), ~98% cost reduction per vision call

## Comprehensive Code Audit (Session latest+1)

Full line-by-line audit of ~60 files (~15,000 lines) covering performance, security, and code quality.

### Critical Fixes
- **Token truncation array desync** (llm.py) — After `messages.pop(1)`, was computing chars from wrong message. Also, inserting truncation notice without corresponding token count desynchronized `msg_token_counts[]`. Fixed by capturing `removed_msg` before pop and inserting truncation token count.
- **SQL injection in 8 INTERVAL queries** (database.py) — `INTERVAL '%s days'` → `INTERVAL '1 day' * %s` (parameterized multiplication). Same for `'%s seconds'`.
- **SSRF fail-open** (tool_executor.py) — DNS resolution failure was allowing requests through (`pass` in `gaierror` handler). Changed to fail-closed (block on DNS error).
- **Currency convert NameError** (tool_executor.py) — `cache_key` variable used but never defined; every successful conversion raised NameError (swallowed by try/except), results never cached. Fixed by adding cache key construction.

### Security Fixes
- **Redis authentication** — Added `--requirepass` with `REDIS_PASSWORD` env var to Redis container and `redis_cache.py`
- **Portainer bound to localhost** — `9443:9443` → `127.0.0.1:9443:9443`
- **OMDB upgraded to HTTPS** — `http://www.omdbapi.com` → `https://www.omdbapi.com`
- **Error messages sanitized** — User-facing Discord error messages no longer expose `str(e)` (was leaking internal state)
- **Debug prints removed** — `print()` that leaked user message content to stdout replaced with `logger.debug()` (user IDs only)

### Performance Fixes
- **HTTP timeout split** (llm.py) — `timeout=60` → `timeout=(5, 55)` connect/read tuple (3 occurrences)
- **Wolfram parallel queries** (tool_executor.py) — Sequential metric + imperial → `asyncio.gather(asyncio.to_thread())` (saves ~2s per query)
- **Weather calls async** (tool_executor.py) — `self.weather.get_current_weather()` → `await asyncio.to_thread()`
- **Event loop unblocking** (events.py, conversations.py) — `store_message()`, `get_consent_status()`, `check_repeated_messages()`, `record_feature_usage()`, `on_reaction_add` DB queries all moved off event loop via `asyncio.to_thread()` or fire-and-forget `asyncio.create_task()`
- **Profanity stats SQL optimization** (database.py) — Sort + limit pushed to SQL subquery instead of fetching all rows into Python
- **Self-contained tool check** (conversations.py) — Substring matching (`any(st in tn)`) → exact set membership (`tn in SELF_CONTAINED_TOOLS`); `SELF_CONTAINED_TOOLS` changed from list to `frozenset` for O(1) lookup

### Bug Fixes
- **Feyd personality loading** (llm.py) — `_load_system_prompt('feyd')` had no matching branch, always loaded default. Added `'feyd'` → `system_prompt_sample.txt` mapping.
- **Hot takes diversity formula** (hot_takes.py) — Was `unique_types / total_reactions` (inverted: many diverse reactions scored LOW). Now uses normalized Shannon entropy (0.0 = single type, 1.0 = perfectly diverse).
- **Double conn.commit()** (database.py) — `upsert_topic_expertise` and `batch_upsert_topic_expertise` called `conn.commit()` manually, but `get_connection()` context manager already commits. Removed redundant commits.
- **datetime.now() timezone** (database.py) — `datetime.now()` → `datetime.now(timezone.utc)` in 2 iRacing cache methods (was using local time instead of UTC).

### Code Quality
- **48 print() → logger** (database.py) — All print statements replaced with structured `logger.error()`/`logger.debug()` calls using `%s` formatting
- **Dead code removed** — `MENTION_RATE_STATE` (never populated), `get_autocommit_connection()` (never called), `_RATE_STATE_LOCK` (only used by removed code)
- **Redundant imports removed** (database.py) — `from datetime import timedelta` inside methods when already at module level
- **Unused parameter removed** (database.py) — `get_question_stats()` had `limit` parameter that was never applied
- **Module-level imports** (llm.py) — `import threading` moved from inside method to module top-level
