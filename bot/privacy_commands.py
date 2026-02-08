"""
GDPR Privacy Commands for Discord Bot
Provides user-facing commands for data rights per GDPR
"""

import discord
from discord.ui import View, Button
import json
import io
from datetime import datetime


class DeleteConfirmView(View):
    """Confirmation view for data deletion"""

    def __init__(self, privacy_manager, user_id: int):
        super().__init__(timeout=300)
        self.privacy_manager = privacy_manager
        self.user_id = user_id
        self.confirmed = False

    @discord.ui.button(label="Yes, Delete Everything", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: Button):
        """Confirm deletion"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you!", ephemeral=True)
            return

        await interaction.response.send_message(
            "Deleting your data... This may take a moment.",
            ephemeral=True
        )

        # Schedule deletion with 30-day grace period
        success = self.privacy_manager.schedule_data_deletion(self.user_id, grace_period_days=30)

        if success:
            await interaction.followup.send(
                "**Data Deletion Scheduled**\n\n"
                "Your data deletion has been scheduled for **30 days from now**.\n\n"
                "**What This Means:**\n"
                "- Your data collection is stopped immediately\n"
                "- You're automatically opted out of all features\n"
                "- In 30 days, all your data will be permanently deleted\n\n"
                "**Grace Period:**\n"
                "You have 30 days to change your mind. Use `/delete_my_data` again "
                "to cancel the pending deletion and restore your account.\n\n",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "Failed to schedule deletion. Please contact an administrator.",
                ephemeral=True
            )

        self.confirmed = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel_delete(self, interaction: discord.Interaction, button: Button):
        """Cancel deletion"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you!", ephemeral=True)
            return

        await interaction.response.send_message(
            "Deletion cancelled. Your data remains intact.",
            ephemeral=True
        )

        self.confirmed = False
        self.stop()


class CancelDeletionView(View):
    """Confirmation view for cancelling a pending deletion"""

    def __init__(self, privacy_manager, user_id: int):
        super().__init__(timeout=300)
        self.privacy_manager = privacy_manager
        self.user_id = user_id

    @discord.ui.button(label="Cancel Pending Deletion", style=discord.ButtonStyle.green)
    async def confirm_cancel(self, interaction: discord.Interaction, button: Button):
        """Cancel the pending deletion"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you!", ephemeral=True)
            return

        success = self.privacy_manager.cancel_scheduled_deletion(self.user_id)

        if success:
            await interaction.response.send_message(
                "**Deletion Cancelled**\n\n"
                "Your scheduled data deletion has been cancelled.\n\n"
                "**What This Means:**\n"
                "- Your data is safe and will not be deleted\n"
                "- Data collection has been re-enabled\n"
                "- You can use all bot features again\n",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Failed to cancel deletion. Please contact an administrator.",
                ephemeral=True
            )

        self.stop()

    @discord.ui.button(label="Keep Deletion Scheduled", style=discord.ButtonStyle.gray)
    async def keep_deletion(self, interaction: discord.Interaction, button: Button):
        """Keep the pending deletion"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not for you!", ephemeral=True)
            return

        await interaction.response.send_message(
            "OK, your data deletion remains scheduled.",
            ephemeral=True
        )
        self.stop()


