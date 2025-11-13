import asyncio
import re
import random
import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional, Dict
from collections import Counter
import pytz
from database import Database
from llm import LLMClient
from local_llm import LocalLLMClient
from cost_tracker import CostTracker
from search import SearchEngine
from features.claims import ClaimsTracker
from features.fact_check import FactChecker
from features.chat_stats import ChatStatistics
from features.hot_takes import HotTakesTracker
from features.reminders import ReminderSystem
from features.events import EventSystem
from features.yearly_wrapped import YearlyWrapped
from features.quote_of_the_day import QuoteOfTheDay
from features.debate_scorekeeper import DebateScorekeeper
from features.iracing import iRacingIntegration
from features.iracing_teams import iRacingTeamManager
from credential_manager import CredentialManager
from iracing_graphics import iRacingGraphics
from self_knowledge import SelfKnowledge
from features.help_system import HelpSystem

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.message_content = True
intents.reactions = True  # Need for hot takes reaction tracking

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)  # Disable built-in help, use custom

# Initialize components
db = Database()
cost_tracker = None  # Will be initialized in on_ready when bot is available
llm = LLMClient(cost_tracker=None)  # Cost tracker will be set in on_ready
local_llm = LocalLLMClient()  # Local uncensored LLM (optional)
search = SearchEngine()

# Setup feature modules
claims_tracker = ClaimsTracker(db, llm)
fact_checker = FactChecker(db, llm, search)
chat_stats = ChatStatistics(db)
hot_takes_tracker = HotTakesTracker(db, llm)
self_knowledge = SelfKnowledge()
help_system = HelpSystem()
reminder_system = ReminderSystem(db)
event_system = EventSystem(db)
yearly_wrapped = YearlyWrapped(db)
qotd = QuoteOfTheDay(db)
debate_scorekeeper = DebateScorekeeper(db, llm)

# GDPR Privacy Compliance (mandatory per EU regulations)
from features.gdpr_privacy import GDPRPrivacyManager
privacy_manager = GDPRPrivacyManager(db)
print("✅ GDPR Privacy Manager loaded")

# iRacing integration (optional - only if encrypted credentials provided)
credential_manager = CredentialManager()
iracing = None
iracing_viz = None

try:
    from iracing_viz import iRacingVisualizer
    iracing_viz = iRacingVisualizer()
    print("✅ iRacing visualizer loaded")
except Exception as e:
    print(f"⚠️ Failed to load iRacing visualizer: {e}")

iracing_credentials = credential_manager.get_iracing_credentials()
if iracing_credentials:
    iracing_email, iracing_password = iracing_credentials
    iracing = iRacingIntegration(db, iracing_email, iracing_password)
    print("✅ iRacing integration enabled (using encrypted credentials)")
else:
    print("⚠️ iRacing integration disabled (no encrypted credentials found)")
    print("   Run 'python encrypt_credentials.py' to set up credentials")

# iRacing Team Management (always available, independent of iRacing API)
iracing_team_manager = iRacingTeamManager(db)
print("✅ iRacing Team Manager loaded")

WOMPIE_USERNAME = "Wompie__"

# iRacing series popularity cache
iracing_popularity_cache = {}  # {time_range: {'data': [(series, count), ...], 'timestamp': datetime}}
MENTION_RATE_STATE = {}  # user_id -> {'count': int, 'window_start': float}

# Concurrent request tracking per user
USER_CONCURRENT_REQUESTS = {}  # user_id -> int (active LLM request count)

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
                    except:
                        pass

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
@tasks.loop(hours=1)  # Run every 60 minutes
async def analyze_user_behavior():
    """Automatically analyze user behavior patterns for users with sufficient activity"""
    if not await _job_guard("analyze_user_behavior", timedelta(hours=1), jitter_seconds=120):
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
        traceback.print_exc()

@analyze_user_behavior.before_loop
async def before_analyze_user_behavior():
    """Wait for bot to be ready before starting behavior analysis"""
    await bot.wait_until_ready()
    print("🧠 User behavior analysis task started (runs hourly)")

