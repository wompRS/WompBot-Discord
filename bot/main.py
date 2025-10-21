import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
from datetime import datetime, timedelta
from database import Database
from llm import LLMClient
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
from credential_manager import CredentialManager
from iracing_graphics import iRacingGraphics

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.message_content = True
intents.reactions = True  # Need for hot takes reaction tracking

bot = commands.Bot(command_prefix='!', intents=intents)  # Prefix won't be used for slash commands

# Initialize components
db = Database()
llm = LLMClient()
search = SearchEngine()

# Setup feature modules
claims_tracker = ClaimsTracker(db, llm)
fact_checker = FactChecker(db, llm, search)
chat_stats = ChatStatistics(db)
hot_takes_tracker = HotTakesTracker(db, llm)
reminder_system = ReminderSystem(db)
event_system = EventSystem(db)
yearly_wrapped = YearlyWrapped(db)
qotd = QuoteOfTheDay(db)
debate_scorekeeper = DebateScorekeeper(db, llm)

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

OPT_OUT_ROLE = os.getenv('OPT_OUT_ROLE_NAME', 'NoDataCollection')
WOMPIE_USERNAME = "Wompie__"

# Background task for pre-computing statistics
@tasks.loop(hours=1)  # Run every hour (can adjust to minutes=30 for 30-min intervals)
async def precompute_stats():
    """Background task to pre-compute common statistics"""
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

