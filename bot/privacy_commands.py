"""
GDPR Privacy Commands for Discord Bot
Provides user-facing commands for data rights per GDPR
"""

import discord
from discord import app_commands
from discord.ui import View, Button
import json
import io
from datetime import datetime


class ConsentView(View):
    """Interactive view for consent collection"""

    def __init__(self, privacy_manager, user_id: int, username: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.privacy_manager = privacy_manager
        self.user_id = user_id
        self.username = username
        self.consent_given = None

    @discord.ui.button(label="✅ I Accept", style=discord.ButtonStyle.green)
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        """User accepts data processing"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not for you!", ephemeral=True)
            return

        success = self.privacy_manager.record_consent(
            self.user_id,
            self.username,
            consent_given=True,
            consent_method='interactive_button'
        )

        if success:
            await interaction.response.send_message(
                "✅ **Consent Recorded**\n\n"
                "Thank you! Your consent has been recorded. You can now use all bot features.\n\n"
                "**Your Rights:**\n"
                "• `/download_my_data` - Export all your data\n"
                "• `/delete_my_data` - Delete all your data\n"
                "• `/wompbot_noconsent` - Withdraw consent anytime\n"
                "• `/privacy_policy` - View full privacy policy",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to record consent. Please try again or contact an administrator.",
                ephemeral=True
            )

        self.consent_given = True
        self.stop()

    @discord.ui.button(label="❌ I Decline", style=discord.ButtonStyle.red)
    async def decline_button(self, interaction: discord.Interaction, button: Button):
        """User declines data processing"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not for you!", ephemeral=True)
            return

        await interaction.response.send_message(
            "📋 **Consent Declined**\n\n"
            "You have declined data processing. The bot will not collect or store your data.\n\n"
            "**Limited Functionality:**\n"
            "Without consent, most bot features will be unavailable. You can change your "
            "mind anytime with `/wompbot_consent`.\n\n"
            "**What Happens Now:**\n"
            "• Your messages will not be stored\n"
            "• Statistics won't include your data\n"
            "• Features requiring data storage won't work\n"
            "• You can still view public information",
            ephemeral=True
        )

        self.privacy_manager.record_consent(
            self.user_id,
            self.username,
            consent_given=False,
            consent_method='interactive_button'
        )

        self.consent_given = False
        self.stop()

    @discord.ui.button(label="📜 Read Policy", style=discord.ButtonStyle.gray)
    async def read_policy_button(self, interaction: discord.Interaction, button: Button):
        """Show privacy policy"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not for you!", ephemeral=True)
            return

        policy = self.privacy_manager.get_privacy_policy()

        if policy:
            # Truncate policy for Discord's 4096 character limit
            policy_text = policy['policy_text'][:3900] + "\n\n... (Use `/privacy_policy` for full policy)"

            embed = discord.Embed(
                title="🔒 WompBot Privacy Policy",
                description=policy_text,
                color=discord.Color.blue(),
                timestamp=policy['effective_date']
            )
            embed.set_footer(text=f"Version {policy['version']}")

            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ Failed to load privacy policy. Please try again later.",
                ephemeral=True
            )


class DeleteConfirmView(View):
    """Confirmation view for data deletion"""

    def __init__(self, privacy_manager, user_id: int):
        super().__init__(timeout=300)
        self.privacy_manager = privacy_manager
        self.user_id = user_id
        self.confirmed = False

    @discord.ui.button(label="⚠️ Yes, Delete Everything", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: discord.Interaction, button: Button):
        """Confirm deletion"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not for you!", ephemeral=True)
            return

        await interaction.response.send_message(
            "🔄 Deleting your data... This may take a moment.",
            ephemeral=True
        )

        # Schedule deletion with 30-day grace period
        success = self.privacy_manager.schedule_data_deletion(self.user_id, grace_period_days=30)

        if success:
            await interaction.followup.send(
                "✅ **Data Deletion Scheduled**\n\n"
                "Your data deletion has been scheduled for **30 days from now**.\n\n"
                "**What This Means:**\n"
                "• Your data collection is stopped immediately\n"
                "• You're automatically opted out of all features\n"
                "• In 30 days, all your data will be permanently deleted\n\n"
                "**Grace Period:**\n"
                "You have 30 days to change your mind. Use `/cancel_deletion` to "
                "restore your account and data before permanent deletion.\n\n"
                "**Questions?** Use `/privacy_support` for assistance.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Failed to schedule deletion. Please contact an administrator.",
                ephemeral=True
            )

        self.confirmed = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel_delete(self, interaction: discord.Interaction, button: Button):
        """Cancel deletion"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not for you!", ephemeral=True)
            return

        await interaction.response.send_message(
            "✅ Deletion cancelled. Your data remains intact.",
            ephemeral=True
        )

        self.confirmed = False
        self.stop()


def setup_privacy_commands(bot, db, privacy_manager):
    """
    Setup all GDPR privacy commands

    Args:
        bot: Discord bot instance
        db: Database instance
        privacy_manager: GDPRPrivacyManager instance
    """

    @bot.tree.command(name="wompbot_consent", description="Give consent for data processing (required for most features)")
    async def wompbot_consent(interaction: discord.Interaction):
        """Collect user consent for data processing"""
        user_id = interaction.user.id
        username = str(interaction.user)

        # Check if already consented
        existing_consent = privacy_manager.check_consent(user_id)

        if existing_consent and existing_consent['consent_given'] and not existing_consent['consent_withdrawn']:
            await interaction.response.send_message(
                "✅ You have already given consent for data processing.\n\n"
                "Use `/wompbot_noconsent` if you wish to withdraw it.",
                ephemeral=True
            )
            return

        # Show consent form
        embed = discord.Embed(
            title="🔒 Data Processing Consent Required",
            description=(
                "WompBot needs your consent to collect and process your data per GDPR.\n\n"
                "**What We Collect:**\n"
                "• Your messages and interactions\n"
                "• Usage statistics and patterns\n"
                "• Claims, quotes, and participation data\n\n"
                "**How We Use It:**\n"
                "• Provide bot features (stats, reminders, etc.)\n"
                "• Generate server analytics\n"
                "• Track claims and fact-checks\n\n"
                "**Your Rights:**\n"
                "• Access your data anytime (`/download_my_data`)\n"
                "• Delete your data anytime (`/delete_my_data`)\n"
                "• Withdraw consent anytime (`/wompbot_noconsent`)\n\n"
                "**Privacy Policy:** Use `/privacy_policy` to read full policy\n\n"
                "⚠️ Without consent, most bot features will be unavailable."
            ),
            color=discord.Color.blue()
        )

        view = ConsentView(privacy_manager, user_id, username)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @bot.tree.command(name="wompbot_noconsent", description="Withdraw consent and opt out of data collection")
    async def wompbot_noconsent(interaction: discord.Interaction):
        """Withdraw data processing consent"""
        user_id = interaction.user.id
        username = str(interaction.user)

        success = privacy_manager.record_consent(
            user_id,
            username,
            consent_given=False,
            consent_method='command'
        )

        if success:
            await interaction.response.send_message(
                "✅ **Consent Withdrawn**\n\n"
                "Your consent has been withdrawn. You are now opted out of data collection.\n\n"
                "**What This Means:**\n"
                "• Future messages won't be stored\n"
                "• Most bot features are disabled\n"
                "• Your existing data remains (for now)\n\n"
                "**Delete Your Data:**\n"
                "Use `/delete_my_data` to permanently delete all stored data.\n\n"
                "**Change Your Mind:**\n"
                "Use `/wompbot_consent` to opt back in anytime.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to withdraw consent. Please try again or contact an administrator.",
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
                    "❌ Failed to export your data. Please try again later.",
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
                title="📦 Your Data Export",
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

            embed.set_footer(text="Export valid for 48 hours • Keep this file secure")
            embed.timestamp = datetime.now()

            await interaction.followup.send(
                embed=embed,
                file=file,
                ephemeral=True
            )

        except Exception as e:
            print(f"❌ Data export error: {e}")
            import traceback
            traceback.print_exc()

            await interaction.followup.send(
                "❌ An error occurred during data export. Please contact an administrator.",
                ephemeral=True
            )

    @bot.tree.command(name="delete_my_data", description="Permanently delete all your data (GDPR Art. 17 - Right to Erasure)")
    async def delete_my_data(interaction: discord.Interaction):
        """Request permanent deletion of all user data"""
        user_id = interaction.user.id

        # Show warning and confirmation
        embed = discord.Embed(
            title="⚠️ Permanent Data Deletion",
            description=(
                "**WARNING: This action will delete ALL your data!**\n\n"
                "This will permanently delete:\n"
                "• All your messages (stored)\n"
                "• Your profile and statistics\n"
                "• All claims, quotes, and hot takes\n"
                "• Behavior analysis data\n"
                "• Debate history\n"
                "• iRacing linkage\n"
                "• Search history\n"
                "• Everything else\n\n"
                "**30-Day Grace Period:**\n"
                "Your data collection stops immediately, but permanent deletion "
                "happens in 30 days. You can cancel within this period.\n\n"
                "**GDPR Article 17 - Right to Erasure**\n\n"
                "⚠️ **This cannot be easily undone after 30 days!**"
            ),
            color=discord.Color.red()
        )

        view = DeleteConfirmView(privacy_manager, user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @bot.tree.command(name="privacy_settings", description="Review WompBot privacy posture for this server")
    @app_commands.default_permissions(administrator=True)
    async def privacy_settings(interaction: discord.Interaction):
        summary = db.get_consent_summary()
        storage = db.get_data_storage_overview()

        policy = privacy_manager.get_privacy_policy()
        policy_version = policy['version'] if policy else privacy_manager.CURRENT_POLICY_VERSION
        policy_date = (
            policy.get('effective_date').strftime('%Y-%m-%d')
            if policy and policy.get('effective_date')
            else 'N/A'
        )

        embed = discord.Embed(
            title="🔒 WompBot Privacy Settings",
            description=(
                "Overview of how WompBot operates in this server."
                " Use `/privacy_audit` for a detailed export."
            ),
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Consent Snapshot",
            value=(
                f"Active consent: **{summary['active_consent']}**\n"
                f"Withdrawn / declined: **{summary['withdrawn']}**\n"
                f"Pending replies: **{summary['pending']}**\n"
                f"Profiles marked opted-out: **{summary['opted_out_profiles']}**"
            ),
            inline=False
        )

        message_stats = storage.get('messages', {})
        message_count = message_stats.get('count', 0)
        last_entry = message_stats.get('last_entry')
        last_entry_display = last_entry.strftime('%Y-%m-%d %H:%M') if last_entry else 'N/A'

        embed.add_field(
            name="Stored Data (approx)",
            value=(
                f"Messages: **{message_count:,}** (latest: {last_entry_display})\n"
                f"Claims: **{storage.get('claims', {}).get('count', 0):,}** | "
                f"Behavior Analyses: **{storage.get('user_behavior', {}).get('count', 0):,}**\n"
                f"Stats Cache: **{storage.get('stats_cache', {}).get('count', 0):,}** entries\n"
                f"iRacing Meta Cache: **{storage.get('iracing_meta_cache', {}).get('count', 0):,}** | "
                f"History Cache: **{storage.get('iracing_history_cache', {}).get('count', 0):,}**"
            ),
            inline=False
        )

        embed.add_field(
            name="Key Modules Using Data",
            value=(
                "• Conversational AI (context up to 6 messages)\n"
                "• Claims tracking & quotes\n"
                "• Chat statistics & behavior insights\n"
                "• iRacing analytics & visualizations"
            ),
            inline=False
        )

        embed.set_footer(text=f"Privacy policy version {policy_version} • Effective {policy_date}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="privacy_audit", description="Generate a privacy compliance summary")
    @app_commands.default_permissions(administrator=True)
    async def privacy_audit(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        summary = db.get_consent_summary()
        storage = db.get_data_storage_overview()

        audit_report = {
            "generated_at": datetime.utcnow().isoformat(),
            "guild_id": interaction.guild_id,
            "consent": summary,
            "storage": storage,
            "policy_version": privacy_manager.CURRENT_POLICY_VERSION,
        }

        policy = privacy_manager.get_privacy_policy()
        if policy:
            audit_report["policy"] = {
                "version": policy.get("version"),
                "effective_date": policy.get("effective_date").isoformat() if policy.get("effective_date") else None,
            }

        buffer = io.StringIO()
        json.dump(audit_report, buffer, indent=2)
        buffer.seek(0)

        file = discord.File(fp=io.BytesIO(buffer.getvalue().encode('utf-8')), filename="wompbot_privacy_audit.json")

        await interaction.followup.send(
            content=(
                "📄 Audit report generated. Share this with server moderators or members "
                "who want to understand what WompBot stores."
            ),
            file=file,
            ephemeral=True
        )

    @bot.tree.command(name="cancel_deletion", description="Cancel your scheduled data deletion")
    async def cancel_deletion(interaction: discord.Interaction):
        """Cancel a scheduled data deletion"""
        user_id = interaction.user.id

        success = privacy_manager.cancel_scheduled_deletion(user_id)

        if success:
            await interaction.response.send_message(
                "✅ **Deletion Cancelled**\n\n"
                "Your scheduled data deletion has been cancelled.\n\n"
                "**What This Means:**\n"
                "• Your data is safe and will not be deleted\n"
                "• Data collection has been re-enabled\n"
                "• You can use all bot features again\n\n"
                "Welcome back! 👋",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ No scheduled deletion found for your account.\n\n"
                "If you believe this is an error, contact an administrator.",
                ephemeral=True
            )

    @bot.tree.command(name="privacy_policy", description="View the complete privacy policy")
    async def privacy_policy_command(interaction: discord.Interaction):
        """Display the full privacy policy"""
        policy = privacy_manager.get_privacy_policy()

        if not policy:
            await interaction.response.send_message(
                "❌ Failed to load privacy policy. Please try again later.",
                ephemeral=True
            )
            return

        # Split policy into chunks for Discord's embed limits
        policy_text = policy['policy_text']
        chunks = [policy_text[i:i+4000] for i in range(0, len(policy_text), 4000)]

        embeds = []
        for i, chunk in enumerate(chunks[:10]):  # Max 10 embeds
            embed = discord.Embed(
                title=f"🔒 WompBot Privacy Policy (Part {i+1}/{len(chunks)})" if i > 0 else "🔒 WompBot Privacy Policy",
                description=chunk,
                color=discord.Color.blue()
            )

            if i == 0:
                embed.add_field(
                    name="📱 Quick Links",
                    value=(
                        "`/wompbot_consent` - Give consent\n"
                        "`/download_my_data` - Export your data\n"
                        "`/delete_my_data` - Delete your data\n"
                        "`/privacy_support` - Get help"
                    ),
                    inline=False
                )

            embed.set_footer(text=f"Version {policy['version']} • Effective {policy['effective_date'].strftime('%Y-%m-%d')}")
            embeds.append(embed)

        await interaction.response.send_message(embeds=embeds, ephemeral=True)

    @bot.tree.command(name="my_privacy_status", description="View your current privacy and consent status")
    async def my_privacy_status(interaction: discord.Interaction):
        """Show user's current privacy status"""
        user_id = interaction.user.id

        consent = privacy_manager.check_consent(user_id)

        embed = discord.Embed(
            title="🔒 Your Privacy Status",
            color=discord.Color.green() if (consent and consent['consent_given']) else discord.Color.orange()
        )

        if consent and consent['consent_given'] and not consent['consent_withdrawn']:
            status = "✅ Active - Data collection enabled"
            embed.add_field(name="Consent Status", value=status, inline=False)
            embed.add_field(
                name="Consent Given",
                value=consent['consent_date'].strftime('%Y-%m-%d %H:%M UTC'),
                inline=True
            )
            embed.add_field(
                name="Policy Version",
                value=consent['consent_version'],
                inline=True
            )
            embed.add_field(
                name="Extended Retention",
                value="Yes" if consent['extended_retention'] else "No",
                inline=True
            )
        else:
            status = "❌ Opted Out - Data collection disabled"
            embed.add_field(name="Consent Status", value=status, inline=False)

            if consent and consent['consent_withdrawn']:
                embed.add_field(
                    name="Withdrawn On",
                    value=consent['consent_withdrawn_date'].strftime('%Y-%m-%d %H:%M UTC'),
                    inline=True
                )

        embed.add_field(
            name="Your Rights",
            value=(
                "`/download_my_data` - Export all your data\n"
                "`/delete_my_data` - Request deletion\n"
                "`/wompbot_noconsent` - Opt out\n"
                "`/wompbot_consent` - Opt back in"
            ),
            inline=False
        )

        embed.set_footer(text="Questions? Use /privacy_support")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="privacy_support", description="Get help with privacy and data questions")
    async def privacy_support(interaction: discord.Interaction):
        """Provide privacy support information"""
        embed = discord.Embed(
            title="🛟 Privacy Support",
            description=(
                "Need help with your privacy or data?\n\n"
                "**Common Questions:**"
            ),
            color=discord.Color.blue()
        )

        embed.add_field(
            name="What data do you collect?",
            value=(
                "Messages, usernames, interactions, claims, quotes, behavioral patterns, "
                "and usage statistics. See `/privacy_policy` for full details."
            ),
            inline=False
        )

        embed.add_field(
            name="Can I see all my data?",
            value="Yes! Use `/download_my_data` to export everything in JSON format.",
            inline=False
        )

        embed.add_field(
            name="How do I delete my data?",
            value=(
                "Use `/delete_my_data` to schedule permanent deletion. You'll have "
                "a 30-day grace period to change your mind."
            ),
            inline=False
        )

        embed.add_field(
            name="What if I opt out?",
            value=(
                "Use `/wompbot_noconsent` to stop data collection. Most bot features "
                "will be unavailable, but your existing data remains until you delete it."
            ),
            inline=False
        )

        embed.add_field(
            name="Is my data secure?",
            value=(
                "Yes! We use encryption, parameterized queries, access controls, and "
                "audit logging to protect your data."
            ),
            inline=False
        )

        embed.add_field(
            name="Do you sell my data?",
            value="**NO.** We never sell your data to third parties.",
            inline=False
        )

        embed.add_field(
            name="Who can I contact?",
            value=(
                "For privacy concerns, contact the bot administrator:\n"
                "[Administrator Contact Information Here]\n\n"
                "For GDPR complaints (EU residents):\n"
                "You have the right to lodge a complaint with your supervisory authority."
            ),
            inline=False
        )

        embed.set_footer(text="GDPR Compliant • Your data, your rights")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    print("✅ GDPR privacy commands registered")
