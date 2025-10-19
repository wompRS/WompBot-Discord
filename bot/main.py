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

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)  # Prefix won't be used for slash commands

# Initialize components
db = Database()
llm = LLMClient()
search = SearchEngine()

# Setup feature modules
claims_tracker = ClaimsTracker(db, llm)
fact_checker = FactChecker(db, llm, search)
chat_stats = ChatStatistics(db)

OPT_OUT_ROLE = os.getenv('OPT_OUT_ROLE_NAME', 'NoDataCollection')
WOMPIE_USERNAME = "Wompie__"

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
    
    # Sync slash commands with Discord
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

@bot.event
async def on_message(message):
    # Ignore bot's own messages
    if message.author == bot.user:
        return
    
    # Check if user opted out
    opted_out = user_has_opted_out(message.author) if hasattr(message.author, 'roles') else False
    
    # Store ALL messages (even if opted out, we flag them)
    db.store_message(message, opted_out=opted_out)
    
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
        for user_id, data in top_users:
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