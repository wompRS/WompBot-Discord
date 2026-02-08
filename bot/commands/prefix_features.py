"""
Prefix feature commands for WompBot Discord bot.

This module contains prefix commands (! syntax) for feature-related commands:
- Claims & Hot Takes
- Reminders & Events
- User Features (myfacts, forget, qotd, weather prefs)
- Message Scheduling
"""

import discord
from discord.ext import commands
from datetime import datetime, timedelta
from commands.prefix_utils import is_bot_admin_ctx, parse_choice


def register_prefix_feature_commands(bot, db, claims_tracker=None, hot_takes_tracker=None,
                                     reminder_system=None, event_system=None, qotd=None,
                                     rag=None, message_scheduler=None, stats_viz=None):
    """
    Register prefix commands for bot features.

    Args:
        bot: Discord bot instance
        db: Database instance
        claims_tracker: Claims tracking system
        hot_takes_tracker: Hot takes tracking system
        reminder_system: Reminder management system
        event_system: Event scheduling system
        qotd: Quote of the day system
        rag: RAG system for user facts
        message_scheduler: Message scheduling system
        stats_viz: Statistics visualization system
    """

    # =============== CLAIMS & HOT TAKES ===============

    if claims_tracker:
        @bot.command(name='receipts', aliases=['claims'])
        async def receipts_cmd(ctx, user: discord.Member = None, *, keyword: str = None):
            """View tracked claims for a user.
            Usage: !receipts [@user] [keyword]
            """
            target = user or ctx.author

            async with ctx.typing():
                try:
                    claims = await claims_tracker.get_user_claims(target.id)

                    if not claims:
                        await ctx.send(f"No tracked claims found for {target.display_name}")
                        return

                    # Filter by keyword if provided
                    if keyword:
                        keyword_lower = keyword.lower()
                        claims = [c for c in claims if keyword_lower in c['claim_text'].lower()]

                        if not claims:
                            await ctx.send(f"No claims found for {target.display_name} matching '{keyword}'")
                            return

                    # Create embed with claims
                    embed = discord.Embed(
                        title=f"Claims by {target.display_name}",
                        color=discord.Color.blue()
                    )

                    if keyword:
                        embed.description = f"Filtered by: {keyword}"

                    for i, claim in enumerate(claims[:10], 1):  # Show max 10
                        status_emoji = {
                            'unverified': '?',
                            'true': 'TRUE',
                            'false': 'FALSE',
                            'mixed': 'MIXED',
                            'outdated': 'OLD'
                        }.get(claim['verification_status'], '?')

                        edited_marker = " (edited)" if claim['is_edited'] else ""

                        field_name = f"{i}. {claim['claim_type'].title()} - {claim['timestamp'].strftime('%Y-%m-%d')}"
                        field_value = f"[{status_emoji}] {claim['claim_text'][:200]}{edited_marker}"

                        embed.add_field(name=field_name, value=field_value, inline=False)

                    if len(claims) > 10:
                        embed.set_footer(text=f"Showing 10 of {len(claims)} claims")

                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error fetching receipts: {str(e)}")

        @bot.command(name='quotes')
        async def quotes_cmd(ctx, user: discord.Member = None):
            """View saved quotes for a user.
            Usage: !quotes [@user]
            """
            target = user or ctx.author

            async with ctx.typing():
                try:
                    quotes = claims_tracker.get_user_quotes(target.id, limit=10)

                    if not quotes:
                        await ctx.send(f"No quotes found for {target.display_name}")
                        return

                    embed = discord.Embed(
                        title=f"Quotes by {target.display_name}",
                        color=discord.Color.purple()
                    )

                    for i, quote in enumerate(quotes, 1):
                        field_name = f"{i}. {quote['timestamp'].strftime('%Y-%m-%d')} (stars: {quote['reaction_count']})"
                        field_value = f"\"{quote['quote_text'][:300]}\""

                        embed.add_field(name=field_name, value=field_value, inline=False)

                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error fetching quotes: {str(e)}")

        @bot.command(name='verify')
        async def verify_cmd(ctx, claim_id: int = None, status: str = None, *, notes: str = None):
            """Verify a claim.
            Usage: !verify <claim_id> <status> [notes]
            Status options: true, false, mixed, outdated
            """
            if claim_id is None or status is None:
                await ctx.send("Usage: `!verify <claim_id> <status> [notes]`\nStatus options: true, false, mixed, outdated")
                return

            if status not in ['true', 'false', 'mixed', 'outdated']:
                await ctx.send("Status must be: true, false, mixed, or outdated")
                return

            async with ctx.typing():
                try:
                    with db.get_connection() as conn:
                        with conn.cursor() as cur:
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
                                await ctx.send(f"Claim #{claim_id} by {username} marked as **{status}**\n> {claim_text[:200]}")
                            else:
                                await ctx.send(f"Claim #{claim_id} not found")

                except Exception as e:
                    await ctx.send(f"Error verifying claim: {str(e)}")

    if hot_takes_tracker:
        @bot.command(name='hottakes', aliases=['ht'])
        async def hottakes_cmd(ctx, leaderboard_type: str = 'controversial', days: int = 30):
            """Show hot takes leaderboard.
            Usage: !hottakes [type] [days]
            Types: controversial, vindicated, worst, community, combined
            """
            valid_types = ['controversial', 'vindicated', 'worst', 'community', 'combined']
            parsed_type = parse_choice(leaderboard_type, valid_types)

            if parsed_type is None:
                await ctx.send(
                    f"Invalid leaderboard type: `{leaderboard_type}`\n"
                    f"Valid types: {', '.join(valid_types)}"
                )
                return

            async with ctx.typing():
                try:
                    results = await hot_takes_tracker.get_leaderboard(parsed_type, days=days, limit=10)

                    if not results:
                        await ctx.send(f"No hot takes found in the last {days} days.")
                        return

                    # Format output based on leaderboard type
                    title_map = {
                        'controversial': 'Most Controversial Takes',
                        'vindicated': 'Best Vindicated Takes',
                        'worst': 'Worst Takes',
                        'community': 'Community Favorites',
                        'combined': 'Hot Take Kings'
                    }

                    if stats_viz:
                        # Define value formatter based on leaderboard type
                        def format_hottakes_value(take):
                            claim_text = take['claim_text'][:100] + ('...' if len(take['claim_text']) > 100 else '')
                            if parsed_type == 'controversial':
                                score_text = f"Controversy: {take['controversy_score']:.1f}/10"
                            elif parsed_type == 'vindicated':
                                score_text = f"Aged like fine wine: {take['age_score']:.1f}/10"
                            elif parsed_type == 'worst':
                                score_text = f"Aged like milk: {take['age_score']:.1f}/10"
                            elif parsed_type == 'community':
                                score_text = f"Community: {take['community_score']:.1f}/10 | {take['total_reactions']} reactions"
                            else:  # combined
                                score_text = f"Combined: {take['combined_score']:.1f} | Controversy: {take['controversy_score']:.1f} | Age: {take.get('age_score', 'N/A')}"
                            return f"{claim_text}\n{score_text}"

                        image_buffer = stats_viz.create_leaderboard(
                            entries=results,
                            title=title_map.get(parsed_type, 'Hot Takes'),
                            subtitle=f"Last {days} days",
                            value_formatter=format_hottakes_value
                        )

                        file = discord.File(fp=image_buffer, filename="hottakes_leaderboard.png")
                        await ctx.send(file=file)
                    else:
                        # Fallback to embed if visualizer not loaded
                        embed = discord.Embed(
                            title=title_map.get(parsed_type, 'Hot Takes'),
                            description=f"Last {days} days",
                            color=discord.Color.red()
                        )

                        for i, take in enumerate(results, 1):
                            username = take['username']
                            claim_text = take['claim_text'][:150] + ('...' if len(take['claim_text']) > 150 else '')

                            if parsed_type == 'controversial':
                                score_text = f"Controversy: {take['controversy_score']:.1f}/10"
                            elif parsed_type == 'vindicated':
                                score_text = f"Aged like fine wine: {take['age_score']:.1f}/10"
                            elif parsed_type == 'worst':
                                score_text = f"Aged like milk: {take['age_score']:.1f}/10"
                            elif parsed_type == 'community':
                                score_text = f"Community: {take['community_score']:.1f}/10 | {take['total_reactions']} reactions"
                            else:  # combined
                                score_text = f"Combined: {take['combined_score']:.1f} | Controversy: {take['controversy_score']:.1f} | Age: {take.get('age_score', 'N/A')}"

                            embed.add_field(
                                name=f"#{i} - {username}",
                                value=f"> {claim_text}\n\n{score_text}",
                                inline=False
                            )

                        await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error fetching hot takes: {str(e)}")
                    print(f"Hot takes error: {e}")
                    import traceback
                    traceback.print_exc()

        @bot.command(name='myht')
        async def myht_cmd(ctx):
            """View your personal hot takes statistics.
            Usage: !myht
            """
            async with ctx.typing():
                try:
                    stats = await hot_takes_tracker.get_user_hot_takes_stats(ctx.author.id)

                    if not stats or stats.get('total_hot_takes', 0) == 0:
                        await ctx.send("You haven't made any hot takes yet. Time to get controversial!")
                        return

                    if stats_viz:
                        # Calculate win rate
                        total_resolved = stats['vindicated_count'] + stats['failed_count']
                        win_rate = (stats['vindicated_count'] / total_resolved) * 100 if total_resolved > 0 else 0

                        # Format metrics for visualization
                        metrics = [
                            ("Total Hot Takes", stats['total_hot_takes'], 'primary'),
                            ("Spiciest Take", f"{stats['spiciest_take']:.1f}/10", 'danger'),
                            ("Avg Controversy", f"{stats['avg_controversy']:.1f}/10", 'warning'),
                            ("Vindicated", stats['vindicated_count'], 'success'),
                            ("Proven Wrong", stats['failed_count'], 'danger'),
                            ("Avg Community", f"{stats['avg_community']:.1f}/10", 'info'),
                        ]

                        if total_resolved > 0:
                            metrics.append(("Win Rate", f"{win_rate:.1f}%", 'success'))

                        image_buffer = stats_viz.create_personal_stats_dashboard(
                            username=f"{ctx.author.display_name}'s Hot Takes",
                            metrics=metrics
                        )

                        file = discord.File(fp=image_buffer, filename="mystats_hottakes.png")
                        await ctx.send(file=file)
                    else:
                        # Fallback to embed if visualizer not loaded
                        embed = discord.Embed(
                            title=f"{ctx.author.display_name}'s Hot Takes Stats",
                            color=discord.Color.red()
                        )

                        embed.add_field(name="Total Hot Takes", value=f"{stats['total_hot_takes']}", inline=True)
                        embed.add_field(name="Spiciest Take", value=f"{stats['spiciest_take']:.1f}/10", inline=True)
                        embed.add_field(name="Avg Controversy", value=f"{stats['avg_controversy']:.1f}/10", inline=True)
                        embed.add_field(name="Vindicated", value=f"{stats['vindicated_count']}", inline=True)
                        embed.add_field(name="Proven Wrong", value=f"{stats['failed_count']}", inline=True)
                        embed.add_field(name="Avg Community Score", value=f"{stats['avg_community']:.1f}/10", inline=True)

                        # Calculate win rate
                        total_resolved = stats['vindicated_count'] + stats['failed_count']
                        if total_resolved > 0:
                            win_rate = (stats['vindicated_count'] / total_resolved) * 100
                            embed.add_field(name="Win Rate", value=f"{win_rate:.1f}%", inline=True)

                        await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error fetching your stats: {str(e)}")
                    print(f"User hot takes stats error: {e}")
                    import traceback
                    traceback.print_exc()

        @bot.command(name='vindicate')
        async def vindicate_cmd(ctx, hot_take_id: int = None, status: str = None, *, notes: str = None):
            """Mark a hot take as vindicated or proven wrong (Admin only).
            Usage: !vindicate <id> <status> [notes]
            Status options: won, lost, mixed, pending
            """
            if hot_take_id is None or status is None:
                await ctx.send(
                    "Usage: `!vindicate <id> <status> [notes]`\n"
                    "Status options: won, lost, mixed, pending"
                )
                return

            # Check if user is admin
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("Only administrators can vindicate hot takes.")
                return

            valid_statuses = ['won', 'lost', 'mixed', 'pending']
            parsed_status = parse_choice(status, valid_statuses)

            if parsed_status is None:
                await ctx.send(
                    f"Invalid status: `{status}`\n"
                    f"Valid options: {', '.join(valid_statuses)}"
                )
                return

            async with ctx.typing():
                try:
                    success = await hot_takes_tracker.vindicate_hot_take(hot_take_id, parsed_status, notes)

                    if success:
                        status_emoji = {
                            'won': 'TRUE',
                            'lost': 'FALSE',
                            'mixed': 'MIXED',
                            'pending': 'PENDING'
                        }
                        label = status_emoji.get(parsed_status, 'DONE')

                        await ctx.send(
                            f"[{label}] Hot take #{hot_take_id} marked as **{parsed_status.upper()}**" +
                            (f"\n\nNotes: {notes}" if notes else "")
                        )
                    else:
                        await ctx.send(f"Failed to vindicate hot take #{hot_take_id}. It may not exist.")

                except Exception as e:
                    await ctx.send(f"Error vindicating hot take: {str(e)}")
                    print(f"Vindication error: {e}")
                    import traceback
                    traceback.print_exc()

    # =============== REMINDER COMMANDS ===============

    if reminder_system:
        @bot.command(name='remind')
        async def remind_cmd(ctx, *, text: str = None):
            """Set a reminder with natural language time.
            Usage: !remind <time> | <message>
            Example: !remind in 5 minutes | Check the oven
            """
            if not text:
                await ctx.send(
                    "Usage: `!remind <time> | <message>`\n"
                    "Example: `!remind in 5 minutes | Check the oven`"
                )
                return

            parts = text.split(' | ', 1)
            if len(parts) < 2:
                await ctx.send(
                    "Usage: `!remind <time> | <message>`\n"
                    "Example: `!remind in 5 minutes | Check the oven`\n"
                    "Use ` | ` (with spaces) to separate time from message."
                )
                return

            time_str = parts[0].strip()
            message = parts[1].strip()

            if not time_str or not message:
                await ctx.send("Both time and message are required.")
                return

            async with ctx.typing():
                try:
                    # Parse and create reminder
                    result = await reminder_system.create_reminder(
                        user_id=ctx.author.id,
                        username=str(ctx.author),
                        channel_id=ctx.channel.id,
                        message_id=ctx.message.id,
                        reminder_text=message,
                        time_string=time_str,
                        recurring=False,
                        recurring_interval=None
                    )

                    if not result:
                        await ctx.send(
                            f"Could not parse time '{time_str}'. Try formats like:\n"
                            "- `in 5 minutes`\n"
                            "- `in 2 hours`\n"
                            "- `tomorrow at 3pm`\n"
                            "- `next Monday`\n"
                            "- `at 15:00`"
                        )
                        return

                    reminder_id, remind_at = result

                    # Format confirmation
                    timestamp = int(remind_at.timestamp())
                    await ctx.send(
                        f"Reminder set! I'll remind you <t:{timestamp}:R> (at <t:{timestamp}:f>)\n"
                        f"**Message:** {message}\n"
                        f"_Reminder ID: {reminder_id}_"
                    )

                except Exception as e:
                    await ctx.send(f"Error setting reminder: {str(e)}")
                    print(f"Reminder error: {e}")
                    import traceback
                    traceback.print_exc()

        @bot.command(name='reminders')
        async def reminders_cmd(ctx):
            """View your active reminders.
            Usage: !reminders
            """
            async with ctx.typing():
                try:
                    user_reminders = await reminder_system.get_user_reminders(ctx.author.id)

                    if not user_reminders:
                        await ctx.send("You have no active reminders.")
                        return

                    embed = discord.Embed(
                        title=f"{ctx.author.display_name}'s Reminders",
                        color=discord.Color.blue()
                    )

                    for reminder in user_reminders[:10]:  # Limit to 10
                        timestamp = int(reminder['remind_at'].timestamp())
                        time_remaining = reminder_system.format_time_remaining(reminder['remind_at'])

                        value = f"**Message:** {reminder['reminder_text'][:100]}\n"
                        value += f"**When:** <t:{timestamp}:R> (<t:{timestamp}:f>)\n"
                        value += f"**Time left:** {time_remaining}\n"
                        if reminder['recurring']:
                            value += "Recurring: Yes"

                        embed.add_field(
                            name=f"ID: {reminder['id']}",
                            value=value,
                            inline=False
                        )

                    if len(user_reminders) > 10:
                        embed.set_footer(text=f"Showing 10 of {len(user_reminders)} reminders")

                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error fetching reminders: {str(e)}")
                    print(f"Reminders fetch error: {e}")
                    import traceback
                    traceback.print_exc()

        @bot.command(name='cancelremind')
        async def cancelremind_cmd(ctx, reminder_id: int = None):
            """Cancel one of your reminders.
            Usage: !cancelremind <id>
            """
            if reminder_id is None:
                await ctx.send("Usage: `!cancelremind <id>`")
                return

            async with ctx.typing():
                try:
                    success = await reminder_system.cancel_reminder(reminder_id, ctx.author.id)

                    if success:
                        await ctx.send(f"Reminder #{reminder_id} cancelled")
                    else:
                        await ctx.send(
                            f"Could not cancel reminder #{reminder_id}. "
                            "It may not exist or you don't own it."
                        )

                except Exception as e:
                    await ctx.send(f"Error cancelling reminder: {str(e)}")
                    print(f"Cancel reminder error: {e}")
                    import traceback
                    traceback.print_exc()

    # =============== EVENT COMMANDS ===============

    if event_system:
        @bot.command(name='event')
        async def event_cmd(ctx, *, text: str = None):
            """Schedule an event with automatic reminders.
            Usage: !event <name> | <date> [| description]
            Example: !event Movie Night | tomorrow at 7pm | Bring snacks
            """
            if not text:
                await ctx.send(
                    "Usage: `!event <name> | <date> [| description]`\n"
                    "Example: `!event Movie Night | tomorrow at 7pm | Bring snacks`"
                )
                return

            parts = text.split(' | ')
            if len(parts) < 2:
                await ctx.send(
                    "Usage: `!event <name> | <date> [| description]`\n"
                    "Use ` | ` (with spaces) to separate fields.\n"
                    "Example: `!event Movie Night | tomorrow at 7pm | Bring snacks`"
                )
                return

            name = parts[0].strip()
            date_str = parts[1].strip()
            description = parts[2].strip() if len(parts) > 2 else None

            if not name or not date_str:
                await ctx.send("Event name and date are required.")
                return

            async with ctx.typing():
                try:
                    # Parse event date
                    event_date = event_system.parse_event_time(date_str)

                    if not event_date:
                        await ctx.send(
                            f"Could not parse time: '{date_str}'\n\n"
                            "Try formats like:\n"
                            "- `tomorrow at 7pm`\n"
                            "- `next Friday at 8pm`\n"
                            "- `in 3 days at 6pm`\n"
                            "- `Monday at 5pm`"
                        )
                        return

                    # Check if event is in the past
                    if event_date < datetime.now():
                        await ctx.send("Event date must be in the future")
                        return

                    # Parse reminder intervals (not supported in prefix version)
                    reminder_intervals = event_system.parse_reminder_intervals(None)

                    # Create event
                    event_id = await event_system.create_event(
                        event_name=name,
                        event_date=event_date,
                        created_by_user_id=ctx.author.id,
                        created_by_username=str(ctx.author),
                        channel_id=ctx.channel.id,
                        guild_id=ctx.guild.id,
                        description=description,
                        reminder_intervals=reminder_intervals
                    )

                    if event_id:
                        # Format event date for Discord timestamp
                        timestamp = int(event_date.timestamp())

                        embed = discord.Embed(
                            title="Event Scheduled",
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

                        embed.set_footer(text=f"Event ID: {event_id} | Created by {ctx.author.display_name}")

                        await ctx.send(embed=embed)
                        print(f"Event created: '{name}' at {event_date} (ID: {event_id})")
                    else:
                        await ctx.send("Failed to create event")

                except Exception as e:
                    await ctx.send(f"Error scheduling event: {str(e)}")
                    print(f"Schedule event error: {e}")
                    import traceback
                    traceback.print_exc()

        @bot.command(name='events')
        async def events_cmd(ctx, limit: int = 10):
            """View upcoming scheduled events.
            Usage: !events [limit]
            """
            async with ctx.typing():
                try:
                    upcoming = await event_system.get_upcoming_events(ctx.guild.id, limit)

                    if not upcoming:
                        await ctx.send("No upcoming events scheduled")
                        return

                    embed = discord.Embed(
                        title="Upcoming Events",
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

                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error getting events: {str(e)}")
                    print(f"Events list error: {e}")
                    import traceback
                    traceback.print_exc()

        @bot.command(name='cancelevent')
        async def cancelevent_cmd(ctx, event_id: int = None):
            """Cancel a scheduled event.
            Usage: !cancelevent <id>
            """
            if event_id is None:
                await ctx.send("Usage: `!cancelevent <id>`")
                return

            async with ctx.typing():
                try:
                    success = await event_system.cancel_event(event_id, ctx.author.id)

                    if success:
                        await ctx.send(f"Event #{event_id} cancelled")
                        print(f"Event #{event_id} cancelled by {ctx.author}")
                    else:
                        await ctx.send(
                            f"Could not cancel event #{event_id}. "
                            "It may not exist or has already been cancelled."
                        )

                except Exception as e:
                    await ctx.send(f"Error cancelling event: {str(e)}")
                    print(f"Cancel event error: {e}")
                    import traceback
                    traceback.print_exc()

    # =============== USER FEATURES ===============

    if rag:
        @bot.command(name='myfacts')
        async def myfacts_cmd(ctx):
            """View facts the bot remembers about you.
            Usage: !myfacts
            """
            async with ctx.typing():
                try:
                    facts = await rag.get_explicit_facts(ctx.author.id)

                    if not facts:
                        await ctx.send(
                            "I don't have any saved facts about you yet.\n"
                            "Tell me something like: `@WompBot remember that I prefer Python over JS`"
                        )
                        return

                    embed = discord.Embed(
                        title=f"What I Remember About {ctx.author.display_name}",
                        color=discord.Color.blue()
                    )

                    for i, fact in enumerate(facts, 1):
                        stored_date = fact['first_mentioned'].strftime('%b %d, %Y') if fact.get('first_mentioned') else 'Unknown'
                        mentions = fact.get('mention_count', 1)
                        mention_text = f" (confirmed {mentions}x)" if mentions > 1 else ""
                        embed.add_field(
                            name=f"#{fact['id']} -- {stored_date}{mention_text}",
                            value=fact['fact'][:200],
                            inline=False
                        )

                    embed.set_footer(text="Use !forget <id> to remove a fact")
                    await ctx.send(embed=embed)

                except Exception as e:
                    await ctx.send(f"Error: {str(e)}")

        @bot.command(name='forget')
        async def forget_cmd(ctx, fact_id: int = None):
            """Remove a remembered fact by its ID.
            Usage: !forget <id>
            """
            if fact_id is None:
                await ctx.send("Usage: `!forget <id>` (use `!myfacts` to see IDs)")
                return

            try:
                deleted = await rag.delete_explicit_fact(ctx.author.id, fact_id)

                if deleted:
                    await ctx.send(f"Fact #{fact_id} forgotten!")
                else:
                    await ctx.send(f"Fact #{fact_id} not found or doesn't belong to you.")
            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

    if qotd:
        @bot.command(name='qotd')
        async def qotd_cmd(ctx, mode: str = None):
            """View featured quotes from different time periods.
            Usage: !qotd [mode]
            Modes: daily, weekly, monthly, alltime, random
            """
            valid_modes = ['daily', 'weekly', 'monthly', 'alltime', 'random']

            if mode is not None:
                selected_mode = parse_choice(mode, valid_modes, default='daily')
                if selected_mode is None:
                    await ctx.send(
                        f"Invalid mode: `{mode}`\n"
                        f"Valid modes: {', '.join(valid_modes)}"
                    )
                    return
            else:
                selected_mode = 'daily'

            async with ctx.typing():
                try:
                    # Get the quote
                    quote = await qotd.get_quote(selected_mode)

                    if not quote:
                        await ctx.send(
                            f"No quotes found for {selected_mode} period. Try a different time range!"
                        )
                        return

                    # Create embed
                    title = qotd.get_mode_title(selected_mode)
                    description = qotd.get_mode_description(selected_mode)

                    embed = discord.Embed(
                        title=title,
                        description=description,
                        color=discord.Color.purple()
                    )

                    # The quote itself
                    quote_text = f"*\"{quote['quote_text']}\"*"
                    embed.add_field(
                        name="Quote",
                        value=quote_text,
                        inline=False
                    )

                    # Attribution
                    timestamp = int(quote['timestamp'].timestamp())
                    attribution = f"-- **{quote['username']}**\n"
                    attribution += f"<t:{timestamp}:D> (<t:{timestamp}:R>)"

                    embed.add_field(
                        name="Said By",
                        value=attribution,
                        inline=True
                    )

                    # Who saved it
                    if quote['added_by_username']:
                        saved_text = f"**{quote['added_by_username']}**"
                        if quote['reaction_count'] > 1:
                            saved_text += f"\n{quote['reaction_count']} reactions"
                        embed.add_field(
                            name="Saved By",
                            value=saved_text,
                            inline=True
                        )

                    # Context if available
                    if quote['context']:
                        context_text = quote['context'][:200]
                        if len(quote['context']) > 200:
                            context_text += "..."
                        embed.add_field(
                            name="Context",
                            value=f"```{context_text}```",
                            inline=False
                        )

                    # Category badge
                    if quote['category']:
                        category_emojis = {
                            'funny': 'Funny',
                            'crazy': 'Crazy',
                            'wise': 'Wise',
                            'wtf': 'WTF',
                            'savage': 'Savage'
                        }
                        label = category_emojis.get(quote['category'], quote['category'].title())
                        embed.add_field(
                            name="Category",
                            value=label,
                            inline=True
                        )

                    # Footer with ID
                    embed.set_footer(text=f"Quote #{quote['id']}")
                    embed.timestamp = datetime.now()

                    await ctx.send(embed=embed)
                    print(f"Displayed {selected_mode} quote: #{quote['id']}")

                except Exception as e:
                    await ctx.send(f"Error fetching quote: {str(e)}")
                    print(f"QOTD error: {e}")
                    import traceback
                    traceback.print_exc()

    # Weather preference commands (these need db directly)
    @bot.command(name='weatherset')
    async def weatherset_cmd(ctx, *, location: str = None):
        """Set your default weather location.
        Usage: !weatherset <location>
        Example: !weatherset Tokyo
        Example: !weatherset London, UK
        """
        if not location:
            await ctx.send(
                "Usage: `!weatherset <location>`\n"
                "Example: `!weatherset Tokyo`\n"
                "Example: `!weatherset London, UK`"
            )
            return

        user_id = ctx.author.id

        # Default to metric units for prefix command
        units = 'metric'

        success = db.set_weather_preference(user_id, location, units)

        if success:
            unit_name = "Celsius"
            await ctx.send(
                f"Default weather location set to **{location}** with **{unit_name}**!\n\n"
                f"Now you can say `wompbot, weather` to get weather for {location}."
            )
        else:
            await ctx.send("Failed to save weather preference. Please try again.")

    @bot.command(name='weatherclear')
    async def weatherclear_cmd(ctx):
        """Clear your saved weather location.
        Usage: !weatherclear
        """
        user_id = ctx.author.id

        success = db.delete_weather_preference(user_id)

        if success:
            await ctx.send("Weather preference cleared!")
        else:
            await ctx.send("You don't have a saved weather location.")

    # =============== MESSAGE SCHEDULING ===============

    if message_scheduler:
        @bot.command(name='schedule')
        async def schedule_cmd(ctx, *, text: str = None):
            """Schedule a message to be sent later.
            Usage: !schedule <time> | <message>
            Time can be: Xm (minutes), Xh (hours), Xd (days), or combined.
            Example: !schedule 2h | Don't forget the meeting
            Example: !schedule 30m | Check the oven
            Example: !schedule 1d | Weekly reminder
            """
            if not text:
                await ctx.send(
                    "Usage: `!schedule <time> | <message>`\n"
                    "Example: `!schedule 2h | Don't forget the meeting`\n"
                    "Example: `!schedule 30m | Check the oven`\n"
                    "Time formats: `Xm` (minutes), `Xh` (hours), `Xd` (days)"
                )
                return

            parts = text.split(' | ', 1)
            if len(parts) < 2:
                await ctx.send(
                    "Usage: `!schedule <time> | <message>`\n"
                    "Use ` | ` (with spaces) to separate time from message.\n"
                    "Example: `!schedule 2h | Don't forget the meeting`"
                )
                return

            time_str = parts[0].strip()
            message_content = parts[1].strip()

            if not time_str or not message_content:
                await ctx.send("Both time and message content are required.")
                return

            # Parse the time string into total minutes
            import re
            total_minutes = 0
            day_match = re.search(r'(\d+)\s*d', time_str, re.IGNORECASE)
            hour_match = re.search(r'(\d+)\s*h', time_str, re.IGNORECASE)
            min_match = re.search(r'(\d+)\s*m', time_str, re.IGNORECASE)

            if day_match:
                total_minutes += int(day_match.group(1)) * 1440
            if hour_match:
                total_minutes += int(hour_match.group(1)) * 60
            if min_match:
                total_minutes += int(min_match.group(1))

            # If no pattern matched, try to parse as plain number (assume minutes)
            if total_minutes <= 0:
                try:
                    total_minutes = int(time_str)
                except ValueError:
                    await ctx.send(
                        f"Could not parse time: `{time_str}`\n"
                        "Use formats like: `30m`, `2h`, `1d`, `1d2h30m`, or a plain number (minutes)."
                    )
                    return

            if total_minutes <= 0:
                await ctx.send("Time must be greater than zero.")
                return

            try:
                send_at = datetime.now() + timedelta(minutes=total_minutes)

                result = await message_scheduler.schedule_message(
                    guild_id=ctx.guild.id,
                    channel_id=ctx.channel.id,
                    user_id=ctx.author.id,
                    content=message_content,
                    send_at=send_at
                )

                if result.get('error'):
                    await ctx.send(f"{result['error']}")
                    return

                # Format the time nicely
                time_display = send_at.strftime("%b %d at %I:%M %p")
                await ctx.send(
                    f"Message scheduled! (#{result['message_id']})\n"
                    f"Will be sent: **{time_display}**\n"
                    f"Preview: {result['content_preview']}"
                )

            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

        @bot.command(name='scheduled')
        async def scheduled_cmd(ctx):
            """View your pending scheduled messages.
            Usage: !scheduled
            """
            try:
                messages = await message_scheduler.get_user_scheduled(
                    ctx.author.id, ctx.guild.id
                )

                if not messages:
                    await ctx.send("You have no pending scheduled messages.")
                    return

                embed = discord.Embed(
                    title="Your Scheduled Messages",
                    color=discord.Color.blue()
                )

                for msg in messages:
                    time_str = msg['send_at'].strftime("%b %d at %I:%M %p")
                    preview = msg['content'][:80] + ('...' if len(msg['content']) > 80 else '')
                    embed.add_field(
                        name=f"#{msg['id']} -- {time_str}",
                        value=f"<#{msg['channel_id']}> -- {preview}",
                        inline=False
                    )

                embed.set_footer(text=f"{len(messages)}/5 slots used | !cancelschedule <id> to cancel")
                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

        @bot.command(name='cancelschedule')
        async def cancelschedule_cmd(ctx, message_id: int = None):
            """Cancel a scheduled message.
            Usage: !cancelschedule <id>
            """
            if message_id is None:
                await ctx.send("Usage: `!cancelschedule <id>` (use `!scheduled` to see IDs)")
                return

            try:
                result = await message_scheduler.cancel_message(
                    message_id, ctx.author.id
                )

                if result.get('error'):
                    await ctx.send(f"{result['error']}")
                    return

                await ctx.send(f"Scheduled message #{message_id} has been cancelled.")

            except Exception as e:
                await ctx.send(f"Error: {str(e)}")

    print("Prefix feature commands registered")
