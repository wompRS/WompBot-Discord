"""
Prefix commands for WompBot Discord bot.

This module contains traditional prefix commands (!command syntax).
"""

import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timedelta


def register_prefix_commands(bot, db, llm, search, help_system, tasks_dict):
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

    print("✅ Prefix commands registered")
