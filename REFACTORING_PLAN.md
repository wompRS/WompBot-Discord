# Main.py Refactoring Plan

**Current State:** 6,135 lines in single file
**Target:** Modular structure with ~200 line entry point

---

## 📊 File Breakdown Analysis

```
Lines   | Component                    | Target Module
--------|------------------------------|----------------------------------
1-114   | Imports & initialization     | main.py (stay)
115-735 | Background tasks (8 tasks)   | tasks/background_jobs.py
814-1283| Event handlers (7 handlers)  | handlers/events.py
1283-1675| Helper functions            | handlers/conversations.py
1676-1915| Prefix commands (7 cmds)    | commands/prefix_commands.py
1916-6135| Slash commands (~40 cmds)   | commands/slash_commands.py
```

**Total to refactor:** ~6,000 lines → 5 modules

---

## 🏗️ Architecture Pattern

### Registration Function Approach

Each module will export a `register()` function that takes dependencies:

```python
# tasks/background_jobs.py
from discord.ext import tasks

def register_tasks(bot, db, iracing, rag, chat_stats, etc.):
    """Register all background tasks with the bot"""

    @tasks.loop(hours=1)
    async def precompute_stats():
        # ... task logic

    @precompute_stats.before_loop
    async def before_precompute_stats():
        await bot.wait_until_ready()

    # Register all tasks
    precompute_stats.start()
    check_reminders.start()
    # ... more tasks

    return {
        'precompute_stats': precompute_stats,
        'check_reminders': check_reminders,
        # ... task references
    }
```

### Main.py becomes:

```python
# main.py (~200 lines)
import discord
from discord.ext import commands

# Import registration functions
from tasks.background_jobs import register_tasks
from handlers.events import register_events
from handlers.conversations import register_conversation_handler
from commands.prefix_commands import register_prefix_commands
from commands.slash_commands import register_slash_commands

# Initialize bot and dependencies
bot = commands.Bot(...)
db = Database()
llm = LLMClient()
# ... other init

# Register all modules
tasks_dict = register_tasks(bot, db, iracing, rag, chat_stats, ...)
register_events(bot, db, llm, claims, fact_checker, ...)
register_conversation_handler(bot, db, llm, rag, ...)
register_prefix_commands(bot, db, llm, ...)
register_slash_commands(bot, db, iracing, stats_viz, ...)

# Start bot
bot.run(os.getenv('DISCORD_TOKEN'))
```

---

## 📦 Module Structure

### tasks/background_jobs.py (~620 lines)
```
- _job_guard() helper
- update_iracing_popularity()
- snapshot_participation_data()
- compute_series_popularity()
- precompute_stats()
- check_reminders()
- check_event_reminders()
- gdpr_cleanup()
- analyze_user_behavior()
- process_embeddings()
- All @before_loop decorators
```

### handlers/events.py (~470 lines)
```
- on_ready()
- on_message()
- on_member_join()
- on_message_edit()
- on_message_delete()
- on_reaction_add()
- on_reaction_remove()
```

### handlers/conversations.py (~400 lines)
```
- clean_discord_mentions()
- handle_bot_mention()
- generate_leaderboard_response()
```

### commands/prefix_commands.py (~240 lines)
```
- refreshstats
- analyze
- stats
- search
- ping
- help
- wompbot group
```

### commands/slash_commands.py (~4,000 lines)
**This is the bulk!** ~40 commands:
```
User & Profile:
- receipts, quotes, verify_claim, whoami, personality

Help & Stats:
- help, stats_server, stats_topics, stats_primetime, stats_engagement

Hot Takes:
- hottakes, mystats_hottakes, vindicate

Reminders & Events:
- remind, reminders, cancel_reminder
- schedule_event, events, cancel_event

Features:
- wrapped, qotd, debate_start, debate_end, debate_stats, debate_leaderboard, debate_review

iRacing (~15 commands):
- iracing_link, iracing_profile, iracing_compare_drivers
- iracing_history, iracing_server_leaderboard, iracing_meta
- iracing_schedule, iracing_series_popularity, iracing_timeslots
- iracing_season_schedule, iracing_results, iracing_win_rate
- + team management commands (10 more)

Privacy:
- wompbot_optout, download_my_data, delete_my_data, etc.
```

---

## ⚡ Execution Plan

### Phase 1: Create Module Skeletons (15 min)
- Create all module files with registration function stubs
- Set up imports in main.py
- Verify bot still starts

### Phase 2: Extract Background Tasks (30 min)
- Move all @tasks.loop decorators
- Move helper functions (_job_guard, compute_series_popularity)
- Test background jobs still run

### Phase 3: Extract Event Handlers (30 min)
- Move all @bot.event decorators
- Test message handling, reactions

### Phase 4: Extract Conversation Handler (20 min)
- Move handle_bot_mention and helpers
- Test bot conversations

### Phase 5: Extract Prefix Commands (20 min)
- Move all @bot.command decorators
- Test prefix commands (!stats, !ping, etc.)

### Phase 6: Extract Slash Commands (90 min)
- Move all @bot.tree.command decorators
- Move autocomplete functions
- Test all slash commands

### Phase 7: Clean up main.py (15 min)
- Remove extracted code
- Keep only initialization and registration
- Add comments

### Phase 8: Testing (30 min)
- Full bot startup test
- Test sample commands from each category
- Monitor logs for errors

**Total Estimated Time: 4 hours**

---

## 🎯 Benefits After Refactor

1. **Maintainability**: Each module is 200-600 lines (manageable)
2. **Testability**: Can test modules independently
3. **Clarity**: Clear separation of concerns
4. **Onboarding**: New developers can navigate easily
5. **Git**: Smaller, focused file diffs

---

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| **Imports break** | Test after each phase |
| **Circular imports** | Use registration functions, not direct imports |
| **Global state issues** | Pass dependencies explicitly |
| **Commands don't register** | Verify `bot.tree.sync()` still works |
| **Background tasks fail** | Test each task decorator migration |

---

## 🚦 Recommendation

**Option A:** Execute full refactor now (4 hours, all phases)
**Option B:** Do Phase 1-2 now (background tasks only, 45 min), test, then continue
**Option C:** Review this plan, approve approach, then execute

**My Recommendation:** Option B - Start with background tasks as proof-of-concept, verify it works, then continue systematically.

---

## ✅ Success Criteria

- [ ] Bot starts without errors
- [ ] All commands register and respond
- [ ] Background tasks run on schedule
- [ ] Event handlers trigger correctly
- [ ] No functionality lost
- [ ] main.py under 300 lines
- [ ] Each module under 700 lines

**Ready to proceed?** Choose an option or modify the plan.
