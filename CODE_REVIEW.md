# WompBot — Final Consolidated Code-Review Report

**Scope:** 80 Python files (~45k LOC), SQL schema/migrations, Docker infra, dependency audit. 129 subsystem findings (high/critical adversarially verified) plus pip-audit, bandit, and inventory data.

---

## 1. Executive Summary

WompBot is a feature-rich, actively-refactored Discord bot with a strong recent track record of latency and security hardening. However, this review surfaced a cluster of **fully-broken user-facing features that fail silently** (each masked by a broad `except` that returns a generic error), a **large unpatched dependency-CVE exposure on libraries that process untrusted user input**, and **systemic event-loop blocking** in command/feature paths that the project's own design principles say should be off-loaded. There are also two genuine **SSRF-guard bypasses** and pervasive **repo hygiene drift** (the docs claim cleanups that were never committed).

Nothing here is a remote-code-execution or data-loss catastrophe, but several flagship commands (GDPR export, iRacing driver comparison, 5 team/event commands, event cancellation) are **100% non-functional right now** and ship to users as opaque "Error" messages.

### Top actions, in priority order

1. **Fix the silently-broken features (all trivial/small, high user impact):**
   - GDPR data export — cursor-after-close bug, export *always* returns None (`gdpr_privacy.py:395`).
   - iRacing `/iracing_compare_drivers` — unterminated docstring deletes the method (`iracing_viz.py:1931`).
   - 5 iRacing team/event commands — `NameError: iracing_viz` never injected (`iracing_team_commands.py`, `iracing_event_commands.py`).
   - `!cancelevent` — queries non-existent column `created_by` (`events.py:375`).
   - Debate analysis — `generate_response` called with misaligned positional args → `retry_count=None` crashes every debate scoring call (`debate_scorekeeper.py:515,570,278`).
2. **Patch CVE-bearing dependencies** that touch user input: `pillow`, `yt-dlp`, `aiohttp`, `requests`, `cryptography` (47 CVEs across 9 packages — see §7).
3. **Close the two real SSRF bypasses:** media-download redirect/rebind bypass (`media_processor.py`) and disable redirects + re-validate.
4. **Move blocking work off the event loop** in GDPR commands, `/mystats`, stats/flow/dashboard, fact-check, and all iRacing viz renders (`asyncio.to_thread`).
5. **Introduce a real migration runner** — initdb-only mounting means migrations 12–17 and the orphaned `weather_preferences` / `iracing_participation_history` tables never apply to existing or fresh deployments.
6. **Repo hygiene sweep:** delete `*.backup` files, stray `0` / `review.txt`, ~41 MB of committed iRacing image assets the docs claim were removed; reconcile CLAUDE.md drift.
7. **Establish baseline engineering hygiene:** add a linter (would have caught the dead-code, unused-import, and unreachable-method findings) and a smoke-test/CI step (would have caught all 5 broken-feature bugs).
8. **Decide the torch/CUDA bloat question** — `llmlingua` pulls multi-GB CUDA wheels into a CPU-only image.

---

## 2. Critical & High-Severity Issues

These are deduplicated and grouped. Each was adversarially verified; verified severity is noted where it differs from the reviewer's original.

### 2.1 Broken features that fail silently (correctness)

