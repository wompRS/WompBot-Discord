"""
Event handlers for WompBot Discord bot.

This module contains all Discord event handlers (@bot.event decorators).
"""

import asyncio
import logging
import os
import re

import discord
from datetime import timedelta
from cost_tracker import CostTracker
from features.team_menu import show_team_menu

logger = logging.getLogger(__name__)


def register_events(bot, db, privacy_manager, claims_tracker, debate_scorekeeper,
                    llm, cost_tracker, iracing, iracing_team_manager, rag,
                    hot_takes_tracker, fact_checker, wompie_user_id, wompie_username,
                    tasks_dict, search, self_knowledge, wolfram=None, weather=None,
                    series_cache=None, trivia=None, reminder_system=None,
                    who_said_it=None, devils_advocate=None, jeopardy=None):
    """
    Register all Discord event handlers with the bot.

    Args:
        bot: Discord bot instance
        db: Database instance
        privacy_manager: Privacy/GDPR manager
        claims_tracker: Claims tracking system
        debate_scorekeeper: Debate tracking system
        llm: LLM client instance
        cost_tracker: API cost tracking
        iracing: iRacing API wrapper
        iracing_team_manager: iRacing team management
        rag: RAG system for embeddings
        hot_takes_tracker: Hot takes detection system
        fact_checker: Fact checking system
        wompie_user_id: Wompie's Discord user ID (mutable ref)
        wompie_username: Wompie's Discord username
        tasks_dict: Dictionary of background task references from register_tasks()
        search: Web search engine for fact-checking
        self_knowledge: Bot documentation system
        series_cache: Dict for iRacing series autocomplete cache (mutable ref)
    """

    # Import handle_bot_mention from conversations module
    # We'll set this up when that module is created
    handle_bot_mention_func = None

    @bot.event
    async def on_ready():
        logger.info("WompBot logged in as %s", bot.user)
        logger.info("Connected to %d servers", len(bot.guilds))

        # Set bot user ID for stats ranking exclusion (tracks bot messages separately)
        db.set_bot_user_id(bot.user.id)

        # Set Wompie user ID for claims tracker and personality command
        if wompie_user_id[0]:
            # Already set from environment variable
            claims_tracker.wompie_user_id = wompie_user_id[0]
            logger.info("Wompie ID from environment: %s", wompie_user_id[0])
        else:
            # Fall back to searching by username
            for guild in bot.guilds:
                member = discord.utils.get(guild.members, name=wompie_username)
                if member:
                    claims_tracker.wompie_user_id = member.id
                    wompie_user_id[0] = member.id
                    logger.info("Wompie identified by username: %s", member.id)
                    break

        # Initialize cost tracker with bot instance
        cost_tracker_instance = CostTracker(db, bot)
        llm.cost_tracker = cost_tracker_instance
        logger.info("Cost tracking enabled - alerts every $1")

        # Setup GDPR privacy commands BEFORE syncing
        from privacy_commands import setup_privacy_commands
        setup_privacy_commands(bot, db, privacy_manager)
        logger.info("GDPR privacy commands registered")

        # Setup iRacing team commands BEFORE syncing
        from iracing_team_commands import setup_iracing_team_commands
        from iracing_event_commands import setup_iracing_event_commands
        setup_iracing_team_commands(bot, iracing_team_manager)
        if iracing:  # Event commands need iRacing API client
            setup_iracing_event_commands(bot, iracing_team_manager, iracing.client)
        else:
            # Set up event commands without API features
            setup_iracing_event_commands(bot, iracing_team_manager, None)
        logger.info("iRacing team & event commands registered")

        # Sync slash commands with Discord (guild-specific for instant updates)
        try:
            # Check for primary guild ID in environment (for instant sync)
            primary_guild_id = os.getenv('PRIMARY_GUILD_ID')
            if primary_guild_id and primary_guild_id.strip().isdigit():
                # Guild-specific sync for instant command updates
                guild = discord.Object(id=int(primary_guild_id))
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                logger.info("Synced %d slash commands to guild (instant)", len(synced))

            # Also sync globally for other servers (takes up to 1 hour)
            await bot.tree.sync()
            logger.info("Global sync initiated")
        except Exception as e:
            logger.error("Failed to sync commands: %s", e)

        # Start background tasks (from tasks_dict)
        if tasks_dict:
            if 'precompute_stats' in tasks_dict and not tasks_dict['precompute_stats'].is_running():
                tasks_dict['precompute_stats'].start()
                logger.info("Background stats pre-computation enabled (runs every hour)")

            if 'check_reminders' in tasks_dict and not tasks_dict['check_reminders'].is_running():
                tasks_dict['check_reminders'].start()
                logger.info("Reminder checking enabled (runs every minute)")

            if 'gdpr_cleanup' in tasks_dict and not tasks_dict['gdpr_cleanup'].is_running():
                tasks_dict['gdpr_cleanup'].start()
                logger.info("GDPR data cleanup enabled (runs daily)")

            if 'analyze_user_behavior' in tasks_dict and not tasks_dict['analyze_user_behavior'].is_running():
                tasks_dict['analyze_user_behavior'].start()
                logger.info("Automatic user behavior analysis enabled (runs hourly)")

            if rag.enabled and 'process_embeddings' in tasks_dict and not tasks_dict['process_embeddings'].is_running():
                tasks_dict['process_embeddings'].start()
                logger.info("RAG embedding processing enabled (runs every 5 minutes)")

            if iracing and 'update_iracing_popularity' in tasks_dict and not tasks_dict['update_iracing_popularity'].is_running():
                tasks_dict['update_iracing_popularity'].start()
                logger.info("iRacing popularity updates enabled (runs weekly)")

            if iracing and db and 'snapshot_participation_data' in tasks_dict and not tasks_dict['snapshot_participation_data'].is_running():
                tasks_dict['snapshot_participation_data'].start()
                logger.info("iRacing participation snapshots enabled (runs daily)")

            if 'check_event_reminders' in tasks_dict and not tasks_dict['check_event_reminders'].is_running():
                tasks_dict['check_event_reminders'].start()
                logger.info("Event reminder checking enabled (runs every 5 minutes)")

            if iracing_team_manager and 'check_team_event_reminders' in tasks_dict and not tasks_dict['check_team_event_reminders'].is_running():
                tasks_dict['check_team_event_reminders'].start()
                logger.info("Team event reminder checking enabled (runs every 15 minutes)")

        # Authenticate with iRacing on startup
        if iracing:
            async def authenticate_iracing():
                try:
                    logger.info("Authenticating with iRacing...")
                    client = await iracing._get_client()
                    if client and client.authenticated:
                        logger.info("iRacing authentication successful")
                    else:
                        logger.warning("iRacing authentication may have failed")
                except Exception as e:
                    logger.error("iRacing authentication error: %s", e)

            # Run authentication in background
            asyncio.create_task(authenticate_iracing())

        # Pre-warm series autocomplete cache (runs in background)
        if iracing:
            async def warm_series_cache():
                # Import cache globals - will need to be handled properly
                # For now, we'll let this work with the globals in main.py
                try:
                    if db:
                        should_run, last_run = db.should_run_job("warm_series_cache", timedelta(hours=1))
                        if not should_run:
                            logger.info("Skipping series cache warm-up; ran recently.")
                            return

                    logger.info("Pre-warming iRacing series cache...")
                    import time
                    series = await iracing.get_current_series()
                    if series:
                        # Update series cache (passed as mutable dict reference)
                        if series_cache is not None:
                            series_cache['data'] = series
                            series_cache['time'] = time.time()
                        logger.info("Series cache ready (%d series loaded)", len(series))
                        if db:
                            db.update_job_last_run("warm_series_cache")
                    else:
                        logger.warning("Failed to pre-warm series cache")
                except Exception as e:
                    logger.warning("Error pre-warming series cache: %s", e)

            # Run in background so it doesn't block bot startup
            bot.loop.create_task(warm_series_cache())

    async def _background_claim_analysis(message, claims_tracker, hot_takes_tracker, wompie_username):
        """Run claim analysis + hot take detection in background (fire-and-forget).
        This avoids blocking the message pipeline with LLM calls for every message."""
        try:
            claim_data = await claims_tracker.analyze_message_for_claim(message)
            if claim_data:
                claim_id = await claims_tracker.store_claim(message, claim_data)

                if claim_id:
                    # Check for contradictions
                    contradiction = await claims_tracker.check_contradiction(claim_data, message.author.id)
                    if contradiction and str(message.author) == wompie_username:
                        embed = discord.Embed(
                            title="🚨 Contradiction Detected",
                            color=discord.Color.red()
                        )
                        embed.add_field(name="New Claim", value=claim_data['claim_text'], inline=False)
                        embed.add_field(name="Contradicts Previous Claim",
                                        value=contradiction['contradicted_claim']['claim_text'], inline=False)
                        embed.add_field(name="Explanation", value=contradiction['explanation'], inline=False)
                        await message.channel.send(embed=embed)

                    # Check if claim is a hot take (controversial)
                    controversy_data = hot_takes_tracker.detect_controversy_patterns(message.content)
                    if controversy_data['is_controversial']:
                        hot_take_id = await hot_takes_tracker.create_hot_take(claim_id, message, controversy_data)
                        if hot_take_id:
                            logger.info("Hot take detected! ID: %s, Confidence: %.2f",
                                        hot_take_id, controversy_data['confidence'])
        except Exception as e:
            logger.warning("Background claim analysis failed: %s", e)

    @bot.event
    async def on_message(message):
        # Check GDPR opt-out status (users are opted-in by default - legitimate interest basis)
        # Bot's own messages are always stored for conversation context
        if message.author == bot.user:
            asyncio.create_task(asyncio.to_thread(db.store_message, message, False))
            return  # Don't respond to own messages (prevent infinite loops)

        consent_status = await asyncio.to_thread(privacy_manager.get_consent_status, message.author.id)
        opted_out = consent_status.get('consent_withdrawn', False) if consent_status else False

        # Store user messages (fire-and-forget to not block message processing)
        asyncio.create_task(asyncio.to_thread(db.store_message, message, opted_out))

        # Track messages for active debates
        if debate_scorekeeper.is_debate_active(message.channel.id):
            debate_scorekeeper.add_debate_message(
                message.channel.id,
                message.author.id,
                str(message.author),
                message.content,
                message.id
            )

        # Check for trivia answer submission
        if trivia and trivia.is_session_active(message.channel.id):
            session = trivia.get_active_session(message.channel.id)

            # Only process if session is active (waiting for answers)
            if session and session['status'] == 'active':
                result = await trivia.submit_answer(
                    message.channel.id,
                    message.author.id,
                    str(message.author),
                    message.content
                )

                if result and not result.get('error'):
                    # Send feedback
                    if result['is_correct']:
                        feedback = f"✅ **{message.author.display_name}** got it! **+{result['points']} points** ({result['time_taken']:.1f}s)"
                        if result['streak'] >= 3:
                            feedback += f" 🔥 Streak: {result['streak']}"
                        await message.channel.send(feedback)

                        # Move to next question after short delay
                        await asyncio.sleep(2)
                        session = trivia.get_active_session(message.channel.id)
                        if session:
                            session['current_question_num'] += 1

                            result = await trivia.ask_next_question(
                                message.channel.id,
                                lambda: trivia.handle_timeout(message.channel)
                            )

                            if result:
                                # Check if this is a session end result (has 'leaderboard' key)
                                if 'leaderboard' in result:
                                    # Display session end results
                                    embed = discord.Embed(
                                        title="🏁 Trivia Complete!",
                                        description=f"**{result['topic'].title()}** - {result['difficulty'].title()} - {result['question_count']} questions",
                                        color=discord.Color.gold()
                                    )

                                    if result['leaderboard']:
                                        # Winner announcement with overall stats
                                        winner_id, winner_data = result['leaderboard'][0]
                                        winner_stats = result.get('winner_overall_stats')

                                        if winner_stats:
                                            accuracy = (winner_stats['total_correct'] / winner_stats['total_questions_answered'] * 100) if winner_stats['total_questions_answered'] > 0 else 0

                                            winner_text = (
                                                f"🏆 **{winner_data['username']}** wins with **{winner_data['score']} points** this session!\n\n"
                                                f"**Overall Stats:**\n"
                                                f"• Total Points: **{winner_stats['total_points']:,}** across all sessions\n"
                                                f"• Total Wins: **{winner_stats['wins']}** 🏆\n"
                                                f"• Accuracy: **{accuracy:.1f}%** ({winner_stats['total_correct']}/{winner_stats['total_questions_answered']} correct)\n"
                                                f"• Best Streak: **{winner_stats['best_streak']}** 🔥"
                                            )
                                            embed.add_field(name="👑 Champion", value=winner_text, inline=False)
                                        else:
                                            embed.add_field(
                                                name="👑 Champion",
                                                value=f"🏆 **{winner_data['username']}** wins with **{winner_data['score']} points**!",
                                                inline=False
                                            )

                                        # Session leaderboard
                                        leaderboard_text = ""
                                        for i, (user_id, data) in enumerate(result['leaderboard'][:10]):
                                            rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
                                            leaderboard_text += f"{rank_emoji} **{data['username']}** - {data['score']} points\n"

                                        embed.add_field(name="Session Leaderboard", value=leaderboard_text, inline=False)

                                    await message.channel.send(embed=embed)
                                else:
                                    # It's a question - display it
                                    q_num = session['current_question_num'] + 1
                                    total = session['question_count']
                                    embed = discord.Embed(
                                        title=f"Question {q_num}/{total}",
                                        description=result['question'],
                                        color=discord.Color.green()
                                    )
                                    embed.set_footer(text=f"You have {session['time_per_question']} seconds to answer")
                                    await message.channel.send(embed=embed)
                    else:
                        # Wrong answer - just react
                        await message.add_reaction("❌")

                # Don't process command or bot mention if this was a trivia answer
                return

        # Check for Who Said It? guess submission
        if who_said_it and who_said_it.is_session_active(message.channel.id):
            session = who_said_it.get_active_session(message.channel.id)
            if session and session['status'] == 'active':
                result = await who_said_it.submit_guess(
                    message.channel.id,
                    message.author.id,
                    message.author.display_name,
                    message.content
                )

                if result:
                    if result['is_correct']:
                        feedback = f"✅ **{result['guesser']}** got it! It was **{result['correct_answer']}**"
                        await message.channel.send(feedback)

                        if result.get('game_over'):
                            # Show final scores
                            embed = discord.Embed(
                                title="🏁 Who Said It? — Game Over!",
                                color=discord.Color.gold()
                            )
                            scores = result.get('final_scores', [])
                            if scores:
                                board = "\n".join(
                                    f"{'🥇🥈🥉'[i] if i < 3 else f'{i+1}.'} **{s['username']}** — {s['correct']}/{result['total_rounds']} correct"
                                    for i, s in enumerate(scores)
                                )
                                embed.description = board
                            await message.channel.send(embed=embed)
                        elif result.get('next_quote'):
                            # Show next question
                            await asyncio.sleep(2)
                            embed = discord.Embed(
                                title=f"❓ Round {result['next_round']}/{result['total_rounds']}",
                                description=f">>> {result['next_quote']}",
                                color=discord.Color.blue()
                            )
                            embed.set_footer(text="Who said this? Type your guess!")
                            await message.channel.send(embed=embed)
                    else:
                        await message.add_reaction("❌")

                    return

        # Check for Devil's Advocate response
        if devils_advocate and devils_advocate.is_session_active(message.channel.id):
            session = devils_advocate.get_active_session(message.channel.id)
            if session and session['status'] == 'active' and session['started_by'] == message.author.id:
                async with message.channel.typing():
                    result = await devils_advocate.respond(
                        message.channel.id,
                        message.content
                    )

                if result and not result.get('error'):
                    response = result['response']
                    # Truncate if too long for Discord
                    if len(response) > 2000:
                        response = response[:1997] + "..."
                    await message.channel.send(f"😈 {response}")
                elif result and result.get('error'):
                    await message.channel.send(f"❌ Error: {result['error']}")
                return

        # Check for Jeopardy answer
        if jeopardy and jeopardy.is_session_active(message.channel.id):
            session = jeopardy.get_active_session(message.channel.id)
            if session and session['status'] == 'answering' and session.get('current_clue'):
                result = await jeopardy.submit_answer(
                    message.channel.id,
                    message.author.id,
                    message.author.display_name,
                    message.content
                )

                if result:
                    if result.get('is_correct'):
                        await message.add_reaction("✅")
                        feedback = (
                            f"🎯 **Correct!** {result['guesser']} earns **${result['value']}**! "
                            f"(Score: ${result['new_score']})\n"
                            f"Answer: {result['correct_answer']}"
                        )
                        if result.get('game_over'):
                            feedback += "\n\n🏁 **GAME OVER!**"
                            scores = result.get('final_scores', [])
                            if scores:
                                board = "\n".join(
                                    f"{'🥇🥈🥉'[i] if i < 3 else f'{i+1}.'} **{s['username']}** — ${s['score']}"
                                    for i, s in enumerate(scores)
                                )
                                feedback += f"\n\n**Final Scores:**\n{board}"
                        else:
                            feedback += f"\n📋 {result['clues_remaining']} clues remaining. Use `!jpick` to select another!"
                        await message.channel.send(feedback)
                    else:
                        await message.add_reaction("❌")
                        await message.channel.send(
                            f"❌ Wrong answer, {result['guesser']}! **-${result['deducted']}** "
                            f"(Score: ${result['new_score']}). Others can still answer!"
                        )
                    return

        # Handle DM commands for team management
        if isinstance(message.channel, discord.DMChannel):
            dm_content_lower = message.content.lower().strip()
            if dm_content_lower == '!team' or dm_content_lower.startswith('!team '):
                try:
                    await show_team_menu(message, bot, iracing_team_manager)
                except Exception as e:
                    await message.channel.send(f"❌ Error opening team menu: {str(e)}")
                    logger.error("Team menu error: %s", e, exc_info=True)
                return

        # Check if bot should respond first
        should_respond = False
        is_addressing_bot = False

        # 1. Direct @mention
        if bot.user.mentioned_in(message):
            should_respond = True
            is_addressing_bot = True

        # 2. "wompbot" or "womp bot" mentioned in message (case insensitive)
        # Use regex to match word boundaries, allowing punctuation like "wompbot," or "wompbot!"
        message_lower = message.content.lower()
        if re.search(r'\bwompbot\b|\bwomp\s+bot\b', message_lower):
            should_respond = True
            is_addressing_bot = True

        # 3. Message starts with "!wb" shorthand (case insensitive)
        if message_lower.startswith('!wb'):
            should_respond = True
            is_addressing_bot = True

        # Analyze for trackable claims ONLY if not directly addressing bot
        # (Skip claim analysis for direct conversations with bot)
        # Fire-and-forget: don't block the message pipeline for claim/hot take analysis
        if not opted_out and len(message.content) > 20 and not is_addressing_bot:
            asyncio.create_task(_background_claim_analysis(
                message, claims_tracker, hot_takes_tracker, wompie_username
            ))

        if should_respond:
            # Import here to avoid circular dependency
            from handlers.conversations import handle_bot_mention
            logger.info("Bot mention detected from %s: %s...", message.author, message.content[:50])
            await handle_bot_mention(message, opted_out, bot, db, llm, cost_tracker,
                                    search=search, self_knowledge=self_knowledge, rag=rag,
                                    wolfram=wolfram, weather=weather,
                                    iracing_manager=iracing, reminder_system=reminder_system)
            # Don't process as command if we already handled it as bot mention
            return

        # Process commands only if we didn't handle as bot mention
        await bot.process_commands(message)

    @bot.event
    async def on_member_join(member):
        """Send privacy notice to new members when they join a guild with WompBot."""
        if member.bot:
            return

        notice_setting = os.getenv("PRIVACY_DM_NEW_MEMBERS", "1").strip().lower()
        if notice_setting in {"0", "false", "no"}:
            return

        try:
            embed = discord.Embed(
                title="👋 Welcome! Let's talk privacy.",
                description=(
                    "WompBot can help with stats, reminders, iRacing analytics, and more.\n\n"
                    "**Your choices:**\n"
                    "• Run `/wompbot_consent` to enable full functionality.\n"
                    "• Run `/wompbot_noconsent` if you prefer that we collect nothing.\n"
                    "• Use `/download_my_data` to export or `/delete_my_data` to erase your data.\n\n"
                    "You can change your mind anytime."
                ),
                color=discord.Color.blue(),
            )
            embed.set_footer(text="Thank you for helping us keep your data safe.")
            await member.send(embed=embed)
        except discord.Forbidden:
            # Member has DMs closed; nothing to do.
            pass
        except Exception as exc:
            logger.warning("Failed to send privacy DM to %s: %s", member, exc)

    @bot.event
    async def on_message_edit(before, after):
        """Track edits to messages with claims"""
        if before.author == bot.user:
            return

        await claims_tracker.handle_claim_edit(before, after)

    @bot.event
    async def on_message_delete(message):
        """Track deletion of messages with claims"""
        if message.author == bot.user:
            return

        await claims_tracker.handle_claim_deletion(message)

    @bot.event
    async def on_reaction_add(reaction, user):
        """Handle emoji reactions for quotes and fact-checks"""
        # Ignore bot's own reactions
        if user == bot.user:
            return

        # Check for cloud emoji ☁️ - Save as quote
        is_cloud = (
            str(reaction.emoji) == "☁️" or
            (hasattr(reaction.emoji, 'name') and reaction.emoji.name == 'cloud') or
            str(reaction.emoji) == ":cloud:"
        )

        # Check for warning emoji ⚠️ - Trigger fact-check
        is_warning = (
            str(reaction.emoji) == "⚠️" or
            str(reaction.emoji) == "⚠" or
            (hasattr(reaction.emoji, 'name') and reaction.emoji.name == 'warning')
        )

        if is_cloud:
            # Only save once (check if already exists)
            quote_id = await claims_tracker.store_quote(reaction.message, user)
            if quote_id:
                # React with checkmark to confirm
                await reaction.message.add_reaction("✅")

        elif is_warning:
            # Check rate limits
            fact_check_cooldown = int(os.getenv('FACT_CHECK_COOLDOWN', '300'))  # 5 minutes default
            fact_check_daily_limit = int(os.getenv('FACT_CHECK_DAILY_LIMIT', '10'))  # 10 per day default

            rate_limit_check = db.check_feature_rate_limit(
                user.id,
                'fact_check',
                cooldown_seconds=fact_check_cooldown,
                daily_limit=fact_check_daily_limit
            )

            if not rate_limit_check['allowed']:
                if rate_limit_check['reason'] == 'cooldown':
                    wait_minutes = rate_limit_check['wait_seconds'] // 60
                    wait_seconds = rate_limit_check['wait_seconds'] % 60
                    await reaction.message.channel.send(
                        f"⏱️ Fact-check cooldown! Wait {wait_minutes}m {wait_seconds}s before requesting another."
                    )
                elif rate_limit_check['reason'] == 'daily_limit':
                    await reaction.message.channel.send(
                        f"📊 Daily limit reached! You've used {rate_limit_check['count']}/{rate_limit_check['limit']} fact-checks today."
                    )
                return

            # Trigger fact-check
            thinking_msg = None
            try:
                thinking_msg = await reaction.message.channel.send("🔍 Fact-checking this claim...")
            except discord.Forbidden:
                logger.error("Missing permissions to send fact-check in channel %s", reaction.message.channel.id)
                return

            try:
                result = await fact_checker.fact_check_message(reaction.message, user)

                # Record usage if successful
                if result['success']:
                    db.record_feature_usage(user.id, 'fact_check')

                if result['success']:
                    # Parse verdict emoji
                    verdict_emoji = fact_checker.parse_verdict(result['analysis'])

                    # Create embed
                    embed = discord.Embed(
                        title=f"{verdict_emoji} Fact-Check Results",
                        description=result['analysis'],
                        color=discord.Color.orange()
                    )

                    embed.add_field(
                        name="Original Claim",
                        value=f"> {reaction.message.content[:200]}",
                        inline=False
                    )

                    if result.get('sources'):
                        sources_text = "\n".join([
                            f"• [{s['title'][:60]}]({s['url']})"
                            for s in result['sources'][:3]
                        ])
                        embed.add_field(
                            name="Sources",
                            value=sources_text,
                            inline=False
                        )

                    embed.set_footer(text=f"Requested by {user.display_name}")

                    try:
                        await reaction.message.reply(embed=embed, mention_author=False)
                        # React with verdict emoji
                        await reaction.message.add_reaction(verdict_emoji)
                    except discord.Forbidden:
                        # Can't reply or react, try sending in channel instead
                        try:
                            await reaction.message.channel.send(embed=embed)
                        except discord.Forbidden:
                            logger.error("Missing permissions to send fact-check results in channel %s", reaction.message.channel.id)
                else:
                    try:
                        await reaction.message.channel.send(
                            f"❌ Fact-check failed: {result.get('error', 'Unknown error')}"
                        )
                    except discord.Forbidden:
                        logger.error("Missing permissions to send error message in channel %s", reaction.message.channel.id)

            except Exception as e:
                try:
                    await reaction.message.channel.send(f"❌ Error during fact-check: {str(e)}")
                except discord.Forbidden:
                    pass
                logger.error("Fact-check error: %s", e, exc_info=True)
            finally:
                # Always try to delete thinking message, but handle if it's already gone
                if thinking_msg:
                    try:
                        await thinking_msg.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass  # Message already deleted or no permission

        # Check for fire emoji 🔥 - Manually mark as hot take
        is_fire = (
            str(reaction.emoji) == "🔥" or
            (hasattr(reaction.emoji, 'name') and reaction.emoji.name == 'fire')
        )

        if is_fire:
            try:
                hot_take_id = await hot_takes_tracker.create_hot_take_from_message(reaction.message, user)
                if hot_take_id:
                    # React with checkmark to confirm
                    await reaction.message.add_reaction("✅")
                    logger.info("Hot take manually created from fire emoji: ID %s", hot_take_id)
            except Exception as e:
                logger.error("Error creating hot take from fire emoji: %s", e)

        # Track reactions for hot takes (update community engagement)
        try:
            def _check_hot_take_reaction():
                with db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT ht.id
                            FROM hot_takes ht
                            JOIN claims c ON c.id = ht.claim_id
                            WHERE c.message_id = %s
                        """, (reaction.message.id,))
                        result = cur.fetchone()
                        return result[0] if result else None

            hot_take_id = await asyncio.to_thread(_check_hot_take_reaction)
            if hot_take_id:
                await hot_takes_tracker.update_reaction_metrics(reaction.message, hot_take_id)
                await hot_takes_tracker.check_and_score_high_engagement(hot_take_id, reaction.message)
        except Exception as e:
            logger.error("Error tracking hot take reaction: %s", e)

    @bot.event
    async def on_reaction_remove(reaction, user):
        """Update hot takes metrics when reactions are removed"""
        if user == bot.user:
            return

        # Update hot takes reaction metrics
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT ht.id
                        FROM hot_takes ht
                        JOIN claims c ON c.id = ht.claim_id
                        WHERE c.message_id = %s
                    """, (reaction.message.id,))

                    result = cur.fetchone()
                    if result:
                        hot_take_id = result[0]
                        await hot_takes_tracker.update_reaction_metrics(reaction.message, hot_take_id)
        except Exception as e:
            logger.error("Error updating hot take reaction removal: %s", e)

    logger.info("Event handlers registered")
