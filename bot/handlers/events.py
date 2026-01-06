"""
Event handlers for WompBot Discord bot.

This module contains all Discord event handlers (@bot.event decorators).
"""

import os
import asyncio
import discord
from datetime import timedelta
from cost_tracker import CostTracker


def register_events(bot, db, privacy_manager, claims_tracker, debate_scorekeeper,
                    llm, cost_tracker, iracing, iracing_team_manager, rag,
                    hot_takes_tracker, fact_checker, wompie_user_id, wompie_username,
                    tasks_dict, search, self_knowledge, wolfram=None, weather=None, series_cache=None):
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
        print(f'✅ WompBot logged in as {bot.user}')
        print(f'📊 Connected to {len(bot.guilds)} servers')

        # Set Wompie user ID for claims tracker and personality command
        if wompie_user_id[0]:
            # Already set from environment variable
            claims_tracker.wompie_user_id = wompie_user_id[0]
            print(f'👑 Wompie ID from environment: {wompie_user_id[0]}')
        else:
            # Fall back to searching by username
            for guild in bot.guilds:
                member = discord.utils.get(guild.members, name=wompie_username)
                if member:
                    claims_tracker.wompie_user_id = member.id
                    wompie_user_id[0] = member.id
                    print(f'👑 Wompie identified by username: {member.id}')
                    break

        # Initialize cost tracker with bot instance
        cost_tracker_instance = CostTracker(db, bot)
        llm.cost_tracker = cost_tracker_instance
        print("💸 Cost tracking enabled - alerts every $1")

        # Setup GDPR privacy commands BEFORE syncing
        from privacy_commands import setup_privacy_commands
        setup_privacy_commands(bot, db, privacy_manager)
        print("🔒 GDPR privacy commands registered")

        # Setup iRacing team commands BEFORE syncing
        from iracing_team_commands import setup_iracing_team_commands
        from iracing_event_commands import setup_iracing_event_commands
        setup_iracing_team_commands(bot, iracing_team_manager)
        if iracing:  # Event commands need iRacing API client
            setup_iracing_event_commands(bot, iracing_team_manager, iracing.client)
        else:
            # Set up event commands without API features
            setup_iracing_event_commands(bot, iracing_team_manager, None)
        print("🏁 iRacing team & event commands registered")

        # Sync slash commands with Discord (guild-specific for instant updates)
        try:
            # Guild-specific sync for instant command updates
            guild = discord.Object(id=YOUR_GUILD_ID)  # Your server ID
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"✅ Synced {len(synced)} slash commands to guild (instant)")

            # Also sync globally for other servers (takes up to 1 hour)
            await bot.tree.sync()
            print(f"✅ Global sync initiated")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")

        # Start background tasks (from tasks_dict)
        if tasks_dict:
            if 'precompute_stats' in tasks_dict and not tasks_dict['precompute_stats'].is_running():
                tasks_dict['precompute_stats'].start()
                print("🔄 Background stats pre-computation enabled (runs every hour)")

            if 'check_reminders' in tasks_dict and not tasks_dict['check_reminders'].is_running():
                tasks_dict['check_reminders'].start()
                print("⏰ Reminder checking enabled (runs every minute)")

            if 'gdpr_cleanup' in tasks_dict and not tasks_dict['gdpr_cleanup'].is_running():
                tasks_dict['gdpr_cleanup'].start()
                print("🧹 GDPR data cleanup enabled (runs daily)")

            if 'analyze_user_behavior' in tasks_dict and not tasks_dict['analyze_user_behavior'].is_running():
                tasks_dict['analyze_user_behavior'].start()
                print("🧠 Automatic user behavior analysis enabled (runs hourly)")

            if rag.enabled and 'process_embeddings' in tasks_dict and not tasks_dict['process_embeddings'].is_running():
                tasks_dict['process_embeddings'].start()
                print("🧠 RAG embedding processing enabled (runs every 5 minutes)")

            if iracing and 'update_iracing_popularity' in tasks_dict and not tasks_dict['update_iracing_popularity'].is_running():
                tasks_dict['update_iracing_popularity'].start()
                print("📊 iRacing popularity updates enabled (runs weekly)")

            if iracing and db and 'snapshot_participation_data' in tasks_dict and not tasks_dict['snapshot_participation_data'].is_running():
                tasks_dict['snapshot_participation_data'].start()
                print("📸 iRacing participation snapshots enabled (runs daily)")

            if 'check_event_reminders' in tasks_dict and not tasks_dict['check_event_reminders'].is_running():
                tasks_dict['check_event_reminders'].start()
                print("📅 Event reminder checking enabled (runs every 5 minutes)")

        # Authenticate with iRacing on startup
        if iracing:
            async def authenticate_iracing():
                try:
                    print("🔐 Authenticating with iRacing...")
                    client = await iracing._get_client()
                    if client and client.authenticated:
                        print("✅ iRacing authentication successful")
                    else:
                        print("⚠️ iRacing authentication may have failed")
                except Exception as e:
                    print(f"❌ iRacing authentication error: {e}")

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
                            print("⏭️ Skipping series cache warm-up; ran recently.")
                            return

                    print("🏎️ Pre-warming iRacing series cache...")
                    import time
                    series = await iracing.get_current_series()
                    if series:
                        # Update series cache (passed as mutable dict reference)
                        if series_cache is not None:
                            series_cache['data'] = series
                            series_cache['time'] = time.time()
                        print(f"✅ Series cache ready ({len(series)} series loaded)")
                        if db:
                            db.update_job_last_run("warm_series_cache")
                    else:
                        print("⚠️ Failed to pre-warm series cache")
                except Exception as e:
                    print(f"⚠️ Error pre-warming series cache: {e}")

            # Run in background so it doesn't block bot startup
            bot.loop.create_task(warm_series_cache())

    @bot.event
    async def on_message(message):
        # DEBUG: Log every on_message call
        import random
        call_id = random.randint(1000, 9999)
        print(f"🔍 [{call_id}] on_message called for: {message.author} | {message.content[:50]}")

        # Check GDPR opt-out status (users are opted-in by default - legitimate interest basis)
        # Bot's own messages are always stored for conversation context
        if message.author == bot.user:
            db.store_message(message, opted_out=False)
            print(f"🔍 [{call_id}] Skipping - message from bot itself")
            return  # Don't respond to own messages (prevent infinite loops)

        consent_status = privacy_manager.get_consent_status(message.author.id)
        opted_out = consent_status.get('consent_withdrawn', False) if consent_status else False

        # Store user messages
        db.store_message(message, opted_out=opted_out)
        print(f"🔍 [{call_id}] Message stored, opted_out={opted_out}")

        # Track messages for active debates
        if debate_scorekeeper.is_debate_active(message.channel.id):
            debate_scorekeeper.add_debate_message(
                message.channel.id,
                message.author.id,
                str(message.author),
                message.content,
                message.id
            )

        # Check if bot should respond first
        should_respond = False
        is_addressing_bot = False

        # 1. Direct @mention
        if bot.user.mentioned_in(message):
            should_respond = True
            is_addressing_bot = True

        # 2. "wompbot" or "womp bot" mentioned in message (case insensitive)
        message_lower = message.content.lower()
        if 'wompbot' in message_lower or 'womp bot' in message_lower:
            should_respond = True
            is_addressing_bot = True

        # 3. Message starts with "!wb" shorthand (case insensitive)
        if message_lower.startswith('!wb'):
            should_respond = True
            is_addressing_bot = True

        # Analyze for trackable claims ONLY if not directly addressing bot
        # (Skip claim analysis for direct conversations with bot)
        if not opted_out and len(message.content) > 20 and not is_addressing_bot:
            claim_data = await claims_tracker.analyze_message_for_claim(message)
            if claim_data:
                claim_id = await claims_tracker.store_claim(message, claim_data)

                # Check for contradictions
                if claim_id:
                    contradiction = await claims_tracker.check_contradiction(claim_data, message.author.id)
                    if contradiction:
                        # Only Wompie can see contradictions
                        if str(message.author) == wompie_username:
                            embed = discord.Embed(
                                title="🚨 Contradiction Detected",
                                color=discord.Color.red()
                            )
                            embed.add_field(
                                name="New Claim",
                                value=claim_data['claim_text'],
                                inline=False
                            )
                            embed.add_field(
                                name="Contradicts Previous Claim",
                                value=contradiction['contradicted_claim']['claim_text'],
                                inline=False
                            )
                            embed.add_field(
                                name="Explanation",
                                value=contradiction['explanation'],
                                inline=False
                            )
                            await message.channel.send(embed=embed)

                    # Check if claim is a hot take (controversial)
                    controversy_data = hot_takes_tracker.detect_controversy_patterns(message.content)
                    if controversy_data['is_controversial']:
                        hot_take_id = await hot_takes_tracker.create_hot_take(claim_id, message, controversy_data)
                        if hot_take_id:
                            print(f"🔥 Hot take detected! ID: {hot_take_id}, Confidence: {controversy_data['confidence']:.2f}")

        print(f"🔍 [{call_id}] should_respond={should_respond}, is_addressing_bot={is_addressing_bot}")

        if should_respond:
            # Import here to avoid circular dependency
            from handlers.conversations import handle_bot_mention
            print(f"🔍 [{call_id}] Calling handle_bot_mention")
            await handle_bot_mention(message, opted_out, bot, db, llm, cost_tracker,
                                    search=search, self_knowledge=self_knowledge, rag=rag,
                                    wolfram=wolfram, weather=weather)
            print(f"🔍 [{call_id}] handle_bot_mention completed")
            # Don't process as command if we already handled it as bot mention
            print(f"🔍 [{call_id}] on_message handler complete (skipped command processing)")
            return

        # Process commands only if we didn't handle as bot mention
        print(f"🔍 [{call_id}] Calling bot.process_commands")
        await bot.process_commands(message)
        print(f"🔍 [{call_id}] on_message handler complete")

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
                    "• Use `/privacy_policy` or `/privacy_settings` for details.\n\n"
                    "You can change your mind anytime, and there are commands to export or delete your data."
                ),
                color=discord.Color.blue(),
            )
            embed.set_footer(text="Thank you for helping us keep your data safe.")
            await member.send(embed=embed)
        except discord.Forbidden:
            # Member has DMs closed; nothing to do.
            pass
        except Exception as exc:
            print(f"⚠️ Failed to send privacy DM to {member}: {exc}")

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
                print(f"❌ Missing permissions to send fact-check in channel {reaction.message.channel.id}")
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
                            print(f"❌ Missing permissions to send fact-check results in channel {reaction.message.channel.id}")
                else:
                    try:
                        await reaction.message.channel.send(
                            f"❌ Fact-check failed: {result.get('error', 'Unknown error')}"
                        )
                    except discord.Forbidden:
                        print(f"❌ Missing permissions to send error message in channel {reaction.message.channel.id}")

            except Exception as e:
                try:
                    await reaction.message.channel.send(f"❌ Error during fact-check: {str(e)}")
                except discord.Forbidden:
                    pass
                print(f"❌ Fact-check error: {e}")
                import traceback
                traceback.print_exc()
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
                    print(f"🔥 Hot take manually created from fire emoji: ID {hot_take_id}")
            except Exception as e:
                print(f"❌ Error creating hot take from fire emoji: {e}")

        # Track reactions for hot takes (update community engagement)
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Check if this message has a hot take
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

                        # Check if now meets threshold for LLM scoring
                        await hot_takes_tracker.check_and_score_high_engagement(hot_take_id, reaction.message)
        except Exception as e:
            print(f"❌ Error tracking hot take reaction: {e}")

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
            print(f"❌ Error updating hot take reaction removal: {e}")

    print("✅ Event handlers registered")
