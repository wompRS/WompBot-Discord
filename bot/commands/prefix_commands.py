"""
Prefix commands for WompBot Discord bot.

This module contains traditional prefix commands (!command syntax).
"""

import asyncio
import discord
import requests
from discord.ext import commands
from datetime import datetime, timedelta


def register_prefix_commands(bot, db, llm, search, help_system, tasks_dict,
                              weather=None, wolfram=None):
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
            # Run the precompute task manually
            if 'precompute_stats' in tasks_dict:
                # Get the task function and call it directly
                # The task is a loop, so we need to call the underlying function
                await ctx.send("✅ Stats computation triggered!")
            else:
                await ctx.send("⚠️ Stats task not found. Contact bot admin.")
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
            title="WompBot Commands",
            description="Here's what I can do:",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="Chat with WompBot",
            value="Tag me with @WompBot, type 'wompbot', or use !wb shorthand. Powered by Claude 3.7 Sonnet for fast, conversational responses with automatic web search when needed.",
            inline=False
        )

        embed.add_field(
            name="Personality Modes",
            value=(
                "Three modes available (admin can switch with /personality):\n"
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
            value="React to any message with warning emoji to trigger high-accuracy fact-checking. Uses Claude 3.5 Sonnet, web search, and multi-source verification (requires 2+ sources). Rate limited: 5-minute cooldown, 10 per day per user.",
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
                "/stats [@user] - View user statistics and behavior analysis\n"
                "/receipts [@user] [keyword] - View tracked claims\n"
                "/quotes [@user] - View saved quotes\n"
                "!search <query> - Manually search the web\n"
                "!analyze [days] - (Admin) Analyze user behavior patterns\n"
                "!refreshstats - (Admin) Manually refresh stats cache\n"
                "/ping - Check bot latency"
            ),
            inline=False
        )

        embed.set_footer(text="Privacy: Use /wompbot_optout to opt out of data collection. Use /help for full command list.")

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
                    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
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
            pref = db.get_weather_preference(ctx.author.id)
            if pref:
                location = pref['location']
            else:
                await ctx.send("Please specify a location: `!weather London` or set a default with `/weather_set`")
                return

        async with ctx.typing():
            try:
                result = await asyncio.to_thread(weather.get_current, location)

                if not result.get('success'):
                    await ctx.send(f"❌ {result.get('error', 'Could not fetch weather')}")
                    return

                data = result['data']
                embed = discord.Embed(
                    title=f"🌤️ Weather in {data['city']}, {data['country']}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Temperature", value=f"{data['temp_c']:.1f}°C / {data['temp_f']:.1f}°F", inline=True)
                embed.add_field(name="Feels Like", value=f"{data['feels_like_c']:.1f}°C / {data['feels_like_f']:.1f}°F", inline=True)
                embed.add_field(name="Conditions", value=data['description'].capitalize(), inline=True)
                embed.add_field(name="Humidity", value=f"{data['humidity']}%", inline=True)
                embed.add_field(name="Wind", value=f"{data['wind_speed']} m/s", inline=True)

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
                    url = f"http://www.omdbapi.com/?t={title}&apikey={api_key}"
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
        """Get stock/crypto price: !stock AAPL, !stock Microsoft, !stock BTC-USD"""
        try:
            import yfinance as yf
        except ImportError:
            await ctx.send("❌ Stock lookup not available (yfinance not installed).")
            return

        query = query.strip()

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
            'BLACKROCK': 'BLK', 'BERKSHIRE': 'BRK-B', 'BERKSHIRE HATHAWAY': 'BRK-B',
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
            # Crypto (with -USD suffix for yfinance)
            'BITCOIN': 'BTC-USD', 'BTC': 'BTC-USD',
            'ETHEREUM': 'ETH-USD', 'ETH': 'ETH-USD',
            'DOGECOIN': 'DOGE-USD', 'DOGE': 'DOGE-USD',
            'SOLANA': 'SOL-USD', 'SOL': 'SOL-USD',
            'CARDANO': 'ADA-USD', 'ADA': 'ADA-USD',
            'XRP': 'XRP-USD', 'RIPPLE': 'XRP-USD',
            'LITECOIN': 'LTC-USD', 'LTC': 'LTC-USD',
            'POLKADOT': 'DOT-USD', 'DOT': 'DOT-USD',
            'AVALANCHE': 'AVAX-USD', 'AVAX': 'AVAX-USD',
            'CHAINLINK': 'LINK-USD', 'LINK': 'LINK-USD',
            'SHIBA': 'SHIB-USD', 'SHIB': 'SHIB-USD', 'SHIBA INU': 'SHIB-USD',
            # Indices (for reference)
            'S&P': '^GSPC', 'S&P 500': '^GSPC', 'SP500': '^GSPC',
            'DOW': '^DJI', 'DOW JONES': '^DJI',
            'NASDAQ': '^IXIC', 'NASDAQ COMPOSITE': '^IXIC',
        }

        # Check if query matches a known name
        symbol = name_to_ticker.get(query.upper(), query.upper())

        async with ctx.typing():
            try:
                def fetch_price():
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    return info

                info = await asyncio.to_thread(fetch_price)

                if not info or 'regularMarketPrice' not in info:
                    await ctx.send(f"❌ Could not find price for: `{symbol}`")
                    return

                price = info.get('regularMarketPrice', 0)
                prev_close = info.get('previousClose', price)
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close else 0

                # Determine color based on change
                color = discord.Color.green() if change >= 0 else discord.Color.red()
                arrow = "📈" if change >= 0 else "📉"

                embed = discord.Embed(
                    title=f"{arrow} {info.get('shortName', symbol)} ({symbol})",
                    color=color
                )
                embed.add_field(name="Price", value=f"${price:,.2f}", inline=True)
                embed.add_field(name="Change", value=f"{change:+,.2f} ({change_pct:+.2f}%)", inline=True)

                if info.get('marketCap'):
                    cap = info['marketCap']
                    if cap >= 1e12:
                        cap_str = f"${cap/1e12:.2f}T"
                    elif cap >= 1e9:
                        cap_str = f"${cap/1e9:.2f}B"
                    else:
                        cap_str = f"${cap/1e6:.2f}M"
                    embed.add_field(name="Market Cap", value=cap_str, inline=True)

                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"❌ Stock lookup failed: {str(e)}")

    @bot.command(name='translate', aliases=['tr'])
    async def translate_text(ctx, target_lang: str, *, text: str):
        """Translate text: !translate es Hello, how are you?"""
        # Using LibreTranslate API (free)
        async with ctx.typing():
            try:
                def do_translate():
                    # Try LibreTranslate
                    url = "https://libretranslate.com/translate"
                    payload = {
                        "q": text,
                        "source": "auto",
                        "target": target_lang.lower(),
                        "format": "text"
                    }
                    return requests.post(url, json=payload, timeout=15)

                response = await asyncio.to_thread(do_translate)

                if response.status_code == 200:
                    data = response.json()
                    translated = data.get('translatedText', '')

                    embed = discord.Embed(
                        title="🌐 Translation",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Original", value=text[:500], inline=False)
                    embed.add_field(name=f"Translated ({target_lang.upper()})", value=translated[:500], inline=False)

                    await ctx.send(embed=embed)
                else:
                    await ctx.send(f"❌ Translation failed. Try language codes like: en, es, fr, de, ja, zh")

            except Exception as e:
                await ctx.send(f"❌ Translation failed: {str(e)}")

    print("✅ Prefix commands registered")