def user_has_opted_out(member):
    """Check if user has the opt-out role"""
    return any(role.name == OPT_OUT_ROLE for role in member.roles)

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
    print(f'🔒 Opt-out role: {OPT_OUT_ROLE}')
    
    # Set Wompie user ID for claims tracker
    for guild in bot.guilds:
        member = discord.utils.get(guild.members, name=WOMPIE_USERNAME)
        if member:
            claims_tracker.wompie_user_id = member.id
            print(f'👑 Wompie identified: {member.id}')
            break
    
    # Sync slash commands with Discord (guild-specific for instant updates)
    try:
        # Guild-specific sync for instant command updates
        guild = discord.Object(id=1206079936331259954)  # Your server ID
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
    
    # Check if user opted out
    opted_out = user_has_opted_out(message.author) if hasattr(message.author, 'roles') else False
    
    # Store ALL messages (even if opted out, we flag them)
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
        # Trigger fact-check
        thinking_msg = await reaction.message.channel.send("🔍 Fact-checking this claim...")

        try:
            result = await fact_checker.fact_check_message(reaction.message, user)

            await thinking_msg.delete()

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

                await reaction.message.reply(embed=embed, mention_author=False)

                # React with verdict emoji
                await reaction.message.add_reaction(verdict_emoji)
            else:
                await reaction.message.channel.send(
                    f"❌ Fact-check failed: {result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            await thinking_msg.delete()
            await reaction.message.channel.send(f"❌ Error during fact-check: {str(e)}")
            print(f"❌ Fact-check error: {e}")

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

async def handle_bot_mention(message, opted_out):
    """Handle when bot is mentioned/tagged"""
    try:
        # Remove bot mention and "wompbot" from message
        content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        content = content.replace(f'<@!{bot.user.id}>', '').strip()  # Also handle nickname mentions
        content = content.replace('wompbot', '').replace('womp bot', '').strip()
        content = content.replace('WompBot', '').replace('Wompbot', '').strip()
        
        if not content or len(content) < 2:
            await message.channel.send("Yeah? What's up?")
            return

        # Check for leaderboard triggers in natural language
        content_lower = content.lower()
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

        # Start typing indicator
        async with message.channel.typing():
            # Get conversation context (exclude bot's own messages)
            conversation_history = db.get_recent_messages(
                message.channel.id,
                limit=int(os.getenv('CONTEXT_WINDOW_MESSAGES', 6)),
                exclude_opted_out=True,
                exclude_bot_id=bot.user.id
            )
            
            # Get user context (if not opted out)
            user_context = None if opted_out else db.get_user_context(message.author.id)
            
            # Check if search is needed
            search_results = None
            search_msg = None

            if llm.should_search(content, conversation_history):
                search_msg = await message.channel.send("🔍 Searching for current info...")

                search_results_raw = search.search(content)
                search_results = search.format_results_for_llm(search_results_raw)

                db.store_search_log(content, len(search_results_raw), message.author.id, message.channel.id)

            # Generate response
            response = llm.generate_response(
                user_message=content,
                conversation_history=conversation_history,
                user_context=user_context,
                search_results=search_results
            )

            # Check if response is empty
            if not response or len(response.strip()) == 0:
                response = "I got nothing. Try asking something else?"

            # Check if LLM says it needs more info
            if not search_results and llm.detect_needs_search_from_response(response):
                if not search_msg:
                    search_msg = await message.channel.send("🔍 Let me search for that...")
                else:
                    await search_msg.edit(content="🔍 Let me search for that...")

                search_results_raw = search.search(content)
                search_results = search.format_results_for_llm(search_results_raw)

                db.store_search_log(content, len(search_results_raw), message.author.id, message.channel.id)

                # Regenerate response with search results
                response = llm.generate_response(
                    user_message=content,
                    conversation_history=conversation_history,
                    user_context=user_context,
                    search_results=search_results
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
    
    except Exception as e:
        print(f"❌ Error handling message: {e}")
        import traceback
        traceback.print_exc()
        await message.channel.send(f"Error processing request: {str(e)}")

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
            
            analysis = llm.analyze_user_behavior(messages)
            
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
            results = search.search(query)
            
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
        value="Tag me in a message to chat. I'll respond with context from the conversation.",
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
        value="React to any message with :warning: emoji to trigger an automatic fact-check using web search.",
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

    embed.set_footer(text=f"Opt-out: Get the '{OPT_OUT_ROLE}' role to exclude your data from analysis.")

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

@bot.tree.command(name="help", description="Show all WompBot commands")
async def help_slash(interaction: discord.Interaction):
    """Show bot commands"""
    embed = discord.Embed(
        title="🤖 WompBot Commands",
        description="Here's what I can do:",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="@mention me",
        value="Tag me in a message to chat. I'll respond with context from the conversation.",
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
        value="React to any message with :warning: emoji to trigger an automatic fact-check using web search.",
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
        name="!leaderboard <type> [days]",
        value="Show top users by: `messages`, `questions`, or `profanity`. Default: 7 days",
        inline=False
    )
    embed.add_field(
        name="!search <query>",
        value="Manually search the web for information.",
        inline=False
    )
    embed.add_field(
        name="!analyze [days]",
        value="(Admin only) Analyze user behavior patterns from the last N days.",
        inline=False
    )
    embed.add_field(
        name="!ping",
        value="Check bot latency.",
        inline=False
    )

    embed.set_footer(text=f"Opt-out: Get the '{OPT_OUT_ROLE}' role to exclude your data from analysis.")

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
                f"✅ Linked your Discord account to iRacing driver **{display_name}** (ID: {cust_id})\n"
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
@app_commands.describe(driver_name="iRacing display name (optional if you've linked your account)")
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
                await interaction.followup.send(f"❌ No driver found with name '{driver_name}'")
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
        file = discord.File(fp=image_buffer, filename=f"licenses_{cust_id}.png")

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

@bot.tree.command(name="iracing_schedule", description="View upcoming iRacing race schedule")
@app_commands.describe(
    series="Filter by series name (optional)",
    hours="Look ahead this many hours (default: 24)"
)
async def iracing_schedule(interaction: discord.Interaction, series: str = None, hours: int = 24):
    """View upcoming race schedule"""
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        upcoming = await iracing.get_upcoming_schedule(series_name=series, hours=hours)

        if not upcoming or len(upcoming) == 0:
            msg = f"❌ No upcoming races found"
            if series:
                msg += f" for series '{series}'"
            await interaction.followup.send(msg)
            return

        # Create embed
        embed = discord.Embed(
            title=f"🏁 Upcoming iRacing Schedule",
            description=f"Next {len(upcoming)} races in the next {hours} hours",
            color=discord.Color.blue()
        )

        if series:
            embed.description = f"Series: **{series}**\n{embed.description}"

        # Add races (limit to 10 to avoid embed size limits)
        for i, race in enumerate(upcoming[:10]):
            series_name = race.get('series_name', 'Unknown Series')
            track_name = race.get('track_name', 'Unknown Track')
            start_time = race.get('start_time', 'TBD')

            embed.add_field(
                name=f"{i+1}. {series_name}",
                value=f"**Track:** {track_name}\n**Time:** {start_time}",
                inline=False
            )

        if len(upcoming) > 10:
            embed.set_footer(text=f"Showing 10 of {len(upcoming)} races")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error getting schedule: {str(e)}")
        print(f"❌ iRacing schedule error: {e}")

@bot.tree.command(name="iracing_series", description="List all active iRacing series")
async def iracing_series_list(interaction: discord.Interaction):
    """List all active iRacing series"""
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        series = await iracing.get_current_series()

        if not series or len(series) == 0:
            await interaction.followup.send("❌ No active series found")
            return

        # Create embed
        embed = discord.Embed(
            title="🏁 Active iRacing Series",
            description=f"Found {len(series)} active series",
            color=discord.Color.blue()
        )

        # Group by category if available, or just list them (limit to 25 fields)
        for i, s in enumerate(series[:25]):
            series_name = s.get('series_name', 'Unknown')
            season_id = s.get('season_id', 'N/A')
            category = s.get('category', 'N/A')

            embed.add_field(
                name=series_name,
                value=f"Category: {category}\nSeason ID: {season_id}",
                inline=True
            )

        if len(series) > 25:
            embed.set_footer(text=f"Showing 25 of {len(series)} series")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error getting series list: {str(e)}")
        print(f"❌ iRacing series error: {e}")

async def series_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete function for series names"""
    if not iracing:
        print("⚠️ Series autocomplete: iRacing integration not available")
        return []

    try:
        # Get all series with timeout protection
        import asyncio
        all_series = await asyncio.wait_for(iracing.get_current_series(), timeout=2.5)

        if not all_series:
            print(f"⚠️ Series autocomplete: No series data returned")
            return []

        print(f"✅ Series autocomplete: Loaded {len(all_series)} series")

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
        return []
    except Exception as e:
        print(f"❌ Series autocomplete error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []

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
    # Reference point: Season 5760 started in late 2024 (2025 Season 1)
    # iRacing increments by 1 each quarter (4 per year)
    reference_season = 5760
    reference_year = 2025
    reference_quarter = 1

    # Calculate offset from reference
    offset = season_id - reference_season

    # Calculate year and quarter
    total_quarters = (reference_year - 2015) * 4 + reference_quarter + offset
    year = 2015 + (total_quarters - 1) // 4
    quarter = ((total_quarters - 1) % 4) + 1

    return f"{year} S{quarter}"

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

        if series_name:
            # Try to get seasons for the specific series
            import asyncio
            client = await asyncio.wait_for(iracing._get_client(), timeout=2.0)
            if client:
                seasons_data = await client.get_series_seasons()

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

                    return season_choices[:25]

        # Fallback: provide recent season IDs with year/quarter
        # Current season around 5760 (2025 S1), go back 20 seasons (5 years)
        base = 5760
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

@bot.tree.command(name="iracing_meta", description="View meta analysis for an iRacing series")
@app_commands.describe(
    series="Series name to analyze",
    season="Season number (optional, defaults to current)",
    week="Week number (optional, defaults to current)"
)
@app_commands.autocomplete(
    series=series_autocomplete,
    week=week_autocomplete,
    season=season_autocomplete
)
async def iracing_meta(interaction: discord.Interaction, series: str, season: int = None, week: int = None):
    """View meta chart showing best cars for a series"""
    if not iracing:
        await interaction.response.send_message("❌ iRacing integration is not configured on this bot")
        return

    await interaction.response.defer()

    try:
        # Get meta chart data
        meta_data = await iracing.get_meta_chart_data(series, season_id=season, week_num=week)

        if not meta_data:
            await interaction.followup.send(f"❌ Could not find series '{series}' or no data available")
            return

        series_name = meta_data.get('series_name', series)
        series_id = meta_data.get('series_id')
        car_data = meta_data.get('cars', [])
        track_name = meta_data.get('track_name')
        track_config = meta_data.get('track_config')
        week_num = meta_data.get('week', week or 'Current')
        message = meta_data.get('message', '')

        # Create embed with car information
        embed = discord.Embed(
            title=f"🏎️ {series_name}",
            description=message,
            color=discord.Color.blue()
        )

        if track_name:
            track_text = f"{track_name}"
            if track_config and track_config not in track_name:
                track_text += f" - {track_config}"
            embed.add_field(name="📍 Track", value=track_text, inline=False)

        if car_data:
            # Group cars into chunks of 10 for readability
            car_list = []
            for idx, car in enumerate(car_data, 1):
                car_name = car.get('car_name', 'Unknown')

                # Add BOP info if present
                bop_info = []
                if car.get('power_adjust_pct', 0) != 0:
                    bop_info.append(f"Pwr: {car.get('power_adjust_pct'):+d}%")
                if car.get('weight_penalty_kg', 0) != 0:
                    bop_info.append(f"Wgt: {car.get('weight_penalty_kg'):+d}kg")

                if bop_info:
                    car_list.append(f"{idx}. {car_name} ({', '.join(bop_info)})")
                else:
                    car_list.append(f"{idx}. {car_name}")

            # Split into multiple fields if needed
            chunk_size = 15
            for i in range(0, len(car_list), chunk_size):
                chunk = car_list[i:i+chunk_size]
                field_name = "🚗 Available Cars" if i == 0 else "🚗 Available Cars (cont.)"
                embed.add_field(
                    name=field_name,
                    value="\n".join(chunk),
                    inline=False
                )

            embed.set_footer(text=f"💡 Performance data (lap times, win rates) requires additional API integration")
        else:
            embed.add_field(
                name="ℹ️ Note",
                value="This series may allow all cars in the class, or car restrictions are not specified for this week.",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error getting meta data: {str(e)}")
        print(f"❌ iRacing meta error: {e}")
        import traceback
        traceback.print_exc()

@bot.tree.command(name="iracing_results", description="View recent iRacing race results for a driver")
@app_commands.describe(driver_name="iRacing display name (optional if you've linked your account)")
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
                await interaction.followup.send(f"❌ No driver found with name '{driver_name}'")
                return
            cust_id = results[0].get('cust_id')
            display_name = results[0].get('display_name', driver_name)

        # Get recent races
        races = await iracing.get_driver_recent_races(cust_id, limit=10)

        if not races or len(races) == 0:
            await interaction.followup.send(f"❌ No recent races found for {display_name}")
            return

        # Create embed
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

        embed.set_footer(text=f"Customer ID: {cust_id}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error getting race results: {str(e)}")
        print(f"❌ iRacing results error: {e}")

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