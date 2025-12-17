"""
Help System for WompBot
Provides general help and detailed command documentation
"""

import discord
import os
from typing import Optional, Dict

class HelpSystem:
    """Manages help documentation for all commands"""

    def __init__(self):
        self.docs_path = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'commands')

        # Command documentation - will be loaded from files if they exist, otherwise use this
        self.command_docs = {
            "help": {
                "usage": "/help [command] or !help [command]",
                "description": "Show general help or detailed help for a specific command",
                "examples": [
                    "/help - Show all commands",
                    "/help stats - Show detailed stats command help",
                    "!help quotes - Show quotes command help"
                ]
            },
            "stats": {
                "usage": "/stats [@user]",
                "description": "View detailed statistics and behavior analysis for yourself or another user",
                "details": [
                    "Shows message count, question frequency, profanity analysis",
                    "Displays tone and conversation style",
                    "Includes participation history",
                    "Privacy: Respects opt-out status (use /wompbot_optout to opt out)"
                ],
                "examples": [
                    "/stats - View your own stats",
                    "/stats @username - View another user's stats"
                ]
            },
            "receipts": {
                "usage": "/receipts [@user] [keyword]",
                "description": "View tracked claims for a user with optional keyword filtering",
                "details": [
                    "Claims are automatically tracked when users make factual statements",
                    "Can be verified or fact-checked later",
                    "Keyword filter helps find specific claims"
                ],
                "examples": [
                    "/receipts - View your own claims",
                    "/receipts @username - View someone else's claims",
                    "/receipts @username election - Filter claims by keyword"
                ]
            },
            "quotes": {
                "usage": "/quotes [@user]",
                "description": "View saved quotes for a user",
                "details": [
                    "Quotes are saved by reacting to messages with ☁️ emoji",
                    "Anyone can save anyone's quotes",
                    "Quotes persist unless deleted"
                ],
                "examples": [
                    "/quotes - View your saved quotes",
                    "/quotes @username - View quotes from specific user"
                ]
            },
            "wompbot_optout": {
                "usage": "/wompbot_optout",
                "description": "Opt out of data collection and behavioral profiling",
                "details": [
                    "WompBot operates under Legitimate Interest (GDPR Art. 6.1.f)",
                    "By default, all users are opted-in for data collection",
                    "This enables personalized responses and feature access",
                    "When opted out:",
                    "  • Message content is not stored (redacted)",
                    "  • Behavioral profiling is disabled",
                    "  • Bot still responds but without personalization",
                    "  • Your existing data remains until deleted",
                    "You can still use /download_my_data and /delete_my_data"
                ],
                "examples": [
                    "/wompbot_optout - Stop data collection"
                ],
                "related": ["download_my_data", "delete_my_data", "my_privacy_status"]
            },
            "download_my_data": {
                "usage": "/download_my_data",
                "description": "Export all your data in JSON format (GDPR Art. 15 - Right of Access)",
                "details": [
                    "Exports everything WompBot has stored about you:",
                    "  • Messages and conversation history",
                    "  • Claims, quotes, and hot takes",
                    "  • Behavioral analysis data",
                    "  • Search logs and fact-checks",
                    "  • Reminders and events",
                    "  • iRacing linkage (if connected)",
                    "Data is provided in machine-readable JSON format",
                    "Export expires after 48 hours for security"
                ],
                "examples": [
                    "/download_my_data - Request full data export"
                ],
                "related": ["delete_my_data", "my_privacy_status", "wompbot_optout"]
            },
            "delete_my_data": {
                "usage": "/delete_my_data",
                "description": "Request permanent deletion of all your data (GDPR Art. 17 - Right to Erasure)",
                "details": [
                    "Deletion process:",
                    "  1. Opt-out from data collection immediately",
                    "  2. 30-day grace period begins",
                    "  3. Can cancel with /cancel_deletion",
                    "  4. After 30 days: permanent deletion",
                    "What gets deleted:",
                    "  • Messages, claims, quotes",
                    "  • Reminders and events",
                    "  • iRacing linkage",
                    "What is retained (legal requirement):",
                    "  • Audit logs (7 years)",
                    "  • Consent/opt-out records (proof of lawful processing)"
                ],
                "examples": [
                    "/delete_my_data - Schedule data deletion",
                    "/cancel_deletion - Cancel scheduled deletion"
                ],
                "related": ["download_my_data", "wompbot_optout", "my_privacy_status"]
            },
            "my_privacy_status": {
                "usage": "/my_privacy_status",
                "description": "View your current privacy and data processing status",
                "details": [
                    "Shows:",
                    "  • Whether you're opted in or out",
                    "  • Legal basis for data processing",
                    "  • What data is being collected",
                    "  • Available privacy commands"
                ],
                "examples": [
                    "/my_privacy_status - Check your status"
                ],
                "related": ["wompbot_optout", "download_my_data", "delete_my_data"]
            },
            "search": {
                "usage": "!search <query>",
                "description": "Manually trigger web search for information",
                "details": [
                    "Uses Tavily search API for current information",
                    "Results are formatted and provided as context",
                    "Rate limits: 5/hour, 20/day per user",
                    "Note: Bot automatically searches when needed during conversations"
                ],
                "examples": [
                    "!search what is the weather in Paris",
                    "!search latest news about AI"
                ]
            },
            "ping": {
                "usage": "!ping",
                "description": "Check bot latency and response time",
                "examples": [
                    "!ping - Show latency"
                ]
            }
        }

    def get_general_help(self) -> discord.Embed:
        """Generate general help embed with all commands"""
        embed = discord.Embed(
            title="🤖 WompBot Commands",
            description="Use `/help <command>` or `!help <command>` for detailed command information",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="@mention me",
            value="Tag me to chat. Powered by Claude 3.7 Sonnet for conversational responses with automatic web search.",
            inline=False
        )

        embed.add_field(
            name="📊 Statistics & Data",
            value=(
                "`/stats [@user]` - User statistics\n"
                "`/receipts [@user] [keyword]` - Tracked claims\n"
                "`/quotes [@user]` - Saved quotes\n"
                "`/stats_server [days]` - Server network graph\n"
                "`/stats_topics [days]` - Trending keywords\n"
                "`/stats_primetime [@user] [days]` - Activity heatmap\n"
                "`/stats_engagement [@user] [days]` - Engagement metrics"
            ),
            inline=False
        )

        embed.add_field(
            name="💬 Interactions",
            value=(
                "☁️ **Save Quote** - React with :cloud: to save a quote\n"
                "⚠️ **Fact-Check** - React with :warning: to fact-check (uses Claude + web search)\n"
                "Rate limits: 5-min cooldown, 10/day per user"
            ),
            inline=False
        )

        embed.add_field(
            name="🎮 iRacing",
            value=(
                "`/iracing_link <customer_id>` - Link your iRacing account\n"
                "`/iracing_stats [@user]` - View iRacing stats\n"
                "`/iracing_leaderboard` - Server iRacing leaderboard"
            ),
            inline=False
        )

        embed.add_field(
            name="📋 Other Commands",
            value=(
                "`!leaderboard <type> [days]` - Top users (messages/questions/profanity)\n"
                "`!search <query>` - Manual web search\n"
                "`!ping` - Check bot latency\n"
                "`!analyze [days]` - (Admin) Behavior analysis"
            ),
            inline=False
        )

        embed.add_field(
            name="🔒 Privacy & Data (Opt-Out Model)",
            value=(
                "`/wompbot_optout` - Opt out of data collection\n"
                "`/download_my_data` - Export your data (GDPR Art. 15)\n"
                "`/delete_my_data` - Delete your data (GDPR Art. 17)\n"
                "`/my_privacy_status` - View your privacy status\n"
                "`/privacy_policy` - View privacy policy\n"
                "`/tos` - View Terms of Service"
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ Rate Limits",
            value=(
                "• Tokens: 1,000/request, 10,000/hour\n"
                "• Context: 4000 tokens (auto-truncates)\n"
                "• Fact-checks: 5-min cooldown, 10/day\n"
                "• Searches: 5/hour, 20/day\n"
                "• Messages: 3s cooldown, 10/min"
            ),
            inline=False
        )

        embed.set_footer(text="Use /help <command> for detailed command help • By using WompBot, you accept /tos")

        return embed

    def get_command_help(self, command: str) -> Optional[discord.Embed]:
        """Generate detailed help for a specific command"""
        command = command.lower().strip().lstrip('/')

        # Try to load from file first
        doc_file = os.path.join(self.docs_path, f"{command}.md")
        if os.path.exists(doc_file):
            try:
                with open(doc_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Parse markdown and create embed
                    # For now, just show the raw content
                    embed = discord.Embed(
                        title=f"📖 Command: `/{command}`",
                        description=content[:4000],  # Discord limit
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="Documentation loaded from docs/commands/")
                    return embed
            except Exception as e:
                print(f"Error loading command doc for {command}: {e}")

        # Fall back to in-memory docs
        if command not in self.command_docs:
            return None

        doc = self.command_docs[command]

        embed = discord.Embed(
            title=f"📖 Command: `{doc['usage']}`",
            description=doc['description'],
            color=discord.Color.blue()
        )

        if 'details' in doc:
            embed.add_field(
                name="Details",
                value="\n".join(f"• {detail}" for detail in doc['details']),
                inline=False
            )

        if 'examples' in doc:
            embed.add_field(
                name="Examples",
                value="\n".join(f"`{ex}`" for ex in doc['examples']),
                inline=False
            )

        if 'related' in doc:
            embed.add_field(
                name="Related Commands",
                value=", ".join(f"`/{cmd}`" for cmd in doc['related']),
                inline=False
            )

        embed.set_footer(text="Use /help to see all commands")

        return embed
