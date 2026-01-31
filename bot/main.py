import asyncio
import re
import random
import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional, Dict
from collections import Counter
import pytz

# Initialize logging FIRST before any other imports
from logging_config import setup_logging, get_logger
setup_logging(
    log_level=os.getenv('LOG_LEVEL', 'INFO'),
    log_dir=os.getenv('LOG_DIR', '/app/logs')
)
logger = get_logger(__name__)

from database import Database
from llm import LLMClient
from local_llm import LocalLLMClient
from cost_tracker import CostTracker
from search import SearchEngine
from rag import RAGSystem
from redis_cache import get_cache
from wolfram import WolframAlpha
from weather import Weather
from features.claims import ClaimsTracker
from features.fact_check import FactChecker
from features.chat_stats import ChatStatistics
from features.hot_takes import HotTakesTracker
from features.reminders import ReminderSystem
from features.events import EventSystem
from features.yearly_wrapped import YearlyWrapped
from features.quote_of_the_day import QuoteOfTheDay
from features.debate_scorekeeper import DebateScorekeeper
from features.iracing import iRacingIntegration
from features.iracing_teams import iRacingTeamManager
from features.trivia import TriviaSystem
from credential_manager import CredentialManager
from iracing_graphics import iRacingGraphics
from self_knowledge import SelfKnowledge
from features.help_system import HelpSystem
from backup_manager import BackupManager

# Import registration functions
from tasks.background_jobs import register_tasks
from handlers.events import register_events
from handlers.conversations import handle_bot_mention
from commands.prefix_commands import register_prefix_commands
from commands.slash_commands import register_slash_commands

logger.info("=" * 60)
logger.info("WompBot Starting Up")
logger.info("=" * 60)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.message_content = True
intents.reactions = True  # Need for hot takes reaction tracking

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)  # Disable built-in help, use custom

# Initialize components
db = Database()
cache = get_cache()  # Redis cache for faster access to hot data
cost_tracker = None  # Will be initialized in on_ready when bot is available
llm = LLMClient(cost_tracker=None)  # Cost tracker will be set in on_ready
local_llm = LocalLLMClient()  # Local uncensored LLM (optional)
search = SearchEngine()

# Initialize Wolfram Alpha and Weather APIs (optional)
try:
    wolfram = WolframAlpha()
    logger.info("✓ Wolfram Alpha initialized")
except Exception as e:
    wolfram = None
    logger.warning(f"Wolfram Alpha not configured: {e}")

try:
    weather = Weather()
    logger.info("✓ Weather API initialized")
except Exception as e:
    weather = None
    logger.warning(f"Weather API not configured: {e}")
rag = RAGSystem(db, llm)  # RAG system for semantic search and intelligent context

# Setup feature modules
claims_tracker = ClaimsTracker(db, llm)
fact_checker = FactChecker(db, llm, search)
chat_stats = ChatStatistics(db)
hot_takes_tracker = HotTakesTracker(db, llm)
self_knowledge = SelfKnowledge()
help_system = HelpSystem()
reminder_system = ReminderSystem(db)
event_system = EventSystem(db)
yearly_wrapped = YearlyWrapped(db)
qotd = QuoteOfTheDay(db)
debate_scorekeeper = DebateScorekeeper(db, llm, search)
trivia = TriviaSystem(db, llm)
print("✅ Trivia system loaded")

# GDPR Privacy Compliance (mandatory per EU regulations)
from features.gdpr_privacy import GDPRPrivacyManager
privacy_manager = GDPRPrivacyManager(db)
print("✅ GDPR Privacy Manager loaded")

# iRacing integration (optional - only if encrypted credentials provided)
credential_manager = CredentialManager()
iracing = None
iracing_viz = None

try:
    from iracing_viz import iRacingVisualizer
    iracing_viz = iRacingVisualizer()
    print("✅ iRacing visualizer loaded")
except Exception as e:
    print(f"⚠️ Failed to load iRacing visualizer: {e}")

stats_viz = None

try:
    from stats_viz import StatsVisualizer
    stats_viz = StatsVisualizer()
    print("✅ Stats visualizer loaded")
except Exception as e:
    print(f"⚠️ Failed to load Stats visualizer: {e}")

