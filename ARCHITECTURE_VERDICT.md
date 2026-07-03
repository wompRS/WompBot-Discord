# WompBot — Architecture Verdict

*Lead architect's decision. Synthesizes four lens reviews (structure, data/concurrency, LLM pipeline, ops/testing) and the rebuild-adversary's case. Companion to `CODE_REVIEW.md` (bug-level findings); this document is about where to invest structurally.*

---

## 1. Verdict: Refactor incrementally. Do NOT rebuild.

**WompBot is fundamentally sound. Every genuine improvement the rebuild case points at is reachable on the current stack, incrementally, with the bot live the whole way. A rewrite is the strictly worse path to the same destination.**

The rebuild adversary made the honest case, and its two strongest arguments are *correct about the destination*: the bot should move to discord.py **Cogs** (killing the `register_*()` closure fan-out) and toward an **async-aware, seam-bounded data layer**. I agree with both goals. But the adversary itself concedes the decisive point: these are refactors you can perform 28 times independently, not a rewrite. The property that makes that safe is already true here — feature coupling is a shallow star (`main.py` → features; only `iracing_meta` and `claim_detector` are cross-imported), verified across the tree.

**Addressing the adversary's single strongest point — "the changelog is a long list of recurring bug classes (SQL injection in INTERVAL queries, tz bugs, double-commits, cache-key NameErrors); a clean-stack rewrite retires those categories."** This is the most seductive argument and it is backwards. Those changelog entries are not evidence the code is rotten — they are evidence it has been *de-mined*. Chesterton's Fence runs the length of this codebase: the SSRF hardening in `media_processor.py`, the semaphore over-release fix in `conversations.py` (commit `6efab51`), the RSS burst-delivery data-loss fix (`bd4d3b2`), the LLMLingua compression tuning, the `should_search` negative-pattern gate — each is institutional knowledge baked into working code. A rewrite inherits *none* of it and rediscovers each bug in production, on a bot real people use. And the categories the adversary wants to "retire structurally" are retirable *in place*: the INTERVAL SQL-injection class is already fixed via parameterized `INTERVAL '1 day' * %s`, and a ruff rule banning f-string SQL closes it permanently — no asyncpg required.

The context seals it. This is **solo-maintained** and just reached its healthiest state ever: 13 hardening commits, 40+ CVEs patched, ruff + CI added, an idempotent migration runner (`bot/db_migrations.py`), image slimmed 3.4 GB → 1.0 GB. A solo rewrite of "28 features + 26 tools + iRacing + RAG + GDPR" has **no user-visible benefit until the day it reaches parity** — a finish line that recedes. The realistic outcome is two half-maintained bots and a stalled migration. You do not throw away a freshly-hardened working system to reach a destination you can walk to.

**One caveat where the adversary is right and it must not be dismissed:** async coloring propagates. A *half*-migrated `database.py` means some callers `await db.x()` and some `await asyncio.to_thread(db.y)`. That transitional ugliness is real — but it is confined to one file's call sites and is temporary. It is a cost of the roadmap below, not a reason to reject it.

---

## 2. Current architecture — honest scorecard