def setup_privacy_commands(bot, db, privacy_manager):
    """
    Setup all GDPR privacy commands

    Args:
        bot: Discord bot instance
        db: Database instance
        privacy_manager: GDPRPrivacyManager instance
    """

    @bot.tree.command(name="wompbot_optout", description="Opt out of data collection and processing")
    async def wompbot_optout(interaction: discord.Interaction):
        """Opt out of data processing"""
        user_id = interaction.user.id
        username = str(interaction.user)

        # Check if already opted out
        existing_consent = privacy_manager.check_consent(user_id)
        if existing_consent and existing_consent.get('consent_withdrawn'):
            await interaction.response.send_message(
                "You are already opted out of data collection.\n\n"
                "Use `/download_my_data` to export your data or `/delete_my_data` to delete it.",
                ephemeral=True
            )
            return

        success = privacy_manager.record_consent(
            user_id,
            username,
            consent_given=False,
            consent_method='command'
        )

        if success:
            await interaction.response.send_message(
                "**You've Opted Out**\n\n"
                "You are now opted out of data collection and processing.\n\n"
                "**What This Means:**\n"
                "- Future messages won't be stored with content\n"
                "- Behavioral profiling is disabled\n"
                "- Bot will still respond but without personalization\n"
                "- Your existing data remains (for now)\n\n"
                "**Delete Your Data:**\n"
                "Use `/delete_my_data` to permanently delete all stored data.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Failed to opt out. Please try again or contact an administrator.",
                ephemeral=True
            )

    @bot.tree.command(name="download_my_data", description="Export all your data (GDPR Art. 15 - Right of Access)")
    async def download_my_data(interaction: discord.Interaction):
        """Export all user data in machine-readable format"""
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id

        try:
            # Export all data
            data_export = privacy_manager.export_user_data(user_id)

            if not data_export:
                await interaction.followup.send(
                    "Failed to export your data. Please try again later.",
                    ephemeral=True
                )
                return

            # Convert to JSON
            json_data = json.dumps(data_export, indent=2, default=str, ensure_ascii=False)

            # Create file
            file_name = f"wompbot_data_export_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            file = discord.File(io.BytesIO(json_data.encode('utf-8')), filename=file_name)

            # Create embed with summary
            embed = discord.Embed(
                title="Your Data Export",
                description=(
                    "Here's all your data in machine-readable JSON format.\n\n"
                    "**GDPR Article 15 - Right of Access**\n"
                    "This export includes everything we have stored about you."
                ),
                color=discord.Color.green()
            )

            summary = data_export.get('summary', {})
            embed.add_field(name="Messages", value=f"{summary.get('total_messages', 0):,}", inline=True)
            embed.add_field(name="Claims", value=f"{summary.get('total_claims', 0):,}", inline=True)
            embed.add_field(name="Quotes", value=f"{summary.get('total_quotes', 0):,}", inline=True)
            embed.add_field(name="Hot Takes", value=f"{summary.get('total_hot_takes', 0):,}", inline=True)
            embed.add_field(name="Debates", value=f"{summary.get('total_debates', 0):,}", inline=True)
            embed.add_field(name="Account Age", value=f"{summary.get('account_age_days', 0)} days", inline=True)

            embed.set_footer(text="Export valid for 48 hours - Keep this file secure")
            embed.timestamp = datetime.now()

            await interaction.followup.send(
                embed=embed,
                file=file,
                ephemeral=True
            )

        except Exception as e:
            print(f"Data export error: {e}")
            import traceback
            traceback.print_exc()

            await interaction.followup.send(
                "An error occurred during data export. Please contact an administrator.",
                ephemeral=True
            )

    @bot.tree.command(name="delete_my_data", description="Permanently delete all your data (GDPR Art. 17 - Right to Erasure)")
    async def delete_my_data(interaction: discord.Interaction):
        """Request permanent deletion of all user data, or cancel a pending deletion"""
        user_id = interaction.user.id

        # Check if there's already a pending deletion
        has_pending = privacy_manager.has_pending_deletion(user_id)

        if has_pending:
            # Show cancel option instead of creating a new deletion request
            embed = discord.Embed(
                title="Pending Data Deletion",
                description=(
                    "You already have a data deletion scheduled.\n\n"
                    "Your data will be permanently deleted after the 30-day grace period.\n\n"
                    "Would you like to **cancel** the pending deletion and restore your account?"
                ),
                color=discord.Color.orange()
            )

            view = CancelDeletionView(privacy_manager, user_id)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

        # No pending deletion - show the normal deletion confirmation
        embed = discord.Embed(
            title="Permanent Data Deletion",
            description=(
                "**WARNING: This action will delete ALL your data!**\n\n"
                "This will permanently delete:\n"
                "- All your messages (stored)\n"
                "- Your profile and statistics\n"
                "- All claims, quotes, and hot takes\n"
                "- Behavior analysis data\n"
                "- Debate history\n"
                "- iRacing linkage\n"
                "- Search history\n"
                "- Everything else\n\n"
                "**30-Day Grace Period:**\n"
                "Your data collection stops immediately, but permanent deletion "
                "happens in 30 days. You can cancel by running `/delete_my_data` again.\n\n"
                "**GDPR Article 17 - Right to Erasure**\n\n"
                "**This cannot be easily undone after 30 days!**"
            ),
            color=discord.Color.red()
        )

        view = DeleteConfirmView(privacy_manager, user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    print("GDPR privacy commands registered (3 commands: optout, download, delete)")
