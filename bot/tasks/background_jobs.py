"""
Background tasks for the Discord bot.
All scheduled tasks that run periodically for data updates, cleanup, and maintenance.
"""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from discord.ext import tasks
import discord


def register_tasks(bot, db, llm, rag, chat_stats, iracing, iracing_popularity_cache,
                   reminder_system, event_system, privacy_manager, iracing_team_manager=None,
                   poll_system=None, devils_advocate=None, jeopardy=None):
    """
    Register all background tasks with the bot.

    Args:
        bot: Discord bot instance
        db: Database instance
        llm: LLM client instance
        rag: RAG system instance
        chat_stats: Chat statistics instance
        iracing: iRacing integration instance
        iracing_popularity_cache: Cache dict for iRacing popularity data
        reminder_system: Reminder system instance
        event_system: Event system instance
        privacy_manager: Privacy manager instance

    Returns:
        Dict of task names to task references
    """

    async def _job_guard(job_name: str, interval: timedelta, jitter_seconds: int = 0) -> bool:
        """
        Determine if a background job should run based on persisted run history.
        Returns True when the job should execute.
        """
        if jitter_seconds:
            delay = random.uniform(0, jitter_seconds)
            if delay > 0:
                await asyncio.sleep(delay)

        if not db:
            return True

        try:
            should_run, last_run = db.should_run_job(job_name, interval)
        except Exception as exc:
            print(f"⚠️ Job guard fallback for {job_name}: {exc}")
            return True

        if should_run:
            return True

        if last_run:
            next_run = last_run + interval
            remaining = next_run - datetime.now(timezone.utc)
            remaining_minutes = max(int(remaining.total_seconds() // 60), 0)
            print(f"⏭️ Skipping {job_name}; ran recently. Next run in ~{remaining_minutes} minutes.")
        else:
            print(f"⏭️ Skipping {job_name}; run history unavailable.")

        return False

    async def compute_series_popularity(time_range: str, limit: int = 10) -> List[Tuple[str, int]]:
        """
        Compute series popularity by participant count.
        First checks database for historical data, falls back to live API if insufficient data.

        Args:
            time_range: 'season', 'weekly', 'yearly', or 'all_time'
            limit: Number of top series to return

        Returns:
            List of (series_name, participant_count) tuples sorted by popularity
        """
        if not iracing:
            return []

        # Get current time info
        now = datetime.now(timezone.utc)
        current_year = now.year
        current_quarter = (now.month - 1) // 3 + 1  # 1-4

        # Try database first (for historical tracking)
        if db:
            try:
                historical_data = db.get_participation_data(time_range, current_year, current_quarter, limit)
                if historical_data:
                    print(f"📊 Using historical data from database for {time_range}")
                    return historical_data
            except Exception as e:
                print(f"⚠️ Error fetching historical data, falling back to live API: {e}")

        # Fall back to live API (ONLY works for currently active series)
        # Note: iRacing API doesn't provide historical standings data
        print(f"📡 Fetching live participation data from iRacing API")
        client = await iracing._get_client()
        all_seasons = await client.get_series_seasons()

        if not all_seasons:
            return []

        # Get only currently ACTIVE series (all ~147 series running right now)
        active_seasons = [s for s in all_seasons if s.get('active', False)]
        print(f"  Found {len(active_seasons)} currently active series")

        # Count participants per series
        series_participation = {}

        # Limit to avoid rate limiting (process top 100)
        seasons_to_check = active_seasons[:100]

        for season in seasons_to_check:
            series_id = season.get('series_id')
            season_id = season.get('season_id')
            car_class_ids = season.get('car_class_ids', [])

            if not car_class_ids:
                continue

            car_class_id = car_class_ids[0]

            try:
                standings = await client.get_series_stats(season_id, car_class_id)

                if standings and isinstance(standings, dict):
                    series_name = standings.get('series_name', f'Series {series_id}')
                    participant_count = 0

                    if 'chunk_info' in standings:
                        chunk_info = standings['chunk_info']
                        if isinstance(chunk_info, dict) and 'rows' in chunk_info:
                            participant_count = chunk_info['rows']

                    if participant_count > 0:
                        if series_name not in series_participation:
                            series_participation[series_name] = 0
                        series_participation[series_name] += participant_count

            except Exception:
                continue

        # Sort and return top N
        sorted_series = sorted(series_participation.items(), key=lambda x: x[1], reverse=True)[:limit]
        return sorted_series

    # Background task for updating iRacing series popularity weekly
    @tasks.loop(hours=168)  # Run every week (7 days * 24 hours)
    async def update_iracing_popularity():
        """Background task to update iRacing series popularity data"""
        if not iracing:
            return

        if not await _job_guard("update_iracing_popularity", timedelta(days=7), jitter_seconds=120):
            return

        try:
            print("📊 Starting weekly iRacing series popularity update...")

            # Update all time ranges
            time_ranges = ['season', 'yearly', 'all_time']

            for time_range in time_ranges:
                try:
                    popularity_data = await compute_series_popularity(time_range)
                    if popularity_data:
                        iracing_popularity_cache[time_range] = {
                            'data': popularity_data,
                            'timestamp': datetime.now()
                        }
                        print(f"  ✅ Cached {time_range} popularity data ({len(popularity_data)} series)")
                except Exception as e:
                    print(f"  ❌ Error computing {time_range} popularity: {e}")

            print("✅ iRacing popularity cache updated successfully")
            if db:
                db.update_job_last_run("update_iracing_popularity")

        except Exception as e:
            print(f"❌ Error updating iRacing popularity cache: {e}")
            import traceback
            traceback.print_exc()

    # Background task for daily participation snapshot
    @tasks.loop(hours=24)  # Run every 24 hours
    async def snapshot_participation_data():
        """Daily task to snapshot current participation data for historical tracking"""
        if not iracing or not db:
            return

        if not await _job_guard("snapshot_participation_data", timedelta(days=1), jitter_seconds=90):
            return

        try:
            print("📸 Starting daily iRacing participation snapshot...")

            client = await iracing._get_client()
            all_seasons = await client.get_series_seasons()

            if not all_seasons:
                print("  ❌ No seasons data available")
                return

            now = datetime.now(timezone.utc)
            current_year = now.year
            current_quarter = (now.month - 1) // 3 + 1

            snapshot_count = 0
            error_count = 0

            # Snapshot only CURRENTLY ACTIVE series (all ~147 series running right now)
            active_seasons = [s for s in all_seasons if s.get('active', False)]

            print(f"  Found {len(active_seasons)} active series to snapshot")

            for season in active_seasons[:100]:  # Limit to 100 to avoid rate limit
                series_id = season.get('series_id')
                season_id = season.get('season_id')
                season_year = season.get('season_year', current_year)
                season_quarter = season.get('season_quarter', current_quarter)
                car_class_ids = season.get('car_class_ids', [])

                if not car_class_ids:
                    continue

                car_class_id = car_class_ids[0]

                try:
                    # Get current standings
                    standings = await client.get_series_stats(season_id, car_class_id)

                    if standings and isinstance(standings, dict):
                        series_name = standings.get('series_name', f'Series {series_id}')
                        participant_count = 0

                        if 'chunk_info' in standings:
                            chunk_info = standings['chunk_info']
                            if isinstance(chunk_info, dict) and 'rows' in chunk_info:
                                participant_count = chunk_info['rows']

                        if participant_count > 0:
                            # Store in database
                            success = db.store_participation_snapshot(
                                series_name=series_name,
                                series_id=series_id,
                                season_id=season_id,
                                season_year=season_year,
                                season_quarter=season_quarter,
                                participant_count=participant_count
                            )

                            if success:
                                snapshot_count += 1
                            else:
                                error_count += 1

                except Exception as e:
                    error_count += 1
                    continue

            print(f"✅ Participation snapshot complete: {snapshot_count} series recorded, {error_count} errors")
            db.update_job_last_run("snapshot_participation_data")

        except Exception as e:
            print(f"❌ Error in participation snapshot: {e}")
            import traceback
            traceback.print_exc()

    # Background task for pre-computing statistics
    @tasks.loop(hours=1)  # Run every hour (can adjust to minutes=30 for 30-min intervals)
    async def precompute_stats():
        """Background task to pre-compute common statistics"""
        if not await _job_guard("precompute_stats", timedelta(hours=1), jitter_seconds=45):
            return

        try:
            print("🔄 Starting background stats computation...")

            for guild in bot.guilds:
                guild_id = guild.id

                # Common time ranges to pre-compute
                time_ranges = [7, 30]  # 7 days, 30 days

                for days in time_ranges:
                    start_date = datetime.now() - timedelta(days=days)
                    end_date = datetime.now()

                    # Get messages once for this time range
                    messages = chat_stats.get_messages_for_analysis(None, start_date, end_date, exclude_opted_out=True)

                    if not messages:
                        continue

                    print(f"📊 Computing stats for guild {guild_id}, last {days} days ({len(messages)} messages)...")

                    # 1. Network stats
                    try:
                        scope = f"server:{guild_id}"
                        network = chat_stats.build_network_graph(messages)
                        chat_stats.cache_stats('network', scope, start_date, end_date, network, cache_hours=2)
                        print(f"  ✅ Network stats cached (last {days} days)")
                    except Exception as e:
                        print(f"  ❌ Network stats failed: {e}")

                    # 2. Topic trends
                    try:
                        scope = f"server:{guild_id}"
                        topics = chat_stats.extract_topics_tfidf(messages, top_n=15)
                        if topics:
                            chat_stats.cache_stats('topics', scope, start_date, end_date, topics, cache_hours=2)
                            print(f"  ✅ Topic trends cached (last {days} days)")
                    except Exception as e:
                        print(f"  ❌ Topic trends failed: {e}")

                    # 3. Primetime (server-wide)
                    try:
                        scope = f"server:{guild_id}"
                        primetime = chat_stats.calculate_primetime(messages)
                        chat_stats.cache_stats('primetime', scope, start_date, end_date, primetime, cache_hours=2)
                        print(f"  ✅ Primetime stats cached (last {days} days)")
                    except Exception as e:
                        print(f"  ❌ Primetime stats failed: {e}")

                    # 4. Engagement (server-wide)
                    try:
                        scope = f"server_engagement:{guild_id}"
                        engagement = chat_stats.calculate_engagement(messages)
                        chat_stats.cache_stats('engagement', scope, start_date, end_date, engagement, cache_hours=2)
                        print(f"  ✅ Engagement stats cached (last {days} days)")
                    except Exception as e:
                        print(f"  ❌ Engagement stats failed: {e}")

                    # 5. User topic expertise (only for 30-day range to avoid redundant work)
                    if days == 30:
                        try:
                            expertise_entries = chat_stats.compute_user_topic_expertise(
                                messages, guild_id, min_messages=5, top_n=10
                            )
                            if expertise_entries:
                                db.batch_upsert_topic_expertise(expertise_entries)
                                user_count = len(set(e[0] for e in expertise_entries))
                                print(f"  ✅ Topic expertise updated ({user_count} users, {len(expertise_entries)} entries)")
                        except Exception as e:
                            print(f"  ❌ Topic expertise failed: {e}")

            print("✅ Background stats computation complete!")
            if db:
                db.update_job_last_run("precompute_stats")

        except Exception as e:
            print(f"❌ Background stats computation error: {e}")
            import traceback
            traceback.print_exc()

    @precompute_stats.before_loop
    async def before_precompute_stats():
        """Wait for bot to be ready before starting background task"""
        await bot.wait_until_ready()
        print("🚀 Background stats computation task started")

    # Background task for checking reminders
    @tasks.loop(minutes=1)  # Check every minute
    async def check_reminders():
        """Check for due reminders and send notifications"""
        try:
            due_reminders = await reminder_system.get_due_reminders()

            for reminder in due_reminders:
                try:
                    # Get user and channel
                    user = await bot.fetch_user(reminder['user_id'])
                    channel = bot.get_channel(reminder['channel_id'])

                    if not user:
                        print(f"⚠️ User {reminder['user_id']} not found for reminder #{reminder['id']}")
                        await reminder_system.mark_completed(reminder['id'])
                        continue

                    # Build reminder message
                    embed = discord.Embed(
                        title="⏰ Reminder",
                        description=reminder['reminder_text'],
                        color=discord.Color.blue(),
                        timestamp=reminder['remind_at']
                    )

                    embed.add_field(
                        name="Set",
                        value=f"<t:{int(reminder['remind_at'].timestamp())}:R>",
                        inline=True
                    )

                    # Add context link if available
                    if reminder['message_id'] and channel:
                        try:
                            message_url = f"https://discord.com/channels/{channel.guild.id}/{channel.id}/{reminder['message_id']}"
                            embed.add_field(
                                name="Context",
                                value=f"[Jump to message]({message_url})",
                                inline=True
                            )
                        except (AttributeError, KeyError):
                            pass  # Channel has no guild or missing required attributes

                    embed.set_footer(text=f"Reminder ID: {reminder['id']}")

                    # Send reminder (try DM first, then mention in channel)
                    try:
                        await user.send(embed=embed)
                        print(f"✅ Sent reminder #{reminder['id']} to {reminder['username']} via DM")
                    except discord.Forbidden:
                        # Can't DM user, mention in channel instead
                        if channel:
                            await channel.send(f"{user.mention}", embed=embed)
                            print(f"✅ Sent reminder #{reminder['id']} to {reminder['username']} in channel")
                        else:
                            print(f"⚠️ Could not send reminder #{reminder['id']} - no DM or channel access")

                    # Mark as completed
                    await reminder_system.mark_completed(reminder['id'])

                    # Reschedule if recurring
                    if reminder['recurring']:
                        await reminder_system.reschedule_recurring(reminder)

                except Exception as e:
                    print(f"❌ Error processing reminder #{reminder['id']}: {e}")
                    # Mark as completed to avoid getting stuck
                    await reminder_system.mark_completed(reminder['id'])

        except Exception as e:
            print(f"❌ Error checking reminders: {e}")
            import traceback
            traceback.print_exc()

    @check_reminders.before_loop
    async def before_check_reminders():
        """Wait for bot to be ready before starting reminder checker"""
        await bot.wait_until_ready()
        print("⏰ Reminder checker task started")

    # Background task for checking event reminders
    @tasks.loop(minutes=5)  # Check every 5 minutes
    async def check_event_reminders():
        """Check for events that need reminders sent"""
        try:
            events_needing_reminders = await event_system.get_events_needing_reminders()

            for event in events_needing_reminders:
                try:
                    # Get channel
                    channel = bot.get_channel(event['channel_id'])

                    if not channel:
                        print(f"⚠️ Channel {event['channel_id']} not found for event #{event['id']}")
                        continue

                    # Format time until event
                    time_until = event_system.format_time_until(event['event_date'])
                    timestamp = int(event['event_date'].timestamp())

                    # Build event reminder embed
                    embed = discord.Embed(
                        title="📅 Event Reminder",
                        description=f"**{event['event_name']}**",
                        color=discord.Color.blue()
                    )

                    embed.add_field(
                        name="When",
                        value=f"<t:{timestamp}:F>\n<t:{timestamp}:R>",
                        inline=False
                    )

                    if event.get('description'):
                        embed.add_field(
                            name="Details",
                            value=event['description'][:500],
                            inline=False
                        )

                    embed.add_field(
                        name="Time Remaining",
                        value=time_until,
                        inline=True
                    )

                    embed.set_footer(text=f"Event ID: {event['id']}")

                    # Send reminder to channel
                    message_content = None
                    if event.get('notify_role_id'):
                        # Ping the role if specified
                        message_content = f"<@&{event['notify_role_id']}>"

                    if message_content:
                        await channel.send(content=message_content, embed=embed)
                    else:
                        await channel.send(embed=embed)

                    print(f"📅 Sent '{event['reminder_interval']}' reminder for event '{event['event_name']}' (ID: {event['id']})")

                    # Mark this reminder as sent
                    await event_system.mark_reminder_sent(event['id'], event['reminder_interval'])

                except Exception as e:
                    print(f"❌ Error processing event reminder #{event['id']}: {e}")
                    import traceback
                    traceback.print_exc()

        except Exception as e:
            print(f"❌ Error checking event reminders: {e}")
            import traceback
            traceback.print_exc()

    @check_event_reminders.before_loop
    async def before_check_event_reminders():
        """Wait for bot to be ready before starting event reminder checker"""
        await bot.wait_until_ready()
        print("📅 Event reminder checker task started")

    # GDPR Compliance: Background task for data retention and cleanup
    @tasks.loop(hours=24)  # Run once daily
    async def gdpr_cleanup():
        """Process GDPR-related tasks: scheduled deletions, data retention cleanup"""
        if not await _job_guard("gdpr_cleanup", timedelta(days=1), jitter_seconds=120):
            return

        try:
            print("🧹 Starting GDPR compliance cleanup...")

            # Process scheduled deletions
            deletions_processed = privacy_manager.process_scheduled_deletions()
            if deletions_processed > 0:
                print(f"   🗑️ Processed {deletions_processed} scheduled user deletions")

            # Clean up old data based on retention policies
            cleanup_counts = privacy_manager.cleanup_old_data()
            if cleanup_counts:
                print(f"   📊 Data cleanup results:")
                for data_type, count in cleanup_counts.items():
                    if count > 0:
                        print(f"      • {data_type}: {count:,} records deleted")

            if db:
                removed_meta = db.cleanup_expired_meta_cache()
                if removed_meta:
                    print(f"   🧹 Removed {removed_meta} expired iRacing meta cache entries")

                removed_history = db.cleanup_expired_history_cache()
                if removed_history:
                    print(f"   🧹 Removed {removed_history} expired iRacing history cache entries")

            print("✅ GDPR compliance cleanup complete")
            if db:
                db.update_job_last_run("gdpr_cleanup")

        except Exception as e:
            print(f"❌ Error during GDPR cleanup: {e}")
            import traceback
            traceback.print_exc()

    @gdpr_cleanup.before_loop
    async def before_gdpr_cleanup():
        """Wait for bot to be ready before starting GDPR cleanup"""
        await bot.wait_until_ready()
        print("🔒 GDPR cleanup task started (runs daily)")

    # Background task for automatic user behavior analysis
    @tasks.loop(hours=6)  # Run every 6 hours (behavior doesn't change fast, saves ~$80/mo in LLM costs)
    async def analyze_user_behavior():
        """Automatically analyze user behavior patterns for users with sufficient activity"""
        if not await _job_guard("analyze_user_behavior", timedelta(hours=6), jitter_seconds=120):
            return

        try:
            # Get active users from last 30 days
            active_users = db.get_all_active_users(days=30)

            if not active_users:
                return

            period_start = datetime.now() - timedelta(days=30)
            period_end = datetime.now()

            analyzed_count = 0

            for user in active_users:
                # Check if user already has recent analysis (within last 24 hours)
                user_context = db.get_user_context(user['user_id'])
                behavior = user_context.get('behavior')

                if behavior:
                    analyzed_at = behavior.get('analyzed_at')
                    if analyzed_at and (datetime.now() - analyzed_at).total_seconds() < 86400:  # 24 hours
                        continue  # Skip, already analyzed recently

                # Get messages for analysis
                messages = db.get_user_messages_for_analysis(user['user_id'], days=30)

                if len(messages) < 5:  # Skip users with too few messages
                    continue

                # Perform analysis
                analysis = await asyncio.to_thread(llm.analyze_user_behavior, messages)

                if analysis:
                    db.store_behavior_analysis(
                        user['user_id'],
                        user['username'],
                        analysis,
                        period_start,
                        period_end
                    )
                    analyzed_count += 1

                    # Rate limit to avoid overwhelming the API
                    if analyzed_count >= 10:
                        break

            if analyzed_count > 0:
                print(f"✅ Behavior analysis complete: {analyzed_count} users analyzed")

            if db:
                db.update_job_last_run("analyze_user_behavior")

        except Exception as e:
            print(f"❌ Error in automatic behavior analysis: {e}")
            import traceback
            traceback.print_exc()

    @analyze_user_behavior.before_loop
    async def before_analyze_user_behavior():
        """Wait for bot to be ready before starting behavior analysis"""
        await bot.wait_until_ready()
        print("🧠 User behavior analysis task started (runs every 6 hours)")

    @tasks.loop(minutes=5)  # Process embeddings every 5 minutes
    async def process_embeddings():
        """Background task to generate embeddings for new messages"""
        if not rag.enabled:
            return  # Skip if RAG is disabled

        if not await _job_guard("process_embeddings", timedelta(minutes=5), jitter_seconds=30):
            return

        try:
            # Process up to 100 messages per run
            count = await rag.process_embedding_queue(limit=100)

            if count > 0:
                print(f"🧠 Processed {count} message embeddings")

            if db:
                db.update_job_last_run("process_embeddings")

        except Exception as e:
            print(f"❌ Error processing embeddings: {e}")

    @process_embeddings.before_loop
    async def before_process_embeddings():
        """Wait for bot to be ready before starting embedding processing"""
        await bot.wait_until_ready()
        if rag.enabled:
            print("🧠 Message embedding task started (runs every 5 min)")

    # Background task for team event reminders
    @tasks.loop(minutes=15)
    async def check_team_event_reminders():
        """Check for team events that need reminder notifications"""
        if not iracing_team_manager:
            return

        try:
            events = iracing_team_manager.get_events_needing_reminders()

            for event in events:
                try:
                    # Get team members
                    members = iracing_team_manager.get_team_members(event['team_id'])

                    # Get guild for context
                    guild = bot.get_guild(event['guild_id'])
                    guild_name = guild.name if guild else "Unknown Server"

                    timestamp = int(event['event_start'].timestamp())
                    reminder_type = event['reminder_type']

                    # Determine reminder message
                    if reminder_type == '24h':
                        title = "Event Tomorrow!"
                        time_text = "starting in approximately 24 hours"
                    else:  # 1h
                        title = "Event Starting Soon!"
                        time_text = "starting in approximately 1 hour"

                    tag_display = f" [{event['team_tag']}]" if event.get('team_tag') else ""

                    for member_data in members:
                        try:
                            user = bot.get_user(member_data['discord_user_id'])
                            if not user:
                                user = await bot.fetch_user(member_data['discord_user_id'])

                            if user:
                                embed = discord.Embed(
                                    title=f"Reminder: {title}",
                                    description=f"**{event['event_name']}** is {time_text}!",
                                    color=discord.Color.orange()
                                )
                                embed.add_field(
                                    name="Team",
                                    value=f"{event['team_name']}{tag_display}",
                                    inline=True
                                )
                                embed.add_field(
                                    name="Type",
                                    value=event['event_type'].replace('_', ' ').title(),
                                    inline=True
                                )
                                embed.add_field(
                                    name="When",
                                    value=f"<t:{timestamp}:F>\n<t:{timestamp}:R>",
                                    inline=False
                                )

                                if event.get('series_name'):
                                    embed.add_field(name="Series", value=event['series_name'], inline=True)
                                if event.get('track_name'):
                                    embed.add_field(name="Track", value=event['track_name'], inline=True)

                                embed.set_footer(text=f"Server: {guild_name}")

                                # Include availability buttons for 24h reminder
                                if reminder_type == '24h':
                                    from features.team_menu import EventResponseDMView
                                    view = EventResponseDMView(
                                        team_manager=iracing_team_manager,
                                        event_id=event['id'],
                                        event_name=event['event_name'],
                                        team_name=f"{event['team_name']}{tag_display}",
                                        guild_id=event['guild_id'],
                                        guild_name=guild_name
                                    )
                                    await user.send(embed=embed, view=view)
                                else:
                                    await user.send(embed=embed)

                        except discord.Forbidden:
                            pass  # User has DMs disabled
                        except Exception as e:
                            print(f"❌ Error sending team event reminder to user: {e}")

                    # Mark reminder as sent
                    iracing_team_manager.mark_event_reminder_sent(event['id'], reminder_type)
                    print(f"📅 Sent {reminder_type} reminder for team event '{event['event_name']}'")

                except Exception as e:
                    print(f"❌ Error processing team event reminder: {e}")
                    import traceback
                    traceback.print_exc()

        except Exception as e:
            print(f"❌ Error in team event reminder task: {e}")
            import traceback
            traceback.print_exc()

    @check_team_event_reminders.before_loop
    async def before_check_team_event_reminders():
        """Wait for bot to be ready before starting team event reminder checker"""
        await bot.wait_until_ready()
        if iracing_team_manager:
            print("📅 Team event reminder task started (runs every 15 min)")

    # ── Poll deadline checker ──
    @tasks.loop(minutes=1)
    async def check_poll_deadlines():
        """Auto-close polls that have reached their deadline"""
        if not poll_system:
            return

        try:
            due_polls = await poll_system.get_due_polls()
            for poll in due_polls:
                try:
                    results = await poll_system.close_poll(poll['id'])
                    if results.get('error'):
                        continue

                    # Try to post results in the original channel
                    channel = bot.get_channel(poll['channel_id'])
                    if channel:
                        from poll_card import create_poll_results_card
                        import discord
                        image_buffer = create_poll_results_card(results)
                        file = discord.File(fp=image_buffer, filename="poll_results.png")
                        winner = results.get('winner', {})
                        embed = discord.Embed(
                            title=f"📊 Poll #{poll['id']} — Time's Up!",
                            description=f"🏆 Winner: **{winner.get('option', 'N/A')}** ({winner.get('percentage', 0)}%)",
                            color=discord.Color.green()
                        )
                        embed.set_image(url="attachment://poll_results.png")
                        embed.set_footer(text=f"{results['total_voters']} total voters")
                        await channel.send(file=file, embed=embed)

                except Exception as e:
                    print(f"  ❌ Error closing poll {poll['id']}: {e}")

        except Exception as e:
            print(f"❌ Poll deadline check error: {e}")

    @check_poll_deadlines.before_loop
    async def before_check_poll_deadlines():
        await bot.wait_until_ready()
        if poll_system:
            print("📊 Poll deadline checker started (runs every 1 min)")

    # ── Devil's Advocate timeout checker ──
    @tasks.loop(minutes=5)
    async def check_devils_advocate_timeouts():
        """End devil's advocate sessions inactive for 30+ minutes"""
        if not devils_advocate:
            return

        try:
            timed_out = await devils_advocate.check_timeouts()
            for channel_id in timed_out:
                try:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send("😈 Devil's advocate session ended due to inactivity (30 minutes).")
                except Exception as e:
                    print(f"  ❌ Error notifying DA timeout for channel {channel_id}: {e}")

        except Exception as e:
            print(f"❌ Devil's advocate timeout check error: {e}")

    @check_devils_advocate_timeouts.before_loop
    async def before_check_devils_advocate_timeouts():
        await bot.wait_until_ready()
        if devils_advocate:
            print("😈 Devil's Advocate timeout checker started (runs every 5 min)")

    # ── Jeopardy timeout checker ──
    @tasks.loop(minutes=5)
    async def check_jeopardy_timeouts():
        """End Jeopardy games inactive for 15+ minutes"""
        if not jeopardy:
            return

        try:
            timed_out = await jeopardy.check_timeouts()
            for channel_id in timed_out:
                try:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send("🎯 Jeopardy game ended due to inactivity (15 minutes).")
                except Exception as e:
                    print(f"  ❌ Error notifying Jeopardy timeout for channel {channel_id}: {e}")

        except Exception as e:
            print(f"❌ Jeopardy timeout check error: {e}")

    @check_jeopardy_timeouts.before_loop
    async def before_check_jeopardy_timeouts():
        await bot.wait_until_ready()
        if jeopardy:
            print("🎯 Jeopardy timeout checker started (runs every 5 min)")

    print("✅ Background tasks registered (will start in on_ready)")

    # Return task references - they will be started in on_ready event handler
    tasks_dict = {
        'update_iracing_popularity': update_iracing_popularity,
        'snapshot_participation_data': snapshot_participation_data,
        'precompute_stats': precompute_stats,
        'check_reminders': check_reminders,
        'check_event_reminders': check_event_reminders,
        'check_team_event_reminders': check_team_event_reminders,
        'gdpr_cleanup': gdpr_cleanup,
        'analyze_user_behavior': analyze_user_behavior,
        'process_embeddings': process_embeddings
    }

    if poll_system:
        tasks_dict['check_poll_deadlines'] = check_poll_deadlines

    if devils_advocate:
        tasks_dict['check_devils_advocate_timeouts'] = check_devils_advocate_timeouts

    if jeopardy:
        tasks_dict['check_jeopardy_timeouts'] = check_jeopardy_timeouts

    return tasks_dict