| Dimension | Grade | Genuinely good | Real weakness (cited) |
|---|---|---|---|
| **Structure & boundaries** | B+ | Single composition root with explicit constructor injection (`main.py`, no service locator/globals); low feature coupling (star topology); tool dispatch is a clean dict-registry (`tool_executor.py:61-93`) | `register_*()` closure pattern — `register_events` takes ~28 kwargs, `register_slash_commands` is **one 4014-line function / 45 nested closures**; zero Cogs used anywhere (verified); god-files `slash_commands.py` (4014), `iracing_viz.py` (2961), `database.py` (1667/64 methods) |
| **Data & concurrency** | B | `get_connection()` context manager is disciplined (commit/rollback/putconn in `finally`, `database.py:57-68`); concurrency guards hardened (per-channel `Semaphore(3)`, acquire-only-release); migration runner is the right shape | **Executor/pool mismatch: 100 threads (`main.py:343`) vs `DB_POOL_MAX=25`, and psycopg2's pool raises `PoolError` instead of queueing** — silent data loss under load; **~45 `async def` DB methods block the event loop** (no `to_thread`); no `statement_timeout` anywhere; two disjoint migration systems (`sql/*` initdb-only vs `bot/migrations/*` every-boot) |
| **LLM / tool pipeline** | B | Concurrent tool exec under 30s timeout; parallel context assembly (`asyncio.gather`); intent gating + self-contained-tool split are real optimizations; fails soft everywhere | **Tool use is single-turn — zero `tool_call_id`/`role:"tool"` threading in the entire codebase (verified).** No agentic loop → no chained tools ("search then chart" is impossible despite tool descriptions promising it); routing done by **two overlapping keyword walls** (`should_search` + `_select_tools_for_message`); conversation rebuilt from strings each turn (no durable transcript) |
| **Ops & testing** | C+ | Secrets handled right (`.env` gitignored, Fernet creds `chmod 600`, Redis fail-loud); good logging infra; DI makes the code *already testable* | **Zero tests** (CI is ruff + compileall only); **`bot` container has no healthcheck** (only postgres/redis do — verified); ~40 env vars via 60 scattered `os.getenv` (`DB_POOL_MIN` drifts 2/5/25 across sources); **22 files still use `print()`** despite changelog claiming migration done; ~37 silent `except: pass`; deploy substrate is Docker Desktop (dies on host sleep) |

**Net:** a solid B+ system with a low capability ceiling and an under-built ops floor — both raisable in place.

---

## 3. Target architecture

Nothing below requires a rewrite. It is the same discord.py, the same psycopg2 pool, the same feature classes — reorganized behind seams that already almost exist.

### Package structure (destination)

```
bot/
  main.py                 # composition root: build services, add_cog(...) x N
  config.py               # NEW: single Settings object; all ~40 env vars, defaults + validation in ONE place
  core/
    pipeline.py           # ConversationPipeline (was conversations.py) — ordered stages, RequestContext dataclass
    agent_runner.py       # NEW: the tool-use loop (append role:"tool" results, re-call, cap at ~4 steps)
    tool_executor.py      # UNCHANGED — the registry is already the right pattern
    llm.py  rag.py  search.py  compression.py  media_processor.py
  data/                   # database.py split by bounded context, behind a facade
    pool.py               # ThreadedConnectionPool + get_connection() (adds SET LOCAL statement_timeout)
    messages_repo.py  stats_repo.py  iracing_cache_repo.py
    ratelimit_repo.py  cost_repo.py  trivia_repo.py  config_repo.py
  cogs/                   # discord.py Cogs replace register_*() closures
    stats_cog.py  iracing_cog.py  games_cog.py  admin_cog.py
    monitoring_cog.py  privacy_cog.py  listeners_cog.py   # on_message/on_reaction
  features/               # UNCHANGED — the star topology is the strength; do not touch
    <28 feature classes>
```

**God-file decomposition (concrete):**
- `slash_commands.py` (4014 lines, 45 closures) → dies by attrition into ~6 domain Cogs. Each closure becomes a Cog method whose deps are `self.db`, `self.llm` — instantiable in a test with a mock context. The 28-kwarg `register_*` signatures collapse into Cog `__init__(db, chat_stats, ...)` with only the 2-4 deps that group needs.
- `database.py` (1667 lines, 64 methods, 8 fused bounded contexts) → per-domain repositories, but **keep `Database` as a facade that composes them** (`self.trivia = TriviaRepo(pool)`), delegating existing `db.create_trivia_session(...)` calls so nothing breaks. Migrate call sites feature-by-feature.
- `iracing_viz.py` (2961 lines) → split by artifact type (`profile_card.py`, `meta_charts.py`, `leaderboard.py`, `schedule_render.py`). Pure cohesion cleanup, leaf code, do opportunistically. **Low priority.**
- `tool_executor.py` (1776) → **leave as-is.** It is cohesive and the registry is already correct. Tools are not commands; do not force them into Cogs.

