# WompBot Performance Audit Report

**Date:** 2026-02-07
**Scope:** Full codebase performance analysis across 40+ Python files
**Categories:** Async/Concurrency, Database, Memory, Network/API, Event Pipeline

---

## Executive Summary

The bot has **5 critical performance bottlenecks** that compound under load:

1. **Every DB call blocks the async event loop** - No database operation uses `asyncio.to_thread()` or an async driver
2. **No HTTP session reuse** - Every LLM/API call creates a new TCP+TLS connection (~200ms wasted per call)
3. **Claims LLM analysis fires on every message** - Broad regex pre-filter triggers expensive API calls constantly
4. **Channel lock held for entire request lifecycle** - One slow request blocks all other users in that channel for minutes
5. **Full table scan of `api_costs` on every LLM call** - `SUM(cost_usd)` with no time filter runs on every response

Fixing these 5 issues alone would reduce response latency by 40-60% and dramatically improve throughput under concurrent load.

---

## Fix Status (as of February 2026)

| Issue | Status | Details |
|-------|--------|---------|
| P1. Sync DB blocking event loop | ⚠️ PARTIAL | `asyncio.to_thread()` added for blocking I/O in key paths |
| P2. No HTTP session reuse | ✅ FIXED | `requests.Session()` added to LLMClient, ToolExecutor, Search, Weather, Wolfram, MediaProcessor |
| P3. Claims pre-filter too broad | 🔴 OPEN | Needs tighter regex patterns and per-user cooldown |
| P4. Channel lock held too long | ✅ FIXED | `asyncio.Lock()` replaced with `asyncio.Semaphore(3)` per channel |
| P5. Full table scan on api_costs | ✅ FIXED | `since_timestamp=start_of_current_month` now always passed |
| P6. Missing database indexes | ✅ FIXED | 11 composite indexes added in `sql/12_missing_indexes.sql` |
| P7. N+1 in embedding queue | 🔴 OPEN | Still processes items individually |
| P8. Thread pool exhaustion | ✅ FIXED | `ThreadPoolExecutor(max_workers=100)` set in main.py |
| P9. DB pool too small | ✅ FIXED | `DB_POOL_MAX` default increased from 10 to 25 |
| P10. Consent check on every msg | ✅ FIXED | In-memory cache with 5-minute TTL in gdpr_privacy.py |
| P11. Reaction JOIN on every reaction | 🔴 OPEN | Still queries on every reaction |
| P12. Sequential tool execution | ✅ FIXED | `asyncio.gather()` runs tool calls in parallel |
| P13. No circuit breaker | 🔴 OPEN | No circuit breaker pattern implemented yet |
| P14. Duplicate get_recent_messages | ✅ FIXED | Second call replaced with slice of already-fetched data |
| P15. Duplicate should_search | ✅ FIXED | Result cached from first call and reused |
| P21. Retry loses parameters | ✅ FIXED | All parameters (user_id, tools, images, etc.) now forwarded |

**12 of 21 HIGH/CRITICAL issues fixed. 4 OPEN items remain for future work.**

---

## CRITICAL Issues (Fix First)

### P1. Synchronous DB Operations Block Event Loop on Every Message
- **Files:** `handlers/events.py`, `handlers/conversations.py`, `features/claims.py`, `rag.py`, `features/hot_takes.py`
- **Problem:** ALL database operations (`store_message`, `get_consent_status`, `get_recent_messages`, `get_user_context`, `record_feature_usage`, `check_repeated_messages`, `record_token_usage`, reaction handlers) run synchronously on the event loop. The bot uses `psycopg2.pool.ThreadedConnectionPool` which blocks the calling thread when getting a connection.
- **Impact:** In a busy server with 20 msg/sec, each DB call blocking for 5-50ms means the event loop falls further behind every second. All Discord events (messages, reactions, edits, deletes) queue up.
- **Fix:** Wrap ALL `db.*` calls in `asyncio.to_thread()`. Long-term: migrate to `asyncpg` (native async PostgreSQL driver).

