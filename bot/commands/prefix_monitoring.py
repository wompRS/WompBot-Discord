"""
Prefix commands for monitoring features: RSS feeds, GitHub repos, price watchlists.
All admin-only commands.
"""

import discord
from commands.prefix_utils import is_bot_admin_ctx


def register_prefix_monitoring_commands(bot, db, rss_monitor=None,
                                         github_monitor=None,
                                         watchlist_manager=None):
    """Register prefix commands for monitoring features."""

    # ===== RSS Feed Monitoring (Admin Only) =====
    if rss_monitor:
        @bot.command(name='feedadd')
        async def feedadd_cmd(ctx, url: str, channel: discord.TextChannel = None):
            """[Admin] Add an RSS feed. Usage: !feedadd <url> [#channel]"""
            if not is_bot_admin_ctx(db, ctx):
                await ctx.send("❌ Admin only.")
                return

            async with ctx.typing():
                try:
                    target_channel = channel or ctx.channel
                    result = await rss_monitor.add_feed(
                        guild_id=ctx.guild.id,
                        channel_id=target_channel.id,
                        feed_url=url,
                        added_by=ctx.author.id
                    )

                    if result.get('error'):
                        await ctx.send(f"❌ {result['error']}")
                        return

                    status = "Reactivated" if result.get('reactivated') else "Added"
                    await ctx.send(
                        f"📡 {status} RSS feed: **{result['title']}**\n"
                        f"🔗 {result['url']}\n"
                        f"📢 Updates will post to <#{target_channel.id}>\n"
                        f"Feed ID: #{result['feed_id']}"
                    )

                except Exception as e:
                    await ctx.send(f"❌ Error: {str(e)}")

        @bot.command(name='feedremove')
        async def feedremove_cmd(ctx, feed_id: int):
            """[Admin] Remove an RSS feed. Usage: !feedremove <id>"""
            if not is_bot_admin_ctx(db, ctx):
                await ctx.send("❌ Admin only.")
                return

            try:
                result = await rss_monitor.remove_feed(ctx.guild.id, feed_id)

                if result.get('error'):
                    await ctx.send(f"❌ {result['error']}")
                    return

                await ctx.send(f"✅ Removed feed: **{result['title']}** (#{feed_id})")

            except Exception as e:
                await ctx.send(f"❌ Error: {str(e)}")

        @bot.command(name='feeds')
        async def feeds_cmd(ctx):
            """[Admin] List monitored RSS feeds. Usage: !feeds"""
            if not is_bot_admin_ctx(db, ctx):
                await ctx.send("❌ Admin only.")
                return

            try:
                feeds = await rss_monitor.list_feeds(ctx.guild.id)

                if not feeds:
                    await ctx.send("📡 No RSS feeds being monitored. Use `!feedadd` to add one!")
                    return

                embed = discord.Embed(
                    title="📡 Monitored RSS Feeds",
                    color=discord.Color.orange()
                )

                for feed in feeds:
                    last_check = feed['last_checked'].strftime("%b %d %I:%M %p") if feed['last_checked'] else "Never"
                    embed.add_field(
                        name=f"#{feed['id']} — {feed['feed_title']}",
                        value=f"🔗 {feed['feed_url']}\n📢 <#{feed['channel_id']}> • Last checked: {last_check}",
                        inline=False
                    )

                embed.set_footer(text=f"{len(feeds)} feeds • Checked every 5 minutes")
                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"❌ Error: {str(e)}")

        print("✅ RSS feed prefix commands registered")

    # ===== GitHub Monitoring (Admin Only) =====
    if github_monitor:
        @bot.command(name='ghwatch')
        async def ghwatch_cmd(ctx, repo: str, watch_type: str = 'all',
                              channel: discord.TextChannel = None):
            """[Admin] Watch a GitHub repo. Usage: !ghwatch owner/repo [releases|issues|prs|all] [#channel]"""
            if not is_bot_admin_ctx(db, ctx):
                await ctx.send("❌ Admin only.")
                return

            valid_types = ['releases', 'issues', 'prs', 'all']
            if watch_type.lower() not in valid_types:
                await ctx.send(f"❌ Invalid watch type. Use: {', '.join(valid_types)}")
                return

            async with ctx.typing():
                try:
                    target_channel = channel or ctx.channel
                    result = await github_monitor.add_watch(
                        guild_id=ctx.guild.id,
                        channel_id=target_channel.id,
                        repo=repo,
                        watch_type=watch_type.lower(),
                        added_by=ctx.author.id
                    )

                    if result.get('error'):
                        await ctx.send(f"❌ {result['error']}")
                        return

                    status = "Reactivated" if result.get('reactivated') else "Now watching"
                    await ctx.send(
                        f"🐙 {status}: **{result['repo']}** ({result['watch_type']})\n"
                        f"📢 Updates will post to <#{target_channel.id}>\n"
                        f"Watch ID: #{result['watch_id']}"
                    )

                except Exception as e:
                    await ctx.send(f"❌ Error: {str(e)}")

        @bot.command(name='ghunwatch')
        async def ghunwatch_cmd(ctx, watch_id: int):
            """[Admin] Stop watching a GitHub repo. Usage: !ghunwatch <id>"""
            if not is_bot_admin_ctx(db, ctx):
                await ctx.send("❌ Admin only.")
                return

            try:
                result = await github_monitor.remove_watch(ctx.guild.id, watch_id)

                if result.get('error'):
                    await ctx.send(f"❌ {result['error']}")
                    return

                await ctx.send(
                    f"✅ Stopped watching: **{result['repo']}** ({result['watch_type']}) (#{watch_id})"
                )

            except Exception as e:
                await ctx.send(f"❌ Error: {str(e)}")

        @bot.command(name='ghwatches')
        async def ghwatches_cmd(ctx):
            """[Admin] List watched GitHub repos. Usage: !ghwatches"""
            if not is_bot_admin_ctx(db, ctx):
                await ctx.send("❌ Admin only.")
                return

            try:
                watches = await github_monitor.list_watches(ctx.guild.id)

                if not watches:
                    await ctx.send("🐙 No GitHub repos being watched. Use `!ghwatch` to add one!")
                    return

                embed = discord.Embed(
                    title="🐙 Watched GitHub Repos",
                    color=discord.Color.dark_grey()
                )

                for watch in watches:
                    last_check = watch['last_checked'].strftime("%b %d %I:%M %p") if watch['last_checked'] else "Never"
                    embed.add_field(
                        name=f"#{watch['id']} — {watch['repo_full_name']}",
                        value=f"👀 {watch['watch_type']} • 📢 <#{watch['channel_id']}> • Last checked: {last_check}",
                        inline=False
                    )

                embed.set_footer(text=f"{len(watches)} watches • Checked every 5 minutes")
                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"❌ Error: {str(e)}")

        print("✅ GitHub monitoring prefix commands registered")

    # ===== Shared Watchlists =====
    if watchlist_manager:
        @bot.command(name='wladd')
        async def wladd_cmd(ctx, *, args: str):
            """[Admin] Add symbols to watchlist. Usage: !wladd AAPL TSLA BTC [threshold=5]"""
            if not is_bot_admin_ctx(db, ctx):
                await ctx.send("❌ Admin only.")
                return

            async with ctx.typing():
                try:
                    # Parse threshold from args if present
                    parts = args.split()
                    threshold = 5.0
                    symbol_parts = []

                    for part in parts:
                        if part.startswith('threshold='):
                            try:
                                threshold = float(part.split('=')[1])
                            except ValueError:
                                pass
                        else:
                            symbol_parts.append(part.upper())

                    if not symbol_parts:
                        await ctx.send("❌ No symbols provided! Usage: `!wladd AAPL TSLA BTC [threshold=5]`")
                        return

                    if len(symbol_parts) > 10:
                        await ctx.send("❌ Max 10 symbols at a time!")
                        return

                    result = await watchlist_manager.add_symbols(
                        guild_id=ctx.guild.id,
                        channel_id=ctx.channel.id,
                        symbols=symbol_parts,
                        added_by=ctx.author.id,
                        alert_threshold=threshold
                    )

                    msg_parts = []
                    if result['added']:
                        added_str = ", ".join(
                            f"**{s['symbol']}** (${s['price']:,.2f})"
                            for s in result['added']
                        )
                        msg_parts.append(f"✅ Added: {added_str}")

                    if result['errors']:
                        error_str = "\n".join(f"❌ {e}" for e in result['errors'])
                        msg_parts.append(error_str)

                    msg_parts.append(f"\n📢 Alerts (±{threshold}%) will post to <#{ctx.channel.id}>")
                    await ctx.send("\n".join(msg_parts))

                except Exception as e:
                    await ctx.send(f"❌ Error: {str(e)}")

        @bot.command(name='wlremove')
        async def wlremove_cmd(ctx, symbol: str):
            """[Admin] Remove a symbol from watchlist. Usage: !wlremove AAPL"""
            if not is_bot_admin_ctx(db, ctx):
                await ctx.send("❌ Admin only.")
                return

            try:
                result = await watchlist_manager.remove_symbol(ctx.guild.id, symbol)

                if result.get('error'):
                    await ctx.send(f"❌ {result['error']}")
                    return

                await ctx.send(f"✅ Removed **{result['symbol']}** from watchlist.")

            except Exception as e:
                await ctx.send(f"❌ Error: {str(e)}")

        @bot.command(name='watchlist', aliases=['wl'])
        async def watchlist_cmd(ctx):
            """View the server's price watchlist. Usage: !watchlist"""
            try:
                items = await watchlist_manager.get_watchlist(ctx.guild.id)

                if not items:
                    await ctx.send("💹 No symbols on watchlist. Use `!wladd` to add some!")
                    return

                embed = discord.Embed(
                    title="💹 Price Watchlist",
                    color=discord.Color.blue()
                )

                lines = []
                for item in items:
                    if item['last_price'] and item['last_price'] >= 1:
                        price_str = f"${item['last_price']:,.2f}"
                    elif item['last_price']:
                        price_str = f"${item['last_price']:.6f}"
                    else:
                        price_str = "N/A"
                    type_emoji = "🪙" if item['symbol_type'] == 'crypto' else "📊"
                    lines.append(
                        f"{type_emoji} **{item['symbol']}** — {price_str} (±{item['alert_threshold']}% alert)"
                    )

                embed.description = "\n".join(lines)
                embed.set_footer(text=f"{len(items)} symbols • Checked every minute for alerts")
                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"❌ Error: {str(e)}")

        print("✅ Watchlist prefix commands registered")