### Data & concurrency approach

Keep psycopg2 + `ThreadedConnectionPool` + `to_thread`. **Do NOT migrate to asyncpg** — at Discord-bot QPS the async-driver win is negligible and the rewrite touches all ~30 SQL-bearing files for no user-visible gain. Instead:
1. **Reconcile executor and pool.** Cap the executor to what the pool can serve *or* gate all DB work behind a global `asyncio.Semaphore(DB_POOL_MAX - margin)`, and make `get_connection()` **wait** for a connection (bounded retry) instead of raising `PoolError`. This converts silent `PoolError → None` failures into honest backpressure. **Highest-leverage 15 minutes in the codebase.**
2. **Finish the `to_thread` migration.** The right pattern already exists in `polls.py` (`_create_poll_sync` + `await asyncio.to_thread`). Extract the ~45 offending bodies (hot paths first: `claims.py`, `hot_takes.py`, `rag.py`) and add a CI grep that fails on `async def` containing `get_connection()` without `to_thread`.
3. **Add `SET LOCAL statement_timeout` per checkout** in `get_connection()` — cheap insurance against a pathological query pinning a pooled connection forever.
4. **Unify migrations** onto `db_migrations.py` as single source of truth; pre-seed `schema_migrations` on existing deploys; retire the initdb-only path (keep only `init.sql` as bootstrap).

### Pipeline shape

Refactor `handle_bot_mention` (1400 lines, two copy-pasted tool-exec blocks at `:1168-1216` and `:1264-1310`) into an ordered `Pipeline` of stages over a shared `RequestContext`:
`ParseMention → ExtractMedia → SpecialIntents → BuildContext → RunAgent → Send`.
`RunAgent` is the new `agent_runner.py` loop, collapsing both duplicated blocks into one. This is the seam that lets you insert moderation, per-guild config, or eval hooks without editing a 1400-line try-block.

### Testing / ops setup

- `pyproject.toml` with `pytest` + `pytest-asyncio`; a third CI job.
- **Tier 1 (pure logic, no I/O):** `should_search()` patterns, `_select_tools_for_message()` routing, token/truncation math, hot-takes Shannon entropy, fuzzy answer matching, ticker classification. These directly cover the logic that has silently regressed before.
- **Tier 2 (real ephemeral Postgres):** spin `pgvector/pgvector:pg15` as a CI service, run migrations, test the 5-10 hottest `Database` methods. Trivial because *all* SQL is behind one class.
- **Tier 3 (pipeline with fakes):** inject fake `LLMClient`/`Search`/`Database` and assert branch logic. DI makes this possible today.
- `/health` route (aiohttp, already transitive) returning 200 only if `bot.is_ready()` + `SELECT 1`; wire into the `bot` service `healthcheck:`; point an external dead-man's-switch at it.
- Single `config.py` Settings object loaded once at boot, fail-loud on missing required vars.

---

## 4. The capability ceiling — how to make the bot genuinely BETTER (not just cleaner)

This is the section that matters most for "better, not bug-hunt." The bot's ceiling is set by **one structural gap**: tool use is single-turn. `generate_response` (`llm.py:735-744`) returns tool calls and exits; `conversations.py` then *stringifies* the results (`tool_results.append(f"{tool_name}: {text}")`) and starts a **brand-new** LLM call in `_synthesize_tool_response` with the results paraphrased into a fresh user turn — the model never sees them in a `tool` role. There is no `role:"tool"` threading anywhere (verified). Consequences:

- **No chained tools.** "Search the top 5 F1 drivers, then chart their points" needs the chart to consume the search *result*. The synthesis pass can't call tools (`tools=None`), so the second hop never fires — even though `VISUALIZATION_TOOLS` descriptions literally say "FIRST web_search... THEN call this with 'data'." The architecture promises a workflow it cannot execute.
- **No self-correction.** A tool returning "city not found" can't be observed-and-retried.
- **Lost structure + doubled cost.** JSON → string → re-prompt discards the model's ability to reason over the real result object.