| Feature | Location | What happens | Fix |
|---|---|---|---|
| **GDPR data export** (verified high) | `bot/features/gdpr_privacy.py:395` (cursor opened 254, closed 392) | The `data_export_requests` INSERT runs *outside* both the `with cursor` and `with get_connection` blocks. `cur.execute()` on a closed cursor raises `InterfaceError`, caught by the outer `except`, so `export_user_data` **always returns None** → `/download_my_data` always replies "Failed to export your data." Breaks GDPR Art. 15 self-service. | Move the INSERT (+ audit log + return) inside the open cursor block, or before building the summary. Add a smoke test asserting a dict is returned. |
| **iRacing `/iracing_compare_drivers`** (verified high) | `bot/iracing_viz.py:1931`; call site `slash_commands.py:2999` | A bare `"""` opens a docstring whose closing quotes were deleted, swallowing ~90 lines plus the entire `create_driver_comparison` method. AST confirms the method no longer exists → `AttributeError` on every call, surfaced as generic "Error comparing drivers." `create_recent_races_dashboard` is also broken (0 call sites). | Restore the closing `"""`; split `create_driver_comparison` back out. Add a `hasattr(viz, 'create_driver_comparison')` smoke test. |
| **5 iRacing team/event commands** (verified **critical**) | `iracing_team_commands.py:340,364,391`; `iracing_event_commands.py:198,247` | `iracing_viz` is referenced as a bare name but is never imported and is not a parameter of `setup_iracing_team_commands`/`setup_iracing_event_commands`. Every call to `/iracing_team_info`, `/iracing_team_list`, `/iracing_my_teams`, `/iracing_event_roster`, `/iracing_upcoming_races` raises `NameError`. The methods are instance methods of `iRacingVisualizer`, so a plain `import` won't fix it. | Add `iracing_viz` as a parameter to both setup functions; thread the instance through from `events.py` (already available). |
| **`!cancelevent` / `cancel_event`** (verified high) | `bot/features/events.py:375`; schema `sql/init.sql:202` | WHERE clause filters on `created_by`, but the column is `created_by_user_id`. Every call raises `UndefinedColumn`, swallowed, returns False → **no event can ever be cancelled.** | Change `created_by` → `created_by_user_id`. Add a create-then-cancel regression test. |
| **Debate analysis / scoring** (verified high) | `bot/features/debate_scorekeeper.py:515,570,278` | `generate_response` is called with 10 positional args that omit the `rag_context` slot, so `0` lands in `rag_context` and `None` lands in `retry_count`. `None > 0` (llm.py:637) raises `TypeError`, and the handler's `retry_count < 2` raises a *second* uncaught `TypeError` → every `_analyze_debate`, JSON-retry, and `_extract_factual_claims` call crashes. (Note: the title's "max_tokens lost / personality=3000" claim is wrong; `max_tokens` actually arrives correctly.) | Use keyword args at all three call sites; ensure `retry_count` is never `None`. Mirror the correct 12-arg form in `trivia.py:331`. |

### 2.2 Dependency CVE exposure (security — treated as high)

47 CVEs across 9 packages (pip-audit). The high-priority subset processes untrusted user input directly:

- **pillow 11.0.0 → 12.2.0** (6 CVEs) — decodes user-uploaded images in `media_processor.py`.
- **yt-dlp 2024.12.6 → 2026.6.9** (5 CVEs) — runs on user-supplied YouTube/video URLs.
- **aiohttp 3.13.3 → 3.14.1** (21 CVEs) — `github_monitor.py`, media fetches.
- **requests 2.32.5 → 2.33.0** (CVE-2026-25645) — nearly every external API call.
- **cryptography 46.0.3 → 48.0.1** (6 CVEs) — Fernet credential encryption.

See §7 for the full plan. These are non-breaking patch/minor bumps and should ship immediately.

### 2.3 SSRF guard bypass in media downloads (verified high)

**Where:** `bot/media_processor.py:72` (HEAD `allow_redirects=True`), `:89` (GET with no `allow_redirects=False`); `_is_safe_url` validates only the *original* host (lines 44–64), reached from user-supplied URLs in `conversations.py:634-639`.

**Why it matters:** An attacker hosts a public URL that passes `_is_safe_url`, then 302-redirects to `http://169.254.169.254/latest/meta-data/` or an internal service. Neither the HEAD nor the streaming GET re-validates the redirect target, so the documented SSRF defense is bypassed. (Response read-back is constrained because bytes go through PIL/ffmpeg, but the *blind* internal request is fully real.) A secondary TOCTOU/DNS-rebinding window also exists.

**Fix:** Set `allow_redirects=False` on both HEAD and GET and re-run `_is_safe_url` on each redirect hop; or resolve+pin the validated IP and connect to it with an explicit `Host` header.

### 2.4 Event-loop blocking in GDPR / `/mystats` / stats commands (verified medium, was high)

Multiple async command handlers run synchronous psycopg2 work directly on the loop, freezing all bot I/O and heartbeats:

- **GDPR commands** — `privacy_commands.py:185` calls `export_user_data` (~14 sequential queries incl. a 10k-row `messages` SELECT) with no `to_thread`. (Consent/delete paths are lighter than originally claimed; the delete-from-handler claim was refuted — heavy delete runs only in the daily background job.)
- **`/mystats`** — `slash_commands.py:3800-3973`: ~11 sequential queries incl. a `DENSE_RANK()` scan over the full `messages` table, on-loop.
- **stats/flow/dashboard** — `slash_commands.py:116,123,3593,3608`: sync fetch + CPU-bound TF-IDF/networkx + matplotlib render, all on-loop.

These are low-frequency, explicitly-invoked, already-deferred commands, so the corrected severity is **medium** — but they violate the project's own documented "event loop unblocking" principle. **Fix:** wrap each in a single `await asyncio.to_thread(...)`.

