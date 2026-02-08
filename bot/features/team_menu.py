"""
Interactive Team Management Menu System
Allows users to manage teams through Discord DMs with interactive buttons and menus
"""

import discord
from discord import ui
from typing import Optional, List
from datetime import datetime
import math


# --- Pagination Helpers ---

ITEMS_PER_PAGE = 25


def _paginate(items: list, page: int) -> tuple:
    """
    Return a page slice and total page count.

    Args:
        items: Full list of items
        page: Zero-indexed page number

    Returns:
        (page_items, total_pages)
    """
    total_pages = max(1, math.ceil(len(items) / ITEMS_PER_PAGE))
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    return items[start:end], total_pages


def _page_footer(page: int, total_pages: int) -> str:
    """Return 'Page X of Y' string for embed footers."""
    return f"Page {page + 1} of {total_pages}"


class TeamMenuView(ui.View):
    """Main team management menu"""

    def __init__(self, team_manager, user_id: int, guild_id: int, guild_name: str, bot=None):
        super().__init__(timeout=300)  # 5 minute timeout
        self.team_manager = team_manager
        self.user_id = user_id
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.bot = bot

    @ui.button(label="My Teams", style=discord.ButtonStyle.primary, row=0)
    async def my_teams(self, interaction: discord.Interaction, button: ui.Button):
        """View teams the user is in"""
        teams = self.team_manager.get_user_teams(self.user_id, self.guild_id)

        if not teams:
            embed = discord.Embed(
                title="My Teams",
                description="You're not in any teams yet.",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                title="My Teams",
                description=f"Your teams in **{self.guild_name}**:",
                color=discord.Color.blue()
            )
            for team in teams:
                tag = f" [{team['tag']}]" if team.get('tag') else ""
                embed.add_field(
                    name=f"{team['name']}{tag}",
                    value=f"Role: **{team['role'].title()}**",
                    inline=False
                )

        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Invitations", style=discord.ButtonStyle.secondary, row=0)
    async def invitations(self, interaction: discord.Interaction, button: ui.Button):
        """View pending invitations"""
        invites = self.team_manager.get_user_invitations(self.user_id, self.guild_id)

        if not invites:
            embed = discord.Embed(
                title="Pending Invitations",
                description="You have no pending team invitations.",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = discord.Embed(
                title="Pending Invitations",
                description="Select an invitation to respond:",
                color=discord.Color.blue()
            )
            for inv in invites:
                tag = f" [{inv['team_tag']}]" if inv.get('team_tag') else ""
                embed.add_field(
                    name=f"{inv['team_name']}{tag}",
                    value=f"Role: **{inv['role'].title()}**",
                    inline=False
                )

            # Show invitation response view
            view = InvitationResponseView(self.team_manager, self.user_id, self.guild_id, self.guild_name, invites, self.bot)
            await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="All Server Teams", style=discord.ButtonStyle.secondary, row=0)
    async def all_teams(self, interaction: discord.Interaction, button: ui.Button):
        """View all teams in the server"""
        teams = self.team_manager.list_server_teams(self.guild_id)

        if not teams:
            embed = discord.Embed(
                title="Server Teams",
                description=f"No teams in **{self.guild_name}** yet.",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                title="Server Teams",
                description=f"All teams in **{self.guild_name}**:",
                color=discord.Color.blue()
            )
            for team in teams[:10]:  # Limit to 10
                tag = f" [{team['tag']}]" if team.get('tag') else ""
                embed.add_field(
                    name=f"{team['name']}{tag}",
                    value=f"Members: **{team['member_count']}**",
                    inline=True
                )

        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Manage Teams", style=discord.ButtonStyle.primary, row=1)
    async def manage_teams(self, interaction: discord.Interaction, button: ui.Button):
        """Manage team members (managers only)"""
        managed_teams = self.team_manager.get_managed_teams(self.user_id, self.guild_id)

        if not managed_teams:
            embed = discord.Embed(
                title="Manage Teams",
                description="You don't manage any teams.\n\nOnly team managers can manage members.",
                color=discord.Color.orange()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = discord.Embed(
                title="Manage Teams",
                description="Select a team to manage:",
                color=discord.Color.blue()
            )
            view = ManageTeamSelectView(self.team_manager, self.user_id, self.guild_id, self.guild_name, managed_teams, self.bot)
            await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Leave Team", style=discord.ButtonStyle.danger, row=2)
    async def leave_team(self, interaction: discord.Interaction, button: ui.Button):
        """Leave a team"""
        teams = self.team_manager.get_user_teams(self.user_id, self.guild_id)

        if not teams:
            embed = discord.Embed(
                title="Leave Team",
                description="You're not in any teams.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = discord.Embed(
                title="Leave Team",
                description="Select a team to leave:",
                color=discord.Color.orange()
            )
            view = LeaveTeamView(self.team_manager, self.user_id, self.guild_id, self.guild_name, teams, self.bot)
            await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Close", style=discord.ButtonStyle.secondary, row=2)
    async def close_menu(self, interaction: discord.Interaction, button: ui.Button):
        """Close the menu"""
        embed = discord.Embed(
            title="Team Management",
            description="Menu closed. Send `!team` again to reopen.",
            color=discord.Color.grey()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


class InvitationResponseView(ui.View):
    """View for responding to invitations with pagination support"""

    def __init__(self, team_manager, user_id: int, guild_id: int, guild_name: str,
                 invitations: List[dict], bot=None, page: int = 0):
        super().__init__(timeout=300)
        self.team_manager = team_manager
        self.user_id = user_id
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.invitations = invitations
        self.bot = bot
        self.page = page

        # Paginate and add select menu for invitations if there are any
        if invitations:
            page_items, self.total_pages = _paginate(invitations, page)
            options = [
                discord.SelectOption(
                    label=f"{inv['team_name']}" + (f" [{inv['team_tag']}]" if inv.get('team_tag') else ""),
                    description=f"Role: {inv['role'].title()}",
                    value=str(inv['id'])
                )
                for inv in page_items
            ]
            self.invitation_select = ui.Select(
                placeholder="Select an invitation...",
                options=options,
                row=0
            )
            self.invitation_select.callback = self.select_callback
            self.add_item(self.invitation_select)

            # Add pagination buttons if needed
            if self.total_pages > 1:
                prev_btn = ui.Button(
                    label="Previous Page",
                    style=discord.ButtonStyle.secondary,
                    disabled=(page <= 0),
                    row=2
                )
                prev_btn.callback = self._prev_page
                self.add_item(prev_btn)

                page_indicator = ui.Button(
                    label=_page_footer(page, self.total_pages),
                    style=discord.ButtonStyle.secondary,
                    disabled=True,
                    row=2
                )
                self.add_item(page_indicator)

                next_btn = ui.Button(
                    label="Next Page",
                    style=discord.ButtonStyle.secondary,
                    disabled=(page >= self.total_pages - 1),
                    row=2
                )
                next_btn.callback = self._next_page
                self.add_item(next_btn)
        else:
            self.total_pages = 1

        self.selected_invitation_id = None

    async def _prev_page(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Pending Invitations",
            description="Select an invitation to respond:",
            color=discord.Color.blue()
        )
        if self.total_pages > 1:
            embed.set_footer(text=_page_footer(self.page - 1, self.total_pages))
        view = InvitationResponseView(
            self.team_manager, self.user_id, self.guild_id, self.guild_name,
            self.invitations, self.bot, page=self.page - 1
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def _next_page(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Pending Invitations",
            description="Select an invitation to respond:",
            color=discord.Color.blue()
        )
        if self.total_pages > 1:
            embed.set_footer(text=_page_footer(self.page + 1, self.total_pages))
        view = InvitationResponseView(
            self.team_manager, self.user_id, self.guild_id, self.guild_name,
            self.invitations, self.bot, page=self.page + 1
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def select_callback(self, interaction: discord.Interaction):
        self.selected_invitation_id = int(self.invitation_select.values[0])
        inv = next((i for i in self.invitations if i['id'] == self.selected_invitation_id), None)
        if inv:
            embed = discord.Embed(
                title=f"Invitation: {inv['team_name']}",
                description=f"Role: **{inv['role'].title()}**\n\nDo you want to accept or decline?",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Accept", style=discord.ButtonStyle.success, row=1)
    async def accept(self, interaction: discord.Interaction, button: ui.Button):
        if not self.selected_invitation_id:
            await interaction.response.send_message("Please select an invitation first.", ephemeral=True)
            return

        success = self.team_manager.accept_invitation(self.selected_invitation_id, self.user_id)
        if success:
            embed = discord.Embed(
                title="Invitation Accepted",
                description="Welcome to the team!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="Error",
                description="Could not accept invitation. It may have expired.",
                color=discord.Color.red()
            )

        # Go back to main menu
        view = TeamMenuView(self.team_manager, self.user_id, self.guild_id, self.guild_name, self.bot)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Decline", style=discord.ButtonStyle.danger, row=1)
    async def decline(self, interaction: discord.Interaction, button: ui.Button):
        if not self.selected_invitation_id:
            await interaction.response.send_message("Please select an invitation first.", ephemeral=True)
            return

        success = self.team_manager.decline_invitation(self.selected_invitation_id, self.user_id)
        if success:
            embed = discord.Embed(
                title="Invitation Declined",
                description="The invitation has been declined.",
                color=discord.Color.grey()
            )
        else:
            embed = discord.Embed(
                title="Error",
                description="Could not decline invitation.",
                color=discord.Color.red()
            )

        view = TeamMenuView(self.team_manager, self.user_id, self.guild_id, self.guild_name, self.bot)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="Team Management",
            description=f"Managing teams for **{self.guild_name}**\n\nSelect an option:",
            color=discord.Color.blue()
        )
        view = TeamMenuView(self.team_manager, self.user_id, self.guild_id, self.guild_name, self.bot)
        await interaction.response.edit_message(embed=embed, view=view)


class LeaveTeamView(ui.View):
    """View for leaving a team with pagination support"""

    def __init__(self, team_manager, user_id: int, guild_id: int, guild_name: str,
                 teams: List[dict], bot=None, page: int = 0):
        super().__init__(timeout=300)
        self.team_manager = team_manager
        self.user_id = user_id
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.teams = teams
        self.bot = bot
        self.page = page

        # Paginate and add select menu for teams
        page_items, self.total_pages = _paginate(teams, page)
        options = [
            discord.SelectOption(
                label=f"{team['name']}" + (f" [{team['tag']}]" if team.get('tag') else ""),
                description=f"Role: {team['role'].title()}",
                value=str(team['id'])
            )
            for team in page_items
        ]
        self.team_select = ui.Select(
            placeholder="Select a team to leave...",
            options=options,
            row=0
        )
        self.team_select.callback = self.select_callback
        self.add_item(self.team_select)

        # Add pagination buttons if needed
        if self.total_pages > 1:
            prev_btn = ui.Button(
                label="Previous Page",
                style=discord.ButtonStyle.secondary,
                disabled=(page <= 0),
                row=2
            )
            prev_btn.callback = self._prev_page
            self.add_item(prev_btn)

            page_indicator = ui.Button(
                label=_page_footer(page, self.total_pages),
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=2
            )
            self.add_item(page_indicator)

            next_btn = ui.Button(
                label="Next Page",
                style=discord.ButtonStyle.secondary,
                disabled=(page >= self.total_pages - 1),
                row=2
            )
            next_btn.callback = self._next_page
            self.add_item(next_btn)

        self.selected_team_id = None
        self.selected_team_name = None

    async def _prev_page(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Leave Team",
            description="Select a team to leave:",
            color=discord.Color.orange()
        )
        if self.total_pages > 1:
            embed.set_footer(text=_page_footer(self.page - 1, self.total_pages))
        view = LeaveTeamView(
            self.team_manager, self.user_id, self.guild_id, self.guild_name,
            self.teams, self.bot, page=self.page - 1
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def _next_page(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Leave Team",
            description="Select a team to leave:",
            color=discord.Color.orange()
        )
        if self.total_pages > 1:
            embed.set_footer(text=_page_footer(self.page + 1, self.total_pages))
        view = LeaveTeamView(
            self.team_manager, self.user_id, self.guild_id, self.guild_name,
            self.teams, self.bot, page=self.page + 1
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def select_callback(self, interaction: discord.Interaction):
        self.selected_team_id = int(self.team_select.values[0])
        team = next((t for t in self.teams if t['id'] == self.selected_team_id), None)
        if team:
            self.selected_team_name = team['name']
            embed = discord.Embed(
                title=f"Leave {team['name']}?",
                description="Are you sure you want to leave this team?",
                color=discord.Color.orange()
            )
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Confirm Leave", style=discord.ButtonStyle.danger, row=1)
    async def confirm_leave(self, interaction: discord.Interaction, button: ui.Button):
        if not self.selected_team_id:
            await interaction.response.send_message("Please select a team first.", ephemeral=True)
            return

        success = self.team_manager.remove_team_member(self.selected_team_id, self.user_id)
        if success:
            embed = discord.Embed(
                title="Left Team",
                description=f"You have left **{self.selected_team_name}**.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="Error",
                description="Could not leave team.",
                color=discord.Color.red()
            )

        view = TeamMenuView(self.team_manager, self.user_id, self.guild_id, self.guild_name, self.bot)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="Team Management",
            description=f"Managing teams for **{self.guild_name}**\n\nSelect an option:",
            color=discord.Color.blue()
        )
        view = TeamMenuView(self.team_manager, self.user_id, self.guild_id, self.guild_name, self.bot)
        await interaction.response.edit_message(embed=embed, view=view)


class ManageTeamSelectView(ui.View):
    """View for selecting which team to manage members for, with pagination support"""

    def __init__(self, team_manager, user_id: int, guild_id: int, guild_name: str,
                 teams: List[dict], bot=None, page: int = 0):
        super().__init__(timeout=300)
        self.team_manager = team_manager
        self.user_id = user_id
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.teams = teams
        self.bot = bot
        self.page = page

        # Paginate and add select menu for teams
        page_items, self.total_pages = _paginate(teams, page)
        options = [
            discord.SelectOption(
                label=f"{team['name']}" + (f" [{team['tag']}]" if team.get('tag') else ""),
                description=f"{team['member_count']} members",
                value=str(team['id'])
            )
            for team in page_items
        ]
        self.team_select = ui.Select(
            placeholder="Select a team to manage...",
            options=options,
            row=0
        )
        self.team_select.callback = self.select_callback
        self.add_item(self.team_select)

        # Add pagination buttons if needed
        if self.total_pages > 1:
            prev_btn = ui.Button(
                label="Previous Page",
                style=discord.ButtonStyle.secondary,
                disabled=(page <= 0),
                row=2
            )
            prev_btn.callback = self._prev_page
            self.add_item(prev_btn)

            page_indicator = ui.Button(
                label=_page_footer(page, self.total_pages),
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=2
            )
            self.add_item(page_indicator)

            next_btn = ui.Button(
                label="Next Page",
                style=discord.ButtonStyle.secondary,
                disabled=(page >= self.total_pages - 1),
                row=2
            )
            next_btn.callback = self._next_page
            self.add_item(next_btn)

    async def _prev_page(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Manage Teams",
            description="Select a team to manage:",
            color=discord.Color.blue()
        )
        if self.total_pages > 1:
            embed.set_footer(text=_page_footer(self.page - 1, self.total_pages))
        view = ManageTeamSelectView(
            self.team_manager, self.user_id, self.guild_id, self.guild_name,
            self.teams, self.bot, page=self.page - 1
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def _next_page(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Manage Teams",
            description="Select a team to manage:",
            color=discord.Color.blue()
        )
        if self.total_pages > 1:
            embed.set_footer(text=_page_footer(self.page + 1, self.total_pages))
        view = ManageTeamSelectView(
            self.team_manager, self.user_id, self.guild_id, self.guild_name,
            self.teams, self.bot, page=self.page + 1
        )
        await interaction.response.edit_message(embed=embed, view=view)

    def _get_member_name(self, member):
        """Get display name for a member"""
        if member.get('iracing_name'):
            return member['iracing_name']
        if self.bot:
            user = self.bot.get_user(member['discord_user_id'])
            if user:
                return user.display_name
        return f"User {member['discord_user_id']}"

    async def select_callback(self, interaction: discord.Interaction):
        team_id = int(self.team_select.values[0])
        team = next((t for t in self.teams if t['id'] == team_id), None)

        if team:
            # Get team members
            members = self.team_manager.get_team_members(team_id)

            if not members:
                embed = discord.Embed(
                    title=f"{team['name']} Members",
                    description="This team has no members.",
                    color=discord.Color.orange()
                )
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                embed = discord.Embed(
                    title=f"{team['name']} Members",
                    description="Select a member to manage:",
                    color=discord.Color.blue()
                )
                for member in members[:10]:
                    name = self._get_member_name(member)
                    embed.add_field(
                        name=name,
                        value=f"Role: **{member['role'].replace('_', ' ').title()}**",
                        inline=True
                    )

                view = MemberManagementView(
                    self.team_manager, self.user_id, self.guild_id, self.guild_name,
                    team_id, team['name'], members, self.bot
                )
                await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="Team Management",
            description=f"Managing teams for **{self.guild_name}**\n\nSelect an option:",
            color=discord.Color.blue()
        )
        view = TeamMenuView(self.team_manager, self.user_id, self.guild_id, self.guild_name, self.bot)
        await interaction.response.edit_message(embed=embed, view=view)


class MemberManagementView(ui.View):
    """View for managing team members with pagination support"""

    def __init__(self, team_manager, user_id: int, guild_id: int, guild_name: str,
                 team_id: int, team_name: str, members: List[dict], bot=None, page: int = 0):
        super().__init__(timeout=300)
        self.team_manager = team_manager
        self.user_id = user_id
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.team_id = team_id
        self.team_name = team_name
        self.members = members
        self.bot = bot
        self.page = page

        # Add select menu for members (exclude self - can't manage yourself)
        other_members = [m for m in members if m['discord_user_id'] != user_id]
        self._other_members = other_members

        if other_members:
            page_items, self.total_pages = _paginate(other_members, page)
            options = [
                discord.SelectOption(
                    label=self._get_member_name(m)[:100],
                    description=f"Role: {m['role'].replace('_', ' ').title()}",
                    value=str(m['discord_user_id'])
                )
                for m in page_items
            ]
            self.member_select = ui.Select(
                placeholder="Select a member...",
                options=options,
                row=0
            )
            self.member_select.callback = self.select_callback
            self.add_item(self.member_select)

            # Add pagination buttons if needed
            if self.total_pages > 1:
                prev_btn = ui.Button(
                    label="Previous Page",
                    style=discord.ButtonStyle.secondary,
                    disabled=(page <= 0),
                    row=2
                )
                prev_btn.callback = self._prev_page
                self.add_item(prev_btn)

                page_indicator = ui.Button(
                    label=_page_footer(page, self.total_pages),
                    style=discord.ButtonStyle.secondary,
                    disabled=True,
                    row=2
                )
                self.add_item(page_indicator)

                next_btn = ui.Button(
                    label="Next Page",
                    style=discord.ButtonStyle.secondary,
                    disabled=(page >= self.total_pages - 1),
                    row=2
                )
                next_btn.callback = self._next_page
                self.add_item(next_btn)
        else:
            self.total_pages = 1

        self.selected_member = None

    async def _prev_page(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"{self.team_name} Members",
            description="Select a member to manage:",
            color=discord.Color.blue()
        )
        if self.total_pages > 1:
            embed.set_footer(text=_page_footer(self.page - 1, self.total_pages))
        view = MemberManagementView(
            self.team_manager, self.user_id, self.guild_id, self.guild_name,
            self.team_id, self.team_name, self.members, self.bot, page=self.page - 1
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def _next_page(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"{self.team_name} Members",
            description="Select a member to manage:",
            color=discord.Color.blue()
        )
        if self.total_pages > 1:
            embed.set_footer(text=_page_footer(self.page + 1, self.total_pages))
        view = MemberManagementView(
            self.team_manager, self.user_id, self.guild_id, self.guild_name,
            self.team_id, self.team_name, self.members, self.bot, page=self.page + 1
        )
        await interaction.response.edit_message(embed=embed, view=view)

    def _get_member_name(self, member):
        """Get display name for a member"""
        if member.get('iracing_name'):
            return member['iracing_name']
        if self.bot:
            user = self.bot.get_user(member['discord_user_id'])
            if user:
                return user.display_name
        return f"User {member['discord_user_id']}"

    async def select_callback(self, interaction: discord.Interaction):
        member_id = int(self.member_select.values[0])
        self.selected_member = next((m for m in self.members if m['discord_user_id'] == member_id), None)

        if self.selected_member:
            name = self._get_member_name(self.selected_member)
            role = self.selected_member['role'].replace('_', ' ').title()
            embed = discord.Embed(
                title=f"Managing: {name}",
                description=f"Team: **{self.team_name}**\nCurrent Role: **{role}**\n\nSet new role:",
                color=discord.Color.blue()
            )
            view = MemberActionView(
                self.team_manager, self.user_id, self.guild_id, self.guild_name,
                self.team_id, self.team_name, self.selected_member, self.bot
            )
            await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Back", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        managed_teams = self.team_manager.get_managed_teams(self.user_id, self.guild_id)
        embed = discord.Embed(
            title="Manage Teams",
            description="Select a team to manage:",
            color=discord.Color.blue()
        )
        view = ManageTeamSelectView(self.team_manager, self.user_id, self.guild_id, self.guild_name, managed_teams, self.bot)
        await interaction.response.edit_message(embed=embed, view=view)


class MemberActionView(ui.View):
    """View for actions on a specific member"""

    def __init__(self, team_manager, user_id: int, guild_id: int, guild_name: str,
                 team_id: int, team_name: str, member: dict, bot=None):
        super().__init__(timeout=300)
        self.team_manager = team_manager
        self.user_id = user_id
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.team_id = team_id
        self.team_name = team_name
        self.member = member
        self.bot = bot
        self.member_name = self._get_member_name(member)
        self.current_role = member['role']

    def _get_member_name(self, member):
        """Get display name for a member"""
        if member.get('iracing_name'):
            return member['iracing_name']
        if self.bot:
            user = self.bot.get_user(member['discord_user_id'])
            if user:
                return user.display_name
        return f"User {member['discord_user_id']}"

    async def _change_role(self, interaction: discord.Interaction, new_role: str):
        """Helper to change member role"""
        if new_role == self.current_role:
            await interaction.response.send_message("That's already their role.", ephemeral=True)
            return

        success = self.team_manager.update_member_role(
            self.team_id,
            self.member['discord_user_id'],
            new_role
        )

        if success:
            embed = discord.Embed(
                title="Role Updated",
                description=f"**{self.member_name}**'s role changed from **{self.current_role.replace('_', ' ').title()}** to **{new_role.replace('_', ' ').title()}**",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="Error",
                description="Could not update role.",
                color=discord.Color.red()
            )

        view = TeamMenuView(self.team_manager, self.user_id, self.guild_id, self.guild_name, self.bot)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Driver", style=discord.ButtonStyle.primary, row=0)
    async def set_driver(self, interaction: discord.Interaction, button: ui.Button):
        await self._change_role(interaction, 'driver')

    @ui.button(label="Crew Chief", style=discord.ButtonStyle.primary, row=0)
    async def set_crew_chief(self, interaction: discord.Interaction, button: ui.Button):
        await self._change_role(interaction, 'crew_chief')

    @ui.button(label="Spotter", style=discord.ButtonStyle.primary, row=0)
    async def set_spotter(self, interaction: discord.Interaction, button: ui.Button):
        await self._change_role(interaction, 'spotter')

    @ui.button(label="Manager", style=discord.ButtonStyle.primary, row=0)
    async def set_manager(self, interaction: discord.Interaction, button: ui.Button):
        await self._change_role(interaction, 'manager')

    @ui.button(label="Remove from Team", style=discord.ButtonStyle.danger, row=2)
    async def remove_member(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title=f"Remove {self.member_name}?",
            description=f"Are you sure you want to remove **{self.member_name}** from **{self.team_name}**?",
            color=discord.Color.red()
        )
        view = ConfirmRemoveMemberView(
            self.team_manager, self.user_id, self.guild_id, self.guild_name,
            self.team_id, self.team_name, self.member, self.bot
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Back", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        members = self.team_manager.get_team_members(self.team_id)
        embed = discord.Embed(
            title=f"{self.team_name} Members",
            description="Select a member to manage:",
            color=discord.Color.blue()
        )
        for member in members[:10]:
            name = self._get_member_name(member)
            embed.add_field(
                name=name,
                value=f"Role: **{member['role'].replace('_', ' ').title()}**",
                inline=True
            )

        view = MemberManagementView(
            self.team_manager, self.user_id, self.guild_id, self.guild_name,
            self.team_id, self.team_name, members, self.bot
        )
        await interaction.response.edit_message(embed=embed, view=view)


class ConfirmRemoveMemberView(ui.View):
    """Confirmation view for removing a member"""

    def __init__(self, team_manager, user_id: int, guild_id: int, guild_name: str,
                 team_id: int, team_name: str, member: dict, bot=None):
        super().__init__(timeout=300)
        self.team_manager = team_manager
        self.user_id = user_id
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.team_id = team_id
        self.team_name = team_name
        self.member = member
        self.bot = bot
        self.member_name = self._get_member_name(member)

    def _get_member_name(self, member):
        """Get display name for a member"""
        if member.get('iracing_name'):
            return member['iracing_name']
        if self.bot:
            user = self.bot.get_user(member['discord_user_id'])
            if user:
                return user.display_name
        return f"User {member['discord_user_id']}"

    @ui.button(label="Confirm Remove", style=discord.ButtonStyle.danger, row=0)
    async def confirm_remove(self, interaction: discord.Interaction, button: ui.Button):
        success = self.team_manager.remove_team_member(self.team_id, self.member['discord_user_id'])

        if success:
            embed = discord.Embed(
                title="Member Removed",
                description=f"**{self.member_name}** has been removed from **{self.team_name}**.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="Error",
                description="Could not remove member.",
                color=discord.Color.red()
            )

        view = TeamMenuView(self.team_manager, self.user_id, self.guild_id, self.guild_name, self.bot)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=0)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        role = self.member['role'].replace('_', ' ').title()
        embed = discord.Embed(
            title=f"Managing: {self.member_name}",
            description=f"Team: **{self.team_name}**\nCurrent Role: **{role}**\n\nSet new role:",
            color=discord.Color.blue()
        )
        view = MemberActionView(
            self.team_manager, self.user_id, self.guild_id, self.guild_name,
            self.team_id, self.team_name, self.member, self.bot
        )
        await interaction.response.edit_message(embed=embed, view=view)


class ServerSelectView(ui.View):
    """View for selecting which server to manage teams for, with pagination support"""

    def __init__(self, team_manager, user_id: int, guilds: List[dict], bot=None, page: int = 0):
        super().__init__(timeout=300)
        self.team_manager = team_manager
        self.user_id = user_id
        self.guilds = guilds
        self.bot = bot
        self.page = page

        # Paginate and add select menu for servers
        page_items, self.total_pages = _paginate(guilds, page)
        options = [
            discord.SelectOption(
                label=guild['name'][:100],
                value=str(guild['id'])
            )
            for guild in page_items
        ]
        self.server_select = ui.Select(
            placeholder="Select a server...",
            options=options,
            row=0
        )
        self.server_select.callback = self.select_callback
        self.add_item(self.server_select)

        # Add pagination buttons if needed
        if self.total_pages > 1:
            prev_btn = ui.Button(
                label="Previous Page",
                style=discord.ButtonStyle.secondary,
                disabled=(page <= 0),
                row=1
            )
            prev_btn.callback = self._prev_page
            self.add_item(prev_btn)

            page_indicator = ui.Button(
                label=_page_footer(page, self.total_pages),
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=1
            )
            self.add_item(page_indicator)

            next_btn = ui.Button(
                label="Next Page",
                style=discord.ButtonStyle.secondary,
                disabled=(page >= self.total_pages - 1),
                row=1
            )
            next_btn.callback = self._next_page
            self.add_item(next_btn)

    async def _prev_page(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Team Management",
            description="Select a server to manage teams:",
            color=discord.Color.blue()
        )
        if self.total_pages > 1:
            embed.set_footer(text=_page_footer(self.page - 1, self.total_pages))
        view = ServerSelectView(
            self.team_manager, self.user_id, self.guilds, self.bot, page=self.page - 1
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def _next_page(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Team Management",
            description="Select a server to manage teams:",
            color=discord.Color.blue()
        )
        if self.total_pages > 1:
            embed.set_footer(text=_page_footer(self.page + 1, self.total_pages))
        view = ServerSelectView(
            self.team_manager, self.user_id, self.guilds, self.bot, page=self.page + 1
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def select_callback(self, interaction: discord.Interaction):
        guild_id = int(self.server_select.values[0])
        guild = next((g for g in self.guilds if g['id'] == guild_id), None)

        if guild:
            embed = discord.Embed(
                title="Team Management",
                description=f"Managing teams for **{guild['name']}**\n\nSelect an option:",
                color=discord.Color.blue()
            )
            view = TeamMenuView(self.team_manager, self.user_id, guild_id, guild['name'], self.bot)
            await interaction.response.edit_message(embed=embed, view=view)


class InvitationDMView(ui.View):
    """
    View with Accept/Decline buttons for team invitations sent via DM.
    Must store guild context since DMs have no guild.
    """

    def __init__(self, team_manager, invitation_id: int, team_id: int,
                 team_name: str, team_tag: str, role: str, guild_id: int,
                 guild_name: str, invited_by_name: str):
        super().__init__(timeout=86400)  # 24 hour timeout
        self.team_manager = team_manager
        self.invitation_id = invitation_id
        self.team_id = team_id
        self.team_name = team_name
        self.team_tag = team_tag
        self.role = role
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.invited_by_name = invited_by_name

    def _disable_all_buttons(self):
        """Disable all buttons after a response"""
        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True

    @ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: ui.Button):
        """Accept the team invitation"""
        success = self.team_manager.accept_invitation(
            self.invitation_id,
            interaction.user.id
        )

        if success:
            tag_display = f" [{self.team_tag}]" if self.team_tag else ""
            embed = discord.Embed(
                title="Welcome to the Team!",
                description=f"You have joined **{self.team_name}**{tag_display} as **{self.role.replace('_', ' ').title()}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Server", value=self.guild_name, inline=True)
            self._disable_all_buttons()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(
                "Could not accept invitation. It may have expired or already been responded to.",
                ephemeral=True
            )
        self.stop()

    @ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: ui.Button):
        """Decline the team invitation"""
        success = self.team_manager.decline_invitation(
            self.invitation_id,
            interaction.user.id
        )

        if success:
            embed = discord.Embed(
                title="Invitation Declined",
                description=f"You have declined the invitation to **{self.team_name}**",
                color=discord.Color.grey()
            )
            self._disable_all_buttons()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(
                "Could not decline invitation. It may have already been responded to.",
                ephemeral=True
            )
        self.stop()


class EventResponseDMView(ui.View):
    """
    View with availability buttons for event notifications sent via DM.
    Stores event and guild context for DM interactions.
    """

    def __init__(self, team_manager, event_id: int, event_name: str,
                 team_name: str, guild_id: int, guild_name: str):
        super().__init__(timeout=172800)  # 48 hour timeout
        self.team_manager = team_manager
        self.event_id = event_id
        self.event_name = event_name
        self.team_name = team_name
        self.guild_id = guild_id
        self.guild_name = guild_name

    def _disable_all_buttons(self):
        """Disable all buttons after a response"""
        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True

    async def _set_availability(self, interaction: discord.Interaction, status: str):
        """Helper to set availability and update message"""
        success = self.team_manager.set_driver_availability(
            event_id=self.event_id,
            discord_user_id=interaction.user.id,
            status=status
        )

        status_display = {
            'available': ('Available', discord.Color.green()),
            'unavailable': ('Unavailable', discord.Color.red()),
            'maybe': ('Maybe', discord.Color.orange())
        }

        display_text, color = status_display.get(status, (status.title(), discord.Color.grey()))

        if success:
            embed = discord.Embed(
                title=f"Availability Updated: {display_text}",
                description=f"Your availability for **{self.event_name}** ({self.team_name}) has been recorded.",
                color=color
            )
            embed.set_footer(text=f"Server: {self.guild_name}")
            self._disable_all_buttons()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message(
                "Could not update availability. The event may have been cancelled.",
                ephemeral=True
            )
        self.stop()

    @ui.button(label="Available", style=discord.ButtonStyle.success)
    async def available(self, interaction: discord.Interaction, button: ui.Button):
        await self._set_availability(interaction, 'available')

    @ui.button(label="Unavailable", style=discord.ButtonStyle.danger)
    async def unavailable(self, interaction: discord.Interaction, button: ui.Button):
        await self._set_availability(interaction, 'unavailable')

    @ui.button(label="Maybe", style=discord.ButtonStyle.secondary)
    async def maybe(self, interaction: discord.Interaction, button: ui.Button):
        await self._set_availability(interaction, 'maybe')


async def show_team_menu(message: discord.Message, bot, team_manager):
    """Show the team management menu in DMs"""
    user = message.author

    # Get mutual guilds
    mutual_guilds = []
    for guild in bot.guilds:
        member = guild.get_member(user.id)
        if member:
            mutual_guilds.append({'id': guild.id, 'name': guild.name})

    if not mutual_guilds:
        await message.channel.send("You're not in any servers with me!")
        return

    if len(mutual_guilds) == 1:
        # Only one server, go directly to menu
        guild = mutual_guilds[0]
        embed = discord.Embed(
            title="Team Management",
            description=f"Managing teams for **{guild['name']}**\n\nSelect an option:",
            color=discord.Color.blue()
        )
        view = TeamMenuView(team_manager, user.id, guild['id'], guild['name'], bot)
        await message.channel.send(embed=embed, view=view)
    else:
        # Multiple servers, show server selection
        embed = discord.Embed(
            title="Team Management",
            description="Select a server to manage teams:",
            color=discord.Color.blue()
        )
        view = ServerSelectView(team_manager, user.id, mutual_guilds, bot)
        await message.channel.send(embed=embed, view=view)