### P2. No HTTP Session Reuse — New TCP+TLS Connection Per API Call
- **Files:** `llm.py`, `search.py`, `tool_executor.py`, `weather.py`, `wolfram.py`, `features/claims.py`
- **Problem:** `requests.post()`/`requests.get()` called as bare functions everywhere. Every LLM call, web search, tool execution, weather lookup, and Wolfram query creates a new TCP connection with full TLS handshake and DNS resolution. The `ToolExecutor` alone has 13+ callsites across 10+ external APIs.
- **Impact:** Each unnecessary TLS handshake adds 100-300ms. A typical bot response triggers 2-4 HTTP calls = 400-1200ms of pure connection overhead.
- **Fix:** Add `self.session = requests.Session()` to `LLMClient.__init__`, `ToolExecutor.__init__`, `Search.__init__`, `Weather.__init__`, `Wolfram.__init__`. Replace all bare `requests.get/post` with `self.session.get/post`.

### P3. Claims Analysis Runs on Every Message with Broad Pre-filter
- **Files:** `handlers/events.py:350-388`, `features/claim_detector.py`
- **Problem:** For every message with `len > 20`, the claim detector runs ~20 regex patterns. Patterns like `r'\b(always|never|every|all|none|no)\b.*\b(is|are|does|do)\b'` match extremely common phrases ("no one is coming", "everyone is here"). When the pre-filter matches, a full LLM API call is made (~$0.001-0.01 per call, 1-3 seconds).
- **Impact:** On a busy server, this triggers hundreds of unnecessary LLM calls per day, costing money and consuming thread pool capacity.
- **Fix:** Tighten pre-filter patterns. Add a cooldown per user (e.g., max 1 claim analysis per user per 5 minutes). Consider moving to reaction-triggered claims only.

### P4. Channel Lock Held for Entire Request Lifecycle (Potentially Minutes)
- **Files:** `handlers/conversations.py:631-638`
- **Problem:** Each channel has a single `asyncio.Lock()` held for the ENTIRE duration: media download (30s+), multiple LLM calls (5-60s each), tool execution, search, DB queries. Other requests wait 10 seconds then get "Channel is busy" rejection. A video analysis request can hold the lock for 2+ minutes.
- **Impact:** In active channels, users regularly get rejected. Only 1 request can process per channel at a time.
- **Fix:** Replace `asyncio.Lock()` with `asyncio.Semaphore(3)` per channel. Or narrow lock scope to just the response-sending portion.

### P5. Full Table Scan of `api_costs` on Every LLM Call
- **Files:** `database.py:1086-1106`, `cost_tracker.py:56`
- **Problem:** `record_costs_sync()` calls `get_total_cost()` with no `since_timestamp`, executing `SELECT COALESCE(SUM(cost_usd), 0) FROM api_costs` — a full table scan of the ever-growing costs table. This runs on EVERY bot response, fact-check, analysis, and embedding.
- **Impact:** As `api_costs` grows over months, this query gets progressively slower. At 100K+ rows, it adds 50-200ms per bot response.
- **Fix:** Always pass `since_timestamp=start_of_current_month` to `get_total_cost()`. Or maintain a running total in a summary table.

---

## HIGH Priority Issues

### P6. Missing Critical Database Indexes
- **Files:** `database.py`, `hot_takes.py`, `chat_stats.py`
- **Missing indexes:**
  - `messages(channel_id, timestamp DESC)` — Hottest query path (`get_recent_messages`), called on every bot response
  - `messages(user_id, timestamp DESC)` — Spam detection (`check_repeated_messages`), called on every bot mention
  - `stats_cache(stat_type, scope, start_date, end_date)` — Cache lookup before every stats computation
  - `messages(channel_id, timestamp)` — Hot takes community reaction tracking (correlated subquery)
- **Impact:** Without composite indexes, PostgreSQL must scan entire tables or sort in memory. The `messages` table grows continuously.
- **Fix:** Single migration file with 4 `CREATE INDEX` statements.

### P7. N+1 Query Pattern in Embedding Queue Processing
- **Files:** `rag.py:190-209`
- **Problem:** Processing 50 embeddings opens up to 100 separate DB connections (one per INSERT + one per DELETE/UPDATE). Combined with a pool max of 10, this can exhaust connections.
- **Fix:** Batch into single `INSERT ... VALUES ...` and `DELETE ... WHERE id = ANY(...)` using one connection.

### P8. Thread Pool Exhaustion Under Concurrent Load
- **Files:** Multiple (all `asyncio.to_thread()` users)
- **Problem:** Default thread pool is ~40 threads. Each LLM call holds a thread for 5-60 seconds. Media processing holds threads for 30-120 seconds. With 10+ concurrent users, the pool exhausts and all async-offloaded operations queue.
- **Fix:** Set explicit thread pool at startup: `loop.set_default_executor(ThreadPoolExecutor(max_workers=100))`. Long-term: convert to `aiohttp` for HTTP calls.