**The single highest-value move to raise the ceiling: a real agent loop** (`agent_runner.py`) wrapped around the *existing* `ToolExecutor`. When the model returns tool calls, append the assistant message + each `{"role":"tool","tool_call_id":...,"content":result}`, re-call with tools still enabled, cap at ~4 steps + a total-step budget, keep the 30s per-tool timeout. The registry and executor are untouched — you simply stop stringifying results. This unlocks ~80% of the "smarter behavior" you'd want (deep research, search→chart, book-then-remind, compare-two-searches). The current `_synthesize_tool_response` becomes unnecessary for most paths — the loop's final grounded turn *is* the synthesis.

**Second: collapse routing and lean on the model.** Search is gated *twice* — by `should_search` (~60 patterns) and by whether `web_search` is in the offered tool list (~90 keywords in `_select_tools_for_message`). These can disagree, producing "why didn't the bot search?" bugs. Pick one decision, demote the keyword walls from *gates* to *hints*, and trust the tool-calling model. De-risk with the eval harness below.

**Third, enabling everything: a tiny eval harness (50-100 golden cases).** message → expected routing (search? which tools? grounded?). Run in CI. This converts vibes-tuning of the 0.55 RAG threshold, 0.5 compression rate, and two keyword lists into engineering, and is what lets you ship the agent loop and routing collapse *safely*. **Build this first, in parallel.**

**Fourth: per-guild config.** Today the only per-guild knob reaching the pipeline is `personality` (one of four prompt files). A `GuildConfig` (enabled tools, model, search policy, temperature, response length), Redis-cached like personality already is, cleanly enables "this finance server always has stock tools" / "this server wants the cheap model" — threaded via the `RequestContext` from the pipeline refactor, not by expanding `generate_response`'s 14-arg signature.

**Performance wins (real, not cosmetic):** the executor/pool fix (§3) is a *capability* fix under load, not just cleanup — it's the line between "degrades gracefully" and "loses data." Offloading PIL/Plotly card rendering (`iracing_viz.py`, `*_card.py`, Kaleido export) to `to_thread` keeps the event loop responsive during chart generation. Streaming the final assistant turn (defer until the agent loop lands and responses get longer) is a genuine UX upgrade once multi-step reasoning makes responses worth streaming.

---

## 5. Prioritized roadmap

Every step ships value independently and keeps the bot live. Sequenced by leverage ÷ risk.