iracing_credentials = credential_manager.get_iracing_credentials()
if iracing_credentials:
    iracing = iRacingIntegration(
        db,
        email=iracing_credentials['email'],
        password=iracing_credentials['password'],
        client_id=iracing_credentials.get('client_id'),
        client_secret=iracing_credentials.get('client_secret')
    )
    print("✅ iRacing integration enabled (using encrypted credentials)")
else:
    print("⚠️ iRacing integration disabled (no encrypted credentials found)")
    print("   Run 'python encrypt_credentials.py' to set up credentials")

# iRacing Team Management (always available, independent of iRacing API)
iracing_team_manager = iRacingTeamManager(db)
print("✅ iRacing Team Manager loaded")

WOMPIE_USERNAME = "wompie__"  # Discord username (lowercase)
# Get Wompie's Discord user ID from environment (permanent, can't be spoofed)
WOMPIE_USER_ID_VALUE = int(os.getenv('WOMPIE_USER_ID', '0')) if os.getenv('WOMPIE_USER_ID') else None
WOMPIE_USER_ID = [WOMPIE_USER_ID_VALUE]  # Mutable reference for event handlers

# iRacing series popularity cache
iracing_popularity_cache = {}  # {time_range: {'data': [(series, count), ...], 'timestamp': datetime}}

# iRacing series autocomplete cache (for slash commands) - mutable dict for event handler updates
series_autocomplete_cache = {'data': None, 'time': 0}

# =========================================================================
# Register all modules with the bot
# =========================================================================

# Register background tasks
print("\n🔧 Registering background tasks...")
tasks_dict = register_tasks(
    bot=bot,
    db=db,
    llm=llm,
    rag=rag,
    chat_stats=chat_stats,
    iracing=iracing,
    iracing_popularity_cache=iracing_popularity_cache,
    reminder_system=reminder_system,
    event_system=event_system,
    privacy_manager=privacy_manager,
    iracing_team_manager=iracing_team_manager
)

# Register event handlers
print("🔧 Registering event handlers...")
register_events(
    bot=bot,
    db=db,
    privacy_manager=privacy_manager,
    claims_tracker=claims_tracker,
    debate_scorekeeper=debate_scorekeeper,
    llm=llm,
    cost_tracker=cost_tracker,
    iracing=iracing,
    iracing_team_manager=iracing_team_manager,
    rag=rag,
    hot_takes_tracker=hot_takes_tracker,
    fact_checker=fact_checker,
    wompie_user_id=WOMPIE_USER_ID,
    wompie_username=WOMPIE_USERNAME,
    tasks_dict=tasks_dict,
    search=search,
    self_knowledge=self_knowledge,
    wolfram=wolfram,
    weather=weather,
    series_cache=series_autocomplete_cache,
    trivia=trivia,
    reminder_system=reminder_system
)

# Register prefix commands
print("🔧 Registering prefix commands...")
register_prefix_commands(
    bot=bot,
    db=db,
    llm=llm,
    search=search,
    help_system=help_system,
    tasks_dict=tasks_dict,
    weather=weather,
    wolfram=wolfram
)

# Register slash commands
print("🔧 Registering slash commands...")
register_slash_commands(
    bot=bot,
    db=db,
    llm=llm,
    claims_tracker=claims_tracker,
    chat_stats=chat_stats,
    stats_viz=stats_viz,
    hot_takes_tracker=hot_takes_tracker,
    reminder_system=reminder_system,
    event_system=event_system,
    debate_scorekeeper=debate_scorekeeper,
    yearly_wrapped=yearly_wrapped,
    qotd=qotd,
    iracing=iracing,
    iracing_viz=iracing_viz,
    iracing_team_manager=iracing_team_manager,
    help_system=help_system,
    wompie_user_id=WOMPIE_USER_ID,
    series_autocomplete_cache=series_autocomplete_cache,
    trivia=trivia
)

print("\n✅ All modules registered successfully!\n")

# =========================================================================
# Error handling
# =========================================================================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ User not found.")
    else:
        await ctx.send(f"❌ Error: {str(error)}")
        print(f"Command error: {error}")

# =========================================================================
# Run bot
# =========================================================================

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ DISCORD_TOKEN not found in environment variables!")
        exit(1)
    
    print("🚀 Starting WompBot...")
    bot.run(token)