### P9. DB Connection Pool Too Small (Max 10)
- **Files:** `database.py:32-33`
- **Problem:** Pool max is 10 connections. Concurrent consumers include: every message (store_message), every bot response (6-10 DB calls), RAG processing (up to 100 rapid checkouts), background tasks, and nested connection patterns that hold 2+ connections simultaneously.
- **Fix:** Increase `DB_POOL_MAX` to 25-30. Eliminate nested connection patterns.

### P10. GDPR Consent Check is a DB Query on Every Message
- **Files:** `handlers/events.py:207`
- **Problem:** `privacy_manager.get_consent_status(user_id)` executes a SELECT for every single message. Consent status changes extremely rarely.
- **Fix:** Add in-memory TTL cache (5-10 minute TTL). Cache ~100 recent user consent statuses.

### P11. Reaction Handlers Run JOIN Query on Every Reaction
- **Files:** `handlers/events.py:597-640`
- **Problem:** `on_reaction_add` and `on_reaction_remove` ALWAYS query `SELECT ht.id FROM hot_takes ht JOIN claims c ON ... WHERE c.message_id = %s` for every reaction on any message, regardless of emoji. Reactions are extremely frequent.
- **Fix:** Maintain an in-memory set of message IDs with associated hot takes. Skip the query for unknown message IDs.

### P12. Sequential Tool Execution When Parallel is Possible
- **Files:** `handlers/conversations.py:770-808`
- **Problem:** When LLM requests multiple tool calls (e.g., web_search + wolfram + weather), they execute sequentially. Three tool calls at 5 seconds each = 15 seconds serial vs ~5 seconds parallel.
- **Fix:** Use `asyncio.gather()` for independent tool calls.

### P13. No Circuit Breaker for External APIs
- **Files:** `llm.py`, `iracing_client.py`
- **Problem:** If OpenRouter is down, each user message waits the full timeout + retry cycle (~186 seconds total) before failing. No mechanism to detect repeated failures and fail fast.
- **Fix:** Track consecutive failures. After N failures within M seconds, set a cooldown period and return an error immediately.

---

## MEDIUM Priority Issues

### P14. Duplicate `get_recent_messages()` Call on Critical Path
- `conversations.py:643` fetches 50 messages, then line 680 fetches 3 more. The second is a subset of the first.

### P15. Duplicate `should_search()` Call
- `conversations.py:660` and `695` call the same function with identical inputs.

### P16. Non-SARGable `COALESCE(opted_out, FALSE) = FALSE` in Queries
- Prevents index usage on `opted_out` column. Replace with `(opted_out IS NOT TRUE)`.

### P17. DELETE Cleanup Runs on Every Insert
- `record_token_usage()` and `record_feature_usage()` run DELETE statements on every call. Move to background task.

### P18. `restore_discord_mentions()` Iterates All Guild Members
- O(n) loop over all guild members per @mention in response. Build a lookup dict instead.

### P19. Python-side Sorting in `get_profanity_stats()`
- Fetches all results, sorts in Python, then slices. Should use `ORDER BY ... LIMIT` in SQL.

### P20. Double Connection Checkout in `check_cost_alert_threshold()`
- Opens a connection, then calls `get_total_cost()` which opens a second connection simultaneously.

### P21. LLM Retry Calls Don't Forward All Parameters
- `llm.py:567-594` — Retries lose `images`, `tools`, `personality`, `max_tokens`, `user_id`, `username`.

### P22. Claims Module Bypasses LLMClient
- `claims.py` makes direct `requests.post()` to hardcoded OpenRouter URL, bypassing session reuse, cost tracking, and retry logic.

### P23. Sequential API Calls in iRacing
- `get_upcoming_races()` fetches up to 10 series schedules sequentially. `classify_questions()` makes sequential LLM calls per user.

### P24. iRacing Profile Cache Disabled
- `iracing.py:196-199` — Cache check commented out with "TEMP: Disable cache to debug". All profile lookups hit API.

---

## MEMORY Issues

### P25. BERT Compression Model Permanent ~400MB Retention
- `compression.py` — `llmlingua` BERT model loaded on first use, never unloaded. Dominates memory footprint.
- **Fix:** Add idle timeout unload, or run as separate process.

