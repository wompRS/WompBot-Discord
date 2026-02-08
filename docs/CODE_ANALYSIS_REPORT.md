# Code Analysis Report

**Date:** February 2026
**Scope:** Complete codebase analysis of WompBot Discord Bot

---

## Summary

| Category | High Priority | Medium Priority | Low Priority | Fixed (Feb 2026) |
|----------|--------------|-----------------|--------------|------------------|
| Performance | 2 | 3 | 1 | 1 fixed |
| Code Quality | 4 | 4 | 2 | 3 fixed |
| Security | 2 | 3 | 1 | 5 new fixes added |
| Architecture | 2 | 2 | 0 | 1 partial |
| Best Practices | 2 | 5 | 0 | 1 partial |
| Rate Limiting | 0 | 2 | 0 | - |
| Data Integrity | 0 | 2 | 0 | - |
| **TOTAL** | **14** | **21** | **4** | **~10 addressed** |

---

## 1. PERFORMANCE ISSUES

### HIGH PRIORITY

#### Issue 1.1: N+1 Database Queries in Embedding Processing
> **Status:** ⚠️ PARTIAL — Improvements planned but individual processing still used
- **File:** `bot/rag.py`, lines 163-174
- **Problem:** `process_embedding_queue()` processes items individually, resulting in N database queries for N items
- **Impact:** Processing 50 messages = 50+ separate DB connections
- **Fix:** Batch embedding storage using PostgreSQL's multi-row INSERT or `executemany()`

#### Issue 1.2: Missing Composite Indexes on Guild-Scoped Queries
> **Status:** ✅ FIXED — 11 composite indexes added in `sql/12_missing_indexes.sql`
- **File:** `sql/init.sql`
- **Problem:** Tables have `guild_id` columns but lack composite indexes on common query patterns
- **Impact:** Queries filtering by (guild_id, user_id) scan through guild data inefficiently
- **Fix:** Add composite indexes:
  ```sql
  CREATE INDEX idx_messages_guild_user ON messages(guild_id, user_id);
  CREATE INDEX idx_claims_guild_user ON claims(guild_id, user_id, timestamp);
  CREATE INDEX idx_quotes_guild_user ON quotes(guild_id, user_id);
  ```

### MEDIUM PRIORITY

#### Issue 1.3: Embedding Retry Without Backoff
- **File:** `bot/rag.py`, lines 187-207
- **Problem:** Failed embeddings retry immediately without exponential backoff
- **Fix:** Add backoff: `await asyncio.sleep(min(300, 2 ** attempt + random.uniform(0, 1)))`

#### Issue 1.4: Slow iRacing Popularity Calculation
- **File:** `bot/tasks/background_jobs.py`, lines 114-148
- **Problem:** Iterates 100 seasons with individual API calls (~80 seconds per time_range)
- **Fix:** Batch requests or limit to top 50 series

#### Issue 1.5: Synchronous Print Statements
> **Status:** ⚠️ PARTIAL — Most print() calls converted to logger, ~50 remain in database.py and tool_executor.py
- **Files:** Multiple files throughout codebase
- **Problem:** Using `print()` in async code can block event loop
- **Fix:** Use `logger.info()` from logging_config module

---

## 2. CODE QUALITY ISSUES

### HIGH PRIORITY

#### Issue 2.1: Bare Exception Handlers
> **Status:** ✅ FIXED — All bare `except:` replaced with `except Exception:`
- **File:** `bot/handlers/conversations.py`, lines 327-328, 395-396
- **Problem:** `except: pass` silently discards errors
- **Fix:** Catch specific exceptions or log: `except Exception as e: logger.warning(f"Error: {e}")`

#### Issue 2.2: Inconsistent Error Handling
- **Files:** `bot/database.py`, `bot/llm.py`
- **Problem:** Some modules print errors, others return None without logging
- **Fix:** Create centralized error handling in logging_config.py

#### Issue 2.3: Global Mutable State
> **Status:** ✅ FIXED — `asyncio.Lock` added to protect mutable state
- **File:** `bot/handlers/conversations.py`, lines 45-46
- **Problem:** Module-level dictionaries used for rate limiting state
- **Fix:** Move to class-based RateLimiter singleton with asyncio.Lock protection

#### Issue 2.4: Missing Input Validation
- **File:** `bot/commands/slash_commands.py`, lines 146-167
- **Problem:** `verify_claim_slash()` doesn't validate claim_id exists before UPDATE
- **Fix:** Check `cur.rowcount` after UPDATE or add pre-check query

### MEDIUM PRIORITY

#### Issue 2.5: Duplicate Mention Handling Logic
- **File:** `bot/handlers/conversations.py`, lines 102-143
- **Problem:** Two functions with similar regex patterns could diverge
- **Fix:** Create single MentionHandler class