### 2.5 Redis default password committed (verified low, was high)

**Where:** `docker-compose.yml:111,155,160` — `${REDIS_PASSWORD:-wompbot_redis_secret}`; `.env.example` has no `REDIS_PASSWORD` entry.

**Verification correction:** The Redis service publishes **no host ports** — it is reachable only on the internal Docker bridge. So the "anyone who can reach the port" threat model does not hold; this is defense-in-depth on regenerable cache data. Real secrets-hygiene weakness, but **low**, not high. **Fix:** remove the `:-wompbot_redis_secret` fallback, make `REDIS_PASSWORD` required (fail fast), document it in `.env.example`.

### 2.6 Migrations never apply on existing or fresh deployments (verified medium)

Two tables are referenced by live code but their migrations are **not mounted** in `docker-compose.yml` and there is **no migration runner**:

- **`weather_preferences`** (`sql/weather_preferences_migration.sql`, not mounted) — `database.py:1435,1450,1470` → `!weatherset`/`!weatherclear`/saved-location `!weather` break on fresh deploy (existing volumes unaffected).
- **`iracing_participation_history`** (`bot/migrations/add_iracing_participation_history.sql`, not mounted) — `database.py:881` snapshot writes + reads fail silently.

Separately, **all** numbered migrations run only on an empty data dir, so 12–17 never apply to upgraded instances (§5/§7). **Fix:** adopt an idempotent migration runner with a `schema_migrations` table; renumber the orphaned files into `sql/` and mount them.

---

## 3. Security

### 3.1 Dependency CVEs
See §2.2 and §7. The dominant exposure is the 47-CVE backlog; the user-input-facing packages (pillow, yt-dlp, aiohttp, requests) are the priority.

### 3.2 f-string SQL — **confirmed NOT exploitable** (false positive)
Bandit flags f-string SQL in `slash_commands.py` (`/mystats`, ~3803–3931) and `rag.py:317`. Verified across multiple reviewers: the only interpolated value is `time_filter`, which is one of two hard-coded constant strings (`''` or `'AND m.timestamp BETWEEN %s AND %s'`), with `.replace('m.timestamp', ...)` operating on that same constant. All user values (`user_id`, dates, `days` clamped 1–365) flow through `%s` bind params. **No injection vector.** Action: do **not** parameterize the fragment; instead select between named literal query constants (removes the brittle `.replace()` hack) or add a scoped `# nosec B608` with a comment so it isn't re-flagged or "fixed" wrongly.

### 3.3 SSRF posture
- **Media downloads (high):** redirect/rebind bypass — §2.3.
- **`image_search` (low):** `tool_executor.py:557` issues a HEAD to DDG-returned URLs with redirects on and no `_is_internal_url` check. Run through `_is_internal_url`, set `allow_redirects=False`.
- **`url_preview` (medium):** `tool_executor.py:887-944` — resolve-then-fetch TOCTOU window; `allow_redirects=False` already mitigates the redirect vector. Also no body-size cap (§4) → reads unbounded response into memory.
- **RSS feeds (low):** `rss_monitor.py:39-48` fetches admin-supplied feed URLs via feedparser with no RFC1918/metadata validation, re-fetched every 5 min. Admin-gated, but reuse the existing `_is_safe_url` helper.
- **YouTube path (low):** `media_processor.py:203-394` — strict 11-char ID regex is good, but yt-dlp download path has no per-user rate limit (cost/DoS).

### 3.4 Prompt injection (verified medium)
Raw user message content is f-string-interpolated into LLM prompts with no fencing in `fact_check.py:64,77`, `claims.py:55,244`, `hot_takes.py:199`, plus YouTube transcripts/search snippets/tool results in `conversations.py` and `llm.py:538-547`. The debate path already wraps content in XML tags; that defense was not applied here. Most damaging: the fact-check verdict is free-text-matched (`'verdict: true' in lowercased output`, `fact_check.py:142`) and persisted as an authoritative ✅/❌. Mitigated by a strict system preamble + the ⚠️-reaction gate (requires a second user) → medium. **Fix:** wrap untrusted/tool content in delimited "data only" blocks; parse the verdict from a constrained field, not free text.

