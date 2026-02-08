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
- `bot/handlers/conversations.py` — Main message handler, tool selection, synthesis logic, placeholder management (~1000 lines)
- `bot/llm.py` — LLMClient class: system prompt loading, should_search(), generate_response(), compression (~750 lines)
- `bot/llm_tools.py` — 26 tool definitions (ALL_TOOLS, COMPUTATIONAL_TOOLS lists), DataRetriever class (~1200 lines)
- `bot/tool_executor.py` — ToolExecutor: routes tool_call name → implementation (~400 lines)
- `bot/database.py` — PostgreSQL connection pool, all queries, get_conversation_context() (~1000 lines)

### Features
- `bot/rag.py` — RAG system: embeddings via OpenAI text-embedding-3-small, pgvector similarity search (threshold: 0.55)
- `bot/search.py` — Tavily/Google search, format_results_for_llm() (max 5 results, 200 char snippets)
- `bot/compression.py` — LLMLingua conversation compression (keep_recent=8, min_messages=10)
- `bot/viz_tools.py` — Matplotlib charts: bar, line, pie, table, comparison (dark theme, MULTI_COLORS palette)
- `bot/media_processor.py` — Image/video/YouTube frame extraction and analysis
- `bot/claims.py` — 2-stage claim detection (fast pattern → LLM verify)
- `bot/claim_detector.py` — Fast keyword pre-filter for claims
- `bot/fact_check.py` — Emoji-triggered fact checking (requires 2+ sources)
- `bot/hot_takes.py` — 3-stage controversy scoring (pattern → engagement → LLM)
- `bot/chat_stats.py` — Network graphs, topic trends, primetime analysis
- `bot/cost_tracker.py` — Per-request API cost tracking, $1/month alert
- `bot/weather.py` — OpenWeatherMap integration
- `bot/wolfram.py` — Wolfram Alpha integration
- `bot/self_knowledge.py` — Bot self-awareness responses
- `bot/help_system.py` — Command documentation system (~1700 lines)

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
- `migrations/` — 13 SQL files (init.sql through 12_missing_indexes.sql)

### iRacing Subsystem
- `bot/iracing.py`, `iracing_client.py`, `iracing_teams.py`, `iracing_meta.py`
- `bot/iracing_viz.py`, `iracing_graphics.py`
- `bot/iracing_event_commands.py`, `iracing_team_commands.py`

## Tool Architecture

Tools are split into two groups in `llm_tools.py`:
- **COMPUTATIONAL_TOOLS** — Non-visual tools (search, weather, wolfram, stocks, etc.)
- **ALL_TOOLS** — Computational + visualization tools (charts, tables)

`_select_tools_for_message()` in conversations.py only passes visualization tools when the message contains viz-intent keywords (chart, graph, plot, visualize, etc.). This prevents the LLM from generating charts for knowledge questions.

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
```

## Database (30+ tables)

Key tables: `messages`, `user_profiles`, `claims`, `fact_checks`, `hot_takes`, `quotes`, `message_embeddings` (vector), `conversation_summaries`, `api_costs`, `rate_limits`, `reminders`, `events`, `iracing_teams`, `gdpr_deletion_requests`, `opt_outs`, `guild_config`, `server_admins`, `stats_cache`

Indexes: 11 composite indexes added in `migrations/12_missing_indexes.sql`

## Important Design Decisions

1. **Intent-based tool filtering** — Viz tools only passed when message has chart keywords. Prevents "what is X" → bar chart bug.
2. **Mandatory chart synthesis** — Charts always get a follow-up LLM call to generate accompanying text.
3. **Self-contained tools** — Only weather and wolfram skip synthesis (they return complete responses).
4. **Search negative filter** — `no_search_patterns` in should_search() blocks web search for conversational/definitional questions the LLM can answer from training data.
5. **Channel semaphore** — asyncio.Semaphore(3) per channel, not a global lock.
6. **HTTP session reuse** — requests.Session() for connection pooling in API clients.
7. **Truncation notice** — When messages are removed from context, a note is inserted so the LLM knows history was trimmed.
8. **GDPR consent caching** — 5-minute TTL in-memory cache to avoid DB hits on every message.
9. **Cost tracking** — Every API call tracked with model, tokens, cost. Alert at $1/month.
10. **Claim detection** — 2-stage: fast regex/keyword filter → LLM verification (saves cost).
11. **Fact-check** — Requires minimum 2 corroborating sources before rendering verdict.

## Build & Deploy

```bash
docker compose up -d --build     # Build and deploy
docker compose logs -f bot       # Watch logs
docker compose restart bot       # Restart bot only
```

## Common Patterns When Editing

- **Adding a new tool**: Define in `llm_tools.py` (add to ALL_TOOLS or COMPUTATIONAL_TOOLS), implement in `tool_executor.py`, add to system prompts if needed
- **Changing LLM behavior**: Edit `llm.py` for search/compression logic, `conversations.py` for tool selection/synthesis
- **New slash command**: Add to `commands/slash_commands.py`, register in `main.py`
- **Database changes**: Create new migration file in `migrations/`, update `database.py`
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
- Cache key generation via `_cache_key()` helper with MD5 fallback for long keys
- All caching gracefully degrades if Redis is unavailable (existing RedisCache pattern)