#### Issue 2.6: Overly Long Functions
> **Status:** ✅ FIXED — `handle_bot_mention()` refactored with extracted helpers
- **File:** `bot/handlers/conversations.py`, lines 224-400+
- **Problem:** `handle_bot_mention()` exceeds 250+ lines
- **Fix:** Extracted `_execute_tool_calls()` and `_synthesize_tool_response()` helper methods to reduce complexity

### LOW PRIORITY

#### Issue 2.7: Unused Import
- **File:** `bot/media_processor.py`, line 11
- **Problem:** `subprocess` imported but never used
- **Fix:** Remove unused import

#### Issue 2.8: Hardcoded Model Names
> **Status:** ⚠️ PARTIAL — MODEL_PRICING updated (obsolete models removed, current models added) but still in Python dict
- **File:** `bot/cost_tracker.py`, lines 8-19
- **Problem:** Model pricing hardcoded in Python
- **Fix:** MODEL_PRICING dict updated to remove obsolete models and add current model pricing. Full externalization to config/database still pending.

---

## 3. SECURITY CONCERNS

### HIGH PRIORITY

#### Issue 3.1: Credentials in Debug Logs
- **File:** `bot/iracing_client.py`, lines 237-239
- **Problem:** Debug logging prints query parameters which may contain sensitive data
- **Fix:** Sanitize logs; never print full URLs/params

#### Issue 3.2a: SQL Injection in DataRetriever
> **Status:** ✅ FIXED — Parameterized queries in data_retriever.py
- **File:** `bot/data_retriever.py`
- **Problem:** Dynamic query construction vulnerable to SQL injection
- **Fix:** All queries now use parameterized statements

#### Issue 3.2b: Prompt Injection in Debate Transcripts
> **Status:** ✅ FIXED — Content sanitization added
- **File:** `bot/features/debate_scorekeeper.py`
- **Problem:** User-supplied debate transcripts could inject prompts into LLM context
- **Fix:** Debate transcript content sanitized before LLM submission

#### Issue 3.2c: Event Cancellation Authorization
> **Status:** ✅ FIXED — Permission check added
- **File:** `bot/iracing_event_commands.py`
- **Problem:** Any user could cancel events created by others
- **Fix:** Permission check ensures only creator or admin can cancel

#### Issue 3.2d: SHA-256 Cache Keys
> **Status:** ✅ FIXED — MD5 replaced with SHA-256
- **File:** `bot/tool_executor.py`
- **Problem:** Cache keys generated using MD5
- **Fix:** `_cache_key()` helper now uses SHA-256

#### Issue 3.2e: HTTPS Enforcement for APIs
> **Status:** ✅ FIXED — Weather and Wolfram migrated to HTTPS
- **Files:** `bot/weather.py`, `bot/wolfram.py`
- **Problem:** Some API calls used HTTP instead of HTTPS
- **Fix:** All external API calls enforce HTTPS/TLS

### MEDIUM PRIORITY

#### Issue 3.2: No Rate Limiting on Expensive Operations
- **Files:** `bot/llm_tools.py`, various feature files
- **Problem:** Stats operations can trigger database scans without limits
- **Fix:** Add rate limiting: "1 call per 30 seconds per user"

#### Issue 3.3: Plaintext API Keys
- **File:** `.env` (documented in `.env.example`)
- **Problem:** Non-iRacing API keys stored plaintext in .env
- **Fix:** Enforce restrictive permissions; document `chmod 600 .env`

---

## 4. ARCHITECTURAL ISSUES

### HIGH PRIORITY

#### Issue 4.1: Tight Coupling Between Database and Features
- **Files:** Multiple feature files
- **Problem:** Each feature directly calls `db.get_connection()`, `db.store_*()` methods
- **Impact:** Hard to test; schema changes require updates across files
- **Fix:** Create repository abstraction layer

#### Issue 4.2: LLM Client Initialized Without Cost Tracker
- **File:** `bot/main.py`, lines 73, 192
- **Problem:** LLM initialized before on_ready(); cost tracking won't work for early calls
- **Fix:** Defer LLM initialization to on_ready() or use lazy initialization

### MEDIUM PRIORITY

#### Issue 4.3: Missing API Client Abstraction
- **Files:** `bot/iracing_client.py`, `bot/search.py`, `bot/weather.py`
- **Problem:** Each client implements own retry/timeout/error handling
- **Fix:** Create base `APIClient` class with standard resilience

#### Issue 4.4: Missing Dependency Validation
- **File:** `bot/features/iracing.py`
- **Problem:** Features don't validate required dependencies at startup
- **Fix:** Add startup validation; fail fast with clear messages

---

## 5. BEST PRACTICES GAPS

### HIGH PRIORITY

#### Issue 5.1: Print Statements Instead of Logger
- **Files:** Throughout codebase
- **Problem:** 44+ print() statements in database.py alone
- **Fix:** Replace with logger.info(), logger.debug(), logger.error()

#### Issue 5.2: Missing API Request/Response Logging
- **Files:** `bot/iracing_client.py`, `bot/search.py`, `bot/llm.py`
- **Problem:** No audit trail of external API calls
- **Fix:** Add request/response logging with sensitive data redacted