| # | Move | Effort | Payoff |
|---|---|---|---|
| **0** | **Fix executor/pool mismatch** — cap executor or add global DB semaphore; make `get_connection()` wait, not raise `PoolError`; add `SET LOCAL statement_timeout` | **15 min – ½ day** | Stops silent data loss under load. The single highest-leverage change in the codebase. Do it today. |
| **1** | **Bot healthcheck + external uptime ping** — `/health` aiohttp route (`is_ready()` + `SELECT 1`), wire into compose `healthcheck:`, external dead-man's-switch | ½ day | Alarms the moment Docker-Desktop-on-sleep (or a wedged loop) bites — the #1 operational pain today. |
| **2** | **Eval harness (50-100 golden cases)** for routing/grounding, run in CI | ½–1 day | Prerequisite that makes every pipeline change below *safe*; ends vibes-tuning. Build in parallel. |
| **3** | **First ~25 tests** (Tier 1 pure logic → Tier 2 ephemeral Postgres) + `pytest` CI job | 1–2 days | Regression net for the "5-broken-commands" bug class that CI (ruff-only) can't catch. |
| **4** | **Move ~45 loop-blocking DB calls into `to_thread`** (hot paths first) + CI grep guard | 1–2 days, mechanical | Removes serialization stalls that undercut the parallel-context work. |
| **5** | **`config.py` Settings object** — all env vars, defaults + validation in one place, fail-loud at boot | ½ day | Kills `DB_POOL_MIN` 2/5/25 drift; makes config injectable in tests. |
| **6** | **Agent loop** (`agent_runner.py`) around existing `ToolExecutor`; append `role:"tool"` results, re-call, cap steps | Medium (2–4 days) | **Raises the capability ceiling** — chained tools, self-correction, deep research. The biggest *better* win. |
| **7** | **Cogs migration, one feature at a time** (start with a leaf: trivia/polls) | Incremental, per-weekend | Dissolves the 28-kwarg `register_*` fan-out and empties `slash_commands.py`; unblocks command-level tests. |
| **8** | **Pipeline stages + `RequestContext`**; collapse the two duplicated tool-exec blocks | Medium | Seam for moderation, per-guild config, eval hooks; kills copy-paste drift. |
| **9** | **Collapse dual search routing**; demote keyword walls to hints | Low–medium (needs #2) | Ends "why didn't it search?" inconsistency. |
| **10** | **Split `database.py` into repos behind a facade** (delegation preserves call sites) | Incremental | Fixes the one real coupling violation (universal `db` blob). |
| **11** | **Per-guild `GuildConfig`** (tools/model/search/temp), Redis-cached, via `RequestContext` | Low–medium (after #8) | Real multi-guild product capability. |
| **12** | **Offload PIL/Plotly rendering to `to_thread`**; **streaming final turn** (after #6) | Low each | Loop stays responsive during charts; better UX for long agentic replies. |
| **13** | **Finish `print()`→logger** (22 files) + ruff `T201`; audit ~37 silent `except: pass` (log-and-continue) + ruff `BLE001` | 2–4 hrs | Makes the *documented* observability state true; ends "logs you can't trust." |

**Fold in the still-pending review items:** remaining SSRF surface (audit any URL-fetching paths not yet covered by `media_processor.py`'s DNS validation), the error-helper (a single sanitized user-facing error formatter so no site leaks `str(e)`), render off-loading (#12), and the test gap (#3) — all already placed above.

**Deploy substrate (parallel track, warranted because no app change fixes a sleeping hypervisor):** move off Docker Desktop — WSL2 + native `dockerd` under systemd on the same box, or a $5-10/mo always-on Linux VPS. The stack is already portable (5 compose services, only the credential volumes are host-specific).

---

## 6. What NOT to do

- **Do NOT rewrite.** The destination (Cogs, async-aware data layer, tests) is 100% reachable incrementally; a rewrite deletes 28 working features and years of hardening to get there, with zero user benefit until parity. For a solo maintainer this ends in two half-maintained bots.
- **Do NOT migrate to asyncpg / add an ORM.** At this QPS the win is negligible and it colors all ~30 SQL files. Fix the *config mismatch* and finish `to_thread` instead.
- **Do NOT touch the `features/` star topology.** Low cross-coupling is the reason 28 features didn't collapse into mud. The problem was never the features — it's the wiring *above* them (`register_*` closures) and the persistence *below* them (`Database` blob).
- **Do NOT force services or the tool registry into Cogs.** Cogs are for discord-facing units (commands, listeners). Keep constructor-injected service classes and the `tool_executor.py` dict-registry as-is — Cog-ifying them is cargo-culting.
- **Do NOT big-bang `database.py`.** Split behind a facade with delegation so existing call sites keep working; migrate feature-by-feature.
- **Do NOT ship pipeline/routing changes (Moves 6, 9) before the eval harness (Move 2).** You cannot safely raise the ceiling while quality is tuned by vibes.
- **Do NOT rip out the synthesis path before the agent loop replaces it.** It becomes redundant *because* the loop's final turn is grounded synthesis — remove it as a consequence, not a prerequisite.
- **Do NOT trust the changelog's "done" claims without a lint guard.** The `print()`→logger migration was documented complete yet 22 files still `print()`. Add `T201`/`BLE001` so "done" stays done.
