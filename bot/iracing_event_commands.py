"""
iRacing Event Scheduling & Driver Availability Commands
Slash commands for creating events, tracking availability, and managing stints
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional
import re
from dateutil import parser as dateparser


def setup_iracing_event_commands(bot, iracing_team_manager, iracing_client):
    """Set up all iRacing event scheduling commands"""

    # ==================== EVENT MANAGEMENT ====================

    @bot.tree.command(name="iracing_event_create", description="Create a team event")
    @app_commands.describe(
        team_id="Your team ID",
        event_name="Name of the event",
        event_type="Type of event",
        event_time="When the event starts (e.g., 'tomorrow 8pm', 'Jan 15 7:00pm')",
        duration="Duration in minutes (optional, for endurance races)",
        series="iRacing series name (optional)",
        track="Track name (optional)",
        notes="Additional notes (optional)"
    )
    @app_commands.choices(event_type=[
        app_commands.Choice(name="Practice", value="practice"),
        app_commands.Choice(name="Qualifying", value="qualifying"),
        app_commands.Choice(name="Race", value="race"),
        app_commands.Choice(name="Endurance Race", value="endurance")
    ])
    async def iracing_event_create(
        interaction: discord.Interaction,
        team_id: int,
        event_name: str,
        event_type: str,
        event_time: str,
        duration: Optional[int] = None,
        series: Optional[str] = None,
        track: Optional[str] = None,
        notes: Optional[str] = None
    ):
        """Create a new team event"""
        await interaction.response.defer()

        # Verify user is team member
        user_teams = iracing_team_manager.get_user_teams(interaction.user.id, interaction.guild.id)
        user_team = next((t for t in user_teams if t['id'] == team_id), None)

        if not user_team:
            await interaction.followup.send("❌ You're not a member of this team.", ephemeral=True)
            return

        # Parse event time
        try:
            event_start = dateparser.parse(event_time, fuzzy=True)
            if not event_start:
                raise ValueError("Could not parse time")

            # If no year specified and date is in the past, assume next year
            if event_start < datetime.now():
                event_start = event_start.replace(year=datetime.now().year + 1)

        except Exception as e:
            await interaction.followup.send(
                f"❌ Could not parse event time. Try formats like:\n"
                f"• 'tomorrow 8pm'\n"
                f"• 'January 15 7:00pm'\n"
                f"• '2025-01-15 19:00'",
                ephemeral=True
            )
            return

        # Create event
        event_id = iracing_team_manager.create_event(
            team_id=team_id,
            guild_id=interaction.guild.id,
            event_name=event_name,
            event_type=event_type,
            event_start=event_start,
            created_by=interaction.user.id,
            event_duration_minutes=duration,
            series_name=series,
            track_name=track,
            notes=notes
        )

        if event_id:
            team_info = iracing_team_manager.get_team_info(team_id)

            embed = discord.Embed(
                title="📅 Event Created Successfully!",
                description=f"**{event_name}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Team", value=f"{team_info['name']} [{team_info['tag']}]", inline=True)
            embed.add_field(name="Type", value=event_type.title(), inline=True)
            embed.add_field(name="Event ID", value=f"`{event_id}`", inline=True)

            # Discord timestamp (shows in user's local time)
            timestamp = int(event_start.timestamp())
            embed.add_field(
                name="Start Time",
                value=f"<t:{timestamp}:F> (<t:{timestamp}:R>)",
                inline=False
            )

            if duration:
                hours = duration // 60
                mins = duration % 60
                duration_str = f"{hours}h {mins}m" if hours else f"{mins}m"
                embed.add_field(name="Duration", value=duration_str, inline=True)

            if series:
                embed.add_field(name="Series", value=series, inline=True)
            if track:
                embed.add_field(name="Track", value=track, inline=True)
            if notes:
                embed.add_field(name="Notes", value=notes, inline=False)

            embed.set_footer(text="Team members: Use /iracing_event_availability to mark your availability")

            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ Failed to create event.", ephemeral=True)

    @bot.tree.command(name="iracing_team_events", description="View upcoming team events")
    @app_commands.describe(team_id="Team ID to view events for")
    async def iracing_team_events(interaction: discord.Interaction, team_id: int):
        """View upcoming events for a team"""
        await interaction.response.defer()

        # Get team info
        team_info = iracing_team_manager.get_team_info(team_id)
        if not team_info:
            await interaction.followup.send("❌ Team not found.", ephemeral=True)
            return

        # Get events
        events = iracing_team_manager.get_team_events(team_id, upcoming_only=True)

        if not events:
            await interaction.followup.send(
                f"No upcoming events for **{team_info['name']}**. Create one with `/iracing_event_create`!"
            )
            return

        embed = discord.Embed(
            title=f"📅 Upcoming Events - {team_info['name']}",
            description=f"Found {len(events)} upcoming event(s)",
            color=discord.Color.blue()
        )

        type_emoji = {
            'practice': '🏋️',
            'qualifying': '⏱️',
            'race': '🏁',
            'endurance': '⏳'
        }

        for event in events[:10]:  # Limit to 10 events
            emoji = type_emoji.get(event['type'], '📅')
            timestamp = int(event['start'].timestamp())

            value_parts = [f"<t:{timestamp}:F> (<t:{timestamp}:R>)"]

            if event['duration_minutes']:
                hours = event['duration_minutes'] // 60
                mins = event['duration_minutes'] % 60
                duration_str = f"{hours}h {mins}m" if hours else f"{mins}m"
                value_parts.append(f"Duration: {duration_str}")

            if event['series']:
                value_parts.append(f"Series: {event['series']}")
            if event['track']:
                value_parts.append(f"Track: {event['track']}")

            value_parts.append(f"Event ID: `{event['id']}`")

            embed.add_field(
                name=f"{emoji} {event['name']} - {event['type'].title()}",
                value='\n'.join(value_parts),
                inline=False
            )

        await interaction.followup.send(embed=embed)

    # ==================== DRIVER AVAILABILITY ====================

    @bot.tree.command(name="iracing_event_availability", description="Set your availability for an event")
    @app_commands.describe(
        event_id="Event ID",
        status="Your availability status",
        notes="Optional notes (e.g., 'Can only do first 2 hours')"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="✅ Available", value="available"),
        app_commands.Choice(name="❌ Unavailable", value="unavailable"),
        app_commands.Choice(name="❓ Maybe", value="maybe"),
        app_commands.Choice(name="✔️ Confirmed", value="confirmed")
    ])
    async def iracing_event_availability(
        interaction: discord.Interaction,
        event_id: int,
        status: str,
        notes: Optional[str] = None
    ):
        """Set your availability for an event"""
        await interaction.response.defer()

        # Set availability
        success = iracing_team_manager.set_driver_availability(
            event_id=event_id,
            discord_user_id=interaction.user.id,
            status=status,
            notes=notes
        )

        if success:
            status_emoji = {
                'available': '✅',
                'unavailable': '❌',
                'maybe': '❓',
                'confirmed': '✔️'
            }.get(status, '📝')

            await interaction.followup.send(
                f"{status_emoji} Your availability has been updated to **{status.title()}** for event `{event_id}`"
            )
        else:
            await interaction.followup.send("❌ Failed to update availability.", ephemeral=True)

    @bot.tree.command(name="iracing_event_roster", description="View driver availability for an event")
    @app_commands.describe(event_id="Event ID")
    async def iracing_event_roster(interaction: discord.Interaction, event_id: int):
        """View driver availability for an event"""
        await interaction.response.defer()

        # Get availability
        availability = iracing_team_manager.get_event_availability(event_id)

        if not availability:
            await interaction.followup.send(
                "No availability info yet. Team members can use `/iracing_event_availability` to mark their status."
            )
            return

        embed = discord.Embed(
            title=f"📊 Driver Roster - Event {event_id}",
            color=discord.Color.blue()
        )

        # Group by status
        available = [a for a in availability if a['status'] == 'available']
        confirmed = [a for a in availability if a['status'] == 'confirmed']
        maybe = [a for a in availability if a['status'] == 'maybe']
        unavailable = [a for a in availability if a['status'] == 'unavailable']

        def format_driver(a):
            name = a['iracing_name'] or f"<@{a['discord_user_id']}>"
            if a['notes']:
                return f"• {name} - *{a['notes'][:50]}*"
            return f"• {name}"

        if confirmed:
            embed.add_field(
                name="✔️ Confirmed",
                value='\n'.join([format_driver(a) for a in confirmed[:10]]),
                inline=False
            )

        if available:
            embed.add_field(
                name="✅ Available",
                value='\n'.join([format_driver(a) for a in available[:10]]),
                inline=False
            )

        if maybe:
            embed.add_field(
                name="❓ Maybe",
                value='\n'.join([format_driver(a) for a in maybe[:10]]),
                inline=False
            )

        if unavailable:
            embed.add_field(
                name="❌ Unavailable",
                value='\n'.join([format_driver(a) for a in unavailable[:10]]),
                inline=False
            )

        total_drivers = len(confirmed) + len(available)
        embed.set_footer(text=f"{total_drivers} driver(s) ready to race")

        await interaction.followup.send(embed=embed)

    # ==================== SPECIAL EVENTS ====================

    @bot.tree.command(name="iracing_upcoming_races", description="View all upcoming official races")
    @app_commands.describe(
        hours="How many hours ahead to search (default: 24)",
        series="Filter by series name (optional)"
    )
    async def iracing_upcoming_races(
        interaction: discord.Interaction,
        hours: int = 24,
        series: Optional[str] = None
    ):
        """View upcoming official iRacing races"""
        await interaction.response.defer()

        try:
            races = await iracing_client.get_upcoming_races(hours_ahead=hours)

            if not races:
                await interaction.followup.send("❌ Could not fetch upcoming races. Try again later.")
                return

            # Filter by series if specified
            if series:
                races = [r for r in races if series.lower() in r.get('series_name', '').lower()]

            if not races:
                msg = f"No upcoming races found"
                if series:
                    msg += f" for series matching '{series}'"
                await interaction.followup.send(msg)
                return

            # Limit to first 20 races
            races = races[:20]

            embed = discord.Embed(
                title="🏁 Upcoming iRacing Races",
                description=f"Next {len(races)} official race(s) in the next {hours}h",
                color=discord.Color.blue()
            )

            for race in races[:10]:  # Discord field limit
                series_name = race.get('series_name', 'Unknown Series')
                track_name = race.get('track_name', 'Unknown Track')
                start_time = race.get('start_time')

                if start_time:
                    if isinstance(start_time, str):
                        start_time = dateparser.parse(start_time)
                    timestamp = int(start_time.timestamp())
                    time_str = f"<t:{timestamp}:t> (<t:{timestamp}:R>)"
                else:
                    time_str = "Time TBD"

                embed.add_field(
                    name=f"🏎️ {series_name}",
                    value=f"**{track_name}**\n{time_str}",
                    inline=False
                )

            if len(races) > 10:
                embed.set_footer(text=f"Showing first 10 of {len(races)} races. Narrow your search with the series parameter.")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"❌ Error fetching upcoming races: {e}")
            await interaction.followup.send("❌ Error fetching races. Make sure iRacing integration is enabled.", ephemeral=True)

    print("✅ iRacing event commands loaded")
