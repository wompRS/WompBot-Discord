"""
iRacing Team Management Discord Commands
Slash commands for creating and managing iRacing teams
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
from typing import Optional
import re

# Store reference to team manager for autocomplete
_team_manager = None


def setup_iracing_team_commands(bot, iracing_team_manager):
    global _team_manager
    _team_manager = iracing_team_manager

    # ==================== AUTOCOMPLETE FUNCTIONS ====================

    async def team_name_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete function for team names"""
        if not _team_manager:
            return []

        try:
            teams = _team_manager.list_server_teams(interaction.guild.id)
            current_lower = current.lower()

            if not current_lower:
                matches = teams[:25]
            else:
                matches = [t for t in teams if current_lower in t['name'].lower()]

            return [
                app_commands.Choice(
                    name=f"{t['name']} [{t['tag']}]" if t.get('tag') else t['name'],
                    value=t['name']
                )
                for t in matches[:25]
            ]
        except Exception as e:
            print(f"❌ Team autocomplete error: {e}")
            return []
    """Set up all iRacing team management commands"""

    # ==================== TEAM MANAGEMENT COMMANDS ====================

    @bot.tree.command(name="iracing_team_create", description="Create a new iRacing team")
    @app_commands.describe(
        team_name="Name of your team",
        team_tag="Short team abbreviation (e.g., TRT, RFR)",
        description="Optional team description"
    )
    async def iracing_team_create(
        interaction: discord.Interaction,
        team_name: str,
        team_tag: str,
        description: Optional[str] = None
    ):
        """Create a new iRacing team"""
        await interaction.response.defer()

        # Validate team tag length
        if len(team_tag) > 10:
            await interaction.followup.send("❌ Team tag must be 10 characters or less.", ephemeral=True)
            return

        # Create the team
        team_id = iracing_team_manager.create_team(
            guild_id=interaction.guild.id,
            team_name=team_name,
            team_tag=team_tag,
            created_by=interaction.user.id,
            description=description
        )

        if team_id:
            embed = discord.Embed(
                title="🏁 Team Created Successfully!",
                description=f"**{team_name}** [{team_tag}]",
                color=discord.Color.green()
            )
            if description:
                embed.add_field(name="Description", value=description, inline=False)
            embed.add_field(name="Team ID", value=f"`{team_id}`", inline=True)
            embed.add_field(name="Creator", value=interaction.user.mention, inline=True)
            embed.set_footer(text="You've been added as team manager. Use /iracing_team_invite to add members.")

            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(
                "❌ Failed to create team. Team name might already exist in this server.",
                ephemeral=True
            )

    @bot.tree.command(name="iracing_team_invite", description="Invite a member to your team")
    @app_commands.describe(
        team_name="Team to invite to",
        member="Discord user to invite",
        role="Member role"
    )
    @app_commands.autocomplete(team_name=team_name_autocomplete)
    @app_commands.choices(role=[
        app_commands.Choice(name="Driver", value="driver"),
        app_commands.Choice(name="Crew Chief", value="crew_chief"),
        app_commands.Choice(name="Spotter", value="spotter"),
        app_commands.Choice(name="Manager", value="manager")
    ])
    async def iracing_team_invite(
        interaction: discord.Interaction,
        team_name: str,
        member: discord.Member,
        role: app_commands.Choice[str] = None
    ):
        """Invite a member to join a team (they must accept)"""
        await interaction.response.defer()

        # Default role is driver
        role_value = role.value if role else "driver"

        # Find team by name
        team_info = iracing_team_manager.get_team_by_name(interaction.guild.id, team_name)
        if not team_info:
            await interaction.followup.send(f"❌ Team not found: '{team_name}'", ephemeral=True)
            return

        team_id = team_info['id']

        # Check if user is team manager
        user_teams = iracing_team_manager.get_user_teams(interaction.user.id, interaction.guild.id)
        user_team = next((t for t in user_teams if t['id'] == team_id), None)

        if not user_team or user_team['role'] != 'manager':
            await interaction.followup.send("❌ Only team managers can invite members.", ephemeral=True)
            return

        # Create invitation (don't add directly)
        result = iracing_team_manager.create_invitation(team_id, member.id, interaction.user.id, role_value)

        if result == -1:
            await interaction.followup.send(f"❌ {member.mention} already has a pending invitation to this team.", ephemeral=True)
        elif result == -2:
            await interaction.followup.send(f"❌ {member.mention} is already a member of this team.", ephemeral=True)
        elif result:
            # Send channel confirmation
            tag_display = f" [{team_info.get('tag', '')}]" if team_info.get('tag') else ""
            embed = discord.Embed(
                title="Invitation Sent",
                description=f"{member.mention} has been invited to join **{team_info['name']}**{tag_display}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Role", value=role_value.replace('_', ' ').title(), inline=True)

            # DM the invited user with buttons
            dm_sent = False
            try:
                from features.team_menu import InvitationDMView

                dm_embed = discord.Embed(
                    title="Team Invitation",
                    description=f"You've been invited to join **{team_info['name']}**{tag_display}",
                    color=discord.Color.blue()
                )
                dm_embed.add_field(name="Role", value=role_value.replace('_', ' ').title(), inline=True)
                dm_embed.add_field(name="Invited by", value=interaction.user.display_name, inline=True)
                dm_embed.add_field(name="Server", value=interaction.guild.name, inline=True)
                dm_embed.set_footer(text="Click a button below to respond")

                view = InvitationDMView(
                    team_manager=iracing_team_manager,
                    invitation_id=result,
                    team_id=team_id,
                    team_name=team_info['name'],
                    team_tag=team_info.get('tag', ''),
                    role=role_value,
                    guild_id=interaction.guild.id,
                    guild_name=interaction.guild.name,
                    invited_by_name=interaction.user.display_name
                )

                await member.send(embed=dm_embed, view=view)
                dm_sent = True
            except discord.Forbidden:
                pass  # Can't DM user
            except Exception as e:
                print(f"❌ Error sending invitation DM: {e}")

            if dm_sent:
                embed.set_footer(text="They can accept/decline via the DM buttons")
            else:
                embed.set_footer(text="Could not DM user. They can use /iracing_team_invites to respond.")

            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ Failed to create invitation.", ephemeral=True)

    @bot.tree.command(name="iracing_team_invites", description="View your pending team invitations")
    async def iracing_team_invites(interaction: discord.Interaction):
        """View pending team invitations"""
        await interaction.response.defer(ephemeral=True)

        invitations = iracing_team_manager.get_user_invitations(interaction.user.id, interaction.guild.id)

        if not invitations:
            await interaction.followup.send("📭 You have no pending team invitations.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📨 Pending Team Invitations",
            color=discord.Color.blue()
        )

        for inv in invitations:
            team_display = f"**{inv['team_name']}**"
            if inv.get('team_tag'):
                team_display += f" [{inv['team_tag']}]"

            embed.add_field(
                name=team_display,
                value=f"Role: {inv['role'].title()}\nInvitation ID: `{inv['id']}`",
                inline=False
            )

        embed.set_footer(text="Use /iracing_team_accept <id> or /iracing_team_decline <id>")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @bot.tree.command(name="iracing_team_accept", description="Accept a team invitation")
    @app_commands.describe(invitation_id="Invitation ID from /iracing_team_invites")
    async def iracing_team_accept(interaction: discord.Interaction, invitation_id: int):
        """Accept a team invitation"""
        await interaction.response.defer()

        success = iracing_team_manager.accept_invitation(invitation_id, interaction.user.id)

        if success:
            # Get team info for the message
            invitations = iracing_team_manager.get_user_invitations(interaction.user.id, interaction.guild.id)
            await interaction.followup.send(f"✅ You have joined the team! Welcome aboard! 🏁")
        else:
            await interaction.followup.send("❌ Could not accept invitation. It may have expired or already been responded to.", ephemeral=True)

    @bot.tree.command(name="iracing_team_decline", description="Decline a team invitation")
    @app_commands.describe(invitation_id="Invitation ID from /iracing_team_invites")
    async def iracing_team_decline(interaction: discord.Interaction, invitation_id: int):
        """Decline a team invitation"""
        await interaction.response.defer(ephemeral=True)

        success = iracing_team_manager.decline_invitation(invitation_id, interaction.user.id)

        if success:
            await interaction.followup.send("✅ Invitation declined.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Could not decline invitation. It may have expired or already been responded to.", ephemeral=True)

    @bot.tree.command(name="iracing_team_leave", description="Leave a team")
    @app_commands.describe(team_name="Team to leave")
    @app_commands.autocomplete(team_name=team_name_autocomplete)
    async def iracing_team_leave(interaction: discord.Interaction, team_name: str):
        """Leave a team"""
        await interaction.response.defer()

        # Find team by name
        team_info = iracing_team_manager.get_team_by_name(interaction.guild.id, team_name)
        if not team_info:
            await interaction.followup.send(f"❌ Team not found: '{team_name}'", ephemeral=True)
            return

        # Remove member
        success = iracing_team_manager.remove_team_member(team_info['id'], interaction.user.id)

        if success:
            await interaction.followup.send(
                f"✅ You have left **{team_info['name']}** [{team_info.get('tag', '')}]"
            )
        else:
            await interaction.followup.send("❌ Failed to leave team.", ephemeral=True)

    @bot.tree.command(name="iracing_team_info", description="View team information")
    @app_commands.describe(team_name="Team to view")
    @app_commands.autocomplete(team_name=team_name_autocomplete)
    async def iracing_team_info(interaction: discord.Interaction, team_name: str):
        """View detailed team information"""
        await interaction.response.defer()

        # Find team by name
        team_info = iracing_team_manager.get_team_by_name(interaction.guild.id, team_name)
        if not team_info:
            await interaction.followup.send(f"❌ Team not found: '{team_name}'", ephemeral=True)
            return

        team_id = team_info['id']

        # Get full team info
        full_team_info = iracing_team_manager.get_team_info(team_id)

        # Get team members
        members = iracing_team_manager.get_team_members(team_id)

        # Create visualization
        image_buffer = iracing_viz.create_team_info_display(
            team_info=full_team_info or team_info,
            members=members
        )

        # Send as file attachment
        file = discord.File(fp=image_buffer, filename="iracing_team_info.png")
        await interaction.followup.send(file=file)

    @bot.tree.command(name="iracing_team_list", description="List all teams in this server")
    async def iracing_team_list(interaction: discord.Interaction):
        """List all teams in the server"""
        await interaction.response.defer()

        teams = iracing_team_manager.list_server_teams(interaction.guild.id)

        if not teams:
            await interaction.followup.send("No teams found in this server. Create one with `/iracing_team_create`!")
            return

        # Create visualization
        image_buffer = iracing_viz.create_team_list_table(
            guild_name=interaction.guild.name,
            teams=teams
        )

        # Send as file attachment
        file = discord.File(fp=image_buffer, filename="iracing_team_list.png")
        await interaction.followup.send(file=file)

    @bot.tree.command(name="iracing_my_teams", description="View your teams")
    async def iracing_my_teams(interaction: discord.Interaction):
        """View teams you're a member of"""
        await interaction.response.defer()

        teams = iracing_team_manager.get_user_teams(interaction.user.id, interaction.guild.id)

        if not teams:
            await interaction.followup.send(
                "You're not in any teams yet. Join a team or create one with `/iracing_team_create`!",
                ephemeral=True
            )
            return

        # Create visualization
        image_buffer = iracing_viz.create_team_list_table(
            guild_name=f"{interaction.user.display_name}'s Teams",
            teams=teams
        )

        # Send as file attachment
        file = discord.File(fp=image_buffer, filename="iracing_my_teams.png")
        await interaction.followup.send(file=file, ephemeral=True)

    # ==================== EVENT SCHEDULING COMMANDS ====================

    async def notify_team_of_event(event_id: int, team_id: int, team_name: str,
                                    team_tag: str, event_name: str, event_start: datetime,
                                    event_type: str, series_name: str, track_name: str,
                                    guild: discord.Guild):
        """Send DM notifications to all team members about a new event"""
        from features.team_menu import EventResponseDMView

        members = iracing_team_manager.get_team_members(team_id)
        timestamp = int(event_start.timestamp())
        tag_display = f" [{team_tag}]" if team_tag else ""

        for member_data in members:
            try:
                user = bot.get_user(member_data['discord_user_id'])
                if not user:
                    user = await bot.fetch_user(member_data['discord_user_id'])

                if user:
                    embed = discord.Embed(
                        title="New Team Event Scheduled",
                        description=f"**{event_name}**",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Team", value=f"{team_name}{tag_display}", inline=True)
                    embed.add_field(name="Type", value=event_type.replace('_', ' ').title(), inline=True)
                    embed.add_field(name="When", value=f"<t:{timestamp}:F>\n<t:{timestamp}:R>", inline=False)

                    if series_name:
                        embed.add_field(name="Series", value=series_name, inline=True)
                    if track_name:
                        embed.add_field(name="Track", value=track_name, inline=True)

                    embed.add_field(name="Server", value=guild.name, inline=False)
                    embed.set_footer(text="Click a button below to set your availability")

                    view = EventResponseDMView(
                        team_manager=iracing_team_manager,
                        event_id=event_id,
                        event_name=event_name,
                        team_name=f"{team_name}{tag_display}",
                        guild_id=guild.id,
                        guild_name=guild.name
                    )

                    await user.send(embed=embed, view=view)

            except discord.Forbidden:
                pass  # User has DMs disabled
            except Exception as e:
                print(f"❌ Error notifying user {member_data['discord_user_id']} about event: {e}")

    @bot.tree.command(name="iracing_team_schedule", description="Schedule a team event")
    @app_commands.describe(
        team_name="Team to schedule event for",
        event_name="Name of the event",
        event_type="Type of event",
        event_time="When the event starts (e.g., 'tomorrow 8pm', 'Jan 15 7:00pm')",
        duration="Duration in minutes (for endurance events)",
        series="iRacing series name",
        track="Track name",
        notes="Additional notes"
    )
    @app_commands.autocomplete(team_name=team_name_autocomplete)
    @app_commands.choices(event_type=[
        app_commands.Choice(name="Practice", value="practice"),
        app_commands.Choice(name="Qualifying", value="qualifying"),
        app_commands.Choice(name="Race", value="race"),
        app_commands.Choice(name="Endurance Race", value="endurance")
    ])
    async def iracing_team_schedule(
        interaction: discord.Interaction,
        team_name: str,
        event_name: str,
        event_type: app_commands.Choice[str],
        event_time: str,
        duration: Optional[int] = None,
        series: Optional[str] = None,
        track: Optional[str] = None,
        notes: Optional[str] = None
    ):
        """Schedule a team event (managers only)"""
        await interaction.response.defer()

        # Find team by name
        team_info = iracing_team_manager.get_team_by_name(interaction.guild.id, team_name)
        if not team_info:
            await interaction.followup.send(f"❌ Team not found: '{team_name}'", ephemeral=True)
            return

        team_id = team_info['id']

        # Check if user is team manager
        user_teams = iracing_team_manager.get_user_teams(interaction.user.id, interaction.guild.id)
        user_team = next((t for t in user_teams if t['id'] == team_id), None)

        if not user_team or user_team['role'] != 'manager':
            await interaction.followup.send("❌ Only team managers can schedule events.", ephemeral=True)
            return

        # Parse event time
        try:
            from dateutil import parser as dateparser
            event_start = dateparser.parse(event_time, fuzzy=True)
            if not event_start:
                raise ValueError("Could not parse time")
            # If parsed date is in the past, assume next year
            if event_start < datetime.now():
                event_start = event_start.replace(year=datetime.now().year + 1)
        except Exception:
            await interaction.followup.send(
                "❌ Could not parse event time. Try formats like:\n"
                "- 'tomorrow 8pm'\n"
                "- 'January 15 7:00pm EST'\n"
                "- '2025-01-15 19:00'",
                ephemeral=True
            )
            return

        # Create event
        event_id = iracing_team_manager.create_event(
            team_id=team_id,
            guild_id=interaction.guild.id,
            event_name=event_name,
            event_type=event_type.value,
            event_start=event_start,
            created_by=interaction.user.id,
            event_duration_minutes=duration,
            series_name=series,
            track_name=track,
            notes=notes
        )

        if event_id:
            # Send confirmation embed
            tag_display = f" [{team_info.get('tag', '')}]" if team_info.get('tag') else ""
            timestamp = int(event_start.timestamp())

            embed = discord.Embed(
                title="Event Scheduled",
                description=f"**{event_name}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Team", value=f"{team_info['name']}{tag_display}", inline=True)
            embed.add_field(name="Type", value=event_type.name, inline=True)
            embed.add_field(name="When", value=f"<t:{timestamp}:F> (<t:{timestamp}:R>)", inline=False)

            if series:
                embed.add_field(name="Series", value=series, inline=True)
            if track:
                embed.add_field(name="Track", value=track, inline=True)
            if duration:
                embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)

            embed.add_field(name="Event ID", value=f"`{event_id}`", inline=True)
            embed.set_footer(text="Team members are being notified via DM")

            await interaction.followup.send(embed=embed)

            # Notify team members via DM
            await notify_team_of_event(
                event_id=event_id,
                team_id=team_id,
                team_name=team_info['name'],
                team_tag=team_info.get('tag', ''),
                event_name=event_name,
                event_start=event_start,
                event_type=event_type.value,
                series_name=series,
                track_name=track,
                guild=interaction.guild
            )
        else:
            await interaction.followup.send("❌ Failed to create event.", ephemeral=True)

    @bot.tree.command(name="iracing_team_events", description="View upcoming team events")
    @app_commands.describe(team_name="Team to view events for")
    @app_commands.autocomplete(team_name=team_name_autocomplete)
    async def iracing_team_events(
        interaction: discord.Interaction,
        team_name: str
    ):
        """View upcoming events for a team"""
        await interaction.response.defer()

        # Find team by name
        team_info = iracing_team_manager.get_team_by_name(interaction.guild.id, team_name)
        if not team_info:
            await interaction.followup.send(f"❌ Team not found: '{team_name}'", ephemeral=True)
            return

        team_id = team_info['id']
        events = iracing_team_manager.get_team_events(team_id, upcoming_only=True)

        tag_display = f" [{team_info.get('tag', '')}]" if team_info.get('tag') else ""

        if not events:
            await interaction.followup.send(
                f"📅 No upcoming events for **{team_info['name']}**{tag_display}"
            )
            return

        embed = discord.Embed(
            title=f"Upcoming Events: {team_info['name']}{tag_display}",
            color=discord.Color.blue()
        )

        for event in events[:10]:  # Limit to 10 events
            timestamp = int(event['start'].timestamp())
            event_details = f"<t:{timestamp}:F> (<t:{timestamp}:R>)"

            if event.get('series'):
                event_details += f"\nSeries: {event['series']}"
            if event.get('track'):
                event_details += f"\nTrack: {event['track']}"

            event_details += f"\nEvent ID: `{event['id']}`"

            embed.add_field(
                name=f"{event['type'].replace('_', ' ').title()}: {event['name']}",
                value=event_details,
                inline=False
            )

        embed.set_footer(text="Use /iracing_team_event_roster <event_id> to see who's available")
        await interaction.followup.send(embed=embed)

    @bot.tree.command(name="iracing_team_event_roster", description="View event participation roster")
    @app_commands.describe(event_id="Event ID to view roster for")
    async def iracing_team_event_roster(
        interaction: discord.Interaction,
        event_id: int
    ):
        """View who's signed up for an event"""
        await interaction.response.defer()

        # Get event details
        event = iracing_team_manager.get_event_details(event_id)
        if not event:
            await interaction.followup.send("❌ Event not found.", ephemeral=True)
            return

        # Check if event belongs to a team in this guild
        if event['guild_id'] != interaction.guild.id:
            await interaction.followup.send("❌ Event not found in this server.", ephemeral=True)
            return

        # Get availability
        availability = iracing_team_manager.get_event_availability(event_id)

        # Get all team members to show who hasn't responded
        team_members = iracing_team_manager.get_team_members(event['team_id'])
        responded_ids = {a['discord_user_id'] for a in availability}

        tag_display = f" [{event['team_tag']}]" if event.get('team_tag') else ""
        timestamp = int(event['event_start'].timestamp())

        embed = discord.Embed(
            title=f"Event Roster: {event['event_name']}",
            description=f"**{event['team_name']}**{tag_display}\n<t:{timestamp}:F>",
            color=discord.Color.blue()
        )

        # Group by status
        available = []
        unavailable = []
        maybe = []
        confirmed = []
        no_response = []

        for a in availability:
            name = a.get('iracing_name') or f"<@{a['discord_user_id']}>"
            if a['status'] == 'available':
                available.append(name)
            elif a['status'] == 'unavailable':
                unavailable.append(name)
            elif a['status'] == 'maybe':
                maybe.append(name)
            elif a['status'] == 'confirmed':
                confirmed.append(name)

        for member in team_members:
            if member['discord_user_id'] not in responded_ids:
                name = member.get('iracing_name')
                if not name:
                    user = bot.get_user(member['discord_user_id'])
                    name = user.display_name if user else f"<@{member['discord_user_id']}>"
                no_response.append(name)

        if confirmed:
            embed.add_field(name=f"Confirmed ({len(confirmed)})", value="\n".join(confirmed), inline=True)
        if available:
            embed.add_field(name=f"Available ({len(available)})", value="\n".join(available), inline=True)
        if maybe:
            embed.add_field(name=f"Maybe ({len(maybe)})", value="\n".join(maybe), inline=True)
        if unavailable:
            embed.add_field(name=f"Unavailable ({len(unavailable)})", value="\n".join(unavailable), inline=True)
        if no_response:
            embed.add_field(name=f"No Response ({len(no_response)})", value="\n".join(no_response[:10]), inline=True)

        total_possible = len(available) + len(confirmed) + len(maybe)
        embed.set_footer(text=f"Total possible drivers: {total_possible}")

        await interaction.followup.send(embed=embed)

    print("✅ iRacing team commands loaded")
