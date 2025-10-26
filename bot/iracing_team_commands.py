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


def setup_iracing_team_commands(bot, iracing_team_manager):
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
        team_id="Your team ID",
        member="Discord user to invite",
        role="Member role (driver, crew_chief, spotter, manager)"
    )
    async def iracing_team_invite(
        interaction: discord.Interaction,
        team_id: int,
        member: discord.Member,
        role: str = "driver"
    ):
        """Invite a member to join a team"""
        await interaction.response.defer()

        # Validate role
        valid_roles = ['driver', 'crew_chief', 'spotter', 'manager']
        if role.lower() not in valid_roles:
            await interaction.followup.send(
                f"❌ Invalid role. Must be one of: {', '.join(valid_roles)}",
                ephemeral=True
            )
            return

        # Get team info
        team_info = iracing_team_manager.get_team_info(team_id)
        if not team_info:
            await interaction.followup.send("❌ Team not found.", ephemeral=True)
            return

        # Check if user is team manager
        user_teams = iracing_team_manager.get_user_teams(interaction.user.id, interaction.guild.id)
        user_team = next((t for t in user_teams if t['id'] == team_id), None)

        if not user_team or user_team['role'] != 'manager':
            await interaction.followup.send("❌ Only team managers can invite members.", ephemeral=True)
            return

        # Add member
        success = iracing_team_manager.add_team_member(team_id, member.id, role.lower())

        if success:
            embed = discord.Embed(
                title="✅ Member Added to Team",
                description=f"{member.mention} has been added to **{team_info['name']}** [{team_info['tag']}]",
                color=discord.Color.green()
            )
            embed.add_field(name="Role", value=role.title(), inline=True)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ Failed to add member to team.", ephemeral=True)

    @bot.tree.command(name="iracing_team_leave", description="Leave a team")
    @app_commands.describe(team_id="Team ID to leave")
    async def iracing_team_leave(interaction: discord.Interaction, team_id: int):
        """Leave a team"""
        await interaction.response.defer()

        # Get team info
        team_info = iracing_team_manager.get_team_info(team_id)
        if not team_info:
            await interaction.followup.send("❌ Team not found.", ephemeral=True)
            return

        # Remove member
        success = iracing_team_manager.remove_team_member(team_id, interaction.user.id)

        if success:
            await interaction.followup.send(
                f"✅ You have left **{team_info['name']}** [{team_info['tag']}]"
            )
        else:
            await interaction.followup.send("❌ Failed to leave team.", ephemeral=True)

    @bot.tree.command(name="iracing_team_info", description="View team information")
    @app_commands.describe(team_id="Team ID to view")
    async def iracing_team_info(interaction: discord.Interaction, team_id: int):
        """View detailed team information"""
        await interaction.response.defer()

        # Get team info
        team_info = iracing_team_manager.get_team_info(team_id)
        if not team_info:
            await interaction.followup.send("❌ Team not found.", ephemeral=True)
            return

        # Get team members
        members = iracing_team_manager.get_team_members(team_id)

        embed = discord.Embed(
            title=f"🏁 {team_info['name']} [{team_info['tag']}]",
            description=team_info.get('description', 'No description'),
            color=discord.Color.blue()
        )

        # Group members by role
        drivers = [m for m in members if m['role'] == 'driver']
        managers = [m for m in members if m['role'] == 'manager']
        crew_chiefs = [m for m in members if m['role'] == 'crew_chief']
        spotters = [m for m in members if m['role'] == 'spotter']

        if managers:
            manager_list = '\n'.join([
                f"<@{m['discord_user_id']}> - {m['iracing_name'] or 'Not linked'}"
                for m in managers
            ])
            embed.add_field(name="👑 Managers", value=manager_list, inline=False)

        if drivers:
            driver_list = '\n'.join([
                f"<@{m['discord_user_id']}> - {m['iracing_name'] or 'Not linked'}"
                for m in drivers[:10]  # Limit to first 10
            ])
            if len(drivers) > 10:
                driver_list += f"\n... and {len(drivers) - 10} more"
            embed.add_field(name="🏎️ Drivers", value=driver_list, inline=False)

        if crew_chiefs:
            cc_list = '\n'.join([
                f"<@{m['discord_user_id']}> - {m['iracing_name'] or 'Not linked'}"
                for m in crew_chiefs
            ])
            embed.add_field(name="🔧 Crew Chiefs", value=cc_list, inline=False)

        if spotters:
            spotter_list = '\n'.join([
                f"<@{m['discord_user_id']}> - {m['iracing_name'] or 'Not linked'}"
                for m in spotters
            ])
            embed.add_field(name="📻 Spotters", value=spotter_list, inline=False)

        embed.add_field(name="Total Members", value=str(len(members)), inline=True)
        embed.add_field(name="Team ID", value=f"`{team_id}`", inline=True)
        embed.set_footer(text=f"Created {team_info['created_at'].strftime('%Y-%m-%d')}")

        await interaction.followup.send(embed=embed)

    @bot.tree.command(name="iracing_team_list", description="List all teams in this server")
    async def iracing_team_list(interaction: discord.Interaction):
        """List all teams in the server"""
        await interaction.response.defer()

        teams = iracing_team_manager.list_server_teams(interaction.guild.id)

        if not teams:
            await interaction.followup.send("No teams found in this server. Create one with `/iracing_team_create`!")
            return

        embed = discord.Embed(
            title=f"🏁 iRacing Teams in {interaction.guild.name}",
            description=f"Found {len(teams)} team(s)",
            color=discord.Color.blue()
        )

        for team in teams[:25]:  # Discord limit is 25 fields
            member_text = f"{team['member_count']} member(s)"
            if team['description']:
                desc = team['description'][:100]  # Truncate long descriptions
                if len(team['description']) > 100:
                    desc += "..."
            else:
                desc = "No description"

            embed.add_field(
                name=f"[{team['tag']}] {team['name']}",
                value=f"{desc}\n{member_text} • ID: `{team['id']}`",
                inline=False
            )

        await interaction.followup.send(embed=embed)

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

        embed = discord.Embed(
            title="🏁 Your iRacing Teams",
            description=f"You're in {len(teams)} team(s)",
            color=discord.Color.blue()
        )

        for team in teams:
            role_emoji = {
                'manager': '👑',
                'driver': '🏎️',
                'crew_chief': '🔧',
                'spotter': '📻'
            }.get(team['role'], '👤')

            embed.add_field(
                name=f"{role_emoji} [{team['tag']}] {team['name']}",
                value=f"Role: **{team['role'].title()}** • ID: `{team['id']}`",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    print("✅ iRacing team commands loaded")
