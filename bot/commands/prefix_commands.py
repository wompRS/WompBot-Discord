"""
Prefix commands for WompBot Discord bot.

This module contains traditional prefix commands (!command syntax).
"""

import asyncio
import json
import logging
import os
import discord
import requests
from discord.ext import commands
from datetime import datetime, timedelta
from urllib.parse import quote as url_quote
import re
from io import BytesIO
import time

logger = logging.getLogger(__name__)


def register_prefix_commands(bot, db, llm, search, help_system, tasks_dict,
                              weather=None, wolfram=None,
                              # Feature deps for migrated slash commands
                              claims_tracker=None, hot_takes_tracker=None,
                              reminder_system=None, event_system=None,
                              debate_scorekeeper=None, qotd=None, rag=None,
                              poll_system=None, who_said_it=None,
                              devils_advocate=None, jeopardy=None,
                              trivia=None, message_scheduler=None,
                              rss_monitor=None, github_monitor=None,
                              watchlist_manager=None,
                              iracing_viz=None, chat_stats=None,
                              stats_viz=None):
    """
    Register all prefix commands with the bot.

    Args:
        bot: Discord bot instance
        db: Database instance
        llm: LLM client instance
        search: Web search instance
        help_system: Help system instance
        tasks_dict: Dictionary of background tasks from register_tasks()
    """

    @bot.command(name='refreshstats')
    @commands.has_permissions(administrator=True)
    async def refresh_stats(ctx):
        """Manually trigger background stats computation (Admin only)"""
        await ctx.send("🔄 Manually triggering stats computation...")

        try:
            if 'precompute_stats' in tasks_dict:
                task = tasks_dict['precompute_stats']
                # The task is a discord.ext.tasks.Loop — invoke its underlying coroutine
                await task.coro()
                await ctx.send("✅ Stats computation complete!")
            else:
                await ctx.send("⚠️ Stats task not found. Contact bot admin.")
        except Exception as e:
            await ctx.send(f"❌ Error computing stats: {str(e)}")
            logger.error("Manual stats refresh error: %s", e)

    @bot.command(name='analyze')
    @commands.has_permissions(administrator=True)
    async def analyze_users(ctx, days: int = 7):
        """Analyze user behavior patterns (Admin only)"""
        await ctx.send(f"🔍 Analyzing user behavior from the last {days} days...")

        try:
            active_users = await asyncio.to_thread(db.get_all_active_users, days=days)

            if not active_users:
                await ctx.send("No active users found in this period.")
                return

            period_start = datetime.now() - timedelta(days=days)
            period_end = datetime.now()

            results = []
            for user in active_users[:10]:  # Limit to 10 users to avoid rate limits
                messages = await asyncio.to_thread(db.get_user_messages_for_analysis, user['user_id'], days=days)

                if len(messages) < 5:  # Skip users with too few messages
                    continue

                await ctx.send(f"Analyzing {user['username']}...")

                analysis = await asyncio.to_thread(llm.analyze_user_behavior, messages)

                if analysis:
                    await asyncio.to_thread(
                        db.store_behavior_analysis,
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
            user_context = await asyncio.to_thread(db.get_user_context, target.id)
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

                asyncio.create_task(asyncio.to_thread(db.store_search_log, query, len(results), ctx.author.id, ctx.channel.id))

            except Exception as e:
                await ctx.send(f"❌ Search error: {str(e)}")

    @bot.command(name='ping')
    async def ping(ctx):
        """Check bot latency"""
        await ctx.send(f"🏓 Pong! Latency: {round(bot.latency * 1000)}ms")

    @bot.command(name='help')
    async def help_prefix(ctx, command: str = None):
        """Show bot commands or get detailed help for a specific command or category"""
        if command:
            command_lower = command.lower().strip()

            # First check if it's a category
            embed = help_system.get_category_help(command_lower)
            if embed:
                await ctx.send(embed=embed)
                return

            # Then check for specific command
            embed = help_system.get_command_help(command_lower)
            if embed:
                await ctx.send(embed=embed)
            else:
                # List available categories
                categories = help_system.get_available_categories()
                await ctx.send(
                    f"❌ No help found for `{command}`.\n\n"
                    f"**Available categories:** {', '.join(f'`{c}`' for c in categories)}\n\n"
                    f"Use `!help` to see all commands or `!help <category>` for category help."
                )
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
            title="WompBot Commands",
            description="Here's what I can do:",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="Chat with WompBot",
            value="Tag me with @WompBot, type 'wompbot', or use !wb shorthand. Powered by DeepSeek for fast, conversational responses with automatic web search when needed.",
            inline=False
        )

        embed.add_field(
            name="Personality Modes",
            value=(
                "Three modes available (admin can switch with !personality):\n"
                "• Default - Conversational and helpful with detailed responses\n"
                "• Concise - Brief, direct answers (1-2 sentences max)\n"
                "• Bogan - Full Australian slang mode for casual fun"
            ),
            inline=False
        )

        embed.add_field(
            name="Save Quote",
            value="React to any message with cloud emoji to save it as a quote.",
            inline=False
        )

        embed.add_field(
            name="Fact-Check",
            value="React to any message with warning emoji to trigger high-accuracy fact-checking. Uses DeepSeek, web search, and multi-source verification (requires 2+ sources). Rate limited: 5-minute cooldown, 10 per day per user.",
            inline=False
        )

        embed.add_field(
            name="Rate Limits and Cost Control",
            value=(
                "Token limits: 1,000 per request, 10,000 per hour per user\n"
                "Context: 4000 token hard cap (auto-truncates)\n"
                "Fact-checks: 5-min cooldown, 10 per day\n"
                "Searches: 5 per hour, 20 per day per user\n"
                "Messages: 3s cooldown, 10 per min\n"
                "Max concurrent requests: 3\n"
                "$1 spending alerts sent via DM to bot owner\n"
                "All limits configurable via .env"
            ),
            inline=False
        )

        embed.add_field(
            name="Chat Statistics",
            value=(
                "/stats_server [days] - Network graph and server stats\n"
                "/stats_topics [days] - Trending keywords (TF-IDF)\n"
                "/stats_primetime [@user] [days] - Activity heatmap\n"
                "/stats_engagement [@user] [days] - Engagement metrics"
            ),
            inline=False
        )

        embed.add_field(
            name="Other Commands",
            value=(
                "!stats [@user] - View user statistics\n"
                "!receipts [@user] [keyword] - View tracked claims\n"
                "!quotes [@user] - View saved quotes\n"
                "!search <query> - Manually search the web\n"
                "!yt <query> - Search YouTube and get video links\n"
                "!analyze [days] - (Admin) Analyze user behavior patterns\n"
                "!refreshstats - (Admin) Manually refresh stats cache\n"
                "!ping - Check bot latency"
            ),
            inline=False
        )

        embed.set_footer(text="Privacy: Use /wompbot_optout to opt out of data collection. Use !help for full command list.")

        await ctx.send(embed=embed)

    # ===== TOOL COMMANDS =====

    @bot.command(name='convert', aliases=['currency', 'fx'])
    async def convert_currency(ctx, amount: float, from_curr: str, to_curr: str = None):
        """Convert currency: !convert 100 USD EUR or !convert 100 USD to EUR"""
        # Handle "to" keyword if present
        if to_curr and to_curr.lower() == 'to':
            # User typed "!convert 100 USD to EUR" - need to get next word
            await ctx.send("Usage: `!convert <amount> <from> <to>` - e.g., `!convert 100 USD EUR`")
            return

        if not to_curr:
            await ctx.send("Usage: `!convert <amount> <from> <to>` - e.g., `!convert 100 USD EUR`")
            return

        from_curr = from_curr.upper().strip()
        to_curr = to_curr.upper().strip()

        # Currency aliases
        currency_aliases = {
            'DOLLAR': 'USD', 'DOLLARS': 'USD', 'BUCK': 'USD', 'BUCKS': 'USD',
            'EURO': 'EUR', 'EUROS': 'EUR',
            'POUND': 'GBP', 'POUNDS': 'GBP', 'STERLING': 'GBP',
            'YEN': 'JPY', 'YUAN': 'CNY', 'RMB': 'CNY',
        }

        from_curr = currency_aliases.get(from_curr, from_curr)
        to_curr = currency_aliases.get(to_curr, to_curr)

        async with ctx.typing():
            try:
                def do_convert():
                    url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_curr}&to={to_curr}"
                    return requests.get(url, timeout=10)

                response = await asyncio.to_thread(do_convert)

                if response.status_code != 200:
                    await ctx.send(f"❌ Could not convert {from_curr} to {to_curr}. Check currency codes.")
                    return

                data = response.json()
                rates = data.get('rates', {})

                if to_curr not in rates:
                    await ctx.send(f"❌ Currency {to_curr} not found.")
                    return

                converted = rates[to_curr]
                rate = converted / amount if amount != 0 else 0

                if converted >= 1000:
                    converted_str = f"{converted:,.2f}"
                elif converted >= 1:
                    converted_str = f"{converted:.2f}"
                else:
                    converted_str = f"{converted:.4f}"

                embed = discord.Embed(
                    title="💱 Currency Conversion",
                    color=discord.Color.green()
                )
                embed.add_field(name="From", value=f"{amount:,.2f} {from_curr}", inline=True)
                embed.add_field(name="To", value=f"{converted_str} {to_curr}", inline=True)
                embed.add_field(name="Rate", value=f"1 {from_curr} = {rate:.4f} {to_curr}", inline=False)

                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"❌ Conversion failed: {str(e)}")

    @bot.command(name='define', aliases=['definition', 'dict'])
    async def define_word(ctx, *, word: str):
        """Get dictionary definition: !define serendipity"""
        async with ctx.typing():
            try:
                def fetch_definition():
                    # URL encode word to handle special characters safely
                    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{url_quote(word, safe='')}"
                    return requests.get(url, timeout=10)

                response = await asyncio.to_thread(fetch_definition)

                if response.status_code != 200:
                    await ctx.send(f"❌ Could not find definition for '{word}'")
                    return

                data = response.json()
                if not data or not isinstance(data, list):
                    await ctx.send(f"❌ No definitions found for '{word}'")
                    return

                entry = data[0]
                embed = discord.Embed(
                    title=f"📖 {word.capitalize()}",
                    color=discord.Color.blue()
                )

                # Get phonetic if available
                phonetics = entry.get('phonetics', [])
                for p in phonetics:
                    if p.get('text'):
                        embed.description = f"*{p['text']}*"
                        break

                # Get meanings
                meanings = entry.get('meanings', [])[:3]  # Limit to 3 parts of speech
                for meaning in meanings:
                    part_of_speech = meaning.get('partOfSpeech', 'unknown')
                    definitions = meaning.get('definitions', [])[:2]  # Limit to 2 definitions each

                    def_text = ""
                    for i, d in enumerate(definitions, 1):
                        def_text += f"{i}. {d.get('definition', '')}\n"
                        if d.get('example'):
                            def_text += f"   *\"{d['example']}\"*\n"

                    if def_text:
                        embed.add_field(name=part_of_speech.capitalize(), value=def_text[:1024], inline=False)

                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"❌ Definition lookup failed: {str(e)}")

    @bot.command(name='weather', aliases=['w'])
    async def weather_lookup(ctx, *, location: str = None):
        """Get current weather: !weather London"""
        if not weather:
            await ctx.send("❌ Weather service not configured.")
            return

        # Check for saved preference if no location provided
        if not location:
            pref = await asyncio.to_thread(db.get_weather_preference, ctx.author.id)
            if pref:
                location = pref['location']
            else:
                await ctx.send("Please specify a location: `!weather London` or set a default with `!weatherset`")
                return

        async with ctx.typing():
            try:
                result = await asyncio.to_thread(weather.get_current_weather, location)

                if not result.get('success'):
                    await ctx.send(f"❌ {result.get('error', 'Could not fetch weather')}")
                    return

                # Weather API returns a summary with all info formatted
                if 'summary' in result:
                    await ctx.send(result['summary'])
                else:
                    # Fallback to embed if no summary
                    embed = discord.Embed(
                        title=f"🌤️ Weather in {result['location']}, {result['country']}",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Temperature", value=f"{result['temperature']}{result['units']['temp']}", inline=True)
                    embed.add_field(name="Feels Like", value=f"{result['feels_like']}{result['units']['temp']}", inline=True)
                    embed.add_field(name="Conditions", value=result['description'], inline=True)
                    embed.add_field(name="Humidity", value=f"{result['humidity']}%", inline=True)
                    embed.add_field(name="Wind", value=f"{result['wind_speed']} {result['units']['speed']}", inline=True)
                    await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"❌ Weather lookup failed: {str(e)}")

    @bot.command(name='time', aliases=['timezone', 'tz'])
    async def time_lookup(ctx, *, timezone: str = "UTC"):
        """Get current time in a timezone: !time Tokyo or !time America/New_York"""
        import pytz
        from datetime import datetime

        # Common timezone aliases
        tz_aliases = {
            'EST': 'America/New_York', 'EDT': 'America/New_York',
            'CST': 'America/Chicago', 'CDT': 'America/Chicago',
            'MST': 'America/Denver', 'MDT': 'America/Denver',
            'PST': 'America/Los_Angeles', 'PDT': 'America/Los_Angeles',
            'GMT': 'Europe/London', 'BST': 'Europe/London',
            'CET': 'Europe/Paris', 'CEST': 'Europe/Paris',
            'JST': 'Asia/Tokyo', 'TOKYO': 'Asia/Tokyo', 'JAPAN': 'Asia/Tokyo',
            'AEST': 'Australia/Sydney', 'SYDNEY': 'Australia/Sydney',
            'IST': 'Asia/Kolkata', 'INDIA': 'Asia/Kolkata',
            'NEW YORK': 'America/New_York', 'NYC': 'America/New_York',
            'LONDON': 'Europe/London', 'PARIS': 'Europe/Paris',
            'BERLIN': 'Europe/Berlin', 'MOSCOW': 'Europe/Moscow',
            'BEIJING': 'Asia/Shanghai', 'SHANGHAI': 'Asia/Shanghai',
            'HONG KONG': 'Asia/Hong_Kong', 'SINGAPORE': 'Asia/Singapore',
            'DUBAI': 'Asia/Dubai', 'LA': 'America/Los_Angeles',
            'CHICAGO': 'America/Chicago', 'DENVER': 'America/Denver',
        }

        tz_name = tz_aliases.get(timezone.upper(), timezone)

        try:
            tz = pytz.timezone(tz_name)
            now = datetime.now(tz)

            embed = discord.Embed(
                title=f"🕐 Time in {tz_name}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Current Time", value=now.strftime('%I:%M:%S %p'), inline=True)
            embed.add_field(name="Date", value=now.strftime('%A, %B %d, %Y'), inline=True)
            embed.add_field(name="UTC Offset", value=now.strftime('%z'), inline=True)

            await ctx.send(embed=embed)

        except pytz.UnknownTimeZoneError:
            await ctx.send(f"❌ Unknown timezone: `{timezone}`\nTry: `!time Tokyo`, `!time EST`, `!time America/New_York`")

    @bot.command(name='roll', aliases=['dice', 'random', 'flip'])
    async def roll_dice(ctx, *, expression: str = "d6"):
        """Roll dice or flip coins: !roll d20, !roll 2d6, !roll coin"""
        import random

        expression = expression.lower().strip()

        # Handle coin flip
        if expression in ['coin', 'flip', 'coinflip']:
            result = random.choice(['Heads', 'Tails'])
            await ctx.send(f"🪙 **Coin flip:** {result}")
            return

        # Handle dice roll (e.g., d20, 2d6, 3d8+5)
        import re
        match = re.match(r'^(\d*)d(\d+)([+-]\d+)?$', expression)

        if not match:
            await ctx.send("Usage: `!roll d20`, `!roll 2d6`, `!roll 3d8+5`, or `!roll coin`")
            return

        num_dice = int(match.group(1)) if match.group(1) else 1
        sides = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0

        if num_dice > 100 or sides > 1000:
            await ctx.send("❌ Too many dice or sides!")
            return

        rolls = [random.randint(1, sides) for _ in range(num_dice)]
        total = sum(rolls) + modifier

        if num_dice == 1:
            if modifier:
                await ctx.send(f"🎲 **d{sides}{modifier:+d}:** {rolls[0]} {modifier:+d} = **{total}**")
            else:
                await ctx.send(f"🎲 **d{sides}:** **{rolls[0]}**")
        else:
            rolls_str = ', '.join(str(r) for r in rolls[:20])
            if len(rolls) > 20:
                rolls_str += f"... (+{len(rolls) - 20} more)"
            if modifier:
                await ctx.send(f"🎲 **{num_dice}d{sides}{modifier:+d}:** [{rolls_str}] {modifier:+d} = **{total}**")
            else:
                await ctx.send(f"🎲 **{num_dice}d{sides}:** [{rolls_str}] = **{total}**")

    @bot.command(name='movie', aliases=['film', 'imdb'])
    async def movie_info(ctx, *, title: str):
        """Get movie/TV show info: !movie Inception"""
        import os
        api_key = os.getenv('OMDB_API_KEY')

        if not api_key:
            await ctx.send("❌ Movie lookup not configured (missing OMDB_API_KEY).")
            return

        async with ctx.typing():
            try:
                def fetch_movie():
                    # URL encode title to handle special characters safely
                    url = f"https://www.omdbapi.com/?t={url_quote(title, safe='')}&apikey={api_key}"
                    return requests.get(url, timeout=10)

                response = await asyncio.to_thread(fetch_movie)
                data = response.json()

                if data.get('Response') == 'False':
                    await ctx.send(f"❌ Could not find: '{title}'")
                    return

                embed = discord.Embed(
                    title=f"🎬 {data.get('Title', 'Unknown')} ({data.get('Year', 'N/A')})",
                    description=data.get('Plot', 'No plot available')[:500],
                    color=discord.Color.gold()
                )

                if data.get('Poster') and data['Poster'] != 'N/A':
                    embed.set_thumbnail(url=data['Poster'])

                embed.add_field(name="Rating", value=data.get('imdbRating', 'N/A'), inline=True)
                embed.add_field(name="Runtime", value=data.get('Runtime', 'N/A'), inline=True)
                embed.add_field(name="Genre", value=data.get('Genre', 'N/A'), inline=True)
                embed.add_field(name="Director", value=data.get('Director', 'N/A'), inline=True)
                embed.add_field(name="Actors", value=data.get('Actors', 'N/A')[:100], inline=False)

                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"❌ Movie lookup failed: {str(e)}")

    @bot.command(name='stock', aliases=['price', 'crypto'])
    async def stock_price(ctx, *, query: str):
        """Get stock/crypto price or history: !stock AAPL, !stock TSLA 1 year, !stock NVDA 3m candle"""
        query = query.strip()

        # Check for chart type modifier (candle/candlestick)
        chart_type = "line"
        if re.search(r'\b(candle|candlestick|ohlc)\b', query, re.IGNORECASE):
            chart_type = "candle"
            query = re.sub(r'\s*(candle|candlestick|ohlc)\s*', ' ', query, flags=re.IGNORECASE).strip()

        # Parse time period from query (e.g., "tsla 1 year", "AAPL 6 months", "NVDA 1Y")
        period_patterns = [
            # Verbose patterns: "1 year", "6 months", "3 month"
            (r'^(.+?)\s+(\d+)\s*(year|years|yr|yrs)$', lambda m: f"{m.group(2)}Y"),
            (r'^(.+?)\s+(\d+)\s*(month|months|mo|mos)$', lambda m: f"{m.group(2)}M"),
            # Short patterns: "1Y", "6M", "1y", "6m"
            (r'^(.+?)\s+(\d+)\s*([YyMm])$', lambda m: f"{m.group(2)}{m.group(3).upper()}"),
            # Keyword patterns: "ytd", "max", "all time"
            (r'^(.+?)\s+(ytd|max|all\s*time)$', lambda m: 'MAX' if 'max' in m.group(2).lower() or 'all' in m.group(2).lower() else '1Y'),
        ]

        period = None
        symbol_part = query
        for pattern, period_func in period_patterns:
            match = re.match(pattern, query, re.IGNORECASE)
            if match:
                symbol_part = match.group(1).strip()
                period = period_func(match)
                # Normalize period to valid values
                period_num = int(re.match(r'(\d+)', period).group(1)) if re.match(r'(\d+)', period) else 1
                period_unit = period[-1].upper()
                if period_unit == 'Y':
                    if period_num == 1:
                        period = '1Y'
                    elif period_num == 2:
                        period = '2Y'
                    elif period_num <= 5:
                        period = '5Y'
                    else:
                        period = '10Y'
                elif period_unit == 'M':
                    if period_num <= 1:
                        period = '1M'
                    elif period_num <= 3:
                        period = '3M'
                    elif period_num <= 6:
                        period = '6M'
                    else:
                        period = '1Y'
                break

        # Common company/crypto name to ticker mappings
        name_to_ticker = {
            # Tech giants
            'MICROSOFT': 'MSFT', 'APPLE': 'AAPL', 'GOOGLE': 'GOOGL', 'ALPHABET': 'GOOGL',
            'AMAZON': 'AMZN', 'META': 'META', 'FACEBOOK': 'META', 'NETFLIX': 'NFLX',
            'NVIDIA': 'NVDA', 'TESLA': 'TSLA', 'AMD': 'AMD', 'INTEL': 'INTC',
            'IBM': 'IBM', 'ORACLE': 'ORCL', 'SALESFORCE': 'CRM', 'ADOBE': 'ADBE',
            'CISCO': 'CSCO', 'QUALCOMM': 'QCOM', 'PAYPAL': 'PYPL', 'UBER': 'UBER',
            'AIRBNB': 'ABNB', 'SPOTIFY': 'SPOT', 'ZOOM': 'ZM', 'TWITTER': 'X',
            'SNAP': 'SNAP', 'SNAPCHAT': 'SNAP', 'PINTEREST': 'PINS', 'SHOPIFY': 'SHOP',
            'SQUARE': 'SQ', 'BLOCK': 'SQ', 'PALANTIR': 'PLTR', 'SNOWFLAKE': 'SNOW',
            'CLOUDFLARE': 'NET', 'DATADOG': 'DDOG', 'CROWDSTRIKE': 'CRWD',
            # Finance
            'JPMORGAN': 'JPM', 'JP MORGAN': 'JPM', 'CHASE': 'JPM',
            'BANK OF AMERICA': 'BAC', 'BOFA': 'BAC', 'WELLS FARGO': 'WFC',
            'GOLDMAN': 'GS', 'GOLDMAN SACHS': 'GS', 'MORGAN STANLEY': 'MS',
            'VISA': 'V', 'MASTERCARD': 'MA', 'AMEX': 'AXP', 'AMERICAN EXPRESS': 'AXP',
            'BLACKROCK': 'BLK', 'BERKSHIRE': 'BRK.A', 'BERKSHIRE HATHAWAY': 'BRK.A',
            # Retail & Consumer
            'WALMART': 'WMT', 'TARGET': 'TGT', 'COSTCO': 'COST', 'HOME DEPOT': 'HD',
            'LOWES': 'LOW', "LOWE'S": 'LOW', 'NIKE': 'NKE', 'STARBUCKS': 'SBUX',
            'MCDONALDS': 'MCD', "MCDONALD'S": 'MCD', 'COCA COLA': 'KO', 'COKE': 'KO',
            'PEPSI': 'PEP', 'PEPSICO': 'PEP', 'DISNEY': 'DIS', 'FORD': 'F',
            'GM': 'GM', 'GENERAL MOTORS': 'GM', 'TOYOTA': 'TM', 'HONDA': 'HMC',
            # Healthcare & Pharma
            'JOHNSON': 'JNJ', 'JOHNSON AND JOHNSON': 'JNJ', 'J&J': 'JNJ',
            'PFIZER': 'PFE', 'MODERNA': 'MRNA', 'MERCK': 'MRK', 'ABBVIE': 'ABBV',
            'UNITEDHEALTH': 'UNH', 'CVS': 'CVS', 'WALGREENS': 'WBA',
            # Energy
            'EXXON': 'XOM', 'EXXONMOBIL': 'XOM', 'CHEVRON': 'CVX', 'SHELL': 'SHEL',
            'BP': 'BP', 'CONOCOPHILLIPS': 'COP',
        }

        # Crypto name to CoinGecko ID mapping
        crypto_to_coingecko = {
            'BITCOIN': 'bitcoin', 'BTC': 'bitcoin', 'BTC-USD': 'bitcoin',
            'ETHEREUM': 'ethereum', 'ETH': 'ethereum', 'ETH-USD': 'ethereum',
            'DOGECOIN': 'dogecoin', 'DOGE': 'dogecoin', 'DOGE-USD': 'dogecoin',
            'SOLANA': 'solana', 'SOL': 'solana', 'SOL-USD': 'solana',
            'CARDANO': 'cardano', 'ADA': 'cardano', 'ADA-USD': 'cardano',
            'XRP': 'ripple', 'RIPPLE': 'ripple', 'XRP-USD': 'ripple',
            'LITECOIN': 'litecoin', 'LTC': 'litecoin', 'LTC-USD': 'litecoin',
            'POLKADOT': 'polkadot', 'DOT': 'polkadot', 'DOT-USD': 'polkadot',
            'AVALANCHE': 'avalanche-2', 'AVAX': 'avalanche-2', 'AVAX-USD': 'avalanche-2',
            'CHAINLINK': 'chainlink', 'LINK': 'chainlink', 'LINK-USD': 'chainlink',
            'SHIBA': 'shiba-inu', 'SHIB': 'shiba-inu', 'SHIB-USD': 'shiba-inu', 'SHIBA INU': 'shiba-inu',
            'MATIC': 'matic-network', 'POLYGON': 'matic-network',
            'UNISWAP': 'uniswap', 'UNI': 'uniswap',
        }

        # Use symbol_part (query minus period) for lookups
        symbol_upper = symbol_part.upper()

        # Check if query matches a known stock name
        symbol = name_to_ticker.get(symbol_upper, symbol_upper)

        # If a time period was specified, fetch stock history with chart
        if period:
            await _fetch_stock_history(ctx, symbol, period, chart_type)
            return

        # Check if it's a crypto (only for current price, no period)
        coingecko_id = crypto_to_coingecko.get(symbol_upper)
        if coingecko_id:
            await _fetch_crypto_price(ctx, coingecko_id, symbol_upper)
            return

        # Try Finnhub first (free, 60 calls/min)
        finnhub_key = os.getenv('FINNHUB_API_KEY')
        if finnhub_key:
            result = await _fetch_finnhub_price(ctx, symbol, finnhub_key)
            if result:
                return

        # Fallback: try as crypto on CoinGecko (maybe user typed a crypto symbol we don't have mapped)
        await _fetch_crypto_price(ctx, symbol_part.lower(), symbol_upper, fallback_stock=symbol)

    async def _fetch_finnhub_price(ctx, symbol: str, api_key: str) -> bool:
        """Fetch stock price from Finnhub. Returns True if successful."""
        async with ctx.typing():
            try:
                def fetch():
                    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}"
                    resp = requests.get(url, timeout=10)
                    return resp.json()

                data = await asyncio.to_thread(fetch)

                # Finnhub returns c=0 for invalid symbols
                if not data or data.get('c', 0) == 0:
                    return False

                price = data['c']  # Current price
                prev_close = data['pc']  # Previous close
                change = data['d']  # Change
                change_pct = data['dp']  # Change percent

                # Get company name
                def fetch_profile():
                    url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={api_key}"
                    resp = requests.get(url, timeout=10)
                    return resp.json()

                profile = await asyncio.to_thread(fetch_profile)
                name = profile.get('name', symbol) if profile else symbol

                color = discord.Color.green() if change >= 0 else discord.Color.red()
                arrow = "📈" if change >= 0 else "📉"

                embed = discord.Embed(
                    title=f"{arrow} {name} ({symbol})",
                    color=color
                )
                embed.add_field(name="Price", value=f"${price:,.2f}", inline=True)
                embed.add_field(name="Change", value=f"{change:+,.2f} ({change_pct:+.2f}%)", inline=True)

                if profile and profile.get('marketCapitalization'):
                    cap = profile['marketCapitalization'] * 1_000_000  # Finnhub returns in millions
                    if cap >= 1e12:
                        cap_str = f"${cap/1e12:.2f}T"
                    elif cap >= 1e9:
                        cap_str = f"${cap/1e9:.2f}B"
                    else:
                        cap_str = f"${cap/1e6:.2f}M"
                    embed.add_field(name="Market Cap", value=cap_str, inline=True)

                embed.set_footer(text="Data from Finnhub")
                await ctx.send(embed=embed)
                return True

            except Exception as e:
                logger.error("Finnhub error for %s: %s", symbol, e)
                return False

    async def _fetch_crypto_price(ctx, coingecko_id: str, display_symbol: str, fallback_stock: str = None):
        """Fetch crypto price from CoinGecko (free, no API key needed)."""
        async with ctx.typing():
            try:
                def fetch():
                    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true"
                    resp = requests.get(url, timeout=10)
                    return resp.json()

                data = await asyncio.to_thread(fetch)

                if not data or coingecko_id not in data:
                    if fallback_stock:
                        await ctx.send(f"❌ Could not find price for: `{fallback_stock}` (no Finnhub API key configured)")
                    else:
                        await ctx.send(f"❌ Could not find crypto: `{display_symbol}`")
                    return

                crypto_data = data[coingecko_id]
                price = crypto_data['usd']
                change_pct = crypto_data.get('usd_24h_change', 0) or 0
                market_cap = crypto_data.get('usd_market_cap', 0)

                color = discord.Color.green() if change_pct >= 0 else discord.Color.red()
                arrow = "📈" if change_pct >= 0 else "📉"

                embed = discord.Embed(
                    title=f"{arrow} {coingecko_id.replace('-', ' ').title()} ({display_symbol})",
                    color=color
                )

                # Format price based on magnitude
                if price >= 1:
                    embed.add_field(name="Price", value=f"${price:,.2f}", inline=True)
                else:
                    embed.add_field(name="Price", value=f"${price:.6f}", inline=True)

                embed.add_field(name="24h Change", value=f"{change_pct:+.2f}%", inline=True)

                if market_cap:
                    if market_cap >= 1e12:
                        cap_str = f"${market_cap/1e12:.2f}T"
                    elif market_cap >= 1e9:
                        cap_str = f"${market_cap/1e9:.2f}B"
                    elif market_cap >= 1e6:
                        cap_str = f"${market_cap/1e6:.2f}M"
                    else:
                        cap_str = f"${market_cap:,.0f}"
                    embed.add_field(name="Market Cap", value=cap_str, inline=True)

                embed.set_footer(text="Data from CoinGecko")
                await ctx.send(embed=embed)

            except Exception as e:
                if fallback_stock:
                    await ctx.send(f"❌ Could not find price for: `{fallback_stock}` (add FINNHUB_API_KEY to .env for stock prices)")
                else:
                    await ctx.send(f"❌ Crypto lookup failed: {str(e)}")

    async def _fetch_stock_history(ctx, symbol: str, period: str, chart_type: str = "line"):
        """Fetch stock history using yfinance and create a chart. No API key needed."""
        async with ctx.typing():
            try:
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
                import pandas as pd
                import yfinance as yf

                # Period display names and yfinance period mapping
                period_map = {
                    '1M': ('1mo', '1 Month'),
                    '3M': ('3mo', '3 Months'),
                    '6M': ('6mo', '6 Months'),
                    '1Y': ('1y', '1 Year'),
                    '2Y': ('2y', '2 Years'),
                    '5Y': ('5y', '5 Years'),
                    '10Y': ('10y', '10 Years'),
                    'MAX': ('max', 'All Time'),
                }
                yf_period, period_display = period_map.get(period, ('1y', '1 Year'))

                # Fetch data using yfinance (runs in thread to not block)
                def fetch_yfinance():
                    hist = pd.DataFrame()
                    info = {}

                    # Try Ticker.history() first (let yfinance handle session)
                    try:
                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(period=yf_period)
                        try:
                            info = ticker.info
                        except Exception:
                            pass
                    except Exception as e:
                        logger.warning("Ticker.history failed: %s", e)

                    # Fallback to download() if history failed
                    if hist.empty:
                        try:
                            hist = yf.download(symbol, period=yf_period, progress=False, auto_adjust=True)
                        except Exception as e:
                            logger.warning("yf.download failed: %s", e)

                    return hist, info

                hist, info = await asyncio.to_thread(fetch_yfinance)

                if hist is None or hist.empty:
                    await ctx.send(f"❌ No historical data found for `{symbol}`. Yahoo Finance may be temporarily unavailable.")
                    return

                # Get company name
                company_name = info.get('shortName', info.get('longName', symbol))

                # Handle MultiIndex columns from yf.download() (columns like ('Close', 'TSLA'))
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = hist.columns.get_level_values(0)

                # Extract data
                closes = hist['Close'].tolist()
                opens = hist['Open'].tolist()
                highs = hist['High'].tolist()
                lows = hist['Low'].tolist()
                volumes = hist['Volume'].tolist()
                dates = [d.strftime('%m/%d/%y') if period in ['1M', '3M', '6M'] else d.strftime('%m/%y') for d in hist.index]

                # Sample data if there are too many points
                max_points = 100 if chart_type == "candle" else 80
                if len(closes) > max_points:
                    step = len(closes) // max_points
                    closes = closes[::step]
                    opens = opens[::step]
                    highs = highs[::step]
                    lows = lows[::step]
                    volumes = volumes[::step]
                    dates = dates[::step]

                # Calculate price change
                start_price = closes[0]
                end_price = closes[-1]
                change = end_price - start_price
                change_pct = (change / start_price) * 100 if start_price else 0

                # Create chart based on type
                if chart_type == "candle":
                    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), height_ratios=[3, 1], sharex=True)
                    fig.patch.set_facecolor('#1a1a2e')

                    # Candlestick chart
                    for i in range(len(closes)):
                        color = '#00C853' if closes[i] >= opens[i] else '#FF5252'
                        # Wick
                        ax1.plot([i, i], [lows[i], highs[i]], color=color, linewidth=1)
                        # Body
                        body_bottom = min(opens[i], closes[i])
                        body_height = abs(closes[i] - opens[i])
                        ax1.bar(i, body_height, bottom=body_bottom, color=color, width=0.8, edgecolor=color)

                    ax1.set_facecolor('#1a1a2e')
                    ax1.tick_params(colors='white')
                    ax1.spines['bottom'].set_color('#444')
                    ax1.spines['left'].set_color('#444')
                    ax1.spines['top'].set_visible(False)
                    ax1.spines['right'].set_visible(False)
                    ax1.grid(True, alpha=0.2, color='white')
                    ax1.set_ylabel('Price ($)', color='white')
                    ax1.set_title(f"{company_name} ({symbol}) - {period_display}", fontsize=14, fontweight='bold', color='white')

                    # Volume bars
                    colors = ['#00C853' if closes[i] >= opens[i] else '#FF5252' for i in range(len(closes))]
                    ax2.bar(range(len(volumes)), volumes, color=colors, alpha=0.7, width=0.8)
                    ax2.set_facecolor('#1a1a2e')
                    ax2.tick_params(colors='white')
                    ax2.spines['bottom'].set_color('#444')
                    ax2.spines['left'].set_color('#444')
                    ax2.spines['top'].set_visible(False)
                    ax2.spines['right'].set_visible(False)
                    ax2.set_ylabel('Volume', color='white')
                    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1e6:.0f}M' if x >= 1e6 else f'{x/1e3:.0f}K'))
                else:
                    # Line chart with volume subplot
                    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), height_ratios=[3, 1], sharex=True)
                    fig.patch.set_facecolor('#1a1a2e')

                    # Color based on overall change
                    line_color = '#00C853' if change >= 0 else '#FF5252'

                    ax1.plot(range(len(closes)), closes, linewidth=2, color=line_color)
                    ax1.fill_between(range(len(closes)), closes, alpha=0.3, color=line_color)
                    ax1.set_facecolor('#1a1a2e')
                    ax1.tick_params(colors='white')
                    ax1.spines['bottom'].set_color('#444')
                    ax1.spines['left'].set_color('#444')
                    ax1.spines['top'].set_visible(False)
                    ax1.spines['right'].set_visible(False)
                    ax1.grid(True, alpha=0.2, color='white')
                    ax1.set_ylabel('Price ($)', color='white')
                    ax1.set_title(f"{company_name} ({symbol}) - {period_display}", fontsize=14, fontweight='bold', color='white')

                    # Volume bars
                    colors = ['#00C853' if i == 0 or closes[i] >= closes[i-1] else '#FF5252' for i in range(len(closes))]
                    ax2.bar(range(len(volumes)), volumes, color=colors, alpha=0.7, width=0.8)
                    ax2.set_facecolor('#1a1a2e')
                    ax2.tick_params(colors='white')
                    ax2.spines['bottom'].set_color('#444')
                    ax2.spines['left'].set_color('#444')
                    ax2.spines['top'].set_visible(False)
                    ax2.spines['right'].set_visible(False)
                    ax2.set_ylabel('Volume', color='white')
                    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1e6:.0f}M' if x >= 1e6 else f'{x/1e3:.0f}K'))

                # X-axis labels (show ~10 labels)
                if len(dates) > 10:
                    step = len(dates) // 10
                    tick_positions = list(range(0, len(dates), step))
                    tick_labels = [dates[i] for i in tick_positions]
                else:
                    tick_positions = range(len(dates))
                    tick_labels = dates
                ax2.set_xticks(tick_positions)
                ax2.set_xticklabels(tick_labels, rotation=45, ha='right', color='white', fontsize=9)

                plt.tight_layout()

                # Save to buffer
                buf = BytesIO()
                plt.savefig(buf, format='png', dpi=150, facecolor='#1a1a2e')
                plt.close(fig)
                buf.seek(0)

                # Create embed
                color = discord.Color.green() if change >= 0 else discord.Color.red()
                arrow = "📈" if change >= 0 else "📉"
                change_str = f"+${change:.2f} (+{change_pct:.1f}%)" if change >= 0 else f"-${abs(change):.2f} ({change_pct:.1f}%)"

                # Additional stats from yfinance
                current_price = info.get('currentPrice', end_price)
                market_cap = info.get('marketCap', 0)
                pe_ratio = info.get('trailingPE', None)
                day_high = info.get('dayHigh', highs[-1] if highs else None)
                day_low = info.get('dayLow', lows[-1] if lows else None)
                fifty_two_high = info.get('fiftyTwoWeekHigh', None)
                fifty_two_low = info.get('fiftyTwoWeekLow', None)

                embed = discord.Embed(
                    title=f"{arrow} {company_name} ({symbol})",
                    description=f"**{period_display}:** ${start_price:.2f} → ${end_price:.2f} ({change_str})",
                    color=color
                )

                # Add current stats
                stats_text = f"**Current:** ${current_price:.2f}"
                if day_high and day_low:
                    stats_text += f"\n**Day Range:** ${day_low:.2f} - ${day_high:.2f}"
                if fifty_two_high and fifty_two_low:
                    stats_text += f"\n**52W Range:** ${fifty_two_low:.2f} - ${fifty_two_high:.2f}"
                if market_cap:
                    if market_cap >= 1e12:
                        cap_str = f"${market_cap/1e12:.2f}T"
                    elif market_cap >= 1e9:
                        cap_str = f"${market_cap/1e9:.2f}B"
                    else:
                        cap_str = f"${market_cap/1e6:.2f}M"
                    stats_text += f"\n**Market Cap:** {cap_str}"
                if pe_ratio:
                    stats_text += f"\n**P/E Ratio:** {pe_ratio:.2f}"

                embed.add_field(name="Stats", value=stats_text, inline=False)
                embed.set_image(url="attachment://stock_chart.png")
                embed.set_footer(text="Data from Yahoo Finance")

                file = discord.File(buf, filename="stock_chart.png")
                await ctx.send(embed=embed, file=file)

            except Exception as e:
                logger.error("Stock history error for %s: %s", symbol, e, exc_info=True)
                await ctx.send(f"❌ Stock history lookup failed: {str(e)}")

    @bot.command(name='yt', aliases=['youtube'])
    async def youtube_search(ctx, *, query: str):
        """Search YouTube and return video links: !yt rickroll"""
        async with ctx.typing():
            try:
                def do_search():
                    # Use YouTube search URL and parse results
                    search_url = f"https://www.youtube.com/results?search_query={url_quote(query)}"
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    resp = requests.get(search_url, headers=headers, timeout=10)
                    return resp.text

                html = await asyncio.to_thread(do_search)

                # Extract video IDs and titles from the page
                video_pattern = r'"videoId":"([^"]+)".*?"title":\{"runs":\[\{"text":"([^"]+)"\}'
                matches = re.findall(video_pattern, html)

                if not matches:
                    await ctx.send(f"❌ No YouTube results found for: `{query}`")
                    return

                # Deduplicate and limit to 5 results
                seen_ids = set()
                results = []
                for video_id, title in matches:
                    if video_id not in seen_ids and len(results) < 5:
                        seen_ids.add(video_id)
                        results.append({
                            "title": title,
                            "url": f"https://www.youtube.com/watch?v={video_id}"
                        })

                if not results:
                    await ctx.send(f"❌ No YouTube results found for: `{query}`")
                    return

                embed = discord.Embed(
                    title=f"🎬 YouTube: {query}",
                    color=discord.Color.red()
                )

                for i, vid in enumerate(results, 1):
                    embed.add_field(
                        name=f"{i}. {vid['title'][:100]}",
                        value=vid['url'],
                        inline=False
                    )

                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"❌ YouTube search failed: {str(e)}")

    @bot.command(name='translate', aliases=['tr'])
    async def translate_text(ctx, lang_spec: str, *, text: str):
        """Translate text: !translate es Hello, !translate en Hola, !translate fi-en moi"""
        # Using MyMemory API (free, no API key needed for low volume)
        async with ctx.typing():
            try:
                # Language code mapping for common names
                lang_map = {
                    'finnish': 'fi', 'spanish': 'es', 'french': 'fr', 'german': 'de',
                    'italian': 'it', 'portuguese': 'pt', 'russian': 'ru', 'japanese': 'ja',
                    'chinese': 'zh', 'korean': 'ko', 'arabic': 'ar', 'dutch': 'nl',
                    'swedish': 'sv', 'norwegian': 'no', 'danish': 'da', 'polish': 'pl',
                    'turkish': 'tr', 'greek': 'el', 'hebrew': 'he', 'hindi': 'hi',
                    'thai': 'th', 'vietnamese': 'vi', 'indonesian': 'id', 'czech': 'cs',
                    'romanian': 'ro', 'hungarian': 'hu', 'ukrainian': 'uk', 'english': 'en'
                }

                # Parse language specification (supports: "es", "fi-en", "spanish", "finnish-english")
                if '-' in lang_spec:
                    parts = lang_spec.lower().split('-')
                    source = lang_map.get(parts[0], parts[0])
                    target = lang_map.get(parts[1], parts[1])
                else:
                    target = lang_map.get(lang_spec.lower(), lang_spec.lower())
                    # If translating TO English, try auto-detecting source
                    # Otherwise assume source is English
                    source = 'autodetect' if target == 'en' else 'en'

                def do_translate():
                    # MyMemory free translation API
                    url = "https://api.mymemory.translated.net/get"
                    params = {
                        "q": text[:500],  # Limit text length
                        "langpair": f"{source}|{target}"
                    }
                    return requests.get(url, params=params, timeout=15)

                response = await asyncio.to_thread(do_translate)

                if response.status_code == 200:
                    data = response.json()
                    translated = data.get('responseData', {}).get('translatedText', '')
                    detected_lang = data.get('responseData', {}).get('detectedLanguage', source)

                    if translated and translated.upper() != text.upper():
                        embed = discord.Embed(
                            title="🌐 Translation",
                            color=discord.Color.blue()
                        )
                        source_display = detected_lang.upper() if source == 'autodetect' else source.upper()
                        embed.add_field(name=f"Original ({source_display})", value=text[:500], inline=False)
                        embed.add_field(name=f"Translated ({target.upper()})", value=translated[:500], inline=False)
                        await ctx.send(embed=embed)
                    else:
                        await ctx.send(f"❌ Translation failed. Try: `!translate es Hello` or `!translate en Bonjour` or `!translate fi-en moi`")
                else:
                    await ctx.send(f"❌ Translation failed. Try: `!translate es Hello` or `!translate fi-en text`")

            except Exception as e:
                await ctx.send(f"❌ Translation failed: {str(e)}")

    @bot.command(name='wiki', aliases=['wikipedia'])
    async def wikipedia_search(ctx, *, query: str):
        """Search Wikipedia and get a summary: !wiki Albert Einstein"""
        async with ctx.typing():
            try:
                def do_wiki_search():
                    # Search Wikipedia for the query
                    search_url = "https://en.wikipedia.org/w/api.php"
                    headers = {'User-Agent': 'WompBot/1.0 (Discord Bot; educational project)'}
                    search_params = {
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "format": "json",
                        "srlimit": 1
                    }
                    search_resp = requests.get(search_url, params=search_params, headers=headers, timeout=10)
                    search_data = search_resp.json()

                    if not search_data.get('query', {}).get('search'):
                        return None, None, None

                    # Get the page title from search results
                    page_title = search_data['query']['search'][0]['title']

                    # Get the summary/extract for that page
                    summary_params = {
                        "action": "query",
                        "prop": "extracts|info",
                        "exintro": True,
                        "explaintext": True,
                        "exsentences": 4,
                        "titles": page_title,
                        "format": "json",
                        "inprop": "url"
                    }
                    summary_resp = requests.get(search_url, params=summary_params, headers=headers, timeout=10)
                    summary_data = summary_resp.json()

                    pages = summary_data.get('query', {}).get('pages', {})
                    if not pages:
                        return None, None, None

                    page = list(pages.values())[0]
                    title = page.get('title', query)
                    extract = page.get('extract', 'No summary available.')
                    url = page.get('fullurl', f"https://en.wikipedia.org/wiki/{url_quote(title)}")

                    return title, extract, url

                title, extract, url = await asyncio.to_thread(do_wiki_search)

                if not title:
                    await ctx.send(f"❌ No Wikipedia article found for: `{query}`")
                    return

                # Truncate extract if too long
                if len(extract) > 1000:
                    extract = extract[:997] + "..."

                embed = discord.Embed(
                    title=f"📚 {title}",
                    description=extract,
                    url=url,
                    color=discord.Color.from_rgb(255, 255, 255)
                )
                embed.set_footer(text="Source: Wikipedia")

                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"❌ Wikipedia search failed: {str(e)}")

    # Wolfram Alpha command (only if wolfram is configured)
    if wolfram:
        @bot.command(name='wa', aliases=['wolfram', 'calc', 'calculate'])
        async def wolfram_query(ctx, *, query: str):
            """Query Wolfram Alpha: !wa 2+2, !wa convert 5 miles to km, !wa population of Japan"""
            async with ctx.typing():
                try:
                    def do_query():
                        # Query with both metric and imperial for comparison
                        metric = wolfram.query(query, units="metric")
                        imperial = wolfram.query(query, units="imperial")
                        return metric, imperial

                    metric_result, imperial_result = await asyncio.to_thread(do_query)

                    if not metric_result.get('success') and not imperial_result.get('success'):
                        await ctx.send(f"❌ Wolfram Alpha couldn't answer: `{query}`\nTry rephrasing or ask something like: `!wa 2+2` or `!wa convert 100 F to C`")
                        return

                    # Use whichever succeeded
                    result = metric_result if metric_result.get('success') else imperial_result
                    answer = result.get('answer', 'No answer available')

                    # Check if metric and imperial answers differ (unit-dependent query)
                    if (metric_result.get('success') and imperial_result.get('success') and
                        metric_result.get('answer') != imperial_result.get('answer')):
                        # Show both for unit-dependent results
                        embed = discord.Embed(
                            title="🔢 Wolfram Alpha",
                            color=discord.Color.orange()
                        )
                        embed.add_field(name="Query", value=query[:200], inline=False)
                        embed.add_field(name="Metric", value=metric_result.get('answer', 'N/A')[:500], inline=True)
                        embed.add_field(name="Imperial", value=imperial_result.get('answer', 'N/A')[:500], inline=True)
                    else:
                        # Single answer
                        embed = discord.Embed(
                            title="🔢 Wolfram Alpha",
                            description=answer[:2000],
                            color=discord.Color.orange()
                        )
                        embed.add_field(name="Query", value=query[:200], inline=False)

                    embed.set_footer(text="Powered by Wolfram Alpha")
                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"❌ Wolfram Alpha query failed: {str(e)}")

    logger.info("Prefix commands registered")

    # ===== Register sub-module prefix commands =====
    from commands.prefix_admin import register_prefix_admin_commands
    register_prefix_admin_commands(bot, db)

    from commands.prefix_features import register_prefix_feature_commands
    register_prefix_feature_commands(
        bot, db,
        claims_tracker=claims_tracker,
        hot_takes_tracker=hot_takes_tracker,
        reminder_system=reminder_system,
        event_system=event_system,
        qotd=qotd,
        rag=rag,
        message_scheduler=message_scheduler,
        stats_viz=stats_viz
    )

    from commands.prefix_games import register_prefix_game_commands
    register_prefix_game_commands(
        bot, db,
        llm=llm,
        debate_scorekeeper=debate_scorekeeper,
        trivia=trivia,
        poll_system=poll_system,
        who_said_it=who_said_it,
        devils_advocate=devils_advocate,
        jeopardy=jeopardy,
        iracing_viz=iracing_viz,
        chat_stats=chat_stats,
        stats_viz=stats_viz
    )

    from commands.prefix_monitoring import register_prefix_monitoring_commands
    register_prefix_monitoring_commands(
        bot, db,
        rss_monitor=rss_monitor,
        github_monitor=github_monitor,
        watchlist_manager=watchlist_manager
    )