### MEDIUM PRIORITY

#### Issue 5.3: Scattered Configuration
> **Status:** ⚠️ PARTIAL — `constants.py` created for SELF_CONTAINED_TOOLS and other shared constants
- **Files:** Hardcoded values throughout codebase
- **Problem:** No single source of truth for configuration
- **Fix:** `constants.py` module created for tool-related constants. Full typed config still pending.

#### Issue 5.4: No Test Coverage
- **Problem:** No `tests/` directory found
- **Fix:** Create test suite for database, LLM, and feature logic

#### Issue 5.5: Missing Documentation for Complex Logic
- **Files:** `bot/rag.py`, `bot/handlers/conversations.py`
- **Problem:** No docstrings on complex functions
- **Fix:** Add comprehensive docstrings; create ARCHITECTURE.md

#### Issue 5.6: No Health Check Endpoint
- **Problem:** No way to monitor bot health externally
- **Fix:** Add background task that logs heartbeat

#### Issue 5.7: Inconsistent Timestamp Handling
- **Files:** `bot/database.py`, `bot/tasks/background_jobs.py`
- **Problem:** Mix of `datetime.now()` and `datetime.now(timezone.utc)`
- **Fix:** Enforce UTC everywhere

---

## 6. RATE LIMITING GAPS

### MEDIUM PRIORITY

#### Issue 6.1: Unused Concurrent Request Limiter
- **File:** `bot/handlers/conversations.py`, lines 44-51
- **Problem:** `USER_CONCURRENT_REQUESTS` declared but never enforced
- **Fix:** Add check in `handle_bot_mention()` before processing

#### Issue 6.2: iRacing Rate Limiting Incomplete
- **File:** `bot/iracing_client.py`, lines 33-34
- **Problem:** No exponential backoff on 429 responses
- **Fix:** Implement proper exponential backoff

---

## 7. DATA INTEGRITY ISSUES

### MEDIUM PRIORITY

#### Issue 7.1: No Transaction Isolation
> **Status:** ✅ FIXED — Separate `get_connection()` (transactional) and `get_autocommit_connection()` (reads) methods
- **File:** `bot/features/claims.py`, lines 113-177
- **Problem:** Multi-step operations not wrapped in transactions
- **Fix:** Use `BEGIN; ... COMMIT;` or `SELECT ... FOR UPDATE`

### LOW PRIORITY

#### Issue 7.2: Deleted Messages in Stats Cache
- **Problem:** Deleted messages not cleaned from stats cache
- **Fix:** Add cache invalidation on message deletion

---

## Recommended Remediation Priority

### Phase 1 (Critical - 1 week)
1. Fix N+1 embedding queries (Issue 1.1)
2. Add composite database indexes (Issue 1.2)
3. Fix bare exception handlers (Issue 2.1)
4. Remove global mutable state (Issue 2.3)
5. Fix LLM cost tracker initialization (Issue 4.2)

### Phase 2 (Important - 2 weeks)
1. Replace print() with logger (Issue 5.1)
2. Add API request/response logging (Issue 5.2)
3. Implement concurrent request limiting (Issue 6.1)
4. Add input validation to database operations (Issue 2.4)
5. Implement proper iRacing rate limiting (Issue 6.2)

### Phase 3 (Maintenance - ongoing)
1. Create repository abstraction layer (Issue 4.1)
2. Add comprehensive test suite (Issue 5.4)
3. Refactor long functions (Issue 2.6)
4. Create API client base class (Issue 4.3)
5. Add architectural documentation (Issue 5.5)

---

---

## February 2026 Comprehensive Refactoring Summary

The following architecture changes were made during the comprehensive refactoring:

**conversations.py Refactoring:**
- `_execute_tool_calls()` extracted: handles tool call execution with 30-second timeout
- `_synthesize_tool_response()` extracted: handles synthesis LLM pass for tool results
- `SELF_CONTAINED_TOOLS` imported from `constants.py` instead of hardcoded
- Tool execution runs in parallel via `asyncio.gather()`

**Security Hardening:**
- SQL injection fix in DataRetriever (parameterized queries)
- Prompt injection defense in debate transcripts (content sanitization)
- Event cancellation permission check (creator/admin only)
- HTTPS enforcement for weather/wolfram APIs
- SHA-256 cache keys (upgraded from MD5)

**Cost Optimization:**
- Search results reduced from 7 to 5 (with 200-char snippets)
- Claims and fact-check use centralized `simple_completion()` with cost tracking
- Token estimation via optional `tiktoken` dependency
- Configurable cost alert threshold (`COST_ALERT_THRESHOLD` env var)
- iRacing parallel fetch for faster data retrieval

**New Dependencies:**
- `cachetools` -- in-memory TTL caching
- `tenacity` -- retry logic with backoff
- `tiktoken` -- optional, accurate token counting

---

*Note: All findings are based on static code analysis. Runtime profiling and integration testing would reveal additional performance bottlenecks.*
