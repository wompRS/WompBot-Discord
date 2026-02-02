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
            },
            "personality": {
                "usage": "/personality <mode>",
                "description": "Change bot personality mode (Admin only)",
                "details": [
                    "Three personality modes available:",
                    "  • Default - Conversational and helpful with detailed responses",
                    "  • Concise - Brief, direct answers (1-2 sentences max)",
                    "  • Bogan - Full Australian slang mode for casual conversations",
                    "Setting is per-server and persists in the database",
                    "Only admin users can change personality modes"
                ],
                "examples": [
                    "/personality default - Set conversational mode",
                    "/personality concise - Set brief response mode",
                    "/personality bogan - Set Australian slang mode"
                ]
            },
            "whoami": {
                "usage": "/whoami",
                "description": "Show your Discord user information",
                "details": [
                    "Displays your Discord username, user ID, account creation date",
                    "Shows when you joined the current server",
                    "Useful for troubleshooting or checking your account info"
                ],
                "examples": [
                    "/whoami - Show your Discord information"
                ]
            },
            "wrapped": {
                "usage": "/wrapped [year] [user]",
                "description": "View your yearly activity summary (Spotify Wrapped for Discord)",
                "details": [
                    "Shows your Discord activity statistics for a specific year",
                    "Includes message counts, social network, claims, quotes",
                    "Personality insights based on your activity",
                    "Achievement badges: Night Owl, Early Bird, Debate Champion, Quote Machine",
                    "Zero LLM cost - pure database queries"
                ],
                "examples": [
                    "/wrapped - View your current year summary",
                    "/wrapped 2024 - View your 2024 summary",
                    "/wrapped 2024 @user - View another user's 2024 summary"
                ]
            },
            "qotd": {
                "usage": "/qotd [mode]",
                "description": "View featured quotes from different time periods",
                "details": [
                    "Modes: Daily, Weekly, Monthly, All-Time Greats, or Random",
                    "Smart selection based on reaction counts",
                    "Zero LLM cost - database queries only"
                ],
                "examples": [
                    "/qotd - View daily quote",
                    "/qotd weekly - View weekly quote",
                    "/qotd all-time - View all-time great quotes"
                ]
            },
            "remind": {
                "usage": "/remind <time> <message> [recurring]",
                "description": "Set a reminder with natural language time",
                "details": [
                    "Natural language parsing: 'in 5 minutes', 'tomorrow at 3pm', 'next Monday'",
                    "Context links jump back to the original message",
                    "Delivery options: DM or channel mention",
                    "Recurring support: daily, weekly, or custom intervals",
                    "Zero LLM cost - pure time parsing"
                ],
                "examples": [
                    "/remind in 30 minutes Check the oven",
                    "/remind tomorrow at 9am Team meeting",
                    "/remind friday at 5pm Weekly standup recurring:weekly"
                ]
            },
            "weather_set": {
                "usage": "/weather_set <location> [units]",
                "description": "Set your default weather location",
                "details": [
                    "Save your location for quick weather lookups",
                    "Units: metric (Celsius) or imperial (Fahrenheit)",
                    "After setting, just say 'wompbot weather' for updates"
                ],
                "examples": [
                    "/weather_set London",
                    "/weather_set New York imperial",
                    "/weather_set Tokyo metric"
                ]
            },
            "trivia_start": {
                "usage": "/trivia_start <topic> [difficulty] [questions] [time_per_question]",
                "description": "Start a multiplayer trivia session with LLM-generated questions",
                "details": [
                    "LLM generates fresh questions every time based on your topic",
                    "Multiplayer competitive - race to answer in the chat",
                    "Fuzzy matching accepts spelling variations and typos",
                    "Points based on speed, difficulty, and streak bonuses",
                    "Difficulty levels: Easy, Medium, Hard",
                    "Questions: 1-20 per session",
                    "Time: 10-60 seconds per question"
                ],
                "examples": [
                    "/trivia_start science - 10 medium science questions",
                    "/trivia_start gaming difficulty:easy questions:5 time_per_question:20",
                    "/trivia_start history difficulty:hard questions:15"
                ]
            },
            "trivia_stop": {
                "usage": "/trivia_stop",
                "description": "Stop the current trivia session and show final scores",
                "examples": [
                    "/trivia_stop - End the active trivia session"
                ]
            },
            "trivia_stats": {
                "usage": "/trivia_stats [@user]",
                "description": "View trivia statistics for yourself or another user",
                "details": [
                    "Shows total sessions, questions answered, and wins",
                    "Displays accuracy percentage and total points",
                    "Average time per question",
                    "Best streak and favorite topic"
                ],
                "examples": [
                    "/trivia_stats - View your stats",
                    "/trivia_stats @user - View another user's stats"
                ]
            },
            "trivia_leaderboard": {
                "usage": "/trivia_leaderboard [days]",
                "description": "View server trivia leaderboard",
                "details": [
                    "Shows top 10 players by total points",
                    "Filter by time period (default: 30 days)",
                    "Displays accuracy and total questions answered"
                ],
                "examples": [
                    "/trivia_leaderboard - Last 30 days",
                    "/trivia_leaderboard 7 - Last week",
                    "/trivia_leaderboard 365 - All time"
                ]
            },
            # Claims and Fact-Checking
            "verify_claim": {
                "usage": "/verify_claim <claim_id> <status> [notes]",
                "description": "Verify a tracked claim as true, false, or mixed",
                "details": [
                    "Status options: true, false, mixed, unverifiable",
                    "Add notes to explain your verification",
                    "Get claim IDs from /receipts command",
                    "Verified claims show status in receipts view"
                ],
                "examples": [
                    "/verify_claim 123 true - Mark claim as verified true",
                    "/verify_claim 456 false This was debunked",
                    "/verify_claim 789 mixed Partially accurate"
                ],
                "related": ["receipts", "quotes"]
            },
            # Chat Statistics
            "stats_server": {
                "usage": "/stats_server [days]",
                "description": "View server network graph and interaction statistics",
                "details": [
                    "Shows network visualization of who talks to whom",
                    "Displays interaction patterns between users",
                    "Filter by time period (default: 30 days)",
                    "Zero LLM cost - pure database queries"
                ],
                "examples": [
                    "/stats_server - Last 30 days",
                    "/stats_server 7 - Last week",
                    "/stats_server 90 - Last 3 months"
                ],
                "related": ["stats_topics", "stats_primetime", "stats_engagement"]
            },
            "stats_topics": {
                "usage": "/stats_topics [days]",
                "description": "View trending topics and keywords in the server",
                "details": [
                    "Uses TF-IDF analysis to find popular topics",
                    "Shows most discussed keywords",
                    "Filter by time period",
                    "Zero LLM cost - pure text analysis"
                ],
                "examples": [
                    "/stats_topics - Recent trending topics",
                    "/stats_topics 7 - This week's topics"
                ],
                "related": ["stats_server", "stats_engagement"]
            },
            "stats_primetime": {
                "usage": "/stats_primetime [@user] [days]",
                "description": "View activity heatmap showing when users are most active",
                "details": [
                    "Shows activity by hour and day of week",
                    "Optionally filter to a specific user",
                    "Helps identify when the server is busiest",
                    "Zero LLM cost"
                ],
                "examples": [
                    "/stats_primetime - Server activity heatmap",
                    "/stats_primetime @user - Specific user's activity",
                    "/stats_primetime @user 30 - Last 30 days"
                ],
                "related": ["stats_server", "stats_engagement"]
            },
            "stats_engagement": {
                "usage": "/stats_engagement [@user] [days]",
                "description": "View engagement metrics and response patterns",
                "details": [
                    "Shows response times and engagement rates",
                    "Conversation initiation vs. reply patterns",
                    "Zero LLM cost"
                ],
                "examples": [
                    "/stats_engagement - Server engagement metrics",
                    "/stats_engagement @user - User's engagement stats"
                ],
                "related": ["stats_server", "stats_primetime"]
            },
            # Hot Takes
            "hottakes": {
                "usage": "/hottakes [type] [days]",
                "description": "View hot takes leaderboard",
                "details": [
                    "Types: controversial, vindicated, worst, community, combined",
                    "Tracks bold predictions and controversial claims",
                    "Shows engagement and vindication status",
                    "Default: combined leaderboard"
                ],
                "examples": [
                    "/hottakes - Combined leaderboard",
                    "/hottakes vindicated - Claims that aged well",
                    "/hottakes worst 30 - Worst takes last 30 days"
                ],
                "related": ["mystats_hottakes", "vindicate"]
            },
            "mystats_hottakes": {
                "usage": "/mystats_hottakes",
                "description": "View your personal hot takes statistics",
                "details": [
                    "Shows your total hot takes count",
                    "Vindication rate and status breakdown",
                    "Your most controversial claims"
                ],
                "examples": [
                    "/mystats_hottakes - Your hot takes stats"
                ],
                "related": ["hottakes", "vindicate"]
            },
            "vindicate": {
                "usage": "/vindicate <hottake_id> <status> [notes]",
                "description": "Mark a hot take as vindicated or not (Admin only)",
                "details": [
                    "Status options: vindicated, wrong, pending",
                    "Used when a prediction comes true or fails",
                    "Get hot take IDs from /hottakes command"
                ],
                "examples": [
                    "/vindicate 123 vindicated Called it!",
                    "/vindicate 456 wrong Didn't age well"
                ],
                "related": ["hottakes", "mystats_hottakes"]
            },
            # Reminders
            "reminders": {
                "usage": "/reminders",
                "description": "View all your active reminders",
                "details": [
                    "Lists all pending reminders with their times",
                    "Shows reminder IDs for cancellation",
                    "Includes recurring reminder schedules"
                ],
                "examples": [
                    "/reminders - List all your reminders"
                ],
                "related": ["remind", "cancel_reminder"]
            },
            "cancel_reminder": {
                "usage": "/cancel_reminder <reminder_id>",
                "description": "Cancel an active reminder",
                "details": [
                    "Get reminder ID from /reminders command",
                    "Cancelled reminders are permanently deleted",
                    "Works for both one-time and recurring reminders"
                ],
                "examples": [
                    "/cancel_reminder 123 - Cancel reminder #123"
                ],
                "related": ["remind", "reminders"]
            },
            # Events
            "schedule_event": {
                "usage": "/schedule_event <name> <date> [description] [reminders]",
                "description": "Schedule an event with automatic reminders",
                "details": [
                    "Natural language date: 'Friday at 8pm', 'next Monday'",
                    "Default reminders: 1 week, 1 day, 1 hour before",
                    "Custom reminders: '1d,2h,30m' format",
                    "Events announced in the channel"
                ],
                "examples": [
                    "/schedule_event 'Movie Night' 'Friday 8pm'",
                    "/schedule_event 'Game Day' 'next Saturday 3pm' 'Bring snacks!'",
                    "/schedule_event 'Meeting' 'tomorrow 10am' '' '1d,1h'"
                ],
                "related": ["events", "cancel_event"]
            },
            "events": {
                "usage": "/events [limit]",
                "description": "View upcoming scheduled events",
                "details": [
                    "Shows event name, time, and description",
                    "Displays event IDs for cancellation",
                    "Default shows next 10 events"
                ],
                "examples": [
                    "/events - Show upcoming events",
                    "/events 5 - Show next 5 events"
                ],
                "related": ["schedule_event", "cancel_event"]
            },
            "cancel_event": {
                "usage": "/cancel_event <event_id>",
                "description": "Cancel a scheduled event",
                "details": [
                    "Get event ID from /events command",
                    "Cancels all associated reminders",
                    "Announces cancellation in the channel"
                ],
                "examples": [
                    "/cancel_event 123 - Cancel event #123"
                ],
                "related": ["events", "schedule_event"]
            },
            # Debates
            "debate_start": {
                "usage": "/debate_start <topic>",
                "description": "Start tracking a debate on a topic",
                "details": [
                    "Automatically tracks arguments from participants",
                    "Records key points and counterpoints",
                    "Use /debate_end to conclude and get analysis"
                ],
                "examples": [
                    "/debate_start 'Is pineapple on pizza acceptable?'",
                    "/debate_start 'Best programming language'"
                ],
                "related": ["debate_end", "debate_stats"]
            },
            "debate_end": {
                "usage": "/debate_end",
                "description": "End the active debate and show analysis",
                "details": [
                    "LLM analyzes all arguments made",
                    "Scores arguments on 0-10 scale",
                    "Detects logical fallacies",
                    "Determines winner with explanation",
                    "Cost: $0.01-0.05 per debate"
                ],
                "examples": [
                    "/debate_end - Conclude and analyze debate"
                ],
                "related": ["debate_start", "debate_stats"]
            },
            "debate_stats": {
                "usage": "/debate_stats [@user]",
                "description": "View debate statistics",
                "details": [
                    "Shows wins, losses, and average scores",
                    "Displays debate history",
                    "View your own or another user's stats"
                ],
                "examples": [
                    "/debate_stats - Your debate stats",
                    "/debate_stats @user - Someone else's stats"
                ],
                "related": ["debate_leaderboard", "debate_start"]
            },
            "debate_leaderboard": {
                "usage": "/debate_leaderboard",
                "description": "View the server's top debaters",
                "details": [
                    "Ranked by win rate and average score",
                    "Shows total debates participated in",
                    "Highlights best arguments"
                ],
                "examples": [
                    "/debate_leaderboard - Show top debaters"
                ],
                "related": ["debate_stats", "debate_start"]
            },
            "debate_review": {
                "usage": "/debate_review <file>",
                "description": "Analyze an uploaded debate transcript",
                "details": [
                    "Upload a text file with debate transcript",
                    "LLM analyzes arguments from both sides",
                    "Provides scoring and winner determination"
                ],
                "examples": [
                    "/debate_review [attach file]"
                ],
                "related": ["debate_start", "debate_stats"]
            },
            # Weather
            "weather_clear": {
                "usage": "/weather_clear",
                "description": "Clear your saved weather location",
                "details": [
                    "Removes your default weather preference",
                    "You'll need to specify location for weather lookups"
                ],
                "examples": [
                    "/weather_clear - Remove saved location"
                ],
                "related": ["weather_set", "weather_info"]
            },
            "weather_info": {
                "usage": "/weather_info",
                "description": "View your saved weather preferences",
                "details": [
                    "Shows your default location and units",
                    "Confirms your weather settings"
                ],
                "examples": [
                    "/weather_info - View saved preferences"
                ],
                "related": ["weather_set", "weather_clear"]
            },
            # Privacy Commands
            "cancel_deletion": {
                "usage": "/cancel_deletion",
                "description": "Cancel a scheduled data deletion request",
                "details": [
                    "Stops the 30-day deletion countdown",
                    "Your data will be retained",
                    "You remain opted out unless you opt back in"
                ],
                "examples": [
                    "/cancel_deletion - Cancel deletion request"
                ],
                "related": ["delete_my_data", "my_privacy_status"]
            },
            "privacy_policy": {
                "usage": "/privacy_policy",
                "description": "View WompBot's complete privacy policy",
                "details": [
                    "Explains what data is collected",
                    "Describes how data is used",
                    "Outlines your rights under GDPR"
                ],
                "examples": [
                    "/privacy_policy - View privacy policy"
                ],
                "related": ["my_privacy_status", "wompbot_optout"]
            },
            "privacy_support": {
                "usage": "/privacy_support",
                "description": "Get help with privacy-related concerns",
                "details": [
                    "Contact information for privacy questions",
                    "Links to relevant documentation",
                    "GDPR request assistance"
                ],
                "examples": [
                    "/privacy_support - Get privacy help"
                ],
                "related": ["privacy_policy", "my_privacy_status"]
            },
            "tos": {
                "usage": "/tos",
                "description": "View Terms of Service",
                "details": [
                    "Legal terms for using WompBot",
                    "Acceptable use guidelines",
                    "Liability and warranty information"
                ],
                "examples": [
                    "/tos - View Terms of Service"
                ],
                "related": ["privacy_policy"]
            },
            "privacy_settings": {
                "usage": "/privacy_settings",
                "description": "View server privacy overview (Admin only)",
                "details": [
                    "Shows consent statistics for the server",
                    "Displays opt-out counts",
                    "Overview of data collection status"
                ],
                "examples": [
                    "/privacy_settings - Server privacy overview"
                ],
                "related": ["privacy_audit", "privacy_policy"]
            },
            "privacy_audit": {
                "usage": "/privacy_audit",
                "description": "Download privacy audit report (Admin only)",
                "details": [
                    "JSON report of privacy posture",
                    "Lists all data categories stored",
                    "Compliance status summary"
                ],
                "examples": [
                    "/privacy_audit - Download audit report"
                ],
                "related": ["privacy_settings", "privacy_policy"]
            },
            # iRacing Commands
            "iracing_link": {
                "usage": "/iracing_link <driver_name>",
                "description": "Link your Discord account to your iRacing profile",
                "details": [
                    "Search by driver name (first and last)",
                    "Links your Discord ID to iRacing customer ID",
                    "Required for personalized iRacing commands"
                ],
                "examples": [
                    "/iracing_link Max Verstappen",
                    "/iracing_link 'John Smith'"
                ],
                "related": ["iracing_profile", "iracing_results"]
            },
            "iracing_profile": {
                "usage": "/iracing_profile [driver_name]",
                "description": "View an iRacing driver's profile",
                "details": [
                    "Shows iRating, Safety Rating, license class",
                    "Displays career stats across categories",
                    "Leave blank to view your own profile"
                ],
                "examples": [
                    "/iracing_profile - Your profile",
                    "/iracing_profile Max Verstappen"
                ],
                "related": ["iracing_link", "iracing_results", "iracing_history"]
            },
            "iracing_schedule": {
                "usage": "/iracing_schedule [series] [category] [week]",
                "description": "View iRacing race schedules",
                "details": [
                    "Shows track rotation for series",
                    "Highlights current week",
                    "Filter by category: road, oval, dirt_road, dirt_oval"
                ],
                "examples": [
                    "/iracing_schedule - All schedules",
                    "/iracing_schedule 'GT3' road",
                    "/iracing_schedule 'IMSA' road 3"
                ],
                "related": ["iracing_season_schedule", "iracing_timeslots"]
            },
            "iracing_meta": {
                "usage": "/iracing_meta <series> [season] [week] [track]",
                "description": "View meta analysis - best cars for a series",
                "details": [
                    "Shows win rates and usage statistics per car",
                    "Helps choose competitive setups",
                    "Filter by specific week or track"
                ],
                "examples": [
                    "/iracing_meta 'GT3 Sprint'",
                    "/iracing_meta 'IMSA' 2024S1 5"
                ],
                "related": ["iracing_win_rate", "iracing_schedule"]
            },
            "iracing_results": {
                "usage": "/iracing_results [driver_name]",
                "description": "View recent race results",
                "details": [
                    "Shows last 10 race results",
                    "Includes position, iRating change, incidents",
                    "Leave blank for your own results"
                ],
                "examples": [
                    "/iracing_results - Your recent races",
                    "/iracing_results 'Max Verstappen'"
                ],
                "related": ["iracing_profile", "iracing_history"]
            },
            "iracing_season_schedule": {
                "usage": "/iracing_season_schedule <series> [season]",
                "description": "View full season track rotation",
                "details": [
                    "Shows all 12 weeks of the season",
                    "Highlights current week",
                    "Includes track configurations"
                ],
                "examples": [
                    "/iracing_season_schedule 'GT3 Sprint'",
                    "/iracing_season_schedule 'IMSA' 2024S2"
                ],
                "related": ["iracing_schedule", "iracing_timeslots"]
            },
            "iracing_server_leaderboard": {
                "usage": "/iracing_server_leaderboard [category]",
                "description": "View server iRacing leaderboard",
                "details": [
                    "Ranks linked Discord members by iRating",
                    "Categories: road, oval, dirt_road, dirt_oval",
                    "Shows license class and safety rating"
                ],
                "examples": [
                    "/iracing_server_leaderboard - Road leaderboard",
                    "/iracing_server_leaderboard oval"
                ],
                "related": ["iracing_link", "iracing_profile"]
            },
            "iracing_history": {
                "usage": "/iracing_history [driver_name] [category] [days]",
                "description": "View iRating progression over time",
                "details": [
                    "Shows rating history chart",
                    "Track improvement or decline",
                    "Filter by time period"
                ],
                "examples": [
                    "/iracing_history - Your road history",
                    "/iracing_history 'Max Verstappen' oval 90"
                ],
                "related": ["iracing_profile", "iracing_results"]
            },
            "iracing_win_rate": {
                "usage": "/iracing_win_rate <series> [season]",
                "description": "View car win rates for a series",
                "details": [
                    "Shows percentage of wins per car",
                    "Helps identify meta cars",
                    "Based on official race data"
                ],
                "examples": [
                    "/iracing_win_rate 'GT3 Sprint'",
                    "/iracing_win_rate 'IMSA' 2024S1"
                ],
                "related": ["iracing_meta", "iracing_schedule"]
            },
            "iracing_compare_drivers": {
                "usage": "/iracing_compare_drivers <driver1> <driver2> [category]",
                "description": "Compare two iRacing drivers side-by-side",
                "details": [
                    "Shows iRating, SR, wins, podiums",
                    "Visual comparison chart",
                    "Compare across any category"
                ],
                "examples": [
                    "/iracing_compare_drivers 'John Smith' 'Jane Doe'",
                    "/iracing_compare_drivers 'Max V' 'Lewis H' road"
                ],
                "related": ["iracing_profile", "iracing_history"]
            },
            "iracing_series_popularity": {
                "usage": "/iracing_series_popularity [time_range]",
                "description": "View most popular iRacing series",
                "details": [
                    "Shows participation numbers",
                    "Time ranges: season, year, all-time",
                    "Helps find active series"
                ],
                "examples": [
                    "/iracing_series_popularity - Current season",
                    "/iracing_series_popularity year"
                ],
                "related": ["iracing_schedule", "iracing_timeslots"]
            },
            "iracing_timeslots": {
                "usage": "/iracing_timeslots <series> [week]",
                "description": "View race session times for a series",
                "details": [
                    "Shows when races start",
                    "Converts to your timezone",
                    "Helps plan race sessions"
                ],
                "examples": [
                    "/iracing_timeslots 'GT3 Sprint'",
                    "/iracing_timeslots 'IMSA' 5"
                ],
                "related": ["iracing_schedule", "iracing_upcoming_races"]
            },
            "iracing_upcoming_races": {
                "usage": "/iracing_upcoming_races [hours] [category]",
                "description": "View races starting soon",
                "details": [
                    "Shows official races starting within timeframe",
                    "Default: next 3 hours",
                    "Filter by category"
                ],
                "examples": [
                    "/iracing_upcoming_races - Next 3 hours",
                    "/iracing_upcoming_races 6 road"
                ],
                "related": ["iracing_timeslots", "iracing_schedule"]
            },
            # iRacing Team Commands
            "iracing_team_create": {
                "usage": "/iracing_team_create <name> <tag> [description]",
                "description": "Create a new racing team",
                "details": [
                    "You become the team manager",
                    "Tag is a short identifier (e.g., 'WRC')",
                    "Invite members with /iracing_team_invite"
                ],
                "examples": [
                    "/iracing_team_create 'Womp Racing' 'WRC'",
                    "/iracing_team_create 'Fast Bois' 'FB' 'Endurance racing team'"
                ],
                "related": ["iracing_team_invite", "iracing_team_info"]
            },
            "iracing_team_invite": {
                "usage": "/iracing_team_invite <team_name> <@member> [role]",
                "description": "Invite a member to your team",
                "details": [
                    "Roles: driver, crew_chief, spotter, manager",
                    "Invitee receives DM with accept/decline buttons",
                    "Only managers can invite"
                ],
                "examples": [
                    "/iracing_team_invite 'Womp Racing' @user driver",
                    "/iracing_team_invite 'Womp Racing' @user spotter"
                ],
                "related": ["iracing_team_create", "iracing_team_info"]
            },
            "iracing_team_leave": {
                "usage": "/iracing_team_leave <team_name>",
                "description": "Leave a racing team",
                "details": [
                    "Removes you from the team roster",
                    "Managers cannot leave unless transferring ownership"
                ],
                "examples": [
                    "/iracing_team_leave 'Womp Racing'"
                ],
                "related": ["iracing_team_info", "iracing_my_teams"]
            },
            "iracing_team_info": {
                "usage": "/iracing_team_info <team_name>",
                "description": "View team details and roster",
                "details": [
                    "Shows team description and tag",
                    "Lists all members with roles",
                    "Shows upcoming team events"
                ],
                "examples": [
                    "/iracing_team_info 'Womp Racing'"
                ],
                "related": ["iracing_team_list", "iracing_my_teams"]
            },
            "iracing_team_list": {
                "usage": "/iracing_team_list",
                "description": "List all teams on this server",
                "details": [
                    "Shows all registered teams",
                    "Displays member counts",
                    "Links to team info"
                ],
                "examples": [
                    "/iracing_team_list - Show all teams"
                ],
                "related": ["iracing_team_info", "iracing_team_create"]
            },
            "iracing_my_teams": {
                "usage": "/iracing_my_teams",
                "description": "View teams you're a member of",
                "details": [
                    "Lists all your team memberships",
                    "Shows your role in each team",
                    "Quick access to team events"
                ],
                "examples": [
                    "/iracing_my_teams - Your team memberships"
                ],
                "related": ["iracing_team_info", "iracing_team_leave"]
            },
            # iRacing Team Events
            "iracing_event_create": {
                "usage": "/iracing_event_create <team_name> <event_name> <type> <time> [series] [track]",
                "description": "Schedule a team event",
                "details": [
                    "Types: practice, qualifying, race, endurance",
                    "Natural language time: 'Saturday 8pm', 'tomorrow 3pm'",
                    "Notifies all team members",
                    "Only managers can schedule"
                ],
                "examples": [
                    "/iracing_event_create 'Womp Racing' 'Practice' practice 'Friday 8pm'",
                    "/iracing_event_create 'Womp Racing' '24h Le Mans' endurance 'June 15 2pm' 'IMSA' 'Le Mans'"
                ],
                "related": ["iracing_team_events", "iracing_event_roster"]
            },
            "iracing_team_events": {
                "usage": "/iracing_team_events <team_name>",
                "description": "View upcoming team events",
                "details": [
                    "Shows scheduled practices, races, etc.",
                    "Displays event times and details",
                    "Shows participation status"
                ],
                "examples": [
                    "/iracing_team_events 'Womp Racing'"
                ],
                "related": ["iracing_event_create", "iracing_event_availability"]
            },
            "iracing_event_availability": {
                "usage": "/iracing_event_availability <event_id> <status> [notes]",
                "description": "Set your availability for a team event",
                "details": [
                    "Status: available, unavailable, maybe",
                    "Add notes to explain availability",
                    "Helps team managers plan"
                ],
                "examples": [
                    "/iracing_event_availability 123 available",
                    "/iracing_event_availability 123 maybe 'Might be late'"
                ],
                "related": ["iracing_team_events", "iracing_event_roster"]
            },
            "iracing_event_roster": {
                "usage": "/iracing_event_roster <event_id>",
                "description": "View who's signed up for an event",
                "details": [
                    "Shows availability status for all members",
                    "Displays confirmed, available, maybe, unavailable",
                    "Helps plan driver lineups"
                ],
                "examples": [
                    "/iracing_event_roster 123"
                ],
                "related": ["iracing_team_events", "iracing_event_availability"]
            }
        }

    def get_general_help(self) -> discord.Embed:
        """Generate general help embed with all commands"""
        embed = discord.Embed(
            title="WompBot Commands",
            description="**62+ slash commands** and **18 AI tools** organized by category\n\nChat: @WompBot, 'wompbot', or '!wb' • Powered by DeepSeek\nSupports images, GIFs, YouTube videos, and video attachments\nUse `/help <command>` for details",
            color=discord.Color.purple()
        )

        embed.add_field(
            name="General and Utility",
            value=(
                "`/help` - Show commands or get help\n"
                "`/whoami` - Show your Discord info\n"
                "`/personality` - Change bot personality mode (Admin only)\n"
                "Three modes: Default (conversational), Concise (brief), Bogan (Aussie slang)"
            ),
            inline=False
        )

        embed.add_field(
            name="Conversational AI Tools (18 tools)",
            value=(
                "WompBot can use tools automatically when you ask questions:\n"
                "**Weather:** `get_weather`, `get_weather_forecast`\n"
                "**Search:** `web_search`, `wikipedia`, `define_word`, `url_preview`\n"
                "**Utility:** `currency_convert`, `get_time`, `translate`, `random_choice`\n"
                "**Media:** `youtube_search`, `movie_info`, `stock_price`\n"
                "**Charts:** `create_bar_chart`, `create_line_chart`, `create_pie_chart`\n"
                "Just ask naturally - e.g., 'convert 100 USD to EUR' or 'weather in Tokyo'"
            ),
            inline=False
        )

        embed.add_field(
            name="Media Analysis",
            value=(
                "Share images, GIFs, or videos with WompBot to analyze them:\n"
                "**Images:** Describe content, read text, identify memes\n"
                "**GIFs:** Extracts 6 frames to describe the animation\n"
                "**YouTube:** Fetches transcript instantly (no download needed)\n"
                "**Videos:** Transcribes audio using Whisper AI\n"
                "Just attach media and ask 'what's this?' or 'what's happening?'"
            ),
            inline=False
        )

        embed.add_field(
            name="Claims and Quotes",
            value=(
                "`/receipts` - View tracked claims\n"
                "`/quotes` - View saved quotes\n"
                "`/verify_claim` - Verify a claim\n"
                "React with cloud emoji to save quote, warning emoji to fact-check"
            ),
            inline=False
        )

        embed.add_field(
            name="Chat Statistics",
            value=(
                "`/stats_server` - Network graph and server stats\n"
                "`/stats_topics` - Trending keywords\n"
                "`/stats_primetime` - Activity heatmap\n"
                "`/stats_engagement` - Engagement metrics"
            ),
            inline=False
        )

        embed.add_field(
            name="Hot Takes",
            value=(
                "`/hottakes` - Hot takes leaderboard\n"
                "`/mystats_hottakes` - Your hot takes stats\n"
                "`/vindicate` - Mark hot take vindicated (Admin)"
            ),
            inline=False
        )

        embed.add_field(
            name="Reminders and Events",
            value=(
                "`/remind` - Set reminder\n"
                "`/reminders` - View your reminders\n"
                "`/cancel_reminder` - Cancel reminder\n"
                "`/schedule_event` - Schedule event\n"
                "`/events` - View upcoming events\n"
                "`/cancel_event` - Cancel event"
            ),
            inline=False
        )

        embed.add_field(
            name="Wrapped and Quote of the Day",
            value=(
                "`/wrapped` - Your yearly summary\n"
                "`/qotd` - Quote of the day"
            ),
            inline=False
        )

        embed.add_field(
            name="Debates",
            value=(
                "`/debate_start` - Start tracking debate\n"
                "`/debate_end` - End and analyze debate\n"
                "`/debate_stats` - Your debate stats\n"
                "`/debate_leaderboard` - Top debaters\n"
                "`/debate_review` - Analyze debate file"
            ),
            inline=False
        )

        embed.add_field(
            name="Trivia (4 commands)",
            value=(
                "`/trivia_start` - Start multiplayer trivia session\n"
                "`/trivia_stop` - Stop active trivia session\n"
                "`/trivia_stats` - View your trivia statistics\n"
                "`/trivia_leaderboard` - Server trivia rankings\n"
                "LLM-generated questions • Fuzzy answer matching • Speed & streak bonuses"
            ),
            inline=False
        )

        embed.add_field(
            name="iRacing (13 commands)",
            value=(
                "`/iracing_link` - Link account\n"
                "`/iracing_profile` - Driver profile\n"
                "`/iracing_schedule` - Race schedules\n"
                "`/iracing_meta` - Series meta analysis\n"
                "`/iracing_results` - Recent results\n"
                "`/iracing_season_schedule` - Full season\n"
                "`/iracing_server_leaderboard` - Server rankings\n"
                "`/iracing_history` - Rating trends\n"
                "`/iracing_win_rate` - Car win rates\n"
                "`/iracing_compare_drivers` - Compare drivers\n"
                "`/iracing_series_popularity` - Popular series\n"
                "`/iracing_timeslots` - Race times\n"
                "`/iracing_upcoming_races` - Upcoming official races"
            ),
            inline=False
        )

        embed.add_field(
            name="Weather",
            value=(
                "Say: 'wompbot weather' or 'wompbot forecast'\n"
                "`/weather_set` - Set default location\n"
                "`/weather_clear` - Clear saved location\n"
                "`/weather_info` - View saved location"
            ),
            inline=False
        )

        embed.add_field(
            name="iRacing Teams (6 commands)",
            value=(
                "`/iracing_team_create` - Create team\n"
                "`/iracing_team_invite` - Invite member\n"
                "`/iracing_team_leave` - Leave team\n"
                "`/iracing_team_info` - Team details\n"
                "`/iracing_team_list` - All teams\n"
                "`/iracing_my_teams` - Your teams"
            ),
            inline=False
        )

        embed.add_field(
            name="iRacing Team Events (4 commands)",
            value=(
                "`/iracing_event_create` - Create team event\n"
                "`/iracing_team_events` - View team events\n"
                "`/iracing_event_availability` - Set availability\n"
                "`/iracing_event_roster` - View event roster"
            ),
            inline=False
        )

        embed.add_field(
            name="Privacy and GDPR (10 commands)",
            value=(
                "`/wompbot_optout` - Opt out of data collection\n"
                "`/download_my_data` - Export data\n"
                "`/delete_my_data` - Delete data\n"
                "`/cancel_deletion` - Cancel deletion\n"
                "`/my_privacy_status` - Check status\n"
                "`/privacy_policy` - View policy\n"
                "`/privacy_support` - Get help\n"
                "`/tos` - Terms of Service\n"
                "`/privacy_settings` - Server privacy (Admin)\n"
                "`/privacy_audit` - Audit report (Admin)"
            ),
            inline=False
        )

        embed.add_field(
            name="Prefix Commands - Utility",
            value=(
                "`!ping` - Check latency\n"
                "`!help` - Show help\n"
                "`!stats` - User stats\n"
                "`!search` - Web search\n"
                "`!analyze` - Behavior analysis (Admin)\n"
                "`!refreshstats` - Refresh cache (Admin)"
            ),
            inline=False
        )

        embed.add_field(
            name="Prefix Commands - Tools",
            value=(
                "`!convert 100 USD EUR` - Currency conversion\n"
                "`!define word` - Dictionary definition\n"
                "`!weather London` - Current weather\n"
                "`!time Tokyo` - Time in timezone\n"
                "`!roll d20` - Roll dice / `!roll coin` - Flip coin\n"
                "`!movie Inception` - Movie/TV info\n"
                "`!stock AAPL` or `Microsoft` - Stock/crypto\n"
                "`!translate es Hello` - Translate text"
            ),
            inline=False
        )

        embed.set_footer(text="Use /help <command> for detailed help • By using WompBot, you accept /tos")

        return embed

    def get_command_help(self, command: str) -> Optional[discord.Embed]:
        """Generate detailed help for a specific command"""
        command = command.lower().strip().lstrip('/')

        # SECURITY: Sanitize command to prevent path traversal attacks
        # Only allow alphanumeric characters, underscores, and hyphens
        import re
        if not re.match(r'^[a-z0-9_-]+$', command):
            return None  # Invalid command name, reject silently

        # Additional safety: use basename and verify no path separators
        command = os.path.basename(command)
        if '..' in command or '/' in command or '\\' in command:
            return None

        # Try to load from file first
        doc_file = os.path.join(self.docs_path, f"{command}.md")

        # SECURITY: Verify the resolved path is within docs_path
        real_doc_file = os.path.realpath(doc_file)
        real_docs_path = os.path.realpath(self.docs_path)
        if not real_doc_file.startswith(real_docs_path):
            return None  # Path traversal attempt detected

        if os.path.exists(doc_file):
            try:
                with open(doc_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Parse markdown and create embed
                    # For now, just show the raw content
                    embed = discord.Embed(
                        title=f"Command: /{command}",
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
            title=f"Command: {doc['usage']}",
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