async def generate_leaderboard_response(channel, stat_type, days):
    """Generate and send leaderboard embed"""
    try:
        embed = discord.Embed(
            title=f"📊 Top Users by {stat_type.title()}",
            description=f"Last {days} days",
            color=discord.Color.gold()
        )
        
        if stat_type == 'messages':
            results = db.get_message_stats(days=days, limit=10)
            
            if not results:
                await channel.send("No data available for this period.")
                return
            
            leaderboard_text = ""
            for i, user in enumerate(results, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                leaderboard_text += f"{medal} **{user['username']}**: {user['message_count']} messages "
                leaderboard_text += f"({user['active_days']} active days)\n"
            
            embed.add_field(name="Most Active Users", value=leaderboard_text, inline=False)
        
        elif stat_type == 'questions':
            # Send thinking message
            thinking_msg = await channel.send("🤔 Analyzing messages to detect questions...")
            
            # Get all messages for the period
            messages = db.get_question_stats(days=days)
            
            if not messages:
                await thinking_msg.edit(content="No messages available for this period.")
                return
            
            # Classify questions using LLM
            results = llm.classify_questions(messages)
            
            if not results:
                await thinking_msg.edit(content="Error analyzing questions.")
                return
            
            # Sort by question count
            sorted_results = sorted(results.values(), key=lambda x: x['question_count'], reverse=True)[:10]
            
            leaderboard_text = ""
            for i, user in enumerate(sorted_results, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                percentage = user['question_percentage']
                leaderboard_text += f"{medal} **{user['username']}**: {user['question_count']} questions "
                leaderboard_text += f"({percentage:.1f}% of {user['total_messages']} messages)\n"
            
            embed.add_field(name="Most Inquisitive Users", value=leaderboard_text, inline=False)
            await thinking_msg.delete()
        
        elif stat_type == 'profanity':
            results = db.get_profanity_stats(days=days, limit=10)
            
            if not results:
                await channel.send("No profanity analysis available yet. An admin needs to run `/analyze` first.")
                return
            
            leaderboard_text = ""
            for i, user in enumerate(results, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                score = user['profanity_score']
                leaderboard_text += f"{medal} **{user['username']}**: {score}/10\n"
            
            embed.add_field(name="Saltiest Users", value=leaderboard_text, inline=False)
            embed.set_footer(text="Based on most recent behavior analysis")
        
        await channel.send(embed=embed)
    
    except Exception as e:
        await channel.send(f"Error generating stats: {str(e)}")
        print(f"Leaderboard generation error: {e}")

@bot.event
async def on_ready():
    print(f'✅ WompBot logged in as {bot.user}')
    print(f'📊 Connected to {len(bot.guilds)} servers')

    # Set Wompie user ID for claims tracker
    for guild in bot.guilds:
        member = discord.utils.get(guild.members, name=WOMPIE_USERNAME)
        if member:
            claims_tracker.wompie_user_id = member.id
            print(f'👑 Wompie identified: {member.id}')
            break

    # Initialize cost tracker with bot instance
    global cost_tracker
    cost_tracker = CostTracker(db, bot)
    llm.cost_tracker = cost_tracker
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

    # Start background stats computation task
    if not precompute_stats.is_running():
        precompute_stats.start()
        print("🔄 Background stats pre-computation enabled (runs every hour)")

    # Start reminder checking task
    if not check_reminders.is_running():
        check_reminders.start()

    # Start GDPR data cleanup task
    if not gdpr_cleanup.is_running():
        gdpr_cleanup.start()
        print("🧹 GDPR data cleanup enabled (runs daily)")

    # Start automatic user behavior analysis task
    if not analyze_user_behavior.is_running():
        analyze_user_behavior.start()
        print("🧠 Automatic user behavior analysis enabled (runs hourly)")

    # Start iRacing popularity update task
    if iracing and not update_iracing_popularity.is_running():
        update_iracing_popularity.start()
        print("📊 iRacing popularity updates enabled (runs weekly)")

    # Start daily participation snapshot task
    if iracing and db and not snapshot_participation_data.is_running():
        snapshot_participation_data.start()
        print("📸 iRacing participation snapshots enabled (runs daily)")

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
            global _series_autocomplete_cache, _series_cache_time
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
                    _series_autocomplete_cache = series
                    _series_cache_time = time.time()
                    print(f"✅ Series cache ready ({len(series)} series loaded)")
                    if db:
                        db.update_job_last_run("warm_series_cache")
                else:
                    print("⚠️ Failed to pre-warm series cache")
            except Exception as e:
                print(f"⚠️ Error pre-warming series cache: {e}")

        # Run in background so it doesn't block bot startup
        bot.loop.create_task(warm_series_cache())
        print("⏰ Reminder checking enabled (runs every minute)")

    # Start event reminder checking task
    if not check_event_reminders.is_running():
        check_event_reminders.start()
        print("📅 Event reminder checking enabled (runs every 5 minutes)")

@bot.event
async def on_message(message):
    # Ignore bot's own messages
    if message.author == bot.user:
        return

    # Check GDPR opt-out status (users are opted-in by default - legitimate interest basis)
    consent_status = privacy_manager.get_consent_status(message.author.id)
    opted_out = consent_status.get('consent_withdrawn', False) if consent_status else False

    # Store consenting messages (opted-out users are tracked without content)
    db.store_message(message, opted_out=opted_out)

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
                    if str(message.author) == WOMPIE_USERNAME:
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
    
    if should_respond:
        await handle_bot_mention(message, opted_out)
    
    # Process commands
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
        with db.conn.cursor() as cur:
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
        with db.conn.cursor() as cur:
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

def clean_discord_mentions(content, message):
    """Convert Discord mentions from <@USER_ID> format to @username format"""
    import re

    # Find all user mentions in format <@USER_ID> or <@!USER_ID>
    mention_pattern = r'<@!?(\d+)>'

    def replace_mention(match):
        user_id = int(match.group(1))
        # Try to find the user in the message's guild
        if message.guild:
            member = message.guild.get_member(user_id)
            if member:
                return f"@{member.name}"
        # Fallback to just @USER_ID if we can't find the member
        return f"@user_{user_id}"

    return re.sub(mention_pattern, replace_mention, content)

async def handle_bot_mention(message, opted_out):
    """Handle when bot is mentioned/tagged"""
    try:
        # Check if this is a text mention ("wompbot") vs @mention only
        # Cost logging will only appear for text mentions to reduce log noise
        message_lower = message.content.lower()
        is_text_mention = 'wompbot' in message_lower or 'womp bot' in message_lower

        # Remove bot mention and "wompbot" from message
        content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        content = content.replace(f'<@!{bot.user.id}>', '').strip()  # Also handle nickname mentions
        content = content.replace('wompbot', '').replace('womp bot', '').strip()
        content = content.replace('WompBot', '').replace('Wompbot', '').strip()

        # Convert Discord mentions to readable usernames
        content = clean_discord_mentions(content, message)

        if not content or len(content) < 2:
            await message.channel.send("Yeah? What's up?")
            return

        # Input sanitization - enforce max length
        max_input_length = int(os.getenv('MAX_INPUT_LENGTH', '2000'))
        if len(content) > max_input_length:
            content = content[:max_input_length]
            await message.channel.send(
                f"⚠️ Message truncated to {max_input_length} characters for processing."
            )

        # Message frequency rate limiting
        message_cooldown = int(os.getenv('MESSAGE_COOLDOWN', '3'))  # 3 seconds default
        max_messages_per_minute = int(os.getenv('MAX_MESSAGES_PER_MINUTE', '10'))  # 10/min default

        freq_check = db.check_feature_rate_limit(
            message.author.id,
            'bot_message',
            cooldown_seconds=message_cooldown,
            hourly_limit=max_messages_per_minute * 6  # Convert per-minute to per-hour approximation
        )

        if not freq_check['allowed']:
            if freq_check['reason'] == 'cooldown':
                # Silent cooldown - just ignore to prevent spam
                return
            elif freq_check['reason'] == 'hourly_limit':
                await message.channel.send(
                    f"⏱️ Slow down! You're sending messages too quickly."
                )
                return

        # Record message
        db.record_feature_usage(message.author.id, 'bot_message')

        content_lower = content.lower()
        normalized_plain = re.sub(r'[^a-z0-9\s]', ' ', content_lower).strip()
        tokens = [tok for tok in normalized_plain.split() if tok]

        greeting_phrases = {
            "hi",
            "hello",
            "hey",
            "yo",
            "sup",
            "what's up",
            "whats up",
            "what is up",
            "morning",
            "good morning",
            "good evening",
            "good afternoon",
        }
        casual_starts = {"hi", "hello", "hey", "yo"}

        basic_greeting = False
        if normalized_plain in greeting_phrases:
            basic_greeting = True
        elif tokens and tokens[0] in casual_starts and len(tokens) <= 3:
            basic_greeting = True
        elif len(tokens) <= 4 and tokens[:2] in (["whats", "up"], ["what", "up"], ["what", "is"], ["how", "are"]):
            basic_greeting = True

        if basic_greeting:
            responses = [
                "Not much, just spinning up the servers. What's new with you?",
                "All systems go! Need anything?",
                "Living the bot life. How can I help?",
                "Just crunching data and sipping electrons. You?",
            ]
            await message.channel.send(random.choice(responses))
            return

        # Check for leaderboard triggers in natural language
        leaderboard_triggers = {
            'messages': ['who talks the most', 'who messages the most', 'most active', 'most messages', 'who chats the most'],
            'questions': ['who asks the most questions', 'most questions', 'most curious', 'who questions'],
            'profanity': ['who swears the most', 'who curses the most', 'most profanity', 'saltiest', 'who says fuck']
        }

        for stat_type, triggers in leaderboard_triggers.items():
            if any(trigger in content_lower for trigger in triggers):
                # Extract days if mentioned
                days = 7
                if 'month' in content_lower or '30 days' in content_lower:
                    days = 30
                elif 'week' in content_lower or '7 days' in content_lower:
                    days = 7
                elif 'year' in content_lower:
                    days = 365

                # Generate leaderboard
                await generate_leaderboard_response(message.channel, stat_type, days)
                return

        # Rate limiting (per user to avoid abuse)
        rate_window = float(os.getenv("MENTION_RATE_WINDOW_SECONDS", "6"))
        max_per_window = int(os.getenv("MENTION_RATE_MAX_CALLS", "3"))
        if rate_window > 0 and max_per_window > 0:
            now_ts = datetime.now(timezone.utc).timestamp()
            user_bucket = MENTION_RATE_STATE.get(message.author.id)
            if user_bucket and now_ts - user_bucket["window_start"] <= rate_window:
                if user_bucket["count"] >= max_per_window:
                    await message.channel.send(
                        "⏱️ Let's take a breather. Try again in a few seconds."
                    )
                    return
                user_bucket["count"] += 1
            else:
                MENTION_RATE_STATE[message.author.id] = {
                    "count": 1,
                    "window_start": now_ts,
                }

        # Token-based rate limiting check
        max_tokens_per_request = int(os.getenv('MAX_TOKENS_PER_REQUEST', '1000'))
        rate_limit_check = db.check_rate_limit(
            message.author.id,
            str(message.author),
            max_tokens_per_request
        )

        if not rate_limit_check['allowed']:
            tokens_used = rate_limit_check['tokens_used']
            limit = rate_limit_check['limit']
            reset_minutes = rate_limit_check['reset_seconds'] // 60
            reset_seconds = rate_limit_check['reset_seconds'] % 60

            await message.channel.send(
                f"⏱️ Token limit reached! You've used {tokens_used:,}/{limit:,} tokens this hour.\n"
                f"Reset in {reset_minutes}m {reset_seconds}s."
            )
            return

        # Concurrent request limiting
        max_concurrent_requests = int(os.getenv('MAX_CONCURRENT_REQUESTS', '3'))
        current_requests = USER_CONCURRENT_REQUESTS.get(message.author.id, 0)

        if current_requests >= max_concurrent_requests:
            await message.channel.send(
                f"⏱️ Too many requests at once! Please wait for your current request to finish."
            )
            return

        # Increment concurrent request counter
        USER_CONCURRENT_REQUESTS[message.author.id] = current_requests + 1

        # Start typing indicator
        async with message.channel.typing():
            # Get conversation context - only this user's messages and bot responses to them
            conversation_history = db.get_recent_messages(
                message.channel.id,
                limit=int(os.getenv('CONTEXT_WINDOW_MESSAGES', 6)),
                exclude_opted_out=True,
                exclude_bot_id=bot.user.id,
                user_id=message.author.id  # Only get this user's conversation history
            )

            # Clean Discord mentions from conversation history
            for msg in conversation_history:
                if msg.get('content'):
                    msg['content'] = clean_discord_mentions(msg['content'], message)

            # Get user context (if not opted out)
            user_context = None if opted_out else db.get_user_context(message.author.id)

            # Check if question is about WompBot itself - load documentation
            # Get full conversation history (including bot messages) for context-aware detection
            full_conversation_history = db.get_recent_messages(
                message.channel.id,
                limit=3,  # Just need last few messages
                exclude_opted_out=True,
                exclude_bot_id=None,  # Don't exclude bot messages
                user_id=message.author.id
            )
            bot_docs = self_knowledge.format_for_llm(content, full_conversation_history, bot.user.id)
            if bot_docs:
                print(f"📚 Loading WompBot documentation for self-knowledge question")

            # Check if search is needed (skip if we're using docs)
            search_results = None
            search_msg = None

            if not bot_docs and llm.should_search(content, conversation_history):
                # Check search rate limits
                search_hourly_limit = int(os.getenv('SEARCH_HOURLY_LIMIT', '5'))
                search_daily_limit = int(os.getenv('SEARCH_DAILY_LIMIT', '20'))

                search_rate_check = db.check_feature_rate_limit(
                    message.author.id,
                    'search',
                    hourly_limit=search_hourly_limit,
                    daily_limit=search_daily_limit
                )

                if not search_rate_check['allowed']:
                    if search_rate_check['reason'] == 'hourly_limit':
                        await message.channel.send(
                            f"⏱️ Search limit reached! You've used {search_rate_check['count']}/{search_rate_check['limit']} searches this hour."
                        )
                    elif search_rate_check['reason'] == 'daily_limit':
                        await message.channel.send(
                            f"📊 Daily search limit reached! You've used {search_rate_check['count']}/{search_rate_check['limit']} searches today."
                        )
                    # Skip search but continue with response
                else:
                    search_msg = await message.channel.send("🔍 Searching for current info...")

                    search_results_raw = await asyncio.to_thread(search.search, content)
                    search_results = search.format_results_for_llm(search_results_raw)

                    db.store_search_log(content, len(search_results_raw), message.author.id, message.channel.id)
                    db.record_feature_usage(message.author.id, 'search')

            # Generate response
            # Only pass user info for text mentions ("wompbot") to reduce cost logging noise
            # Use bot docs if available, otherwise use search results
            context_for_llm = bot_docs or search_results

            response = await asyncio.to_thread(
                llm.generate_response,
                content,
                conversation_history,
                user_context,
                context_for_llm,
                0,
                bot.user.id,
                message.author.id if is_text_mention else None,
                str(message.author) if is_text_mention else None,
            )

            # Check if response is empty
            if not response or len(response.strip()) == 0:
                response = "I got nothing. Try asking something else?"

            # Check if LLM says it needs more info (skip if we used bot docs)
            if not bot_docs and not search_results and llm.detect_needs_search_from_response(response):
                # Check search rate limits (second attempt)
                search_hourly_limit = int(os.getenv('SEARCH_HOURLY_LIMIT', '5'))
                search_daily_limit = int(os.getenv('SEARCH_DAILY_LIMIT', '20'))

                search_rate_check = db.check_feature_rate_limit(
                    message.author.id,
                    'search',
                    hourly_limit=search_hourly_limit,
                    daily_limit=search_daily_limit
                )

                if search_rate_check['allowed']:
                    if not search_msg:
                        search_msg = await message.channel.send("🔍 Let me search for that...")
                    else:
                        await search_msg.edit(content="🔍 Let me search for that...")

                    search_results_raw = await asyncio.to_thread(search.search, content)
                    search_results = search.format_results_for_llm(search_results_raw)

                    db.store_search_log(content, len(search_results_raw), message.author.id, message.channel.id)
                    db.record_feature_usage(message.author.id, 'search')

                # Regenerate response with search results (or without if rate limited)
                # Update context (bot docs take priority over search)
                context_for_llm = bot_docs or search_results

                response = await asyncio.to_thread(
                    llm.generate_response,
                    content,
                    conversation_history,
                    user_context,
                    context_for_llm,
                    0,
                    bot.user.id,
                    message.author.id if is_text_mention else None,
                    str(message.author) if is_text_mention else None,
                )

            # Final check for empty response
            if not response or len(response.strip()) == 0:
                response = "Error: Got an empty response. Try rephrasing?"

            # Send or edit response
            if search_msg:
                # Edit the search message with the response
                if len(response) > 2000:
                    await search_msg.edit(content=response[:2000])
                    # Send remaining chunks as new messages
                    remaining = response[2000:]
                    chunks = [remaining[i:i+2000] for i in range(0, len(remaining), 2000)]
                    for chunk in chunks:
                        if chunk.strip():
                            await message.channel.send(chunk)
                else:
                    await search_msg.edit(content=response)
            else:
                # No search, just send normally
                if len(response) > 2000:
                    chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        if chunk.strip():
                            await message.channel.send(chunk)
                else:
                    await message.channel.send(response)

            # Record token usage for rate limiting
            # Estimate: ~4 characters per token (common approximation)
            # Include both input (content) and output (response) tokens
            estimated_tokens = (len(content) + len(response)) // 4
            db.record_token_usage(message.author.id, str(message.author), estimated_tokens)

    except Exception as e:
        print(f"❌ Error handling message: {e}")
        import traceback
        traceback.print_exc()
        await message.channel.send(f"Error processing request: {str(e)}")
    finally:
        # Decrement concurrent request counter
        if message.author.id in USER_CONCURRENT_REQUESTS:
            USER_CONCURRENT_REQUESTS[message.author.id] -= 1
            if USER_CONCURRENT_REQUESTS[message.author.id] <= 0:
                del USER_CONCURRENT_REQUESTS[message.author.id]

@bot.command(name='refreshstats')
@commands.has_permissions(administrator=True)
async def refresh_stats(ctx):
    """Manually trigger background stats computation (Admin only)"""
    await ctx.send("🔄 Manually triggering stats computation...")

    try:
        # Run the precompute task manually
        await precompute_stats()
        await ctx.send("✅ Stats computation complete! Cache refreshed.")
    except Exception as e:
        await ctx.send(f"❌ Error computing stats: {str(e)}")
        print(f"❌ Manual stats refresh error: {e}")

@bot.command(name='analyze')
@commands.has_permissions(administrator=True)
async def analyze_users(ctx, days: int = 7):
    """Analyze user behavior patterns (Admin only)"""
    await ctx.send(f"🔍 Analyzing user behavior from the last {days} days...")
    
    try:
        active_users = db.get_all_active_users(days=days)
        
        if not active_users:
            await ctx.send("No active users found in this period.")
            return
        
        period_start = datetime.now() - timedelta(days=days)
        period_end = datetime.now()
        
        results = []
        for user in active_users[:10]:  # Limit to 10 users to avoid rate limits
            messages = db.get_user_messages_for_analysis(user['user_id'], days=days)
            
            if len(messages) < 5:  # Skip users with too few messages
                continue
            
            await ctx.send(f"Analyzing {user['username']}...")
            
            analysis = await asyncio.to_thread(llm.analyze_user_behavior, messages)
            
            if analysis:
                db.store_behavior_analysis(
                    user['user_id'],
                    user['username'],
                    analysis,
                    period_start,
                    period_end
                )
                results.append(f"**{user['username']}**: Profanity {analysis['profanity_score']}/10, {analysis['message_count']} messages")
        
        if results:
            await ctx.send("✅ Analysis complete!\n\n" + "\n".join(results))
        else:
            await ctx.send("No users had enough messages to analyze.")
    
    except Exception as e:
        await ctx.send(f"❌ Error during analysis: {str(e)}")

@bot.command(name='stats')
async def user_stats(ctx, member: discord.Member = None):
    """Show statistics for a user"""
    target = member or ctx.author
    
    try:
        user_context = db.get_user_context(target.id)
        profile = user_context.get('profile')
        behavior = user_context.get('behavior')
        
        if not profile:
            await ctx.send(f"No data found for {target.display_name}")
            return
        
        embed = discord.Embed(
            title=f"📊 Stats for {target.display_name}",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Total Messages", value=profile['total_messages'], inline=True)
        embed.add_field(name="First Seen", value=profile['first_seen'].strftime('%Y-%m-%d'), inline=True)
        embed.add_field(name="Last Seen", value=profile['last_seen'].strftime('%Y-%m-%d'), inline=True)
        
        if behavior:
            embed.add_field(name="Profanity Score", value=f"{behavior['profanity_score']}/10", inline=True)
            embed.add_field(name="Tone", value=behavior['tone_analysis'][:100], inline=False)
            embed.add_field(name="Style", value=behavior['conversation_style'][:100], inline=False)
        else:
            embed.add_field(name="Behavior Analysis", value="Not yet analyzed. Use `/analyze` to generate.", inline=False)
        
        await ctx.send(embed=embed)
    
    except Exception as e:
        await ctx.send(f"❌ Error fetching stats: {str(e)}")

@bot.command(name='search')
async def manual_search(ctx, *, query: str):
    """Manually trigger a web search"""
    async with ctx.typing():
        try:
            results = await asyncio.to_thread(search.search, query)
            
            if not results:
                await ctx.send("No results found.")
                return
            
            embed = discord.Embed(
                title=f"🔍 Search Results: {query}",
                color=discord.Color.green()
            )
            
            for i, result in enumerate(results[:3], 1):
                embed.add_field(
                    name=f"{i}. {result['title'][:100]}",
                    value=f"{result['content'][:200]}...\n[Read more]({result['url']})",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
            db.store_search_log(query, len(results), ctx.author.id, ctx.channel.id)
        
        except Exception as e:
            await ctx.send(f"❌ Search error: {str(e)}")

@bot.command(name='ping')
async def ping(ctx):
    """Check bot latency"""
    await ctx.send(f"🏓 Pong! Latency: {round(bot.latency * 1000)}ms")

@bot.command(name='help')
async def help_prefix(ctx, command: str = None):
    """Show bot commands or get detailed help for a specific command"""
    if command:
        # Show detailed help for specific command
        embed = help_system.get_command_help(command)
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ No help found for command `{command}`. Use `!help` to see all available commands.")
    else:
        # Show general help
        embed = help_system.get_general_help()
        await ctx.send(embed=embed)

@bot.group(name='wompbot', invoke_without_command=True)
async def wompbot_command(ctx):
    """WompBot command group"""
    if ctx.invoked_subcommand is None:
        await ctx.send("Use `!wompbot help` to see available commands.")

@wompbot_command.command(name='help')
async def wompbot_help(ctx):
    """Show bot commands"""
    embed = discord.Embed(
        title="🤖 WompBot Commands",
        description="Here's what I can do:",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="@mention me",
        value="Tag me in a message to chat. Powered by Hermes-3 70B for fast, conversational responses with automatic web search when needed.",
        inline=False
    )
    embed.add_field(
        name="/stats [@user]",
        value="View statistics and behavior analysis for yourself or another user.",
        inline=False
    )
    embed.add_field(
        name="/receipts [@user] [keyword]",
        value="View tracked claims for a user. Optional keyword filter.",
        inline=False
    )
    embed.add_field(
        name="/quotes [@user]",
        value="View saved quotes for a user.",
        inline=False
    )
    embed.add_field(
        name="☁️ Save Quote",
        value="React to any message with :cloud: emoji to save it as a quote.",
        inline=False
    )
    embed.add_field(
        name="⚠️ Fact-Check",
        value="React to any message with :warning: emoji to trigger high-accuracy fact-checking. Uses Claude 3.5 Sonnet, web search, and multi-source verification (requires ≥2 sources). Rate limited: 5-minute cooldown, 10/day per user.",
        inline=False
    )
    embed.add_field(
        name="🛡️ Rate Limits & Cost Control",
        value=(
            "• Token limits: 1,000/request, 10,000/hour per user\n"
            "• Context: 4000 token hard cap (auto-truncates)\n"
            "• Fact-checks: 5-min cooldown, 10/day\n"
            "• Searches: 5/hour, 20/day per user\n"
            "• Messages: 3s cooldown, 10/min\n"
            "• Max concurrent requests: 3\n"
            "• $1 spending alerts: DM to bot owner\n"
            "All limits configurable via .env"
        ),
        inline=False
    )
    embed.add_field(
        name="📊 Chat Statistics",
        value=(
            "/stats_server [days|date_range] - Network graph & server stats\n"
            "/stats_topics [days|date_range] - Trending keywords (TF-IDF)\n"
            "/stats_primetime [@user] [days|date_range] - Activity heatmap\n"
            "/stats_engagement [@user] [days|date_range] - Engagement metrics"
        ),
        inline=False
    )
    embed.add_field(
        name="/leaderboard <type> [days]",
        value="Show top users by: `messages`, `questions`, or `profanity`. Default: 7 days",
        inline=False
    )
    embed.add_field(
        name="/search <query>",
        value="Manually search the web for information.",
        inline=False
    )
    embed.add_field(
        name="/analyze [days]",
        value="(Admin only) Analyze user behavior patterns from the last N days.",
        inline=False
    )
    embed.add_field(
        name="/ping",
        value="Check bot latency.",
        inline=False
    )

    embed.set_footer(text="Privacy: Use /wompbot_noconsent to opt out of data collection.")

    await ctx.send(embed=embed)

# SLASH COMMANDS USING APP_COMMANDS

@bot.tree.command(name="receipts", description="View tracked claims for a user")
@app_commands.describe(
    user="The user to check (optional, defaults to you)",
    keyword="Filter claims by keyword (optional)"
)
async def receipts_slash(interaction: discord.Interaction, user: discord.Member = None, keyword: str = None):
    """Show tracked claims for a user"""
    target = user or interaction.user
    
    await interaction.response.defer()
    
    try:
        claims = await claims_tracker.get_user_claims(target.id)
        
        if not claims:
            await interaction.followup.send(f"No tracked claims found for {target.display_name}")
            return
        
        # Filter by keyword if provided
        if keyword:
            keyword_lower = keyword.lower()
            claims = [c for c in claims if keyword_lower in c['claim_text'].lower()]
            
            if not claims:
                await interaction.followup.send(f"No claims found for {target.display_name} matching '{keyword}'")
                return
        
        # Create embed with claims
        embed = discord.Embed(
            title=f"📋 Claims by {target.display_name}",
            color=discord.Color.blue()
        )
        
        if keyword:
            embed.description = f"Filtered by: {keyword}"
        
        for i, claim in enumerate(claims[:10], 1):  # Show max 10
            status_emoji = {
                'unverified': '❓',
                'true': '✅',
                'false': '❌',
                'mixed': '🔀',
                'outdated': '📅'
            }.get(claim['verification_status'], '❓')
            
            edited_marker = " ✏️" if claim['is_edited'] else ""
            
            field_name = f"{i}. {claim['claim_type'].title()} - {claim['timestamp'].strftime('%Y-%m-%d')}"
            field_value = f"{status_emoji} {claim['claim_text'][:200]}{edited_marker}"
            
            embed.add_field(name=field_name, value=field_value, inline=False)
        
        if len(claims) > 10:
            embed.set_footer(text=f"Showing 10 of {len(claims)} claims")
        
        await interaction.followup.send(embed=embed)
    
    except Exception as e:
        await interaction.followup.send(f"❌ Error fetching receipts: {str(e)}")

@bot.tree.command(name="quotes", description="View saved quotes for a user")
@app_commands.describe(user="The user to check (optional, defaults to you)")
async def quotes_slash(interaction: discord.Interaction, user: discord.Member = None):
    """Show saved quotes for a user"""
    target = user or interaction.user
    
    await interaction.response.defer()
    
    try:
        quotes = claims_tracker.get_user_quotes(target.id, limit=10)
        
        if not quotes:
            await interaction.followup.send(f"No quotes found for {target.display_name}")
            return
        
        embed = discord.Embed(
            title=f"☁️  Quotes by {target.display_name}",
            color=discord.Color.purple()
        )
        
        for i, quote in enumerate(quotes, 1):
            field_name = f"{i}. {quote['timestamp'].strftime('%Y-%m-%d')} (⭐ {quote['reaction_count']})"
            field_value = f"\"{quote['quote_text'][:300]}\""
            
            embed.add_field(name=field_name, value=field_value, inline=False)
        
        await interaction.followup.send(embed=embed)
    
    except Exception as e:
        await interaction.followup.send(f"❌ Error fetching quotes: {str(e)}")

@bot.tree.command(name="verify_claim", description="Verify a claim (Admin only)")
@app_commands.describe(
    claim_id="The claim ID to verify",
    status="Status: true, false, mixed, or outdated",
    notes="Verification notes (optional)"
)
@app_commands.checks.has_permissions(administrator=True)
async def verify_claim_slash(interaction: discord.Interaction, claim_id: int, status: str, notes: str = None):
    """Verify a claim"""
    if status not in ['true', 'false', 'mixed', 'outdated']:
        await interaction.response.send_message("❌ Status must be: true, false, mixed, or outdated", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        with db.conn.cursor() as cur:
            cur.execute("""
                UPDATE claims
                SET verification_status = %s,
                    verification_date = %s,
                    verification_notes = %s
                WHERE id = %s
                RETURNING claim_text, username
            """, (status, datetime.now(), notes, claim_id))

            result = cur.fetchone()

            if result:
                claim_text, username = result
                await interaction.followup.send(f"✅ Claim #{claim_id} by {username} marked as **{status}**\n> {claim_text[:200]}")
            else:
                await interaction.followup.send(f"❌ Claim #{claim_id} not found")

    except Exception as e:
        await interaction.followup.send(f"❌ Error verifying claim: {str(e)}")

@bot.tree.command(name="help", description="Show all commands or get detailed help for a specific command")
@app_commands.describe(command="Optional: specific command to get detailed help for")
async def help_slash(interaction: discord.Interaction, command: str = None):
    """Show bot commands or detailed help for a specific command"""
    if command:
        # Show detailed help for specific command
        embed = help_system.get_command_help(command)
        if embed:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❌ No help found for command `{command}`. Use `/help` to see all available commands.",
                ephemeral=True
            )
    else:
        # Show general help
        embed = help_system.get_general_help()
        await interaction.response.send_message(embed=embed)

# CHAT STATISTICS SLASH COMMANDS

@bot.tree.command(name="stats_server", description="Show server network graph and interaction statistics")
@app_commands.describe(date_range="Days (e.g., '30') or date range (e.g., '01/15/2024-02/15/2024')")
async def stats_server(interaction: discord.Interaction, date_range: str = "30"):
    """Show server network statistics and interaction graph"""
    await interaction.response.defer()

    try:
        # Parse date range
        start_date, end_date = chat_stats.parse_date_range(date_range)

        # Check cache
        scope = f"server:{interaction.guild.id}"
        cached = chat_stats.get_cached_stats('network', scope, start_date, end_date)

        if cached:
            results = cached
        else:
            # Get messages
            messages = chat_stats.get_messages_for_analysis(None, start_date, end_date, exclude_opted_out=True)

            if not messages:
                await interaction.followup.send("No messages found in this time range.")
                return

            # Build network graph
            network = chat_stats.build_network_graph(messages)
            results = network

            # Cache results
            chat_stats.cache_stats('network', scope, start_date, end_date, results, cache_hours=6)

        # Format output
        embed = discord.Embed(
            title="📊 Server Network Statistics",
            description=f"Analysis from {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}",
            color=discord.Color.blue()
        )

        # Top connected users
        nodes = results['nodes']
        top_users = sorted(nodes.items(), key=lambda x: x[1]['degree'], reverse=True)[:10]

        table_data = []
        for _, data in top_users:
            table_data.append([data['username'][:15], str(data['messages']), str(data['degree'])])

        table = chat_stats.format_as_discord_table(
            ['User', 'Messages', 'Connections'],
            table_data
        )

        embed.add_field(name="Most Connected Users", value=table, inline=False)
        embed.set_footer(text=f"Total users analyzed: {len(nodes)} | Cached for 6 hours")

        await interaction.followup.send(embed=embed)

    except ValueError as e:
        await interaction.followup.send(f"❌ {str(e)}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error generating stats: {str(e)}")
        print(f"❌ Stats error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="stats_topics", description="Show trending topics and keywords")
@app_commands.describe(date_range="Days (e.g., '30') or date range (e.g., '01/15/2024-02/15/2024')")
async def stats_topics(interaction: discord.Interaction, date_range: str = "30"):
    """Show trending topics using TF-IDF keyword extraction"""
    await interaction.response.defer()

    try:
        # Parse date range
        start_date, end_date = chat_stats.parse_date_range(date_range)

        # Check cache
        scope = f"server:{interaction.guild.id}"
        cached = chat_stats.get_cached_stats('topics', scope, start_date, end_date)

        if cached:
            topics = cached
        else:
            # Get messages
            messages = chat_stats.get_messages_for_analysis(None, start_date, end_date, exclude_opted_out=True)

            if not messages:
                await interaction.followup.send("No messages found in this time range.")
                return

            # Extract topics
            topics = chat_stats.extract_topics_tfidf(messages, top_n=15)

            if not topics:
                await interaction.followup.send("Could not extract topics from messages.")
                return

            # Cache results
            chat_stats.cache_stats('topics', scope, start_date, end_date, topics, cache_hours=6)

        # Format output
        embed = discord.Embed(
            title="🔥 Trending Topics",
            description=f"Top keywords from {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}",
            color=discord.Color.orange()
        )

        table_data = []
        for i, topic in enumerate(topics[:15], 1):
            # Create bar visualization
            bar_length = int(topic['score'] * 20)
            bar = "█" * bar_length
            table_data.append([f"{i}.", topic['keyword'][:20], str(topic['count']), bar])

        table = chat_stats.format_as_discord_table(
            ['#', 'Keyword', 'Count', 'Relevance'],
            table_data
        )

        embed.add_field(name="Top Keywords (TF-IDF Analysis)", value=table, inline=False)
        embed.set_footer(text="Cached for 6 hours | Uses keyword extraction (no LLM)")

        await interaction.followup.send(embed=embed)

    except ValueError as e:
        await interaction.followup.send(f"❌ {str(e)}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error generating topics: {str(e)}")
        print(f"❌ Topics error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="stats_primetime", description="Show activity patterns and peak hours")
@app_commands.describe(
    user="User to analyze (optional, defaults to server-wide)",
    date_range="Days (e.g., '30') or date range (e.g., '01/15/2024-02/15/2024')"
)
async def stats_primetime(interaction: discord.Interaction, user: discord.Member = None, date_range: str = "30"):
    """Show activity heatmap and peak hours"""
    await interaction.response.defer()

    try:
        # Parse date range
        start_date, end_date = chat_stats.parse_date_range(date_range)

        # Determine scope
        if user:
            scope = f"user:{user.id}"
        else:
            scope = f"server:{interaction.guild.id}"

        # Check cache
        cached = chat_stats.get_cached_stats('primetime', scope, start_date, end_date)

        if cached:
            results = cached
        else:
            # Get messages
            messages = chat_stats.get_messages_for_analysis(None, start_date, end_date, exclude_opted_out=True)

            # Filter by user if specified
            if user:
                messages = [m for m in messages if m['user_id'] == user.id]

            if not messages:
                await interaction.followup.send(f"No messages found for {user.display_name if user else 'server'} in this time range.")
                return

            # Calculate primetime stats
            results = chat_stats.calculate_primetime(messages)

            # Cache results
            chat_stats.cache_stats('primetime', scope, start_date, end_date, results, cache_hours=6)

        # Format output
        target_name = user.display_name if user else "Server"
        embed = discord.Embed(
            title=f"⏰ Prime Time Analysis - {target_name}",
            description=f"Activity from {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}",
            color=discord.Color.purple()
        )

        # Hourly heatmap
        hourly = results['hourly']
        max_hour_count = max(hourly.values()) if hourly else 1

        hourly_viz = []
        for hour in range(24):
            count = hourly.get(hour, 0)
            bar_length = int((count / max_hour_count) * 15) if max_hour_count > 0 else 0
            bar = "█" * bar_length
            time_str = f"{hour:02d}:00"
            hourly_viz.append([time_str, str(count), bar])

        hourly_table = chat_stats.format_as_discord_table(
            ['Hour', 'Msgs', 'Activity'],
            hourly_viz
        )

        embed.add_field(name="Hourly Activity", value=hourly_table, inline=False)

        # Day of week breakdown
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        daily = results['daily']
        max_day_count = max(daily.values()) if daily else 1

        daily_viz = []
        for day in range(7):
            count = daily.get(day, 0)
            bar_length = int((count / max_day_count) * 15) if max_day_count > 0 else 0
            bar = "█" * bar_length
            daily_viz.append([day_names[day], str(count), bar])

        daily_table = chat_stats.format_as_discord_table(
            ['Day', 'Msgs', 'Activity'],
            daily_viz
        )

        embed.add_field(name="Day of Week", value=daily_table, inline=False)

        peak_hour = results['peak_hour']
        peak_day = day_names[results['peak_day']]
        embed.set_footer(text=f"Peak hour: {peak_hour:02d}:00 | Peak day: {peak_day} | Total: {results['total_messages']} msgs")

        await interaction.followup.send(embed=embed)

    except ValueError as e:
        await interaction.followup.send(f"❌ {str(e)}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error generating primetime stats: {str(e)}")
        print(f"❌ Primetime error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="stats_engagement", description="Show engagement metrics and conversation patterns")
@app_commands.describe(
    user="User to analyze (optional, defaults to server-wide)",
    date_range="Days (e.g., '30') or date range (e.g., '01/15/2024-02/15/2024')"
)
async def stats_engagement(interaction: discord.Interaction, user: discord.Member = None, date_range: str = "30"):
    """Show engagement metrics"""
    await interaction.response.defer()

    try:
        # Parse date range
        start_date, end_date = chat_stats.parse_date_range(date_range)

        # Determine scope
        if user:
            scope = f"user_engagement:{user.id}"
        else:
            scope = f"server_engagement:{interaction.guild.id}"

        # Check cache
        cached = chat_stats.get_cached_stats('engagement', scope, start_date, end_date)

        if cached:
            results = cached
        else:
            # Get messages
            messages = chat_stats.get_messages_for_analysis(None, start_date, end_date, exclude_opted_out=True)

            # Filter by user if specified
            if user:
                messages = [m for m in messages if m['user_id'] == user.id]

            if not messages:
                await interaction.followup.send(f"No messages found for {user.display_name if user else 'server'} in this time range.")
                return

            # Calculate engagement
            results = chat_stats.calculate_engagement(messages)

            # Cache results
            chat_stats.cache_stats('engagement', scope, start_date, end_date, results, cache_hours=6)

        # Format output
        target_name = user.display_name if user else "Server"
        embed = discord.Embed(
            title=f"📈 Engagement Metrics - {target_name}",
            description=f"Analysis from {start_date.strftime('%m/%d/%Y')} to {end_date.strftime('%m/%d/%Y')}",
            color=discord.Color.green()
        )

        # Summary stats
        embed.add_field(name="Total Messages", value=f"{results['total_messages']:,}", inline=True)
        embed.add_field(name="Unique Users", value=f"{results['unique_users']}", inline=True)
        embed.add_field(name="Avg Length", value=f"{results['avg_message_length']:.1f} chars", inline=True)

        if not user:
            embed.add_field(name="Avg Msgs/User", value=f"{results['avg_messages_per_user']:.1f}", inline=True)

        # Top responders
        if results['top_responders']:
            table_data = []
            for username, count in results['top_responders'][:10]:
                table_data.append([username[:15], str(count)])

            table = chat_stats.format_as_discord_table(
                ['User', 'Responses'],
                table_data
            )

            embed.add_field(name="Most Responsive Users", value=table, inline=False)

        await interaction.followup.send(embed=embed)

    except ValueError as e:
        await interaction.followup.send(f"❌ {str(e)}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error generating engagement stats: {str(e)}")
        print(f"❌ Engagement error: {e}")
        import traceback
        traceback.print_exc()

# =============== HOT TAKES COMMANDS ===============

@bot.tree.command(name="hottakes", description="Show hot takes leaderboard")
@app_commands.describe(
    leaderboard_type="Type of leaderboard (controversial/vindicated/worst/community/combined)",
    days="Number of days to look back (default: 30)"
)
@app_commands.choices(leaderboard_type=[
    app_commands.Choice(name="Most Controversial", value="controversial"),
    app_commands.Choice(name="Best Vindicated", value="vindicated"),
    app_commands.Choice(name="Worst Takes", value="worst"),
    app_commands.Choice(name="Community Favorite", value="community"),
    app_commands.Choice(name="Hot Take Kings", value="combined"),
])
async def hottakes(interaction: discord.Interaction, leaderboard_type: str = "controversial", days: int = 30):
    """Show hot takes leaderboard"""
    await interaction.response.defer()

    try:
        results = await hot_takes_tracker.get_leaderboard(leaderboard_type, days=days, limit=10)

        if not results:
            await interaction.followup.send(f"No hot takes found in the last {days} days.")
            return

        # Format embed based on leaderboard type
        title_map = {
            'controversial': '🔥 Most Controversial Takes',
            'vindicated': '✅ Best Vindicated Takes',
            'worst': '❌ Worst Takes',
            'community': '⭐ Community Favorites',
            'combined': '👑 Hot Take Kings'
        }

        embed = discord.Embed(
            title=title_map.get(leaderboard_type, '🔥 Hot Takes'),
            description=f"Last {days} days",
            color=discord.Color.red()
        )

        for i, take in enumerate(results, 1):
            username = take['username']
            claim_text = take['claim_text'][:150] + ('...' if len(take['claim_text']) > 150 else '')

            if leaderboard_type == 'controversial':
                score_text = f"🔥 Controversy: {take['controversy_score']:.1f}/10"
            elif leaderboard_type == 'vindicated':
                score_text = f"✅ Aged like fine wine: {take['age_score']:.1f}/10"
            elif leaderboard_type == 'worst':
                score_text = f"❌ Aged like milk: {take['age_score']:.1f}/10"
            elif leaderboard_type == 'community':
                score_text = f"⭐ Community: {take['community_score']:.1f}/10 | 👍 {take['total_reactions']} reactions"
            else:  # combined
                score_text = f"👑 Combined: {take['combined_score']:.1f} | 🔥 {take['controversy_score']:.1f} | ✅ {take.get('age_score', 'N/A')}"

            embed.add_field(
                name=f"#{i} - {username}",
                value=f"> {claim_text}\n\n{score_text}",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error fetching hot takes: {str(e)}")
        print(f"❌ Hot takes error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="mystats_hottakes", description="View your personal hot takes statistics")
async def mystats_hottakes(interaction: discord.Interaction):
    """Show user's personal hot takes stats"""
    await interaction.response.defer()

    try:
        stats = await hot_takes_tracker.get_user_hot_takes_stats(interaction.user.id)

        if not stats or stats.get('total_hot_takes', 0) == 0:
            await interaction.followup.send("You haven't made any hot takes yet. Time to get controversial! 🔥")
            return

        embed = discord.Embed(
            title=f"🔥 {interaction.user.display_name}'s Hot Takes Stats",
            color=discord.Color.red()
        )

        embed.add_field(name="Total Hot Takes", value=f"{stats['total_hot_takes']}", inline=True)
        embed.add_field(name="Spiciest Take", value=f"{stats['spiciest_take']:.1f}/10", inline=True)
        embed.add_field(name="Avg Controversy", value=f"{stats['avg_controversy']:.1f}/10", inline=True)
        embed.add_field(name="Vindicated", value=f"✅ {stats['vindicated_count']}", inline=True)
        embed.add_field(name="Proven Wrong", value=f"❌ {stats['failed_count']}", inline=True)
        embed.add_field(name="Avg Community Score", value=f"{stats['avg_community']:.1f}/10", inline=True)

        # Calculate win rate
        total_resolved = stats['vindicated_count'] + stats['failed_count']
        if total_resolved > 0:
            win_rate = (stats['vindicated_count'] / total_resolved) * 100
            embed.add_field(name="Win Rate", value=f"{win_rate:.1f}%", inline=True)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error fetching your stats: {str(e)}")
        print(f"❌ User hot takes stats error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="vindicate", description="Mark a hot take as vindicated or proven wrong (Admin only)")
@app_commands.describe(
    hot_take_id="ID of the hot take",
    status="Vindication status (won/lost/mixed/pending)",
    notes="Optional notes about the vindication"
)
@app_commands.choices(status=[
    app_commands.Choice(name="Won (Proven Right)", value="won"),
    app_commands.Choice(name="Lost (Proven Wrong)", value="lost"),
    app_commands.Choice(name="Mixed (Partially Right)", value="mixed"),
    app_commands.Choice(name="Pending", value="pending"),
])
async def vindicate(interaction: discord.Interaction, hot_take_id: int, status: str, notes: str = None):
    """Vindicate a hot take (admin only)"""
    # Check if user is admin
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only administrators can vindicate hot takes.", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        success = await hot_takes_tracker.vindicate_hot_take(hot_take_id, status, notes)

        if success:
            status_emoji = {
                'won': '✅',
                'lost': '❌',
                'mixed': '🔀',
                'pending': '⏳'
            }
            emoji = status_emoji.get(status, '✅')

            await interaction.followup.send(
                f"{emoji} Hot take #{hot_take_id} marked as **{status.upper()}**" +
                (f"\n\nNotes: {notes}" if notes else "")
            )
        else:
            await interaction.followup.send(f"❌ Failed to vindicate hot take #{hot_take_id}. It may not exist.")

    except Exception as e:
        await interaction.followup.send(f"❌ Error vindicating hot take: {str(e)}")
        print(f"❌ Vindication error: {e}")
        import traceback
        traceback.print_exc()

# =============== REMINDER COMMANDS ===============

@bot.tree.command(name="remind", description="Set a reminder with natural language time")
@app_commands.describe(
    time="When to remind (e.g., 'in 5 minutes', 'tomorrow at 3pm', 'next Monday')",
    message="What to remind you about",
    recurring="Make this a recurring reminder (optional)"
)
async def remind(interaction: discord.Interaction, time: str, message: str, recurring: bool = False):
    """Set a reminder"""
    await interaction.response.defer()

    try:
        # Parse and create reminder
        result = await reminder_system.create_reminder(
            user_id=interaction.user.id,
            username=str(interaction.user),
            channel_id=interaction.channel.id,
            message_id=None,  # Slash commands don't have a message to link back to
            reminder_text=message,
            time_string=time,
            recurring=recurring,
            recurring_interval=time if recurring else None
        )

        if not result:
            await interaction.followup.send(
                f"❌ Could not parse time '{time}'. Try formats like:\n"
                "• `in 5 minutes`\n"
                "• `in 2 hours`\n"
                "• `tomorrow at 3pm`\n"
                "• `next Monday`\n"
                "• `at 15:00`"
            )
            return

        reminder_id, remind_at = result

        # Format confirmation
        timestamp = int(remind_at.timestamp())
        await interaction.followup.send(
            f"✅ Reminder set! I'll remind you <t:{timestamp}:R> (at <t:{timestamp}:f>)\n"
            f"**Message:** {message}\n"
            f"{'🔄 **Recurring:** Yes' if recurring else ''}\n"
            f"_Reminder ID: {reminder_id}_"
        )

    except Exception as e:
        await interaction.followup.send(f"❌ Error setting reminder: {str(e)}")
        print(f"❌ Reminder error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="reminders", description="View your active reminders")
async def reminders(interaction: discord.Interaction):
    """View active reminders"""
    await interaction.response.defer()

    try:
        user_reminders = await reminder_system.get_user_reminders(interaction.user.id)

        if not user_reminders:
            await interaction.followup.send("You have no active reminders.")
            return

        embed = discord.Embed(
            title=f"⏰ {interaction.user.display_name}'s Reminders",
            color=discord.Color.blue()
        )

        for reminder in user_reminders[:10]:  # Limit to 10
            timestamp = int(reminder['remind_at'].timestamp())
            time_remaining = reminder_system.format_time_remaining(reminder['remind_at'])

            value = f"**Message:** {reminder['reminder_text'][:100]}\n"
            value += f"**When:** <t:{timestamp}:R> (<t:{timestamp}:f>)\n"
            value += f"**Time left:** {time_remaining}\n"
            value += f"{'🔄 Recurring' if reminder['recurring'] else ''}"

            embed.add_field(
                name=f"ID: {reminder['id']}",
                value=value,
                inline=False
            )

        if len(user_reminders) > 10:
            embed.set_footer(text=f"Showing 10 of {len(user_reminders)} reminders")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error fetching reminders: {str(e)}")
        print(f"❌ Reminders fetch error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="cancel_reminder", description="Cancel one of your reminders")
@app_commands.describe(reminder_id="ID of the reminder to cancel")
async def cancel_reminder(interaction: discord.Interaction, reminder_id: int):
    """Cancel a reminder"""
    await interaction.response.defer()

    try:
        success = await reminder_system.cancel_reminder(reminder_id, interaction.user.id)

        if success:
            await interaction.followup.send(f"✅ Reminder #{reminder_id} cancelled")
        else:
            await interaction.followup.send(
                f"❌ Could not cancel reminder #{reminder_id}. "
                "It may not exist or you don't own it."
            )

    except Exception as e:
        await interaction.followup.send(f"❌ Error cancelling reminder: {str(e)}")
        print(f"❌ Cancel reminder error: {e}")
        import traceback
        traceback.print_exc()

# ===== Event Scheduling Commands =====
@bot.tree.command(name="schedule_event", description="Schedule an event with automatic reminders")
@app_commands.describe(
    name="Name of the event",
    date="When the event happens (e.g., 'tomorrow at 7pm', 'next Friday at 8pm', 'in 3 days')",
    description="Optional description of the event",
    reminders="Optional: comma-separated reminder intervals (e.g., '1 week, 1 day, 1 hour')"
)
async def schedule_event(
    interaction: discord.Interaction,
    name: str,
    date: str,
    description: str = None,
    reminders: str = None
):
    """Schedule an event with periodic reminders"""
    await interaction.response.defer()

    try:
        # Parse event date
        event_date = event_system.parse_event_time(date)

        if not event_date:
            await interaction.followup.send(
                f"❌ Could not parse time: '{date}'\n\n"
                "Try formats like:\n"
                "• `tomorrow at 7pm`\n"
                "• `next Friday at 8pm`\n"
                "• `in 3 days at 6pm`\n"
                "• `Monday at 5pm`"
            )
            return

        # Check if event is in the past
        if event_date < datetime.now():
            await interaction.followup.send("❌ Event date must be in the future")
            return

        # Parse reminder intervals
        reminder_intervals = event_system.parse_reminder_intervals(reminders)

        # Create event
        event_id = await event_system.create_event(
            event_name=name,
            event_date=event_date,
            created_by_user_id=interaction.user.id,
            created_by_username=str(interaction.user),
            channel_id=interaction.channel.id,
            guild_id=interaction.guild.id,
            description=description,
            reminder_intervals=reminder_intervals
        )

        if event_id:
            # Format event date for Discord timestamp
            timestamp = int(event_date.timestamp())

            embed = discord.Embed(
                title="📅 Event Scheduled",
                description=f"**{name}**",
                color=discord.Color.green()
            )

            embed.add_field(
                name="When",
                value=f"<t:{timestamp}:F> (<t:{timestamp}:R>)",
                inline=False
            )

            if description:
                embed.add_field(
                    name="Description",
                    value=description,
                    inline=False
                )

            embed.add_field(
                name="Reminders",
                value=", ".join(reminder_intervals) if reminder_intervals else "None",
                inline=False
            )

            embed.set_footer(text=f"Event ID: {event_id} • Created by {interaction.user.display_name}")

            await interaction.followup.send(embed=embed)
            print(f"📅 Event created: '{name}' at {event_date} (ID: {event_id})")
        else:
            await interaction.followup.send("❌ Failed to create event")

    except Exception as e:
        await interaction.followup.send(f"❌ Error scheduling event: {str(e)}")
        print(f"❌ Schedule event error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="events", description="View upcoming scheduled events")
@app_commands.describe(limit="Maximum number of events to show (default: 10)")
async def events(interaction: discord.Interaction, limit: int = 10):
    """List upcoming events"""
    await interaction.response.defer()

    try:
        upcoming = await event_system.get_upcoming_events(interaction.guild.id, limit)

        if not upcoming:
            await interaction.followup.send("📅 No upcoming events scheduled")
            return

        embed = discord.Embed(
            title="📅 Upcoming Events",
            color=discord.Color.blue()
        )

        for event in upcoming:
            timestamp = int(event['event_date'].timestamp())
            time_until = event_system.format_time_until(event['event_date'])

            field_value = f"**When:** <t:{timestamp}:F>\n**Time until:** {time_until}"

            if event.get('description'):
                field_value += f"\n**Details:** {event['description'][:100]}"

            field_value += f"\n**Created by:** {event['created_by_username']}"
            field_value += f"\n**ID:** {event['id']}"

            embed.add_field(
                name=event['event_name'],
                value=field_value,
                inline=False
            )

        embed.set_footer(text=f"Showing {len(upcoming)} event{'s' if len(upcoming) != 1 else ''}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error getting events: {str(e)}")
        print(f"❌ Events list error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="cancel_event", description="Cancel a scheduled event")
@app_commands.describe(event_id="ID of the event to cancel")
async def cancel_event(interaction: discord.Interaction, event_id: int):
    """Cancel an event"""
    await interaction.response.defer()

    try:
        success = await event_system.cancel_event(event_id, interaction.user.id)

        if success:
            await interaction.followup.send(f"✅ Event #{event_id} cancelled")
            print(f"📅 Event #{event_id} cancelled by {interaction.user}")
        else:
            await interaction.followup.send(
                f"❌ Could not cancel event #{event_id}. "
                "It may not exist or has already been cancelled."
            )

    except Exception as e:
        await interaction.followup.send(f"❌ Error cancelling event: {str(e)}")
        print(f"❌ Cancel event error: {e}")
        import traceback
        traceback.print_exc()

# ===== Yearly Wrapped =====
@bot.tree.command(name="wrapped", description="View your yearly activity summary (Spotify Wrapped for Discord!)")
@app_commands.describe(
    year="Year to get wrapped for (defaults to current year)",
    user="User to view wrapped for (defaults to yourself)"
)
async def wrapped(interaction: discord.Interaction, year: int = None, user: discord.Member = None):
    """Generate yearly wrapped statistics"""
    await interaction.response.defer()

    try:
        # Rate limiting for expensive wrapped generation
        wrapped_cooldown = int(os.getenv('WRAPPED_COOLDOWN', '60'))  # 60 seconds default
        rate_check = db.check_feature_rate_limit(
            interaction.user.id,
            'wrapped',
            cooldown_seconds=wrapped_cooldown
        )

        if not rate_check['allowed']:
            wait_seconds = rate_check.get('wait_seconds', 60)
            await interaction.followup.send(
                f"⏱️ Wrapped cooldown! Please wait {wait_seconds} seconds before generating another wrapped."
            )
            return

        target_user = user if user else interaction.user
        target_year = year if year else datetime.now().year

        # Validate year
        current_year = datetime.now().year
        if target_year < 2020 or target_year > current_year:
            await interaction.followup.send(f"❌ Please choose a year between 2020 and {current_year}")
            return

        # Generate wrapped data
        wrapped_data = await yearly_wrapped.generate_wrapped(target_user.id, target_year)

        if not wrapped_data:
            await interaction.followup.send(
                f"📊 No data found for {target_user.display_name} in {target_year}"
            )
            return

        # Create beautiful embed
        embed = discord.Embed(
            title=f"📊 {target_year} Wrapped",
            description=f"**{target_user.display_name}'s Year in Review**",
            color=discord.Color.gold()
        )

        # Set thumbnail
        embed.set_thumbnail(url=target_user.display_avatar.url)

        # Message Activity
        msg_stats = wrapped_data['message_stats']
        activity_text = f"**{msg_stats['total_messages']:,}** messages sent"
        if msg_stats['server_rank']:
            activity_text += f"\n🏆 **Rank #{msg_stats['server_rank']}** in server"
        if msg_stats['most_active_month']:
            month_name = yearly_wrapped.format_month_name(msg_stats['most_active_month'])
            activity_text += f"\n📅 Most active: **{month_name}**"
        if msg_stats['most_active_day_of_week'] is not None:
            day_name = yearly_wrapped.format_day_name(msg_stats['most_active_day_of_week'])
            activity_text += f"\n📆 Favorite day: **{day_name}**"
        if msg_stats['most_active_hour'] is not None:
            hour = msg_stats['most_active_hour']
            period = 'AM' if hour < 12 else 'PM'
            display_hour = hour if hour <= 12 else hour - 12
            display_hour = 12 if display_hour == 0 else display_hour
            activity_text += f"\n⏰ Peak hour: **{display_hour} {period}**"

        embed.add_field(
            name="💬 Message Activity",
            value=activity_text,
            inline=False
        )

        # Social Stats
        social_stats = wrapped_data['social_stats']
        if social_stats['top_conversation_partner'] or social_stats['replies_sent'] > 0:
            social_text = ""
            if social_stats['replies_sent'] > 0:
                social_text += f"**{social_stats['replies_sent']}** replies sent\n"
            if social_stats['replies_received'] > 0:
                social_text += f"**{social_stats['replies_received']}** replies received\n"
            if social_stats['top_conversation_partner']:
                social_text += f"🗣️ Top buddy: <@{social_stats['top_conversation_partner']}> ({social_stats['top_partner_count']} replies)"

            if social_text:
                embed.add_field(
                    name="👥 Social Network",
                    value=social_text,
                    inline=False
                )

        # Claims & Hot Takes
        claims_stats = wrapped_data['claims_stats']
        if claims_stats['total_claims'] > 0 or claims_stats['hot_take_count'] > 0:
            claims_text = ""
            if claims_stats['total_claims'] > 0:
                claims_text += f"📋 **{claims_stats['total_claims']}** claims tracked\n"
            if claims_stats['hot_take_count'] > 0:
                claims_text += f"🔥 **{claims_stats['hot_take_count']}** hot takes\n"
                if claims_stats['avg_controversy_score'] > 0:
                    claims_text += f"⚡ Controversy: **{claims_stats['avg_controversy_score']}/10**\n"
                if claims_stats['vindicated'] > 0:
                    claims_text += f"✅ Vindicated: **{claims_stats['vindicated']}**\n"
                if claims_stats['wrong'] > 0:
                    claims_text += f"❌ Wrong: **{claims_stats['wrong']}**"

            if claims_text:
                embed.add_field(
                    name="🔥 Claims & Hot Takes",
                    value=claims_text,
                    inline=True
                )

        # Quotes
        quotes_stats = wrapped_data['quotes_stats']
        if quotes_stats['quotes_received'] > 0 or quotes_stats['quotes_saved'] > 0:
            quotes_text = ""
            if quotes_stats['quotes_received'] > 0:
                quotes_text += f"☁️ **{quotes_stats['quotes_received']}** times quoted\n"
            if quotes_stats['quotes_saved'] > 0:
                quotes_text += f"💾 **{quotes_stats['quotes_saved']}** quotes saved\n"
            if quotes_stats['most_quoted_person']:
                quotes_text += f"⭐ Favorite quotee: <@{quotes_stats['most_quoted_person']}>"

            if quotes_text:
                embed.add_field(
                    name="☁️ Quotes",
                    value=quotes_text,
                    inline=True
                )

        # Personality Insights
        personality = wrapped_data['personality']
        if personality['question_rate'] > 0 or personality['fact_checks_requested'] > 0:
            personality_text = ""
            if personality['question_rate'] > 0:
                personality_text += f"❓ Question rate: **{personality['question_rate']}%**\n"
            if personality['profanity_score'] > 0:
                personality_text += f"🤬 Profanity: **{personality['profanity_score']}/10**\n"
            if personality['fact_checks_requested'] > 0:
                personality_text += f"⚠️ Fact checks: **{personality['fact_checks_requested']}**"

            if personality_text:
                embed.add_field(
                    name="🎭 Personality",
                    value=personality_text,
                    inline=False
                )

        # Achievements
        achievements = wrapped_data['achievements']
        if achievements:
            embed.add_field(
                name="🏆 Achievements",
                value=" ".join(achievements),
                inline=False
            )

        # Footer
        embed.set_footer(text=f"Your {target_year} wrapped • Generated with ❤️")
        embed.timestamp = datetime.now()

        await interaction.followup.send(embed=embed)
        db.record_feature_usage(interaction.user.id, 'wrapped')
        print(f"📊 Generated {target_year} wrapped for {target_user.display_name}")

    except Exception as e:
        await interaction.followup.send(f"❌ Error generating wrapped: {str(e)}")
        print(f"❌ Wrapped error: {e}")
        import traceback
        traceback.print_exc()

# ===== Quote of the Day =====
@bot.tree.command(name="qotd", description="View featured quotes from different time periods")
@app_commands.describe(
    mode="Time period: daily, weekly, monthly, alltime, or random"
)
@app_commands.choices(mode=[
    app_commands.Choice(name="Daily (last 24 hours)", value="daily"),
    app_commands.Choice(name="Weekly (last 7 days)", value="weekly"),
    app_commands.Choice(name="Monthly (last 30 days)", value="monthly"),
    app_commands.Choice(name="All-Time Great", value="alltime"),
    app_commands.Choice(name="Random", value="random")
])
async def quote_of_the_day(interaction: discord.Interaction, mode: app_commands.Choice[str] = None):
    """Display featured quote of the day/week/month"""
    await interaction.response.defer()

    try:
        # Default to daily if no mode specified
        selected_mode = mode.value if mode else 'daily'

        # Get the quote
        quote = await qotd.get_quote(selected_mode)

        if not quote:
            await interaction.followup.send(
                f"❌ No quotes found for {selected_mode} period. Try a different time range!"
            )
            return

        # Create beautiful embed
        title = qotd.get_mode_title(selected_mode)
        description = qotd.get_mode_description(selected_mode)

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.purple()
        )

        # The quote itself - make it stand out
        quote_text = f"*\"{quote['quote_text']}\"*"
        embed.add_field(
            name="💬 Quote",
            value=quote_text,
            inline=False
        )

        # Attribution
        timestamp = int(quote['timestamp'].timestamp())
        attribution = f"— **{quote['username']}**\n"
        attribution += f"<t:{timestamp}:D> (<t:{timestamp}:R>)"

        embed.add_field(
            name="👤 Said By",
            value=attribution,
            inline=True
        )

        # Who saved it
        if quote['added_by_username']:
            saved_text = f"**{quote['added_by_username']}**"
            if quote['reaction_count'] > 1:
                saved_text += f"\n☁️ {quote['reaction_count']} reactions"
            embed.add_field(
                name="💾 Saved By",
                value=saved_text,
                inline=True
            )

        # Context if available
        if quote['context']:
            context_text = quote['context'][:200]
            if len(quote['context']) > 200:
                context_text += "..."
            embed.add_field(
                name="📝 Context",
                value=f"```{context_text}```",
                inline=False
            )

        # Category badge
        if quote['category']:
            category_emojis = {
                'funny': '😂',
                'crazy': '🤪',
                'wise': '🧠',
                'wtf': '😳',
                'savage': '🔥'
            }
            emoji = category_emojis.get(quote['category'], '💬')
            embed.add_field(
                name="🏷️ Category",
                value=f"{emoji} {quote['category'].title()}",
                inline=True
            )

        # Footer with ID
        embed.set_footer(text=f"Quote #{quote['id']}")
        embed.timestamp = datetime.now()

        await interaction.followup.send(embed=embed)
        print(f"💬 Displayed {selected_mode} quote: #{quote['id']}")

    except Exception as e:
        await interaction.followup.send(f"❌ Error fetching quote: {str(e)}")
        print(f"❌ QOTD error: {e}")
        import traceback
        traceback.print_exc()

# ===== Debate Scorekeeper =====
@bot.tree.command(name="debate_start", description="Start tracking a debate")
@app_commands.describe(topic="What's being debated?")
async def debate_start(interaction: discord.Interaction, topic: str):
    """Start tracking a debate in this channel"""
    success = await debate_scorekeeper.start_debate(
        interaction.channel.id,
        interaction.guild.id,
        topic,
        interaction.user.id,
        str(interaction.user)
    )

    if success:
        await interaction.response.send_message(
            f"⚔️ **Debate Started!**\n"
            f"Topic: **{topic}**\n\n"
            f"All messages in this channel are now being tracked.\n"
            f"Use `/debate_end` when finished to see analysis and results!"
        )
    else:
        await interaction.response.send_message(
            "❌ There's already an active debate in this channel!\n"
            f"Current topic: **{debate_scorekeeper.get_active_debate_topic(interaction.channel.id)}**"
        )

@bot.tree.command(name="debate_end", description="End debate and show LLM analysis")
async def debate_end(interaction: discord.Interaction):
    """End debate and analyze with LLM"""
    await interaction.response.defer()

    try:
        result = await debate_scorekeeper.end_debate(interaction.channel.id)

        if not result:
            await interaction.followup.send("❌ No active debate in this channel!")
            return

        if 'error' in result:
            await interaction.followup.send(f"❌ {result['message']}")
            return

        # Create results embed
        embed = discord.Embed(
            title=f"⚔️ Debate Results: {result['topic']}",
            description=result['analysis'].get('summary', 'Debate concluded'),
            color=discord.Color.red()
        )

        duration_mins = int(result['duration_minutes'])
        embed.add_field(
            name="📊 Stats",
            value=f"Duration: {duration_mins} min\nParticipants: {result['participant_count']}\nMessages: {result['message_count']}",
            inline=True
        )

        # Winner
        if 'winner' in result['analysis']:
            winner = result['analysis']['winner']
            reason = result['analysis'].get('winner_reason', 'Superior arguments')
            embed.add_field(
                name="🏆 Winner",
                value=f"**{winner}**\n{reason[:100]}",
                inline=True
            )

        # Participant scores
        if 'participants' in result['analysis']:
            for username, data in result['analysis']['participants'].items():
                score = data.get('score', '?')
                strengths = data.get('strengths', 'N/A')[:150]
                fallacies = data.get('fallacies', [])

                field_value = f"**Score:** {score}/10\n**Strengths:** {strengths}"
                if fallacies:
                    field_value += f"\n**Fallacies:** {', '.join(fallacies[:2])}"

                embed.add_field(
                    name=f"👤 {username}",
                    value=field_value,
                    inline=False
                )

        embed.set_footer(text=f"Debate #{result['debate_id']}")
        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error ending debate: {str(e)}")
        print(f"❌ Debate end error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="debate_stats", description="View your debate statistics")
@app_commands.describe(user="User to view stats for (defaults to yourself)")
async def debate_stats(interaction: discord.Interaction, user: discord.Member = None):
    """View debate statistics for a user"""
    await interaction.response.defer()

    try:
        target_user = user if user else interaction.user
        stats = await debate_scorekeeper.get_debate_stats(target_user.id)

        if not stats:
            await interaction.followup.send(
                f"📊 {target_user.display_name} hasn't participated in any debates yet!"
            )
            return

        embed = discord.Embed(
            title=f"⚔️ Debate Stats: {target_user.display_name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)

        embed.add_field(
            name="📊 Record",
            value=f"**{stats['wins']}W - {stats['losses']}L**\nWin Rate: {stats['win_rate']}%",
            inline=True
        )

        if stats['avg_score']:
            embed.add_field(
                name="⭐ Average Score",
                value=f"**{stats['avg_score']}/10**",
                inline=True
            )

        embed.add_field(
            name="💬 Total Debates",
            value=f"**{stats['total_debates']}**",
            inline=True
        )

        if stats['favorite_topic']:
            embed.add_field(
                name="🎯 Favorite Topic",
                value=stats['favorite_topic'][:100],
                inline=False
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error getting stats: {str(e)}")
        print(f"❌ Debate stats error: {e}")

@bot.tree.command(name="debate_leaderboard", description="Top debaters leaderboard")
async def debate_leaderboard(interaction: discord.Interaction):
    """Show debate leaderboard"""
    await interaction.response.defer()

    try:
        leaderboard = await debate_scorekeeper.get_leaderboard(interaction.guild.id)

        if not leaderboard:
            await interaction.followup.send("📊 No debate data yet! Start a debate with `/debate_start`")
            return

        embed = discord.Embed(
            title="🏆 Debate Leaderboard",
            description="Top debaters by wins and average score",
            color=discord.Color.gold()
        )

        for i, entry in enumerate(leaderboard[:10], 1):
            medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f'{i}.')
            value = f"**{entry['wins']}W** ({entry['win_rate']}%) • Avg: {entry['avg_score']}/10 • {entry['total_debates']} debates"
            embed.add_field(
                name=f"{medal} {entry['username']}",
                value=value,
                inline=False
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error getting leaderboard: {str(e)}")
        print(f"❌ Debate leaderboard error: {e}")

@bot.tree.command(name="debate_review", description="Analyze a debate from uploaded text file")
@app_commands.describe(
    file="Text file containing the debate transcript (format: 'Username: message')",
    topic="Optional topic/title for the debate"
)
async def debate_review(interaction: discord.Interaction, file: discord.Attachment, topic: str = None):
    """Analyze debate from uploaded text file"""
    await interaction.response.defer()

    try:
        # Validate file type
        if not file.filename.endswith(('.txt', '.log', '.md')):
            await interaction.followup.send(
                "❌ **Invalid file type**\n\n"
                "Please upload a text file (.txt, .log, or .md)\n\n"
                "**Expected format:**\n"
                "```\n"
                "Username1: First argument here\n"
                "Username2: Counter argument\n"
                "Username1: Response to counter\n"
                "...\n"
                "```"
            )
            return

        # Check file size (max 1MB)
        if file.size > 1024 * 1024:
            await interaction.followup.send("❌ File too large. Maximum size is 1MB.")
            return

        # Download and read file content
        transcript_bytes = await file.read()
        try:
            transcript_text = transcript_bytes.decode('utf-8')
        except UnicodeDecodeError:
            await interaction.followup.send("❌ File must be UTF-8 encoded text.")
            return

        # Use filename as topic if not provided
        if not topic:
            topic = file.filename.rsplit('.', 1)[0]  # Remove extension

        # Analyze the debate
        result = await debate_scorekeeper.analyze_uploaded_debate(transcript_text, topic)

        # Handle errors
        if 'error' in result:
            error_messages = {
                'insufficient_participants': result['message'],
                'insufficient_messages': result['message'],
                'analysis_failed': f"Analysis failed: {result['message']}"
            }
            error_msg = error_messages.get(result['error'], f"Error: {result.get('message', 'Unknown error')}")
            await interaction.followup.send(f"❌ {error_msg}")
            return

        # Format successful analysis
        analysis = result['analysis']

        # Check if analysis failed
        if 'error' in analysis:
            error_msg = analysis.get('raw_analysis', analysis.get('message', 'Unknown error'))
            # Truncate to fit Discord's 2000 char limit (with room for formatting)
            if len(error_msg) > 1800:
                error_msg = error_msg[:1800] + "...\n(truncated)"

            await interaction.followup.send(
                f"❌ **Analysis Error**\n\n"
                f"The LLM analysis encountered an issue:\n"
                f"```\n{error_msg}\n```"
            )
            return

        # Build embed with results
        embed = discord.Embed(
            title=f"🎭 Comprehensive Debate Analysis: {result['topic']}",
            description=analysis.get('summary', 'Analysis complete'),
            color=discord.Color.purple()
        )

        # Add participant scores
        if 'participants' in analysis:
            for username, data in analysis['participants'].items():
                overall_score = data.get('overall_score', data.get('score', 'N/A'))

                field_value = f"**Overall: {overall_score}/10**\n\n"

                # Rhetorical scores
                logos = data.get('logos', {})
                ethos = data.get('ethos', {})
                pathos = data.get('pathos', {})
                factual = data.get('factual_accuracy', {})

                # Show scores with indicators
                logos_score = logos.get('score', 'N/A') if isinstance(logos, dict) else 'N/A'
                ethos_score = ethos.get('score', 'N/A') if isinstance(ethos, dict) else 'N/A'
                pathos_score = pathos.get('score', 'N/A') if isinstance(pathos, dict) else 'N/A'
                factual_score = factual.get('score', 'N/A') if isinstance(factual, dict) else 'N/A'

                field_value += f"**📊 Scores:**\n"
                field_value += f"🧠 Logos (Logic): {logos_score}/10\n"
                field_value += f"🎯 Ethos (Credibility): {ethos_score}/10\n"
                field_value += f"❤️ Pathos (Emotion): {pathos_score}/10\n"
                field_value += f"✅ Factual Accuracy: {factual_score}/10\n\n"

                # Logos details (fallacies)
                if isinstance(logos, dict) and logos.get('fallacies'):
                    fallacies = logos['fallacies']
                    if fallacies and len(fallacies) > 0:
                        field_value += f"**🚫 Logical Fallacies:**\n"
                        for fallacy in fallacies[:2]:
                            field_value += f"• {fallacy}\n"
                        if len(fallacies) > 2:
                            field_value += f"• _(+{len(fallacies) - 2} more)_\n"
                        field_value += "\n"

                # Factual accuracy details
                if isinstance(factual, dict):
                    correct = factual.get('correct_points', [])
                    errors = factual.get('major_errors', [])

                    if correct and len(correct) > 0:
                        field_value += f"**✅ Key Facts Right:**\n"
                        for point in correct[:2]:
                            field_value += f"• {point[:60]}...\n" if len(point) > 60 else f"• {point}\n"

                    if errors and len(errors) > 0:
                        field_value += f"\n**❌ Key Errors:**\n"
                        for error in errors[:2]:
                            field_value += f"• {error[:60]}...\n" if len(error) > 60 else f"• {error}\n"

                embed.add_field(
                    name=f"👤 {username}",
                    value=field_value[:1024],  # Discord field value limit
                    inline=False
                )

        # Add winner
        winner = analysis.get('winner', 'N/A')
        winner_reason = analysis.get('winner_reason', 'N/A')
        embed.add_field(
            name="🏆 Winner",
            value=f"**{winner}**\n{winner_reason}",
            inline=False
        )

        # Add metadata
        embed.set_footer(text=f"{result['participant_count']} participants • {result['message_count']} messages")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error analyzing debate: {str(e)}")
        print(f"❌ Debate review error: {e}")
        import traceback
        traceback.print_exc()

# ===== iRacing Integration =====
@bot.tree.command(name="iracing_link", description="Link your Discord account to your iRacing account")
@app_commands.describe(iracing_id_or_name="Your iRacing Customer ID (numeric) or display name")
async def iracing_link(interaction: discord.Interaction, iracing_id_or_name: str):
    """Link Discord account to iRacing"""
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        cust_id = None
        display_name = None

        # Check if input is a customer ID (all digits)
        if iracing_id_or_name.strip().isdigit():
            cust_id = int(iracing_id_or_name.strip())

            # Get profile to verify customer ID and get display name
            profile = await iracing.get_driver_profile(cust_id)

            if profile:
                # Try to extract display name from profile
                # The structure may vary, try different locations
                if isinstance(profile, dict):
                    display_name = (
                        profile.get('display_name') or
                        profile.get('name') or
                        profile.get('member_info', {}).get('display_name') or
                        f"Driver {cust_id}"
                    )
                    # Log what we extracted for debugging
                    print(f"🔍 Link: Extracted display_name='{display_name}' from profile for cust_id={cust_id}")
                    print(f"   profile.get('display_name')='{profile.get('display_name')}'")
                    print(f"   profile.get('name')='{profile.get('name')}'")
                else:
                    display_name = f"Driver {cust_id}"
                    print(f"⚠️ Link: Profile is not a dict, using fallback: {display_name}")
            else:
                await interaction.followup.send(
                    f"❌ Could not find iRacing profile for customer ID {cust_id}\n"
                    f"Make sure the ID is correct."
                )
                return
        else:
            # Search by name
            results = await iracing.search_driver(iracing_id_or_name)

            if not results or len(results) == 0:
                await interaction.followup.send(
                    f"❌ No iRacing driver found with name '{iracing_id_or_name}'\n"
                    f"💡 **Tip**: Try using your iRacing Customer ID instead (just the numbers)\n"
                    f"Find it at: https://members.iracing.com/membersite/member/Home.do"
                )
                return

            # Take first result (exact match preferred)
            driver = results[0]
            cust_id = driver.get('cust_id')
            display_name = driver.get('display_name', iracing_id_or_name)

        # Link the account
        success = await iracing.link_discord_to_iracing(
            interaction.user.id,
            cust_id,
            display_name
        )

        if success:
            await interaction.followup.send(
                f"✅ Linked your Discord account to iRacing driver **{display_name}**\n"
                f"You can now use `/iracing_profile` without specifying a name!"
            )
        else:
            await interaction.followup.send("❌ Failed to link accounts")

    except Exception as e:
        await interaction.followup.send(f"❌ Error linking account: {str(e)}")
        print(f"❌ iRacing link error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="iracing_profile", description="View iRacing driver profile and stats")
@app_commands.describe(driver_name="Driver display name, real name, or customer ID (optional if linked)")
async def iracing_profile(interaction: discord.Interaction, driver_name: str = None):
    """View iRacing driver profile"""
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        cust_id = None
        display_name = driver_name

        # If no driver name provided, check for linked account
        if not driver_name:
            linked = await iracing.get_linked_iracing_id(interaction.user.id)
            if linked:
                cust_id, display_name = linked
            else:
                await interaction.followup.send(
                    "❌ No driver name provided and no linked account found.\n"
                    "Use `/iracing_link` to link your account or provide a driver name."
                )
                return
        else:
            # Search for driver
            results = await iracing.search_driver(driver_name)
            if not results or len(results) == 0:
                await interaction.followup.send(
                    f"❌ No driver found with name '{driver_name}'\n"
                    f"💡 Tip: Try the driver's customer ID for reliable results"
                )
                return
            cust_id = results[0].get('cust_id')
            display_name = results[0].get('display_name', driver_name)

        # Get profile data
        profile = await iracing.get_driver_profile(cust_id)

        if not profile:
            await interaction.followup.send("❌ Failed to retrieve profile data")
            return

        # Extract actual display name from profile (not customer ID, not first/last name)
        # Prioritize fresh API data over cached database value
        fresh_display_name = (
            profile.get('display_name') or
            profile.get('name') or
            display_name or
            f"Driver {cust_id}"
        )

        # Update display_name for use in visualizations and embeds
        display_name = fresh_display_name

        # Update database if user has linked account and name differs
        if display_name and display_name != f"Driver {cust_id}":
            # Attempt to update linked account with fresh display name
            try:
                await iracing.link_discord_to_iracing(interaction.user.id, cust_id, display_name)
            except:
                pass  # Not critical if update fails

        if not iracing_viz:
            # Fallback to simple embed if visualizer failed to load
            embed = discord.Embed(
                title=f"🏁 {display_name}",
                description=f"Member since {profile.get('member_since', 'Unknown')}",
                color=discord.Color.blue()
            )

            licenses = profile.get('licenses', {})
            for key, name in [('oval', '🏁 Oval'), ('sports_car', '🏎️ Road')]:
                if key in licenses:
                    lic = licenses[key]
                    irating = lic.get('irating', 0)
                    sr = lic.get('safety_rating', 0.0)
                    embed.add_field(name=name, value=f"iR: {irating}\nSR: {sr:.2f}", inline=True)

            await interaction.followup.send(embed=embed)
            return

        # Get licenses data
        licenses = profile.get('licenses', {})

        if not licenses:
            await interaction.followup.send("❌ No license data found")
            return

        # Generate professional license overview showing all 5 categories
        image_buffer = iracing_viz.create_driver_license_overview(display_name, licenses)

        # Send as Discord file attachment
        file = discord.File(fp=image_buffer, filename="licenses.png")

        # Also fetch and display career stats
        career_stats = await iracing.get_driver_career_stats(cust_id)

        embed = discord.Embed(
            title=f"🏁 {display_name}",
            description=f"Member since {profile.get('member_since', 'Unknown')}",
            color=discord.Color.blue()
        )

        if career_stats:
            # Add career stats summary
            stats = career_stats.get('stats', [])
            if stats:
                total_starts = sum(s.get('starts', 0) for s in stats)
                total_wins = sum(s.get('wins', 0) for s in stats)
                total_podiums = sum(s.get('top3', 0) for s in stats)
                total_poles = sum(s.get('poles', 0) for s in stats)

                embed.add_field(name="Career Stats",
                              value=f"**Starts:** {total_starts}\n**Wins:** {total_wins}\n**Podiums:** {total_podiums}\n**Poles:** {total_poles}",
                              inline=True)

        await interaction.followup.send(embed=embed, file=file)

    except Exception as e:
        await interaction.followup.send(f"❌ Error getting profile: {str(e)}")
        print(f"❌ iRacing profile error: {e}")
        import traceback
        traceback.print_exc()

# Cache for series autocomplete to prevent repeated API calls
_series_autocomplete_cache = None
_series_cache_time = None

async def series_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete function for series names"""
    global _series_autocomplete_cache, _series_cache_time

    if not iracing:
        print("⚠️ Series autocomplete: iRacing integration not available")
        return []

    try:
        import asyncio
        import time

        # Use cached data if less than 5 minutes old
        current_time = time.time()
        if _series_autocomplete_cache and _series_cache_time and (current_time - _series_cache_time) < 300:
            all_series = _series_autocomplete_cache
            print(f"✅ Series autocomplete: Using cached data ({len(all_series)} series)")
        else:
            # Get all series with increased timeout (API can take 10+ seconds)
            all_series = await asyncio.wait_for(iracing.get_current_series(), timeout=15.0)

            if not all_series:
                print(f"⚠️ Series autocomplete: No series data returned")
                # Use old cache if available
                if _series_autocomplete_cache:
                    all_series = _series_autocomplete_cache
                    print(f"⚠️ Using stale cache as fallback")
                else:
                    return []
            else:
                # Update cache
                _series_autocomplete_cache = all_series
                _series_cache_time = current_time
                print(f"✅ Series autocomplete: Loaded {len(all_series)} series (cache updated)")

        # Filter by current input
        current_lower = current.lower()

        # If no input yet, return top 25 series
        if not current_lower:
            matches = all_series[:25]
        else:
            matches = [
                s for s in all_series
                if current_lower in s.get('series_name', '').lower()
            ]

        # Return up to 25 choices (Discord limit)
        choices = [
            app_commands.Choice(
                name=s.get('series_name', 'Unknown')[:100],  # Discord limit is 100 chars
                value=s.get('series_name', 'Unknown')[:100]
            )
            for s in matches[:25]
        ]

        print(f"✅ Series autocomplete: Returning {len(choices)} choices for '{current}'")
        return choices

    except asyncio.TimeoutError:
        print(f"⚠️ Series autocomplete: Timeout fetching series data")
        # Use cached data if available
        if _series_autocomplete_cache:
            print(f"⚠️ Using cached data as timeout fallback ({len(_series_autocomplete_cache)} series)")
            all_series = _series_autocomplete_cache

            # Filter by current input
            current_lower = current.lower()
            if not current_lower:
                matches = all_series[:25]
            else:
                matches = [s for s in all_series if current_lower in s.get('series_name', '').lower()]

            return [
                app_commands.Choice(
                    name=s.get('series_name', 'Unknown')[:100],
                    value=s.get('series_name', 'Unknown')[:100]
                )
                for s in matches[:25]
            ]
        return []
    except Exception as e:
        print(f"❌ Series autocomplete error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []

@bot.tree.command(name="iracing_schedule", description="View iRacing race schedule for a series or category")
@app_commands.describe(
    series="Series name (leave blank if using category)",
    category="Show all series in this category for current week",
    week="Which week to show (current = this week, upcoming = next week, full = entire season)"
)
@app_commands.choices(
    category=[
        app_commands.Choice(name="Oval", value="oval"),
        app_commands.Choice(name="Sports Car", value="sports_car"),
        app_commands.Choice(name="Formula Car", value="formula_car"),
        app_commands.Choice(name="Dirt Oval", value="dirt_oval"),
        app_commands.Choice(name="Dirt Road", value="dirt_road")
    ],
    week=[
        app_commands.Choice(name="Current Week", value="current"),
        app_commands.Choice(name="Upcoming Week", value="upcoming"),
        app_commands.Choice(name="Full Season", value="full")
    ]
)
@app_commands.autocomplete(series=series_autocomplete)
async def iracing_schedule(interaction: discord.Interaction, series: str = None, category: str = None, week: str = "full"):
    """View series race schedule or category overview"""
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        # Get all series
        all_series = await iracing.get_current_series()
        if not all_series:
            await interaction.followup.send("❌ Failed to retrieve series data")
            return

        # Handle series-based schedule (takes priority if both series and category are provided)
        if series:
            # Find matching series (use partial match like meta command)
            series_match = None
            for s in all_series:
                if series.lower() in s.get('series_name', '').lower():
                    series_match = s
                    break

            if not series_match:
                await interaction.followup.send(f"❌ Series not found: '{series}'")
                return

            series_id = series_match.get('series_id')
            series_name = series_match.get('series_name')
            season_id = series_match.get('season_id')

            print(f"🔍 Schedule request: series_id={series_id}, season_id={season_id}, series_name={series_name}")

            # Get schedule for this series
            schedule = await iracing.get_series_schedule(series_id, season_id)

            print(f"📅 Schedule API returned {len(schedule) if schedule else 0} entries")

            if not schedule or len(schedule) == 0:
                await interaction.followup.send(f"❌ No schedule found for {series_name}")
                return

            # Create visualization
            image_buffer = iracing_viz.create_schedule_table(series_name, schedule, week)

            # Send image
            file = discord.File(fp=image_buffer, filename="schedule.png")
            await interaction.followup.send(file=file)

        # Handle category-based schedule
        elif category:
            # Filter series by category (category_id is a string, not a number)
            category_series = [s for s in all_series if s.get('category_id') == category]

            print(f"🔍 Looking for category_id='{category}', found {len(category_series)} series (before dedup)")

            # Deduplicate by series_id - keep only one season per series (prefer active=True)
            series_dict = {}
            for s in category_series:
                series_id = s.get('series_id')
                # If we haven't seen this series, or this one is active, use it
                if series_id not in series_dict or s.get('active'):
                    series_dict[series_id] = s

            category_series = list(series_dict.values())
            print(f"🔍 After deduplication: {len(category_series)} unique series")

            if not category_series:
                await interaction.followup.send(f"❌ No series found for category: {category}")
                return

            # Get current week track for each series (using cached data from get_current_series)
            series_tracks = []

            # Get all seasons data once (this contains schedules already)
            client = await iracing._get_client()
            all_seasons = await client.get_series_seasons()

            # Build a map of season_id -> season data for fast lookup
            seasons_map = {season.get('season_id'): season for season in all_seasons}

            for s in category_series:
                series_name = s.get('series_name')
                season_id = s.get('season_id')

                # Get the full season data with schedules
                season_data = seasons_map.get(season_id)
                if not season_data:
                    continue

                schedules = season_data.get('schedules', [])
                if not schedules:
                    continue

                # Calculate current week based on dates
                now = datetime.now(timezone.utc)
                current_week_num = 0

                # Debug: check first schedule entry
                if schedules and series_name == category_series[0].get('series_name'):
                    first_week = schedules[0]
                    print(f"🔍 First schedule entry keys for {series_name}: {list(first_week.keys())}")
                    print(f"🔍 First week start_date: {first_week.get('start_date')}")
                    print(f"🔍 First week race_week_num: {first_week.get('race_week_num')}")
                    print(f"🔍 Total schedules: {len(schedules)}")
                    print(f"🔍 Current time: {now}")

                for week_data in schedules:
                    start_date = week_data.get('start_date')
                    if start_date:
                        try:
                            # Parse date string (format: "2025-10-28") and make it timezone-aware
                            week_start = datetime.fromisoformat(start_date)
                            # Make it timezone-aware (UTC)
                            week_start = week_start.replace(tzinfo=timezone.utc)
                            week_end = week_start + timedelta(days=7)

                            if week_start <= now < week_end:
                                current_week_num = week_data.get('race_week_num', 0)
                                print(f"✅ Found current week {current_week_num} for {series_name} (dates: {week_start.date()} to {week_end.date()})")
                                break
                        except Exception as e:
                            print(f"⚠️ Error parsing date {start_date}: {e}")
                            pass

                if current_week_num == 0 and series_name == category_series[0].get('series_name'):
                    print(f"⚠️ No current week found for {series_name}, defaulting to 0")

                # Find the current week's track
                for week_data in schedules:
                    if week_data.get('race_week_num') == current_week_num:
                        track = week_data.get('track', {})
                        track_name = track.get('track_name', 'Unknown') if isinstance(track, dict) else 'Unknown'
                        config_name = track.get('config_name', '') if isinstance(track, dict) else ''

                        if config_name and config_name not in track_name:
                            full_track_name = f"{track_name} - {config_name}"
                        else:
                            full_track_name = track_name

                        series_tracks.append({
                            'series_name': series_name,
                            'track_name': full_track_name,
                            'week_num': current_week_num + 1
                        })
                        break

            if not series_tracks:
                await interaction.followup.send(f"❌ No schedule data found for {category} series")
                return

            # Create category schedule visualization
            category_display_name = category.replace('_', ' ').title()
            image_buffer = iracing_viz.create_category_schedule_table(category_display_name, series_tracks)

            file = discord.File(fp=image_buffer, filename="category_schedule.png")
            await interaction.followup.send(file=file)

        else:
            await interaction.followup.send("❌ Please specify either a series name or a category")

    except Exception as e:
        await interaction.followup.send(f"❌ Error getting schedule: {str(e)}")
        print(f"❌ iRacing schedule error: {e}")
        import traceback
        traceback.print_exc()

async def week_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete function for week numbers with track names"""
    if not iracing:
        return [app_commands.Choice(name=f"Week {w}", value=w) for w in range(0, 13)]

    try:
        # Get namespace to access series parameter
        namespace = interaction.namespace
        series_name = getattr(namespace, 'series', None)

        if series_name:
            # Try to get actual week schedules for the series
            import asyncio
            client = await asyncio.wait_for(iracing._get_client(), timeout=2.0)
            if client:
                series_seasons = await client.get_series_seasons()

                # Find matching series
                for season in series_seasons:
                    schedules = season.get('schedules', [])
                    if not schedules:
                        continue

                    # Check if this season matches the selected series
                    first_schedule = schedules[0]
                    if series_name.lower() in first_schedule.get('series_name', '').lower():
                        # Build week choices with track names
                        week_choices = []

                        for week_schedule in schedules[:13]:  # Max 13 weeks
                            week_num = week_schedule.get('race_week_num')
                            track = week_schedule.get('track', {})
                            track_name = track.get('track_name', '')
                            track_config = track.get('config_name', '')

                            # Format: "Week 0: Daytona" or "Week 1: Spa - Grand Prix"
                            if track_config and track_config not in track_name:
                                name = f"Week {week_num}: {track_name} - {track_config}"
                            else:
                                name = f"Week {week_num}: {track_name}"

                            # Truncate if too long (Discord limit is 100 chars)
                            if len(name) > 100:
                                name = name[:97] + "..."

                            week_choices.append(app_commands.Choice(name=name, value=week_num))

                        if week_choices:
                            # Filter by current input
                            if current:
                                try:
                                    current_int = int(current)
                                    week_choices = [w for w in week_choices if w.value == current_int or str(current_int) in str(w.value)]
                                except ValueError:
                                    # Search by track name
                                    week_choices = [w for w in week_choices if current.lower() in w.name.lower()]

                            return week_choices[:25]

                        break

    except Exception as e:
        print(f"⚠️ Week autocomplete error: {e}")

    # Fallback to simple week numbers
    weeks = list(range(0, 13))
    if current:
        try:
            current_int = int(current)
            weeks = [w for w in weeks if str(w).startswith(str(current_int))]
        except ValueError:
            pass

    return [
        app_commands.Choice(name=f"Week {w}", value=w)
        for w in weeks[:25]
    ]

def season_id_to_year_quarter(season_id: int) -> str:
    """
    Convert iRacing season ID to year and quarter format.
    iRacing runs 4 seasons per year (quarters).

    Args:
        season_id: iRacing season ID

    Returns:
        String like "2025 S1" or "2024 S4"
    """
    # Reference point: Season 5513 = 2025 Season 1 (updated from actual API data)
    # Each season is +1, 4 seasons per year
    reference_season = 5513
    reference_year = 2025
    reference_quarter = 1

    # Calculate offset from reference (negative = past, positive = future)
    offset = season_id - reference_season

    # Calculate total quarters from reference point
    total_quarters = reference_quarter + offset

    # Calculate year and quarter
    # If offset is negative, we go backwards in time
    years_offset = 0
    quarter = total_quarters

    while quarter <= 0:
        years_offset -= 1
        quarter += 4

    while quarter > 4:
        years_offset += 1
        quarter -= 4

    year = reference_year + years_offset

    return f"{year} S{quarter}"

def season_string_to_id(season_str: str) -> int:
    """
    Convert a human-friendly season label (e.g., "2025 S1") into the numeric season_id.

    Accepts forms like "2025 S1", "2025 season 1", or the raw numeric id.
    """
    if not season_str:
        raise ValueError("Season string cannot be empty")

    normalized = season_str.strip().upper()

    if normalized.isdigit():
        return int(normalized)

    normalized = normalized.replace("SEASON", "S")
    normalized = re.sub(r"\s+", "", normalized)

    match = re.match(r"^(\d{4})S([1-4])$", normalized)
    if not match:
        raise ValueError(f"Invalid season format '{season_str}'. Use values like '2025 S1'.")

    year = int(match.group(1))
    quarter = int(match.group(2))

    reference_season = 5513  # 2025 Season 1
    reference_year = 2025
    reference_quarter = 1

    years_offset = year - reference_year
    quarters_offset = quarter - reference_quarter
    total_offset = years_offset * 4 + quarters_offset

    return reference_season + total_offset

async def season_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[int]]:
    """Autocomplete function for season numbers with year/quarter"""
    if not iracing:
        return []

    try:
        # Get namespace to access other parameters
        namespace = interaction.namespace
        series_name = getattr(namespace, 'series', None)

        season_choices = []

        print(f"🔍 Season autocomplete called with series='{series_name}', current='{current}'")

        if series_name:
            # Try to get seasons for the specific series
            import asyncio
            try:
                client = await asyncio.wait_for(iracing._get_client(), timeout=5.0)
                if client:
                    seasons_data = await asyncio.wait_for(client.get_series_seasons(), timeout=10.0)

                # Find matching series and extract unique season info
                seen_seasons = set()
                for season in seasons_data:
                    season_id = season.get('season_id')
                    if season_id in seen_seasons:
                        continue

                    schedules = season.get('schedules', [])
                    for schedule in schedules:
                        if series_name.lower() in schedule.get('series_name', '').lower():
                            seen_seasons.add(season_id)

                            # Format: "2025 S1 (Active)" or "2024 S4"
                            year_quarter = season_id_to_year_quarter(season_id)
                            is_active = season.get('active', False)
                            name = f"{year_quarter}{' (Active)' if is_active else ''}"

                            season_choices.append(app_commands.Choice(name=name, value=season_id))
                            break

                    if season_choices:
                        # Sort by season ID descending (most recent first)
                        season_choices.sort(key=lambda x: x.value, reverse=True)

                        # Filter by current input
                        if current:
                            season_choices = [
                                s for s in season_choices
                                if current.lower() in s.name.lower() or current in str(s.value)
                            ]

                        print(f"✅ Season autocomplete returning {len(season_choices)} choices")
                        return season_choices[:25]
            except Exception as e:
                print(f"⚠️ Season autocomplete error: {e}")

        # Fallback: provide recent season IDs with year/quarter
        # Current season around 5516 (2025 S4), go back 20 seasons (5 years)
        base = 5516
        for season_id in range(base, base - 20, -1):
            year_quarter = season_id_to_year_quarter(season_id)
            is_current = (season_id == base)
            name = f"{year_quarter}{' (Current)' if is_current else ''}"
            season_choices.append(app_commands.Choice(name=name, value=season_id))

        # Filter by current input if provided
        if current:
            season_choices = [
                s for s in season_choices
                if current.lower() in s.name.lower() or current in str(s.value)
            ]

        return season_choices[:25]

    except Exception as e:
        print(f"❌ Season autocomplete error: {e}")
        # Fallback to basic season list with year/quarter
        base = 5760
        season_choices = []
        for season_id in range(base, base - 12, -1):  # 3 years worth
            year_quarter = season_id_to_year_quarter(season_id)
            season_choices.append(app_commands.Choice(name=year_quarter, value=season_id))

        return season_choices[:10]

async def season_label_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """
    Wrapper around season_autocomplete that returns string labels (e.g., '2025 S1').
    Useful for commands that accept the human-readable label instead of the raw ID.
    """
    base_choices = await season_autocomplete(interaction, current)

    label_choices: list[app_commands.Choice[str]] = []
    seen_labels: set[str] = set()

    for choice in base_choices:
        season_id = choice.value
        try:
            label = season_id_to_year_quarter(season_id)
        except Exception:
            continue

        if label in seen_labels:
            continue

        label_choices.append(app_commands.Choice(name=choice.name, value=label))
        seen_labels.add(label)

    return label_choices[:25]

async def track_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete function for track names"""
    if not iracing:
        return []

    try:
        # Get namespace to access series parameter
        namespace = interaction.namespace
        series_name = getattr(namespace, 'series', None)

        if series_name:
            # Get tracks used in this series
            import asyncio
            client = await asyncio.wait_for(iracing._get_client(), timeout=2.0)
            if client:
                series_seasons = await client.get_series_seasons()

                # Find matching series and extract tracks
                track_set = set()
                track_choices = []

                for season in series_seasons:
                    schedules = season.get('schedules', [])
                    if not schedules:
                        continue

                    # Check if this season matches the selected series
                    first_schedule = schedules[0]
                    if series_name.lower() in first_schedule.get('series_name', '').lower():
                        # Extract all unique tracks from this series
                        for schedule in schedules:
                            track = schedule.get('track', {})
                            track_id = track.get('track_id')
                            track_name = track.get('track_name', '')
                            track_config = track.get('config_name', '')

                            if not track_id or track_id in track_set:
                                continue

                            track_set.add(track_id)

                            # Format: "Spa-Francorchamps - Grand Prix"
                            if track_config and track_config not in track_name:
                                display_name = f"{track_name} - {track_config}"
                            else:
                                display_name = track_name

                            # Truncate if needed
                            if len(display_name) > 100:
                                display_name = display_name[:97] + "..."

                            track_choices.append(app_commands.Choice(
                                name=display_name,
                                value=display_name[:100]
                            ))

                        if track_choices:
                            # Sort alphabetically
                            track_choices.sort(key=lambda x: x.name)

                            # Filter by current input
                            if current:
                                track_choices = [
                                    t for t in track_choices
                                    if current.lower() in t.name.lower()
                                ]

                            return track_choices[:25]
                        break

    except Exception as e:
        print(f"⚠️ Track autocomplete error: {e}")

    return []

async def category_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete function for license categories"""
    categories = [
        app_commands.Choice(name="Oval", value="oval"),
        app_commands.Choice(name="Sports Car (Road)", value="sports_car_road"),
        app_commands.Choice(name="Formula Car (Road)", value="formula_car_road"),
        app_commands.Choice(name="Dirt Oval", value="dirt_oval"),
        app_commands.Choice(name="Dirt Road", value="dirt_road")
    ]

    if not current:
        return categories

    # Filter based on user input
    current_lower = current.lower()
    return [c for c in categories if current_lower in c.name.lower() or current_lower in c.value.lower()][:25]

@bot.tree.command(name="iracing_meta", description="View meta analysis for an iRacing series")
@app_commands.describe(
    series="Series name to analyze",
    season="Season number (optional, defaults to current)",
    week="Week number (optional, defaults to current)",
    track="Track name (optional, analyzes all tracks if not specified)"
)
@app_commands.autocomplete(
    series=series_autocomplete,
    week=week_autocomplete,
    season=season_autocomplete,
    track=track_autocomplete
)
async def iracing_meta(interaction: discord.Interaction, series: str, season: int = None, week: int = None, track: str = None):
    """View meta chart showing best cars for a series"""
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    # Send initial response immediately
    await interaction.response.send_message("🔄 Analyzing race data... This may take up to 60 seconds for detailed performance statistics.")

    try:
        # Get meta chart data with performance analysis
        # This call will now wait for the full analysis to complete
        meta_data = await iracing.get_meta_chart_data(series, season_id=season, week_num=week, track_name=track, force_analysis=True)

        if not meta_data:
            await interaction.edit_original_response(content=f"❌ Could not find series '{series}' or no data available")
            return

        series_name = meta_data.get('series_name', series)
        series_id = meta_data.get('series_id')
        car_data = meta_data.get('cars', [])
        track_name_result = meta_data.get('track_name')
        track_config = meta_data.get('track_config')
        week_num = meta_data.get('week', week or 'Current')
        season_analyzed = meta_data.get('season_analyzed')
        has_performance_data = meta_data.get('has_performance_data', False)

        # If no cars found after analysis, show error
        if not car_data:
            await interaction.edit_original_response(content=f"❌ No race data available for {series_name}. No recent races found to analyze.")
            return

        # Always create a professional chart if we have car data
        if has_performance_data and any(car.get('avg_lap_time') for car in car_data):
            # Use iRacing visualizer to create meta chart
            from iracing_viz import iRacingVisualizer
            viz = iRacingVisualizer()

            # Prepare track name for display
            display_track = track_name_result or "All Tracks"
            if track_name_result and track_config and track_config not in track_name_result:
                display_track = f"{track_name_result} - {track_config}"

            # Get total races analyzed
            total_races = meta_data.get('total_races_analyzed', 0)

            # Calculate total unique drivers across all cars
            # Just sum up the unique drivers per car (they're already counted)
            unique_drivers_count = sum(car.get('unique_drivers', 0) for car in car_data)

            # Get weather data if available
            weather_data = meta_data.get('weather', {})

            # Create the meta chart
            chart_image = await viz.create_meta_chart(
                series_name=series_name,
                track_name=display_track,
                week_num=week_num,
                car_data=car_data,
                total_races=total_races,
                unique_drivers=unique_drivers_count,
                weather_data=weather_data
            )

            # Send as file attachment
            file = discord.File(fp=chart_image, filename=f"meta_{series_name.replace(' ', '_')}_week{week_num}.png")

            # Create minimal embed with just the image
            chart_embed = discord.Embed(
                title=f"{series_name} - Meta Analysis",
                color=discord.Color.blue()
            )

            chart_embed.set_image(url=f"attachment://meta_{series_name.replace(' ', '_')}_week{week_num}.png")

            # Replace the loading message with the chart
            await interaction.edit_original_response(content=None, embed=chart_embed, attachments=[file])
        else:
            # If still no performance data after waiting, show what cars are available
            embed = discord.Embed(
                title=f"🏎️ {series_name}",
                description=f"Week {week_num} - No race data available yet for this track/series combination.\n\nShowing available cars:",
                color=discord.Color.orange()
            )

            if track_name_result:
                track_text = f"{track_name_result}"
                if track_config and track_config not in track_name_result:
                    track_text += f" - {track_config}"
                embed.add_field(name="📍 Track", value=track_text, inline=False)

            # Show car list
            car_list = []
            for idx, car in enumerate(car_data, 1):
                car_name = car.get('car_name', 'Unknown')
                car_list.append(f"{idx}. **{car_name}**")

            # Split into chunks
            chunk_size = 15
            for i in range(0, len(car_list), chunk_size):
                chunk = car_list[i:i+chunk_size]
                field_name = "🚗 Available Cars" if i == 0 else "🚗 Available Cars (cont.)"
                embed.add_field(name=field_name, value="\n".join(chunk), inline=False)

            embed.set_footer(text="No race results found for this series/track combination in recent seasons")

            await interaction.edit_original_response(content=None, embed=embed)

    except Exception as e:
        try:
            await interaction.edit_original_response(content=f"❌ Error getting meta data: {str(e)}")
        except:
            # If edit fails, try followup
            await interaction.followup.send(f"❌ Error getting meta data: {str(e)}")

        print(f"❌ iRacing meta error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="iracing_results", description="View recent iRacing race results for a driver")
@app_commands.describe(driver_name="Driver display name, real name, or customer ID (optional if linked)")
async def iracing_results(interaction: discord.Interaction, driver_name: str = None):
    """View driver's recent race results"""
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        cust_id = None
        display_name = driver_name

        # If no driver name provided, check for linked account
        if not driver_name:
            linked = await iracing.get_linked_iracing_id(interaction.user.id)
            if linked:
                cust_id, display_name = linked
            else:
                await interaction.followup.send(
                    "❌ No driver name provided and no linked account found.\n"
                    "Use `/iracing_link` to link your account or provide a driver name."
                )
                return
        else:
            # Search for driver
            results = await iracing.search_driver(driver_name)
            if not results or len(results) == 0:
                await interaction.followup.send(
                    f"❌ No driver found with name '{driver_name}'\n"
                    f"💡 Tip: Try the driver's customer ID for reliable results"
                )
                return
            cust_id = results[0].get('cust_id')
            display_name = results[0].get('display_name', driver_name)

        # Get recent races
        races = await iracing.get_driver_recent_races(cust_id, limit=10)

        if not races or len(races) == 0:
            await interaction.followup.send(f"❌ No recent races found for {display_name}")
            return

        # Look up track names for each race
        for race in races:
            # Track might be an object or a direct ID
            track_data = race.get('track')
            if isinstance(track_data, dict):
                # Track is an object with track_id and track_name
                track_id = track_data.get('track_id')
                track_name = track_data.get('track_name', 'Unknown Track')
                config_name = track_data.get('config_name', '')

                # Append config if it exists and isn't already in the name
                if config_name and config_name not in track_name:
                    track_name = f"{track_name} - {config_name}"

                race['track_name'] = track_name
            else:
                # Try to look up by track_id
                track_id = race.get('track_id')
                if track_id and (not race.get('track_name') or race.get('track_name') == 'Unknown Track'):
                    track_name = await iracing.get_track_name(track_id)
                    race['track_name'] = track_name

        # Generate visual table
        if not iracing_viz:
            # Fallback to simple embed if visualizer failed to load
            embed = discord.Embed(
                title=f"🏁 Recent Races - {display_name}",
                description=f"Last {len(races)} races",
                color=discord.Color.blue()
            )

            for i, race in enumerate(races):
                series_name = race.get('series_name', 'Unknown Series')
                track_name = race.get('track_name', 'Unknown Track')
                finish_pos = race.get('finish_position', 'N/A')
                start_pos = race.get('start_position', 'N/A')
                incidents = race.get('incidents', 'N/A')

                embed.add_field(
                    name=f"{i+1}. {series_name}",
                    value=f"**Track:** {track_name}\n**Finish:** P{finish_pos} (started P{start_pos})\n**Incidents:** {incidents}",
                    inline=False
                )

            await interaction.followup.send(embed=embed)
            return

        # Create visualization
        image_buffer = iracing_viz.create_recent_results_table(display_name, races)

        # Send as Discord file attachment
        file = discord.File(fp=image_buffer, filename="results.png")
        await interaction.followup.send(file=file)

    except Exception as e:
        await interaction.followup.send(f"❌ Error getting race results: {str(e)}")
        print(f"❌ iRacing results error: {e}")


@bot.tree.command(name="iracing_season_schedule", description="View full season schedule for an iRacing series")
@app_commands.describe(
    series_name="Series name",
    season="Season (e.g., '2025 S1', optional - uses current if not specified)"
)
@app_commands.autocomplete(
    series_name=series_autocomplete,
    season=season_label_autocomplete
)
async def iracing_season_schedule(interaction: discord.Interaction, series_name: str, season: str = None):
    """View complete season track rotation"""
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        # Get series info
        all_series = await iracing.get_current_series()
        if not all_series:
            await interaction.followup.send("❌ Failed to retrieve series data")
            return

        # Find matching series
        series_match = None
        for s in all_series:
            if series_name.lower() in s.get('series_name', '').lower():
                series_match = s
                break

        if not series_match:
            await interaction.followup.send(f"❌ Series not found: '{series_name}'")
            return

        series_id = series_match.get('series_id')
        series_full_name = series_match.get('series_name')

        # If season not specified, use current
        if season:
            try:
                season_id = season_string_to_id(season)
            except ValueError as err:
                await interaction.followup.send(f"❌ {err}")
                return
        else:
            season_id = series_match.get('season_id')

        # Get schedule
        schedule = await iracing.get_series_schedule(series_id, season_id)

        if not schedule or len(schedule) == 0:
            await interaction.followup.send(f"❌ No schedule found for {series_full_name}")
            return

        # Sort schedule by race week to ensure consistent visualization
        schedule_sorted = sorted(schedule, key=lambda entry: entry.get('race_week_num', 0))

        # Human-friendly season label
        season_label = season if season else None
        if not season_label:
            try:
                season_label = season_id_to_year_quarter(season_id)
            except Exception:
                season_label = "Current Season"

        # Gather date range for summary (if available)
        start_dates = []
        for week in schedule_sorted:
            start_date_raw = (
                week.get('start_date')
                or week.get('start_time')
                or week.get('start_date_time')
            )
            if start_date_raw:
                try:
                    dt = datetime.fromisoformat(str(start_date_raw).replace('Z', '+00:00'))
                    start_dates.append(dt)
                except Exception:
                    continue

        season_span = None
        if start_dates:
            season_span = f"{min(start_dates).strftime('%b %d, %Y')} - {max(start_dates).strftime('%b %d, %Y')}"

        if iracing_viz:
            try:
                image_buffer = iracing_viz.create_schedule_table(series_full_name, schedule_sorted, "full")

                safe_base = "".join(c if c.isalnum() else "_" for c in series_full_name.lower())
                filename = f"{safe_base or 'schedule'}_{season_id}_schedule.png"

                embed = discord.Embed(
                    title=f"📅 {series_full_name}",
                    description=f"{season_label} • {len(schedule_sorted)} weeks",
                    color=discord.Color.blue()
                )
                if season_span:
                    embed.add_field(name="Season Dates", value=season_span, inline=False)

                embed.set_footer(text="Generated by WompBot iRacing Visualizer")
                embed.set_image(url=f"attachment://{filename}")

                file = discord.File(fp=image_buffer, filename=filename)
                await interaction.followup.send(embed=embed, file=file)
                return
            except Exception as viz_error:
                print(f"⚠️ Failed to render season schedule visualization: {viz_error}")
                import traceback
                traceback.print_exc()
                # Fallback to text embed below

        # Fallback text-based embed when visualizer unavailable
        embed = discord.Embed(
            title=f"📅 {series_full_name}",
            description=f"{season_label} • {len(schedule_sorted)} weeks",
            color=discord.Color.blue()
        )

        display_limit = min(len(schedule_sorted), 12)

        for i, week in enumerate(schedule_sorted[:display_limit]):
            week_num = week.get('race_week_num', i)
            track_name = week.get('track_name', 'Unknown Track')
            layout = week.get('track_layout', '')

            if layout and layout != track_name:
                track_display = f"{track_name} - {layout}"
            else:
                track_display = track_name

            embed.add_field(
                name=f"Week {week_num + 1}",
                value=track_display,
                inline=True
            )

        if len(schedule_sorted) > display_limit:
            embed.set_footer(text=f"Showing first {display_limit} of {len(schedule_sorted)} weeks")

        await interaction.followup.send(embed=embed)

        if len(schedule_sorted) > display_limit:
            remaining_lines = []
            for i, week in enumerate(schedule_sorted[display_limit:], start=display_limit):
                week_num = week.get('race_week_num', i)
                track_name = week.get('track_name', 'Unknown Track')
                layout = week.get('track_layout', '')

                if layout and layout != track_name:
                    track_display = f"{track_name} - {layout}"
                else:
                    track_display = track_name

                remaining_lines.append(f"Week {week_num + 1}: {track_display}")

            if remaining_lines:
                chunks = []
                chunk = []
                total_chars = 0

                for line in remaining_lines:
                    if total_chars + len(line) + 1 > 1900:
                        chunks.append("\n".join(chunk))
                        chunk = [line]
                        total_chars = len(line)
                    else:
                        chunk.append(line)
                        total_chars += len(line) + 1

                if chunk:
                    chunks.append("\n".join(chunk))

                for text_chunk in chunks:
                    await interaction.followup.send(f"```\n{text_chunk}\n```")

    except Exception as e:
        await interaction.followup.send(f"❌ Error getting schedule: {str(e)}")
        print(f"❌ iRacing schedule error: {e}")
        import traceback
        traceback.print_exc()


@bot.tree.command(name="iracing_server_leaderboard", description="Show iRating leaderboard for this Discord server")
@app_commands.describe(category="License category (oval/sports_car_road/formula_car_road/dirt_oval/dirt_road)")
@app_commands.autocomplete(category=category_autocomplete)
async def iracing_server_leaderboard(interaction: discord.Interaction, category: str = "sports_car_road"):
    """Show server-wide iRating rankings"""
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        # Rate limiting for expensive server leaderboard
        iracing_leaderboard_cooldown = int(os.getenv('IRACING_LEADERBOARD_COOLDOWN', '60'))  # 60 seconds
        rate_check = db.check_feature_rate_limit(
            interaction.user.id,
            'iracing_leaderboard',
            cooldown_seconds=iracing_leaderboard_cooldown
        )

        if not rate_check['allowed']:
            wait_seconds = rate_check.get('wait_seconds', 60)
            await interaction.followup.send(
                f"⏱️ Leaderboard cooldown! Please wait {wait_seconds} seconds before requesting another leaderboard."
            )
            return

        # Get all linked accounts in this guild
        guild_member_ids = [member.id for member in interaction.guild.members]

        if len(guild_member_ids) == 0:
            await interaction.followup.send("❌ No members in this server")
            return

        # Get linked iRacing accounts
        leaderboard_data = []

        for discord_id in guild_member_ids:
            linked = await iracing.get_linked_iracing_id(discord_id)
            if linked:
                cust_id, display_name = linked

                # Get profile to fetch current iRating
                profile = await iracing.get_driver_profile(cust_id)
                if profile:
                    licenses = profile.get('licenses', {})

                    # Map category names
                    category_map = {
                        'oval': 'oval',
                        'road': 'sports_car',
                        'dirt_oval': 'dirt_oval',
                        'dirt_road': 'dirt_road',
                        'formula_car': 'formula_car',
                        'formula': 'formula_car'
                    }

                    license_key = category_map.get(category.lower(), 'sports_car')

                    if license_key in licenses:
                        lic = licenses[license_key]
                        irating = lic.get('irating', 0)
                        sr = lic.get('safety_rating', 0.0)

                        # Get Discord member
                        member = interaction.guild.get_member(discord_id)
                        discord_name = member.display_name if member else "Unknown"

                        leaderboard_data.append({
                            'discord_name': discord_name,
                            'iracing_name': display_name,
                            'irating': irating,
                            'safety_rating': sr,
                            'cust_id': cust_id
                        })

        if len(leaderboard_data) == 0:
            await interaction.followup.send("❌ No linked iRacing accounts found in this server.\nUse `/iracing_link` to link your account!")
            return

        # Sort by iRating
        leaderboard_data.sort(key=lambda x: x['irating'], reverse=True)

        # Create visualization
        category_display = category.replace('_', ' ').title()

        if not iracing_viz:
            # Fallback to embed if visualizer not available
            embed = discord.Embed(
                title=f"🏆 {interaction.guild.name} - {category_display} Leaderboard",
                description=f"{len(leaderboard_data)} linked drivers",
                color=discord.Color.gold()
            )

            for i, driver in enumerate(leaderboard_data[:10]):
                rank_emoji = ["🥇", "🥈", "🥉"][i] if i < 3 else f"**{i+1}.**"
                embed.add_field(
                    name=f"{rank_emoji} {driver['discord_name']}",
                    value=f"iR: {driver['irating']:,} | SR: {driver['safety_rating']:.2f}\n*{driver['iracing_name']}*",
                    inline=False
                )

            if len(leaderboard_data) > 10:
                embed.set_footer(text=f"Showing top 10 of {len(leaderboard_data)} drivers")

            await interaction.followup.send(embed=embed)
            db.record_feature_usage(interaction.user.id, 'iracing_leaderboard')
        else:
            # Use visualization
            image_buffer = iracing_viz.create_server_leaderboard_table(
                interaction.guild.name,
                category_display,
                leaderboard_data
            )

            file = discord.File(fp=image_buffer, filename="server_leaderboard.png")
            await interaction.followup.send(file=file)
            db.record_feature_usage(interaction.user.id, 'iracing_leaderboard')

    except Exception as e:
        await interaction.followup.send(f"❌ Error generating leaderboard: {str(e)}")
        print(f"❌ Server leaderboard error: {e}")
        import traceback
        traceback.print_exc()


IRACING_HISTORY_TIMEFRAMES = {
    "day": ("Last 24 Hours", timedelta(days=1)),
    "week": ("Last 7 Days", timedelta(days=7)),
    "month": ("Last 30 Days", timedelta(days=30)),
    "season": ("Last Season", timedelta(weeks=12)),
    "year": ("Last Year", timedelta(days=365)),
    "all": ("Recent History", None),
}

IRACING_HISTORY_CACHE_TTLS = {
    "day": 0.5,
    "week": 2,
    "month": 6,
    "season": 12,
    "year": 24,
    "all": 24,
}


@bot.tree.command(
    name="iracing_history",
    description="Analyze rating and safety trends across your recent races",
)
@app_commands.describe(
    driver_name="iRacing display name (optional if you've linked your account)",
    timeframe="Time range to analyze (default: Last 7 Days)",
)
@app_commands.choices(
    timeframe=[
        app_commands.Choice(name="Last 24 Hours", value="day"),
        app_commands.Choice(name="Last 7 Days", value="week"),
        app_commands.Choice(name="Last 30 Days", value="month"),
        app_commands.Choice(name="Last Season (~12 weeks)", value="season"),
        app_commands.Choice(name="Last Year", value="year"),
        app_commands.Choice(name="All Recent Races", value="all"),
    ]
)
async def iracing_history(
    interaction: discord.Interaction,
    driver_name: str = None,
    timeframe: Optional[app_commands.Choice[str]] = None,
):
    """Render a performance dashboard with iRating/Safety trends and key stats."""
    if not iracing or not iracing_viz:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        cust_id = None
        display_name = driver_name

        timeframe_key = timeframe.value if timeframe else "week"
        timeframe_label, delta = IRACING_HISTORY_TIMEFRAMES.get(
            timeframe_key, IRACING_HISTORY_TIMEFRAMES["week"]
        )

        # Resolve driver identity
        if not driver_name:
            linked = await iracing.get_linked_iracing_id(interaction.user.id)
            if linked:
                cust_id, display_name = linked
            else:
                await interaction.followup.send(
                    "❌ No driver name provided and no linked account found.\n"
                    "Use `/iracing_link` to link your account or provide a driver name."
                )
                return
        else:
            results = await iracing.search_driver(driver_name)
            if not results:
                await interaction.followup.send(
                    f"❌ No driver found with name '{driver_name}'\n"
                    f"💡 Tip: Try the driver's customer ID for reliable results"
                )
                return
            cust_id = results[0].get('cust_id')
            display_name = results[0].get('display_name', driver_name)

        cache_hit = False
        rating_points: List[Dict] = []
        summary_stats: Dict = {}

        cache_payload = db.get_iracing_history_cache(cust_id, timeframe_key) if db else None
        if cache_payload:
            try:
                rating_points = [
                    {
                        "date": datetime.fromisoformat(point["date"]),
                        "irating": point["irating"],
                        "safety_rating": point["safety_rating"],
                    }
                    for point in cache_payload.get("rating_points", [])
                ]

                summary_stats = cache_payload.get("summary_stats", {})
                summary_stats["series_counts"] = [
                    (entry["name"], entry["count"])
                    for entry in summary_stats.get("series_counts", [])
                ]
                summary_stats["car_counts"] = [
                    (entry["name"], entry["count"])
                    for entry in summary_stats.get("car_counts", [])
                ]

                if rating_points and summary_stats:
                    timeframe_label = cache_payload.get("timeframe_label", timeframe_label)
                    display_name = cache_payload.get("display_name", display_name)
                    cache_hit = True
                    print(f"📦 Using cached history for driver {cust_id} ({timeframe_key})")
            except Exception as cache_error:
                print(f"⚠️ Failed to deserialize history cache: {cache_error}")
                cache_hit = False

        if not cache_hit:
            races = await iracing.get_driver_recent_races(cust_id, limit=200)
            if not races:
                await interaction.followup.send(f"❌ No race history found for {display_name}")
                return

            now = datetime.now(timezone.utc)
            cutoff = now - delta if delta else None

            def parse_race_start(race: Dict) -> Optional[datetime]:
                for key in ("session_start_time", "start_time", "start_time_utc"):
                    raw = race.get(key)
                    if raw is None:
                        continue
                    if isinstance(raw, (int, float)):
                        return datetime.fromtimestamp(raw, tz=timezone.utc)
                    if isinstance(raw, str):
                        try:
                            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        except ValueError:
                            try:
                                dt = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                continue
                            dt = dt.replace(tzinfo=timezone.utc)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        else:
                            dt = dt.astimezone(timezone.utc)
                        return dt
                return None

            def to_int(value):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

            processed: List[Dict] = []
            for race in races:
                start_dt = parse_race_start(race)
                if start_dt is None:
                    continue
                if cutoff and start_dt < cutoff:
                    continue
                race_copy = dict(race)
                race_copy["_start_dt"] = start_dt
                processed.append(race_copy)

            if not processed:
                await interaction.followup.send(
                    f"❌ No races for {display_name} in the selected timeframe ({timeframe_label})."
                )
                return

            processed.sort(key=lambda r: r["_start_dt"])

            total_races = len(processed)
            finish_values = []
            incident_values = []
            ir_changes = []
            sr_changes = []
            series_counter: Counter[str] = Counter()
            car_counter: Counter[str] = Counter()
            rating_points = []

            baseline_added = False
            for race in processed:
                start_dt = race["_start_dt"]
                finish = to_int(race.get("finish_position"))
                if finish is not None:
                    finish_values.append(finish)
                incidents = to_int(race.get("incidents"))
                if incidents is not None:
                    incident_values.append(incidents)

                old_ir = to_int(race.get("oldi_rating"))
                new_ir = to_int(race.get("newi_rating"))
                old_sr_raw = to_int(race.get("old_sub_level"))
                new_sr_raw = to_int(race.get("new_sub_level"))

                if not baseline_added and old_ir is not None and old_sr_raw is not None:
                    rating_points.append({
                        "date": start_dt - timedelta(seconds=1),
                        "irating": old_ir,
                        "safety_rating": old_sr_raw / 100.0,
                    })
                    baseline_added = True

                if new_ir is not None and old_ir is not None:
                    ir_changes.append(new_ir - old_ir)
                if new_sr_raw is not None and old_sr_raw is not None:
                    sr_changes.append((new_sr_raw - old_sr_raw) / 100.0)

                sr_for_point = None
                if new_sr_raw is not None:
                    sr_for_point = new_sr_raw / 100.0
                elif old_sr_raw is not None:
                    sr_for_point = old_sr_raw / 100.0

                if new_ir is not None and sr_for_point is not None:
                    rating_points.append({
                        "date": start_dt,
                        "irating": new_ir,
                        "safety_rating": sr_for_point,
                    })
                elif new_ir is not None:
                    rating_points.append({
                        "date": start_dt,
                        "irating": new_ir,
                        "safety_rating": sr_for_point or 0.0,
                    })

                series_name = (race.get("series_name") or race.get("series") or "Unknown Series").strip()
                series_counter[series_name] += 1

                car_name = (
                    race.get("car_name")
                    or race.get("display_car_name")
                    or race.get("car")
                    or "Unknown Car"
                )
                car_counter[str(car_name).strip()] += 1

            if not rating_points:
                await interaction.followup.send(
                    f"❌ Not enough rating data available for {display_name} in {timeframe_label}."
                )
                return

            wins = sum(1 for value in finish_values if value == 1)
            podiums = sum(1 for value in finish_values if value is not None and value <= 3)
            avg_finish = sum(finish_values) / len(finish_values) if finish_values else 0
            avg_incidents = sum(incident_values) / len(incident_values) if incident_values else 0
            total_ir_change = sum(ir_changes)
            total_sr_change = sum(sr_changes)

            series_counts = series_counter.most_common(5)
            car_counts = car_counter.most_common(5)

            summary_stats = {
                "timeframe_label": timeframe_label,
                "total_races": total_races,
                "wins": wins,
                "podiums": podiums,
                "avg_finish": avg_finish,
                "avg_incidents": avg_incidents,
                "ir_change": total_ir_change,
                "sr_change": total_sr_change,
                "ir_per_race": total_ir_change / total_races if total_races else 0.0,
                "sr_per_race": total_sr_change / total_races if total_races else 0.0,
                "series_counts": series_counts,
                "car_counts": car_counts,
            }

            if db:
                serialized_points = [
                    {
                        "date": point["date"].isoformat(),
                        "irating": point["irating"],
                        "safety_rating": point["safety_rating"],
                    }
                    for point in rating_points
                ]
                serialized_summary = dict(summary_stats)
                serialized_summary["series_counts"] = [
                    {"name": name, "count": count} for name, count in series_counts
                ]
                serialized_summary["car_counts"] = [
                    {"name": name, "count": count} for name, count in car_counts
                ]

                payload = {
                    "display_name": display_name,
                    "timeframe_label": timeframe_label,
                    "rating_points": serialized_points,
                    "summary_stats": serialized_summary,
                }

                ttl_hours = IRACING_HISTORY_CACHE_TTLS.get(timeframe_key, 2)
                db.store_iracing_history_cache(cust_id, timeframe_key, payload, ttl_hours=ttl_hours)

        image_buffer = iracing_viz.create_rating_performance_dashboard(
            display_name,
            timeframe_label,
            rating_points,
            summary_stats,
        )

        file = discord.File(fp=image_buffer, filename="rating_history.png")
        await interaction.followup.send(file=file)

    except Exception as e:
        await interaction.followup.send(f"❌ Error generating history dashboard: {str(e)}")
        print(f"❌ iRacing history error: {e}")
        import traceback
        traceback.print_exc()


@bot.tree.command(name="iracing_win_rate", description="View win rate analysis for cars in a series")
@app_commands.describe(
    series_name="Series name (autocomplete available)",
    season="Season (e.g., '2025 S1', optional)",
    week="Week number (optional, defaults to current week)",
    track="Track name filter (optional)"
)
async def iracing_win_rate(interaction: discord.Interaction, series_name: str,
                           season: str = None, week: int = None, track: str = None):
    """View win rate and podium rate analysis"""
    if not iracing or not iracing_viz:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        # Get series list
        all_series = await iracing.get_current_series()
        if not all_series:
            await interaction.followup.send("❌ Failed to retrieve series data")
            return

        # Find series
        series_match = None
        for s in all_series:
            if series_name.lower() in s.get('series_name', '').lower():
                series_match = s
                break

        if not series_match:
            await interaction.followup.send(f"❌ Series not found: '{series_name}'")
            return

        series_id = series_match.get('series_id')
        series_full_name = series_match.get('series_name')
        season_id = series_match.get('season_id') if not season else season_string_to_id(season)

        # Determine week (current week if not specified)
        if week is None:
            week = series_match.get('race_week_num', 0)

        # Get meta analysis (with track filter if specified)
        track_id_filter = None
        if track:
            tracks = await iracing.get_all_tracks()
            for t in tracks:
                if track.lower() in t.get('track_name', '').lower():
                    track_id_filter = t.get('track_id')
                    break

        # Get meta stats
        meta_stats = await iracing.get_meta_for_series(
            series_id,
            season_id,
            week,
            track_id=track_id_filter
        )

        if not meta_stats or 'cars' not in meta_stats or len(meta_stats['cars']) == 0:
            await interaction.followup.send(f"❌ No meta data available for {series_full_name}")
            return

        cars = meta_stats['cars']

        # Calculate win rates and podium rates
        car_data = []
        for car in cars:
            total_races = car.get('total_races', 0)
            wins = car.get('wins', 0)
            podiums = car.get('podiums', 0)

            if total_races > 0:
                win_rate = (wins / total_races) * 100
                podium_rate = (podiums / total_races) * 100

                car_data.append({
                    'car_name': car.get('car_name', 'Unknown'),
                    'wins': wins,
                    'races': total_races,
                    'win_rate': win_rate,
                    'podium_rate': podium_rate
                })

        if len(car_data) == 0:
            await interaction.followup.send("❌ Not enough data to calculate win rates")
            return

        # Generate chart
        track_name = meta_stats.get('track_name') if track_id_filter else None
        image_buffer = iracing_viz.create_win_rate_chart(series_full_name, car_data, track_name)

        # Send as Discord file attachment
        file = discord.File(fp=image_buffer, filename=f"win_rate_{series_id}.png")

        embed = discord.Embed(
            title=f"📊 Win Rate Analysis",
            description=f"{series_full_name}\nWeek {week + 1}",
            color=discord.Color.gold()
        )
        embed.add_field(name="Total Cars Analyzed", value=str(len(car_data)), inline=True)
        embed.add_field(name="Total Races", value=str(sum(c['races'] for c in car_data)), inline=True)

        await interaction.followup.send(embed=embed, file=file)

    except Exception as e:
        await interaction.followup.send(f"❌ Error generating win rate analysis: {str(e)}")
        print(f"❌ Win rate error: {e}")
        import traceback
        traceback.print_exc()


@bot.tree.command(name="iracing_compare_drivers", description="Compare two drivers side-by-side")
@app_commands.describe(
    driver1="First driver (name or customer ID)",
    driver2="Second driver (name or customer ID)",
    category="License category to compare (oval/sports_car_road/formula_car_road/dirt_oval/dirt_road)"
)
@app_commands.autocomplete(category=category_autocomplete)
async def iracing_compare_drivers(interaction: discord.Interaction, driver1: str, driver2: str, category: str = "sports_car_road"):
    """Compare two drivers side-by-side"""
    if not iracing or not iracing_viz:
        await interaction.response.send_message("❌ iRacing integration is not configured")
        return

    await interaction.response.defer()

    try:
        # Helper to resolve driver name or ID to customer ID
        async def resolve_driver(input_str: str) -> tuple:
            """Returns (cust_id, display_name) or (None, None)"""
            # Try as customer ID first
            if input_str.strip().isdigit():
                cust_id = int(input_str.strip())
                profile = await iracing.get_driver_profile(cust_id)
                if profile:
                    return cust_id, profile.get('display_name', f'Driver {cust_id}')
                return None, None

            # Search by name
            results = await iracing.search_driver(input_str)
            if results and len(results) > 0:
                return results[0].get('cust_id'), results[0].get('display_name', input_str)
            return None, None

        # Get both drivers
        cust_id1, name1 = await resolve_driver(driver1)
        if not cust_id1:
            await interaction.followup.send(f"❌ Driver not found: '{driver1}'")
            return

        cust_id2, name2 = await resolve_driver(driver2)
        if not cust_id2:
            await interaction.followup.send(f"❌ Driver not found: '{driver2}'")
            return

        # Get full profiles
        profile1 = await iracing.get_driver_profile(cust_id1)
        profile2 = await iracing.get_driver_profile(cust_id2)

        if not profile1 or not profile2:
            await interaction.followup.send("❌ Failed to retrieve profile data")
            return

        # Get career stats
        stats1 = await iracing.get_driver_career_stats(cust_id1)
        stats2 = await iracing.get_driver_career_stats(cust_id2)

        print(f"📊 Career stats for {name1}: {len(stats1.get('stats', [])) if stats1 else 0} stat entries")
        print(f"📊 Career stats for {name2}: {len(stats2.get('stats', [])) if stats2 else 0} stat entries")

        # Build comparison data
        def build_data(profile, stats_data, name):
            stats_summary = {
                'starts': 0,
                'wins': 0,
                'top3': 0,
                'top5': 0,
                'poles': 0,
                'avg_finish': 0,
                'avg_incidents': 0,
                'win_rate': 0
            }

            if stats_data and 'stats' in stats_data and len(stats_data['stats']) > 0:
                all_stats = stats_data['stats']

                # Debug: Show what categories are in stats
                print(f"   Stats for {name}: {len(all_stats)} categories")
                for s in all_stats:
                    print(f"      Category {s.get('category_id', 'N/A')}: starts={s.get('starts', 0)} "
                          f"wins={s.get('wins', 0)} category={s.get('category', 'N/A')}")

                total_starts = sum(s.get('starts', 0) for s in all_stats)

                stats_summary = {
                    'starts': total_starts,
                    'wins': sum(s.get('wins', 0) for s in all_stats),
                    'top3': sum(s.get('top3', 0) for s in all_stats),
                    'top5': sum(s.get('top5', 0) for s in all_stats),
                    'poles': sum(s.get('poles', 0) for s in all_stats),
                    'avg_finish': sum(s.get('avg_finish', 0) for s in all_stats) / len(all_stats) if len(all_stats) > 0 else 0,
                    'avg_incidents': sum(s.get('avg_incidents', 0) for s in all_stats) / len(all_stats) if len(all_stats) > 0 else 0,
                    'win_rate': (sum(s.get('wins', 0) for s in all_stats) / total_starts * 100) if total_starts > 0 else 0
                }

            # Map license keys to match visualization expectations
            # Licenses is a list, need to convert to dict by category
            licenses_mapped = {}

            # Category ID to name mapping (based on iRacing API)
            # 1=Oval, 3=Dirt Road, 4=Dirt Oval
            # 5=Sports Car Road, 6=Formula Car Road
            # Note: Category 2 was removed - iRacing uses 5 & 6 for road racing categories
            category_id_to_name = {
                1: 'oval',
                3: 'dirt_road',
                4: 'dirt_oval',
                5: 'sports_car_road',  # Sports Car Road
                6: 'formula_car_road'  # Formula Car Road
            }

            licenses_list = profile.get('licenses', [])
            if isinstance(licenses_list, list):
                for lic_data in licenses_list:
                    # Get category identifier
                    cat_id = lic_data.get('category_id', lic_data.get('category'))
                    cat_name = category_id_to_name.get(cat_id, f'unknown_{cat_id}')

                    # Store both iRating and TT Rating separately
                    irating = lic_data.get('irating', 0)
                    tt_rating = lic_data.get('tt_rating', 0)

                    licenses_mapped[cat_name] = {
                        'irating': irating,
                        'tt_rating': tt_rating,
                        'safety_rating': lic_data.get('safety_rating', 0.0),
                        'license_class': lic_data.get('group_name', 'R')  # Use group_name (e.g., "Rookie", "Class A")
                    }

                    print(f"   License: {cat_name} - iR:{irating} ttR:{tt_rating} "
                          f"SR:{lic_data.get('safety_rating')} class:{lic_data.get('group_name', 'N/A')}")

            return {
                'name': name,
                'licenses': licenses_mapped,
                'stats': stats_summary
            }

        driver1_data = build_data(profile1, stats1, name1)
        driver2_data = build_data(profile2, stats2, name2)

        # Generate comparison chart
        image_buffer = iracing_viz.create_driver_comparison(driver1_data, driver2_data, category)
        file = discord.File(fp=image_buffer, filename="comparison.png")

        await interaction.followup.send(file=file)

    except Exception as e:
        await interaction.followup.send(f"❌ Error comparing drivers: {str(e)}")
        print(f"❌ Compare drivers error: {e}")
        import traceback
        traceback.print_exc()


@bot.tree.command(name="iracing_series_popularity", description="View most popular series by participation")
@app_commands.describe(
    time_range="Time period for popularity analysis"
)
@app_commands.choices(time_range=[
    app_commands.Choice(name="This Season", value="season"),
    app_commands.Choice(name="This Week", value="weekly"),
    app_commands.Choice(name="This Year", value="yearly"),
    app_commands.Choice(name="All Seasons", value="all_time")
])
async def iracing_series_popularity(interaction: discord.Interaction, time_range: str = "season"):
    """Show series popularity rankings based on driver participation"""
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration not configured")
        return

    await interaction.response.defer()

    try:
        # Get current time info
        now = datetime.now(timezone.utc)
        current_year = now.year
        current_quarter = (now.month - 1) // 3 + 1

        # Check if we have enough historical data for this time range
        availability_info = None
        if db:
            availability_info = db.get_data_availability_info(current_year, current_quarter)

        # Determine if we can show this time range
        can_show = True
        warning_message = None

        if availability_info and time_range != "season":
            quarter_days = availability_info.get('quarter_days', 0)
            total_days = availability_info.get('total_days', 0)

            if time_range == "yearly" and total_days < 30:
                can_show = False
                warning_message = (
                    f"📊 **Historical Data Not Yet Available**\n\n"
                    f"Yearly statistics require at least 30 days of data collection. "
                    f"Currently collected: **{total_days} days**\n\n"
                    f"The bot is collecting participation data daily. Check back in **{30 - total_days} days** "
                    f"to see yearly trends!\n\n"
                    f"*Showing current season data instead:*"
                )
                time_range = "season"  # Fall back to season
            elif time_range == "all_time" and total_days < 90:
                can_show = False
                warning_message = (
                    f"📊 **Historical Data Not Yet Available**\n\n"
                    f"All-time statistics require at least 90 days of data collection. "
                    f"Currently collected: **{total_days} days**\n\n"
                    f"The bot is collecting participation data daily. Check back in **{90 - total_days} days** "
                    f"to see all-time trends!\n\n"
                    f"*Showing current season data instead:*"
                )
                time_range = "season"

        # Check cache first
        if time_range in iracing_popularity_cache:
            cache_entry = iracing_popularity_cache[time_range]
            sorted_series = cache_entry['data']
            cache_age = (datetime.now() - cache_entry['timestamp']).total_seconds() / 3600
            print(f"📊 Using cached {time_range} popularity data (age: {cache_age:.1f} hours)")
        else:
            # Compute if not cached
            print(f"📊 Computing {time_range} popularity (not in cache)")
            sorted_series = await compute_series_popularity(time_range)
            if sorted_series:
                iracing_popularity_cache[time_range] = {
                    'data': sorted_series,
                    'timestamp': datetime.now()
                }

        # Check if we have data
        if not sorted_series:
            await interaction.followup.send("❌ No participation data available")
            return

        print(f"📈 Top {len(sorted_series)} series by participation:")
        for name, count in sorted_series:
            print(f"  {name}: {count:,} drivers")

        # Create visualization
        time_range_names = {
            "season": "This Season",
            "weekly": "This Week",
            "yearly": "This Year",
            "all_time": "All Seasons"
        }

        image_buffer = iracing_viz.create_popularity_chart(
            sorted_series,
            time_range_names.get(time_range, "This Season")
        )

        file = discord.File(fp=image_buffer, filename="series_popularity.png")

        # Send with warning message if applicable
        if warning_message:
            await interaction.followup.send(content=warning_message, file=file)
        else:
            await interaction.followup.send(file=file)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
        print(f"❌ Popularity error: {e}")
        import traceback
        traceback.print_exc()


@bot.tree.command(name="iracing_timeslots", description="View race session times for a specific series")
@app_commands.describe(
    series="Series name to look up",
    week="Race week number (leave blank for current week)"
)
@app_commands.autocomplete(series=series_autocomplete)
async def iracing_timeslots(interaction: discord.Interaction, series: str, week: int = None):
    """
    Show race session start times for a specific series and week.

    For series with infrequent races (like Nurburgring Endurance), this extracts
    scheduled times from race_time_descriptors since the race_guide API only
    returns sessions starting in the next 24-48 hours.

    TODO: Optimize by caching season schedule data (TTL: 1 hour) to reduce
    redundant API calls. Currently makes 3-4 API calls per invocation.
    """
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        # Get all series to find the matching one
        # TODO: Cache this or add get_season_by_id() to avoid fetching all 147 seasons
        all_series = await iracing.get_current_series()
        if not all_series:
            await interaction.followup.send("❌ Failed to retrieve series data")
            return

        # Find matching series
        series_match = None
        for s in all_series:
            if series.lower() in s.get('series_name', '').lower():
                series_match = s
                break

        if not series_match:
            await interaction.followup.send(f"❌ Series not found: '{series}'")
            return

        series_id = series_match.get('series_id')
        series_name = series_match.get('series_name')
        season_id = series_match.get('season_id')

        print(f"🕐 Race times request: series_id={series_id}, season_id={season_id}, week={week}")

        # Get race times for this series
        sessions = await iracing.get_race_times(series_id, season_id, week)

        # Get track name and week info from schedule
        schedule = await iracing.get_series_schedule(series_id, season_id)

        # Get current week - use parameter, or first session week, or current week from series
        client = await iracing._get_client()
        all_seasons = await client.get_series_seasons()
        season_data = None
        for s in all_seasons:
            if s.get('season_id') == season_id:
                season_data = s
                break

        current_week = week
        if not current_week and sessions:
            current_week = sessions[0].get('race_week_num')
        elif not current_week and season_data:
            current_week = season_data.get('race_week', 0)

        track_name = "Unknown Track"
        if schedule and current_week is not None:
            for week_entry in schedule:
                if week_entry.get('race_week_num') == current_week:
                    track_name = week_entry.get('track_name', 'Unknown Track')
                    break

        # If no upcoming sessions found, try to get exact times from schedule data
        if not sessions:
            # Look for session times in the schedule data
            week_schedule = None
            if schedule and current_week is not None:
                for week_entry in schedule:
                    if week_entry.get('race_week_num') == current_week:
                        week_schedule = week_entry
                        break

            # Extract session times from race_time_descriptors
            # Note: There may be multiple descriptors for different session types
            if week_schedule:
                race_time_descriptors = week_schedule.get('race_time_descriptors', [])

                if race_time_descriptors:
                    # Iterate through ALL descriptors (not just first one)
                    # Some series may have multiple session types or time slots
                    sessions = []
                    for descriptor in race_time_descriptors:
                        session_times_list = descriptor.get('session_times', [])

                        for time_str in session_times_list:
                            sessions.append({
                                'start_time': time_str,
                                'series_id': series_id,
                                'race_week_num': current_week
                            })

                    if sessions:
                        print(f"📅 Using scheduled session times from race_time_descriptors: {len(sessions)} sessions")

            # Final fallback: show recurring pattern if we couldn't find exact times
            if not sessions:
                schedule_desc = season_data.get('schedule_description', '') if season_data else ''

                if schedule_desc:
                    embed = discord.Embed(
                        title=f"🏁 {series_name}",
                        description=f"**Week {current_week}** • {track_name}",
                        color=discord.Color.orange()
                    )

                    embed.add_field(
                        name="📅 Recurring Schedule",
                        value=schedule_desc,
                        inline=False
                    )

                    embed.add_field(
                        name="ℹ️ Note",
                        value="No live sessions in the next 24-48 hours. This series follows a recurring schedule as shown above.",
                        inline=False
                    )

                    embed.set_footer(text="Times are in GMT • Check iRacing for exact session times")

                    await interaction.followup.send(embed=embed)
                    return
                else:
                    # Provide more informative error message
                    error_msg = (
                        f"❌ **No session times available for {series_name}**\n\n"
                        f"This can happen if:\n"
                        f"• No sessions are scheduled in the next 24-48 hours\n"
                        f"• Schedule data is unavailable for week {current_week}\n"
                        f"• The series is not currently active\n\n"
                        f"Try checking iRacing.com directly or contact support if you believe this is an error."
                    )
                    await interaction.followup.send(error_msg)
                    return

        # Build embed for upcoming sessions
        embed = discord.Embed(
            title=f"🏁 {series_name}",
            description=f"**Week {current_week}** • {track_name}",
            color=discord.Color.blue()
        )

        # Group sessions by day
        sessions_by_day = {}

        for session in sessions[:50]:  # Limit to 50 sessions
            # Get session start time
            start_time_str = session.get('start_time') or session.get('session_start_time')
            if not start_time_str:
                continue

            try:
                # Parse the time
                if isinstance(start_time_str, str):
                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                else:
                    start_time = datetime.fromtimestamp(start_time_str, tz=timezone.utc)

                # Get day of week
                day_name = start_time.strftime('%A, %B %d')

                if day_name not in sessions_by_day:
                    sessions_by_day[day_name] = []

                # Format time in both UTC and relative
                time_utc = start_time.strftime('%H:%M UTC')
                timestamp = int(start_time.timestamp())

                sessions_by_day[day_name].append({
                    'time_utc': time_utc,
                    'timestamp': timestamp,
                    'start_time': start_time
                })

            except Exception as e:
                print(f"⚠️ Error parsing session time: {e}")
                continue

        # Calculate total sessions
        total_sessions = sum(len(times) for times in sessions_by_day.values())

        # If fewer than 10 sessions, show as a numbered list
        if total_sessions < 10:
            # Flatten all sessions into a single list sorted by time
            all_times = []
            for day_name in sessions_by_day.keys():
                for time_entry in sessions_by_day[day_name]:
                    all_times.append({
                        'day_name': day_name,
                        'timestamp': time_entry['timestamp'],
                        'start_time': time_entry['start_time']
                    })

            # Sort by start_time
            all_times.sort(key=lambda t: t['start_time'])

            # Create numbered list
            session_list = []
            for i, time_entry in enumerate(all_times, 1):
                # Format: "1. <t:timestamp:f>" - Short date/time with AM/PM
                session_list.append(f"{i}. <t:{time_entry['timestamp']}:f>")

            # Join with newlines
            sessions_text = "\n".join(session_list)

            embed.add_field(
                name="📅 Race Sessions",
                value=sessions_text,
                inline=False
            )

            embed.set_footer(text=f"{total_sessions} race sessions • Times shown in your local timezone with AM/PM")

        else:
            # Show grouped by day for many sessions
            for day_name in sorted(sessions_by_day.keys(), key=lambda d: sessions_by_day[d][0]['start_time']):
                times = sessions_by_day[day_name]

                # Sort times by start_time
                times.sort(key=lambda t: t['start_time'])

                # Format times with AM/PM format
                time_strings = []
                for t in times[:10]:  # Max 10 times per day
                    # Use Discord short time format for automatic timezone conversion
                    time_strings.append(f"<t:{t['timestamp']}:t>")

                value = " • ".join(time_strings)
                embed.add_field(name=day_name, value=value, inline=False)

            embed.set_footer(text=f"{total_sessions} race sessions • Times shown in your local timezone with AM/PM")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
        print(f"❌ Race times error: {e}")
        import traceback
        traceback.print_exc()


@bot.tree.command(name="uncensored", description="Query a local uncensored LLM model")
@app_commands.describe(prompt="Your question or prompt for the uncensored model")
async def uncensored(interaction: discord.Interaction, prompt: str):
    """Query a local uncensored LLM (Drummer's models or similar)"""

    # Check if local LLM is enabled
    if not local_llm.enabled:
        await interaction.response.send_message(
            "❌ **Local LLM not enabled**\n\n"
            "To enable uncensored LLM:\n"
            "1. Set up a local LLM server (Ollama recommended)\n"
            "2. Add to your `.env` file:\n"
            "```\n"
            "LOCAL_LLM_ENABLED=true\n"
            "LOCAL_LLM_URL=http://localhost:11434/v1\n"
            "LOCAL_LLM_MODEL=dolphin-llama3:latest\n"
            "```\n"
            "3. Restart the bot\n\n"
            "**Popular Drummer models**: dolphin-llama3, dolphin-mixtral, wizardlm-uncensored",
            ephemeral=True
        )
        return

    await interaction.response.defer()

    try:
        # Generate response from local LLM
        response = local_llm.generate_response(prompt)

        # Discord has a 2000 character limit
        if len(response) > 1900:
            # Split into chunks
            chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
            await interaction.followup.send(f"**Uncensored Response (Part 1/{len(chunks)}):**\n{chunks[0]}")
            for i, chunk in enumerate(chunks[1:], 2):
                await interaction.followup.send(f"**Part {i}/{len(chunks)}:**\n{chunk}")
        else:
            await interaction.followup.send(f"**Uncensored Response:**\n{response}")

    except Exception as e:
        await interaction.followup.send(f"❌ Error generating response: {str(e)}")
        print(f"❌ Uncensored LLM error: {e}")
        import traceback
        traceback.print_exc()


# Error handling
async def leaderboard(ctx, stat_type: str = 'messages', days: int = 7):
    """Show leaderboard for various statistics
    
    Usage:
    /leaderboard messages [days]
    /leaderboard questions [days]
    /leaderboard profanity [days]
    """
    stat_type = stat_type.lower()
    
    if stat_type not in ['messages', 'questions', 'profanity']:
        await ctx.send("❌ Invalid type. Use: `messages`, `questions`, or `profanity`")
        return
    
    if days < 1 or days > 365:
        await ctx.send("❌ Days must be between 1 and 365")
        return
    
    await generate_leaderboard_response(ctx.channel, stat_type, days)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ User not found.")
    else:
        await ctx.send(f"❌ Error: {str(error)}")
        print(f"Command error: {error}")

# Run bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ DISCORD_TOKEN not found in environment variables!")
        exit(1)
    
    print("🚀 Starting bot...")
    bot.run(token)