### P26. Chat Stats Loads Up to 50K Messages into Memory
- `chat_stats.py` — `get_messages_for_analysis()` materializes 50K messages (~25-200MB). Plus NetworkX DiGraph and TF-IDF sparse matrix (~10-100MB each).
- **Fix:** Process in batches. Limit to 10K messages. Use `max_features` on TfidfVectorizer.

### P27. Matplotlib Figure Leaks on Exceptions
- `viz_tools.py`, `iracing_viz.py`, `stats_viz.py`, `iracing_graphics.py` — If exception occurs between `plt.figure()` and `plt.close()`, figure leaks (~1-10MB each).
- **Fix:** Wrap all figure creation in `try/finally: plt.close(fig)`.

### P28. Active Debates Messages Accumulate Without Bound
- `debate_scorekeeper.py:20` — `active_debates` stores all messages forever if debate is never ended.
- **Fix:** Add max message count per debate. Auto-close after 24h inactivity.

### P29. Lookup Dicts Recreated Per Call
- `tool_executor.py`, `prefix_commands.py` — `timezone_aliases` (50+ entries), `name_to_ticker` (80+ entries), `crypto_to_coingecko` (30+ entries) recreated on every command invocation.
- **Fix:** Move to module-level constants.

### P30. LogoMatcher Convenience Functions Create New Instance Per Call
- `logo_matcher.py:286-327` — Each call loads and parses `data.json` from disk.
- **Fix:** Use a module-level singleton.

---

## LOW Priority Issues

- P31. Typing indicator active alongside placeholder message (wasteful heartbeat)
- P32. Admin IDs parsed from env var on every call
- P33. Slash command sync on every restart
- P34. `aiohttp.ClientSession` created per logo download in `iracing_viz.py`
- P35. `self_knowledge.py` reads doc files from disk on every query
- P36. `bug_tracker.py` loads/saves entire JSON file on every operation
- P37. iRacing permanent caches (cars/tracks/series) have no TTL
- P38. GDPR export loads all user data into single dict simultaneously
- P39. `db.store_message()` performs two DB writes per message (INSERT + UPSERT)
- P40. Weather icons fetched from network on every render (only 18 unique icons)

---

## Recommended Fix Order (Impact vs Effort)

| Priority | Issue | Effort | Expected Impact |
|----------|-------|--------|----------------|
| 1 | P2: Add `requests.Session()` to 5 classes | Low | -200-400ms per response (TLS savings) |
| 2 | P6: Add 4 missing composite indexes | Low | -50-200ms on hottest query paths |
| 3 | P5: Pass `since_timestamp` to `get_total_cost()` | Low | Eliminate full table scan per response |
| 4 | P10: Cache GDPR consent status in memory | Low | Eliminate DB query per message |
| 5 | P1: Wrap DB calls in `asyncio.to_thread()` | Medium | Unblock event loop entirely |
| 6 | P4: Replace channel Lock with Semaphore(3) | Low | 3x concurrent throughput per channel |
| 7 | P3: Tighten claims pre-filter + add cooldown | Low | Eliminate 80%+ of unnecessary LLM calls |
| 8 | P12: `asyncio.gather()` for parallel tool calls | Low | -50-70% latency for multi-tool requests |
| 9 | P7: Batch embedding queue DB operations | Medium | 100 DB calls → 2 |
| 10 | P8: Set explicit thread pool size (100) | Low | Prevent thread exhaustion |
| 11 | P9: Increase DB pool to 25-30 | Low | Prevent connection exhaustion |
| 12 | P11: Cache hot take message IDs | Low | Eliminate JOIN per reaction |
| 13 | P13: Add circuit breaker to LLMClient | Medium | Fast fail during outages |
| 14 | P22: Refactor claims to use LLMClient | Medium | Gain session reuse + cost tracking |
| 15 | P21: Fix retry parameter forwarding | Low | Correct behavior on retries |

---

## Estimated Latency Improvement

**Current typical response time:** ~3-5 seconds
**After P1-P6 fixes:** ~1.5-2.5 seconds (40-50% reduction)
**After all HIGH fixes:** ~1-2 seconds (50-70% reduction)

**Current throughput:** ~1 concurrent request per channel
**After P4 fix:** ~3 concurrent requests per channel
**After P1+P8+P9:** Sustained 20+ concurrent requests across all channels