### 3.5 Raw `str(e)` leaked to users (medium)
~76 command handlers send raw exception text to the channel (`prefix_*.py`, `slash_commands.py`, `privacy_commands.py`, `main.py:320-328` global handler, game modules `devils_advocate.py`/`jeopardy.py`/`polls.py` via `events.py:411`). psycopg2/requests exceptions can leak SQL fragments, table/column names, internal URLs, and API tokens in query strings. The project's prior audits fixed this elsewhere; the command layer reintroduces it. **Fix:** a single helper that logs `exc_info=True` server-side and returns a generic user message.

### 3.6 Credential storage co-location (medium)
`credential_manager.py:18` / `encrypt_credentials.py:46` write `.encryption_key` and `.iracing_credentials` into `/app`, which is the bind-mounted `./bot` source tree (`docker-compose.yml:119`) — and the repo lives under OneDrive. `.gitignore` excludes them today, but key + ciphertext co-located in a cloud-synced, developer-visible path means one mistake exposes both. **Fix:** move secrets to a named volume or Docker secrets outside `/app`; separate key from ciphertext.

### 3.7 Other
- **Cost-alert recipient by mutable username** (`cost_tracker.py:45`) — matches `member.name == 'wompie__'`; usernames are changeable/non-unique. Use `WOMPIE_USER_ID`.
- **Currency-convert query-param injection** (`tool_executor.py:1596`) — LLM-controlled currency codes f-string-interpolated into the Frankfurter URL. Bounded (fixed low-risk host, no auth token), but pass via `params=` dict instead.
- **Inconsistent admin authorization** — Discord-perms vs bot-admin vs super-admin gates mixed across the command surface; pick one model (`is_bot_admin_ctx`) and document it.
- **Game-start LLM-cost abuse** (jeopardy/trivia/devils_advocate) — no per-user/guild rate limit on LLM-backed game starts; the per-channel guard is trivially bypassed across channels. Use the existing `feature_rate_limits` infra.
- **Discord Views lack `interaction_check`** (`team_menu.py`) — currently masked by DM-only delivery; add owner checks as defense-in-depth.

---

## 4. Performance

### 4.1 Event-loop blocking (the dominant theme)
Beyond §2.4:
- **iRacing viz renders (verified high):** 13+ call sites in `slash_commands.py` (1185,1754,1916,2018,2223,2840,3156,3354) + team/event commands call `iRacingVisualizer` methods directly; each does synchronous matplotlib `savefig` at dpi 150–160 (hundreds of ms to ~1-2s) on the loop. Even `async def create_meta_chart` does its render synchronously inside the coroutine. (Correction: this module is matplotlib-only — the "Plotly+Kaleido/Chromium" attribution applies to `tool_executor.py:279/314`, not these files.) **Fix:** `await asyncio.to_thread(...)`, after fixing the global-pyplot thread-safety issue (§5).
- **fact-check (verified medium):** `fact_check.py:38` (sync Tavily/requests search) and `:113` (sync DB write) on the loop; only the LLM call is `to_thread`-wrapped. Rate-limited ⚠️-reaction trigger → medium.
- **on_reaction_add:** `events.py:587,620` — `check_feature_rate_limit`/`record_feature_usage` run sync on the loop.
- **DNS resolution:** `media_processor.py:53` — `_is_safe_url`'s `getaddrinfo` runs on the loop before dispatch to `to_thread`.
- **GDPR/cost paths:** `cost_tracker.record_costs_sync` is threaded in `generate_response` but called inline in `simple_completion` (`llm.py:240`), e.g. `jeopardy.py:127` awaits a sync function. Standardize to always-threaded.
- **Hot-take scoring (medium):** `hot_takes.py:213` hand-rolls `requests.post` to OpenRouter (sync, on-loop, no retry, no cost tracking) instead of `LLMClient.simple_completion`. Replace with `to_thread(self.llm.simple_completion, ...)`.

### 4.2 N+1 / fetch-all-then-compute-in-Python
- **`precompute_stats` (medium):** `background_jobs.py:284` runs hourly, per guild × [7,30]-day windows, pulling the *entire* message set into Python for network/TF-IDF/primetime. Push aggregation into SQL; skip recompute when `max(timestamp)`/`COUNT` unchanged; widen the 30-day cadence.
- **Cost-alert path (medium):** `check_cost_alert_threshold` (`database.py:1217`) holds a connection while calling `get_total_cost`, opening a *second* connection; `get_total_cost` does a **full-table scan of `api_costs`** (`SELECT SUM(cost_usd)` with no time bound) on **every** recorded cost. Inline a single month-bounded query.
- **Random-content selection (medium):** `quote_of_the_day.py:148` (COUNT + random OFFSET, two round trips + TOCTOU); `who_said_it.py:87` and `jeopardy.py:226` (`ORDER BY RANDOM()` full scan + sort, jeopardy pulls 500 rows per start, who_said_it has no time bound). Use `TABLESAMPLE`/timestamp-window+offset.
- **Watchlist baseline (medium):** `watchlists.py:199` overwrites `last_price` every minute, so the alert baseline is always "this minute vs last minute" — a gradual ±5% drift **never** triggers, and the "daily summary" % is meaningless. Track a stable reference price separately.
- **Game session persistence:** trivia/debate/devils_advocate re-serialize the *entire* session JSONB on every message (O(n²) writes); unlimited wrong-answer resubmission in trivia (`trivia.py:557`) yields hundreds of DB round trips per round. Throttle/incrementalize persistence; rate-limit answers.

