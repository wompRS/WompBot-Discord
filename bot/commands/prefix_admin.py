"""
Prefix admin commands for WompBot Discord bot.

Converts admin-related slash commands to prefix (!) commands:
  !whoami, !setadmin, !removeadmin, !admins, !personality,
  !bug, !bugs, !bug_resolve
"""

import discord
from discord.ext import commands
from commands.prefix_utils import is_bot_admin_ctx, parse_choice
from features.admin_utils import is_super_admin, SUPER_ADMIN_IDS


def register_prefix_admin_commands(bot, db):
    """
    Register admin-related prefix commands with the bot.

    Args:
        bot: Discord bot instance
        db: Database instance
    """

    # ==================== User Info ====================

    @bot.command(name='whoami')
    async def whoami(ctx):
        """Show your Discord user information"""
        is_admin = is_bot_admin_ctx(db, ctx)
        admin_status = "Yes (Bot Admin)" if is_admin else "No"

        await ctx.send(
            f"**Your Discord Information:**\n"
            f"- Username: {ctx.author.name}\n"
            f"- Display Name: {ctx.author.display_name}\n"
            f"- User ID: `{ctx.author.id}`\n"
            f"- Mention: {ctx.author.mention}\n"
            f"- Bot Admin: {admin_status}"
        )

    # ==================== Bot Admin Management Commands ====================

    @bot.command(name='setadmin')
    async def setadmin(ctx, user: discord.Member):
        """Add a bot admin for this server. Usage: !setadmin @user"""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        # Check if caller is already an admin or super admin
        if not is_bot_admin_ctx(db, ctx):
            # Allow Discord server owner to add first admin
            if ctx.guild.owner_id != ctx.author.id:
                await ctx.send(
                    "You don't have permission to add bot admins.\n"
                    "Only existing bot admins or the server owner can add new admins."
                )
                return

        # Can't add bots as admins
        if user.bot:
            await ctx.send("Bots cannot be bot admins.")
            return

        # Add the admin
        success = db.add_server_admin(ctx.guild.id, user.id, ctx.author.id)

        if success:
            await ctx.send(
                f"**{user.display_name}** is now a bot admin for this server.\n"
                f"They can now use admin-only bot commands like `!personality`, `!bug`, etc."
            )
        else:
            await ctx.send(
                f"**{user.display_name}** is already a bot admin for this server."
            )

    @setadmin.error
    async def setadmin_error(ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `!setadmin @user`")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("Could not find that member. Make sure to mention them or use their exact name.")

    @bot.command(name='removeadmin')
    async def removeadmin(ctx, user: discord.Member):
        """Remove a bot admin from this server. Usage: !removeadmin @user"""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        # Only super admins or the server owner can remove admins
        if not is_super_admin(ctx.author.id) and ctx.guild.owner_id != ctx.author.id:
            await ctx.send(
                "Only super admins or the server owner can remove bot admins."
            )
            return

        # Can't remove super admins from the list (they're not in the database)
        if is_super_admin(user.id):
            await ctx.send(
                f"**{user.display_name}** is a super admin and cannot be removed."
            )
            return

        # Remove the admin
        success = db.remove_server_admin(ctx.guild.id, user.id)

        if success:
            await ctx.send(
                f"**{user.display_name}** is no longer a bot admin for this server."
            )
        else:
            await ctx.send(
                f"**{user.display_name}** was not a bot admin for this server."
            )

    @removeadmin.error
    async def removeadmin_error(ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: `!removeadmin @user`")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("Could not find that member. Make sure to mention them or use their exact name.")

    @bot.command(name='admins')
    async def admins(ctx):
        """List bot admins for this server"""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        async with ctx.typing():
            # Get server-specific admins
            server_admins = db.get_server_admins(ctx.guild.id)

            embed = discord.Embed(
                title="Bot Admins",
                description="Users who can use admin-only bot commands in this server",
                color=discord.Color.blue()
            )

            # Super admins section
            super_admin_lines = []
            for admin_id in SUPER_ADMIN_IDS:
                member = ctx.guild.get_member(admin_id)
                if member:
                    super_admin_lines.append(f"- {member.mention} (Super Admin)")
                else:
                    super_admin_lines.append(f"- User ID `{admin_id}` (Super Admin, not in server)")

            if super_admin_lines:
                embed.add_field(
                    name="Super Admins",
                    value="\n".join(super_admin_lines) or "None",
                    inline=False
                )

            # Server admins section
            admin_lines = []
            for admin in server_admins:
                member = ctx.guild.get_member(admin['user_id'])
                if member:
                    admin_lines.append(f"- {member.mention}")
                else:
                    admin_lines.append(f"- User ID `{admin['user_id']}` (left server)")

            embed.add_field(
                name="Server Admins",
                value="\n".join(admin_lines) if admin_lines else "No server-specific admins set.\nUse `!setadmin @user` to add one.",
                inline=False
            )

            embed.set_footer(text="Server owner can always add/remove admins")
            await ctx.send(embed=embed)

    # ==================== Personality Command ====================

    @bot.command(name='personality')
    async def personality(ctx, mode: str = None):
        """Change bot personality mode (Admin only). Usage: !personality <default|concise|bogan>"""
        # Check if user is a bot admin
        if not is_bot_admin_ctx(db, ctx):
            await ctx.send(
                "You don't have permission to change the bot's personality.\n"
                "Only bot admins can use this command."
            )
            return

        valid_modes = ['default', 'concise', 'bogan']

        if mode is None:
            await ctx.send(
                "**Usage:** `!personality <mode>`\n\n"
                "**Available modes:**\n"
                "- `default` - Conversational\n"
                "- `concise` - Brief responses\n"
                "- `bogan` - Australian Bogan"
            )
            return

        personality_value = parse_choice(mode, valid_modes)
        if personality_value is None:
            await ctx.send(
                f"Invalid mode `{mode}`. Valid modes are: {', '.join(valid_modes)}"
            )
            return

        try:
            server_id = ctx.guild.id

            # Update database
            success = db.set_server_personality(server_id, personality_value, ctx.author.id)

            if success:
                if personality_value == 'bogan':
                    await ctx.send(
                        "**Personality changed to Australian Bogan**\n\n"
                        "The bot will now respond with:\n"
                        "- Full-on Aussie bogan speak\n"
                        "- Heaps of slang and colloquialisms\n"
                        "- 'Yeah nah' and 'she'll be right' energy\n"
                        "- Calls everyone 'mate' and 'legend'\n"
                        "- Still helpful, just sounds like a pub chat\n\n"
                        "*\"Yeah nah mate, she'll be right!\"*"
                    )
                elif personality_value == 'concise':
                    await ctx.send(
                        "**Personality changed to Concise**\n\n"
                        "The bot will now respond with:\n"
                        "- Very brief responses (1-2 sentences)\n"
                        "- Straight to the point, no fluff\n"
                        "- Simple statements get simple acknowledgments\n"
                        "- No unnecessary explanation\n"
                        "- Economical with words"
                    )
                else:
                    await ctx.send(
                        "**Personality changed to Default (Conversational)**\n\n"
                        "The bot will now respond with:\n"
                        "- Conversational and friendly tone\n"
                        "- Helpful and informative\n"
                        "- Direct and honest\n"
                        "- Focused on providing value"
                    )
            else:
                await ctx.send("Error updating personality setting")

        except Exception as e:
            await ctx.send(f"Error changing personality: {e}")

    # ==================== Bug Tracking Commands ====================

    from bug_tracker import report_bug, list_bugs, resolve_bug, get_bug, get_stats

    @bot.command(name='bug')
    async def bug(ctx, *, args: str = None):
        """Report a bug (Admin only). Usage: !bug <description> [--priority low|normal|high|critical]"""
        if not is_bot_admin_ctx(db, ctx):
            await ctx.send("Only bot admins can report bugs.")
            return

        if not args:
            await ctx.send(
                "**Usage:** `!bug <description> [--priority low|normal|high|critical]`\n\n"
                "Example: `!bug The weather command crashes when no city is given --priority high`"
            )
            return

        # Parse --priority flag from the description
        priority_val = "normal"
        description = args
        valid_priorities = ['low', 'normal', 'high', 'critical']

        if '--priority' in args.lower():
            # Split on --priority (case-insensitive)
            import re
            match = re.search(r'--priority\s+(\S+)', args, re.IGNORECASE)
            if match:
                parsed_priority = parse_choice(match.group(1), valid_priorities, default="normal")
                if parsed_priority:
                    priority_val = parsed_priority
                # Remove the --priority flag and its value from the description
                description = re.sub(r'\s*--priority\s+\S+', '', args, flags=re.IGNORECASE).strip()

        if not description:
            await ctx.send("Please provide a bug description.")
            return

        guild_name = ctx.guild.name if ctx.guild else "DM"
        channel_name = ctx.channel.name if hasattr(ctx.channel, 'name') else "DM"

        bug_id = report_bug(
            description=description,
            reporter=str(ctx.author),
            guild_name=guild_name,
            channel_name=channel_name,
            priority=priority_val
        )

        priority_emoji = {"low": "🟢", "normal": "🟡", "high": "🟠", "critical": "🔴"}.get(priority_val, "🟡")

        await ctx.send(
            f"**Bug Tracked**\n\n"
            f"**Bug ID:** `#{bug_id}`\n"
            f"**Priority:** {priority_emoji} {priority_val.capitalize()}\n"
            f"**Description:** {description}\n\n"
            f"*Use `!bugs` to view all tracked bugs*"
        )

    @bot.command(name='bugs')
    async def bugs(ctx, status: str = None, limit: int = 10):
        """List tracked bugs (Admin only). Usage: !bugs [all|open|fixed|wontfix] [limit]"""
        if not is_bot_admin_ctx(db, ctx):
            await ctx.send("Only bot admins can view bugs.")
            return

        valid_statuses = ['all', 'open', 'fixed', 'wontfix']
        status_val = None

        if status is not None:
            parsed_status = parse_choice(status, valid_statuses)
            if parsed_status is None:
                await ctx.send(
                    f"Invalid status `{status}`. Valid statuses are: {', '.join(valid_statuses)}"
                )
                return
            if parsed_status != 'all':
                status_val = parsed_status

        bugs_list_result = list_bugs(status=status_val, limit=limit)

        if not bugs_list_result:
            await ctx.send("No bugs found!")
            return

        stats = get_stats()
        status_emoji = {"open": "🔴", "fixed": "✅", "wontfix": "⚪", "duplicate": "🔁", "invalid": "❌"}
        priority_emoji = {"low": "🟢", "normal": "🟡", "high": "🟠", "critical": "🔴"}

        embed = discord.Embed(
            title="Bug Tracker",
            description=f"**Open:** {stats['open']} | **Fixed:** {stats['fixed']} | **Total:** {stats['total']}",
            color=discord.Color.red() if stats['open'] > 0 else discord.Color.green()
        )

        for bug_item in bugs_list_result[:10]:  # Max 10 in embed
            s_emoji = status_emoji.get(bug_item['status'], "?")
            p_emoji = priority_emoji.get(bug_item['priority'], "🟡")
            created = bug_item['created_at'][:10] if bug_item['created_at'] else "Unknown"

            embed.add_field(
                name=f"{s_emoji} #{bug_item['id']} - {p_emoji} {bug_item['priority'].capitalize()}",
                value=f"{bug_item['description'][:100]}{'...' if len(bug_item['description']) > 100 else ''}\n*{created}*",
                inline=False
            )

        await ctx.send(embed=embed)

    @bot.command(name='bug_resolve')
    async def bug_resolve_cmd(ctx, bug_id: int = None, resolution: str = None):
        """Resolve a bug (Admin only). Usage: !bug_resolve <id> <fixed|wontfix|duplicate|invalid>"""
        if not is_bot_admin_ctx(db, ctx):
            await ctx.send("Only bot admins can resolve bugs.")
            return

        if bug_id is None or resolution is None:
            await ctx.send(
                "**Usage:** `!bug_resolve <bug_id> <resolution>`\n\n"
                "**Resolutions:** `fixed`, `wontfix`, `duplicate`, `invalid`\n"
                "Example: `!bug_resolve 42 fixed`"
            )
            return

        valid_resolutions = ['fixed', 'wontfix', 'duplicate', 'invalid']
        resolution_val = parse_choice(resolution, valid_resolutions)
        if resolution_val is None:
            await ctx.send(
                f"Invalid resolution `{resolution}`. Valid resolutions are: {', '.join(valid_resolutions)}"
            )
            return

        bug_item = get_bug(bug_id)
        if not bug_item:
            await ctx.send(f"Bug #{bug_id} not found.")
            return

        success = resolve_bug(bug_id, resolution_val)

        if success:
            resolution_emoji = {"fixed": "✅", "wontfix": "⚪", "duplicate": "🔁", "invalid": "❌"}.get(resolution_val, "✅")
            await ctx.send(
                f"{resolution_emoji} **Bug #{bug_id} marked as {resolution_val}**\n\n"
                f"*{bug_item['description'][:100]}*"
            )
        else:
            await ctx.send(f"Failed to resolve bug #{bug_id}")

    @bug_resolve_cmd.error
    async def bug_resolve_error(ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("**Usage:** `!bug_resolve <bug_id> <resolution>`\nBug ID must be a number.")

    print("Prefix admin commands registered")