### 4.3 Caching
- **iRacing global request lock (verified medium, was high):** `iracing_client.py:258` holds `_request_lock` across the entire HTTP round-trip, so the `Semaphore(10)` in `iracing_meta.py:253` gives **zero** real concurrency — a 50-subsession `/iracing_meta` runs fully sequential. Hold the lock only for the rate-limit pacing window, then release before `session.get`.
- **Unbounded in-memory caches:** `iracing.py:54` (profile/career/schedule, never evicted), `gdpr_privacy.py:32` (`_consent_cache`, `_cleanup` never called), `iracing_popularity_cache` never expires (`slash_commands.py:3013`), series-autocomplete lost its TTL gate in refactor (`slash_commands.py:1031`). Use `cachetools.TTLCache` (already a dependency) and wire the module-level popularity cache into `register_slash_commands`.
- **`register_vector` per checkout:** `rag.py:137,205,314` re-registers pgvector on every pooled-connection acquisition (hot path). Register once per physical connection via a pool init hook.
- **Redis stampede:** `redis_cache.py:120` `get_or_set` is non-atomic; concurrent misses on hot keys all run the fallback. Add SET-NX single-flight for hot keys or document the non-atomicity.

### 4.4 Image/dependency bloat
`llmlingua==0.2.2` pulls `torch` + ~15 `nvidia-cuda-*` wheels (multi-GB) into a **CPU-only** container (no `--gpus`). Pin CPU-only torch (`torch==x.y.z+cpu` from the CPU index) or drop `llmlingua` entirely. Directly reduces image size, build time, and CVE surface.

---

## 5. Correctness / Latent Bugs

Beyond the broken features in §2.1:

- **Channel semaphore over-release (verified medium):** `conversations.py:993` assigns `channel_lock` before the timed acquire; on `TimeoutError` the `finally` (1378) still calls `release()`. `asyncio.Semaphore` does **not** raise on over-release, so the `except ValueError: pass` is dead code and the channel's effective concurrency cap inflates permanently (4, 5, 6…). The cleanup at line 389 only evicts when `_value == 3`, so the inflated semaphore is never reclaimed. Track an `acquired` boolean; release only when truly acquired. The same spurious-release pattern affects `USER_CONCURRENT_REQUESTS` (early returns before the increment at line 978 decrement another in-flight request's count).
- **Global pyplot state (medium):** `iracing_viz.py` (25×) / `viz_tools.py` use `plt.figure()/plt.savefig()/plt.close()` with no figure arg. Safe today (serialized on one thread) but **corrupts under the `to_thread` fix in §4.1** — convert to figure-local `fig = Figure(); fig.savefig(); plt.close(fig)`. This is a prerequisite for off-loading renders.
- **GitHub `all` watch type (low):** `github_monitor.py:258` tracks one `last_event_id` across releases/issues/PRs (disjoint ID spaces) → duplicate posts. Use per-type cursors.
- **RSS cap data loss (low):** `rss_monitor.py:221` caps to 3 newest but advances the cursor past the un-posted older ones → permanent loss on bursty feeds. Post oldest-first, advance cursor only past posted entries.
- **Contradiction-check IndexError (medium):** `claims.py:283` indexes `past_claims[result['claim_number']-1]` with an unvalidated LLM number (IndexError swallowed → dropped contradiction; `0` → wrong attribution). Validate the index; use `.get('explanation')`.
- **Jeopardy / Who-Said-It substring matching (medium/low):** `jeopardy.py:465` and `who_said_it.py:160` treat any substring containment as correct — a 1–2 char guess wins (and in jeopardy *deducts* opponents' points). Require min length + substantial coverage / word-boundary match.
- **Naive `datetime.now()` vs UTC (multiple, low):** `rag.py:298,568`; `weather.py:168`; `chat_stats.py:32,86`; `quote_of_the_day.py`/`yearly_wrapped.py`; all game modules. Stored timestamps are UTC; naive local-time windows mis-bucket when container TZ ≠ UTC. Standardize on `datetime.now(timezone.utc)`.
- **`feyd` personality unreachable (low):** `llm.py:422-428` has no `feyd` branch, so a server configured as `feyd` silently falls back to default.
- **`should_search` over-filters (low):** `llm.py:297` negatives ('can you', 'could you', …) match before positive triggers → polite factual queries skip proactive search.
- **Session-persistence loaders never called (verified medium):** `debate_scorekeeper.py:83` / `trivia.py:95` loaders are dead; jeopardy/who_said_it/devils_advocate have no loader at all. The advertised "sessions survive restarts" feature doesn't work, and stale `is_active=TRUE` rows leak. Wire loaders into `on_ready` + add a startup reconciliation, or delete the persistence machinery.
- **`get_argumentation_profile` NameError (verified medium):** `debate_scorekeeper.py:978` calls `logger` but the file never imports logging; the error path itself crashes (caught upstream, so degraded not fatal). Add `import logging; logger = ...`.
- **Redundant `conn.commit()/rollback()` outside context manager (low):** `events.py:315,320,380,385,488,493` — manual rollback runs on a connection already returned to the pool (use-after-return), latent until the broken `cancel_event` query makes it fire every call. Let the context manager own the transaction.
- **`add_debate_message` uses deprecated `get_event_loop()`** with `except RuntimeError: pass` → saves silently dropped (`debate_scorekeeper.py:185`).
- **GitHub aiohttp session never closed** (`github_monitor.py:29`) → "Unclosed client session" + socket leak. Add `close()` wired into shutdown (mirror `iracing_client.py:1161`).
- **Chunk download omits Bearer token** (`iracing_client.py:835`) — inconsistent with every other request; fragile against API changes.
- **`get_linked_iracing_id` mis-typed** (`iracing.py:307`) — annotated `Optional[int]` but returns a tuple; callers compensate defensively.
- **TOCTOU in message-scheduler abuse limits** (`message_scheduler.py:81`) and **poll multi-vote** relying on exception-as-control-flow / a UNIQUE constraint that may be absent (`polls.py:184`).
- **Guild-timezone support is dead** for reminders/events — callers always pass `guild_id=None` (`reminders.py:186`, `events.py` via `prefix_features.py:562`), despite CLAUDE.md advertising it.

---

## 6. Architecture & Maintainability

- **God-files:** `slash_commands.py` (4014), `iracing_viz.py` (2961), `tool_executor.py` (1772), `database.py` (1667). The unterminated-docstring bug in `iracing_viz.py` is a direct symptom of files too large to review safely. Split by feature domain.
- **No tests / CI / linter.** This is the root cause of the §2.1 cluster — every one of those bugs (closed cursor, missing method, missing parameter, wrong column, arg misalignment) is caught by a smoke test that imports the module and invokes the command path, or by a linter (`pyflakes`/`ruff` flags undefined names, unreachable methods, unused imports). **Highest-leverage strategic action.**
- **Duplication / drift:** `iracing_graphics.py` (768 lines, imported `main.py:44`, never instantiated) duplicates `card_base.py` + `iracing_viz.py`; six `iRacingVisualizer` methods are dead (one with hardcoded fake sample data); `IRACING_LOGO_URL`/`IRACING_IMAGE_BASE` hardcoded in 3 files; `wolfram.py` has 3 never-called methods + unused import/URL.
- **Inconsistent transaction handling:** some modules manually `commit()/rollback()` inside the context manager (which already does it), some don't.
- **Inconsistent logging:** despite documented `print()→logger` sweeps, the command layer, privacy commands, game modules, `redis_cache.py`, `reminders.py`/`events.py`, and iRacing team/event setup still use `print()`/`traceback.print_exc()` (and one leaks raw tracebacks that may contain user data, `privacy_commands.py:230`).
- **Broad `except Exception` masking error categories** across all external-API tools (`tool_executor.py`, `weather.py`, `wolfram.py`) and analytics modules — conflates JSON/network/KeyError/Type errors into one opaque message, hiding real bugs (this is exactly how all the §2.1 features fail silently). Catch specific exceptions; log with `exc_info=True`.
- **Background-task crash recovery:** `background_jobs.py` `@tasks.loop` bodies swallow all errors with no `@loop.error` handler, no backoff, no alerting. Worse, reminders/scheduled messages call `mark_completed`/`mark_sent` in the `except` path (lines 433,887,892), so a transient Discord 5xx permanently marks an undelivered message done → **silent data loss**. Distinguish transient vs permanent failures with a bounded retry counter.

---

## 7. Dependencies — Upgrade Plan

### Bump now (CVE patches, non-breaking)
| Package | Current → Target | CVEs | Why now |
|---|---|---|---|
| `pillow` | 11.0.0 → 12.2.0 | 6 | Decodes user images |
| `yt-dlp` | 2024.12.6 → 2026.6.9 | 5 | User-supplied video URLs |
| `aiohttp` | 3.13.3 → 3.14.1 | 21 | Monitoring + media fetches |
| `requests` | 2.32.5 → 2.33.0 | CVE-2026-25645 | All external APIs |
| `cryptography` | 46.0.3 → 48.0.1 | 6 | Credential encryption |
| `python-dotenv` | 1.0.1 → 1.2.2 | CVE-2026-28684 | Config load |
| `curl-cffi` | 0.7.4 → 0.15.0 | CVE-2026-33752 | yt-dlp transitive |
| `wheel` | 0.45.1 → 0.46.2 | — | Build |
| `pip` | 24.0 → latest | 5 | Build toolchain |

These are patch/minor bumps; ship as one PR after a smoke run.

### Held for breaking changes (schedule deliberately, test in isolation)
`discord.py 2.6.4→2.7.1` (minor, low-risk — bump soon), `openai 1.x→2.x` (held — major), `numpy 1.26→2.x` (held — major, ABI), `pandas 2.2→3.0` (major), `redis 5.0→8.0` (major), `scikit-learn 1.5→1.9`, `tavily-python 0.3.9→0.7.26` (large gap — verify API).

### Torch/CUDA bloat decision
`llmlingua` → `torch` + ~15 CUDA wheels on a CPU-only image. **Decision:** if compression stays, pin `torch==<ver>+cpu` from `https://download.pytorch.org/whl/cpu`; if its value is marginal, drop `llmlingua` and the compression path. Either way removes multi-GB and a chunk of the CVE surface.

---

## 8. Repo Hygiene & Dead Code

CLAUDE.md documents cleanups that were never committed — the repo state contradicts the docs:

- **`.backup` files (tracked):** `bot/main.py.backup` (6135 lines, 258 KB), `bot/iracing_viz.py.backup` (3159 lines, 137 KB). Stale, divergent, pollute grep/reachability analysis (the `main.py.backup` copy is why `local_llm` looked reachable). `git rm` both; add `*.backup` to `.gitignore`.
- **~41 MB committed image assets:** `iRacing Logos/` (33 MB, 735 files) + `iracing_tracks_assets/` (7.9 MB) — CLAUDE.md claims the local-asset system was removed and replaced by API thumbnails; no Python references either dir. `git rm -r`; consider `git filter-repo` for clone size.
- **Stray root files:** `0` (32-byte shell-redirect artifact, likely a `2>0` typo for `2>/dev/null`) and `review.txt`. Delete; audit ops scripts for the bad redirect.
- **Dead modules:** `local_llm.py` (instantiated `main.py:75`, never used — and ships an "uncensored, no-guardrails" prompt, a latent liability), `backup_manager.py` (246 lines, never instantiated; real backups are the `postgres-backup-local` sidecar — README:969 still documents the dead path), `iracing_graphics.py` (768 lines), `update_logging.py` + `assets/normalize_logos.py` (one-shot codemods shipped into the image), `test_plotly_chart.py` (broken — calls a non-existent method, hardcoded `/tmp`).
- **Stale `.pyc`:** `__pycache__` has `slash_commands_new.cpython-314.pyc` for a deleted file, plus mixed 3.11/3.12/3.14 bytecode. Pin the interpreter to 3.11.
- **SQL cruft:** duplicate/conflicting `iracing_meta_cache` definitions (`init.sql:253` vs `migrations/add_iracing_meta_cache.sql`); entirely dead `add_iracing_advanced_features.sql` (6 unreferenced tables); duplicate index `idx_messages_guild_timestamp` (ASC vs intended DESC — the DESC variant is a silent no-op, `12_missing_indexes.sql:5`); redundant `idx_server_personality_server_id` (PK already covers it); non-idempotent `CREATE TRIGGER` in weather/trivia migrations; `init.sql` creates privacy/breach tables that `13_gdpr_trim` immediately drops.
- **Misc dead code:** unused imports (`poll_card.py:12 format_number`, `wolfram.py:7`), dead vars (`tool_executor.py:604`, orphan docstring `iracing_team_commands.py:52`), `_subsession_cache` docstring lies about caching failures (`iracing_meta.py:196`).

---

## 9. Prioritized Action Plan

### Quick wins (trivial/small effort, high value)

| # | Action | Location | Effort |
|---|---|---|---|
| 1 | Fix GDPR export cursor-after-close | `gdpr_privacy.py:395` | trivial |
| 2 | Restore unterminated docstring; split out `create_driver_comparison` | `iracing_viz.py:1931` | small |
| 3 | Inject `iracing_viz` into team/event setup functions | `iracing_*_commands.py` | small |
| 4 | `created_by` → `created_by_user_id` | `events.py:375` | trivial |
| 5 | Keyword args for `generate_response` in debate code | `debate_scorekeeper.py:515,570,278` | small |
| 6 | Bump CVE deps (pillow, yt-dlp, aiohttp, requests, cryptography, dotenv, curl-cffi, wheel) | `requirements.txt` | small |
| 7 | `allow_redirects=False` + re-validate on media HEAD/GET | `media_processor.py:72,89` | small |
| 8 | Track `acquired` boolean for channel semaphore + user counter | `conversations.py:993,978` | small |
| 9 | Add `import logging; logger=...` to debate_scorekeeper | `debate_scorekeeper.py:978` | trivial |
| 10 | Make `REDIS_PASSWORD` required; document in `.env.example` | `docker-compose.yml`, `.env.example` | small |
| 11 | Delete `.backup` files, `0`, `review.txt`, 41 MB assets; `.gitignore` them | repo root, `bot/` | trivial |
| 12 | Wrap GDPR export / `/mystats` blocking blocks in `to_thread` | `privacy_commands.py:185`, `slash_commands.py:3800` | small |
| 13 | Generic user error + `exc_info=True` logging (shared helper) | ~76 handlers, `main.py:320` | medium |
| 14 | Resolve cost-alert recipient by `WOMPIE_USER_ID` | `cost_tracker.py:45` | trivial |
| 15 | Inline month-bounded cost-alert query (kill full-table scan + double conn) | `database.py:1217` | small |

### Strategic (larger effort, foundational)

| # | Action | Why |
|---|---|---|
| A | **Add a linter (ruff/pyflakes) + smoke-test CI** | Would have caught the entire §2.1 broken-feature cluster and most dead-code/unused-import findings. Highest leverage. |
| B | **Idempotent migration runner** with `schema_migrations` tracking; renumber/mount orphaned migrations | Fixes weather_preferences + iracing_participation_history + the 12–17-never-apply class of bugs. |
| C | **Off-load all viz renders** to `to_thread` *after* converting pyplot to figure-local API | Removes the largest event-loop-blocking class; pyplot fix is the prerequisite. |
| D | **Wrap untrusted/tool content in delimited blocks; structured fact-check verdict parsing** | Closes the indirect-prompt-injection surface. |
| E | **Resolve the torch/CUDA bloat** (CPU-only torch pin or drop llmlingua) | Multi-GB image + CVE-surface reduction. |
| F | **Split god-files** (`slash_commands.py`, `iracing_viz.py`, `tool_executor.py`, `database.py`) | Files this large are why the docstring/arg-alignment bugs survived review. |
| G | **Background-task crash recovery** (`@loop.error`, transient-vs-permanent retry, stop mark-as-done-on-transient-failure) | Prevents silent reminder/scheduled-message data loss. |
| H | **Wire/repair or delete session-persistence loaders** + startup reconciliation of stale `is_active=TRUE` rows | Either deliver the advertised restart-survival feature or remove the dead, leaking machinery. |
| I | **Move secrets off the bind-mounted/OneDrive `/app` path** (named volume or Docker secrets) | Prevents key+ciphertext co-location exposure. |
| J | **Reconcile CLAUDE.md/README with reality** | Docs claim cleanups, configurable cost threshold, guild timezones, and restart persistence that don't exist in the committed code. |

---

**Bottom line:** the codebase is feature-rich and shows real prior hardening effort, but it is operating without the two safety nets (a linter and any test/CI) that would have caught every one of the five completely-broken commands found here. Ship the §9 quick wins immediately (broken features + CVE bumps + SSRF redirect fix), then invest in the strategic items A–C, which collectively address the root causes — no automated verification, initdb-only migrations, and on-loop rendering.