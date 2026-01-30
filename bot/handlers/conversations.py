"""
Conversation handlers for WompBot Discord bot.

This module contains conversation-related functions including bot mention handling
and leaderboard generation.
"""

import os
import re
import random
import asyncio
import discord
from datetime import datetime, timezone

# Tool system imports
from viz_tools import GeneralVisualizer
from llm_tools import VISUALIZATION_TOOLS, ALL_TOOLS, DataRetriever
from tool_executor import ToolExecutor

# Rotating search status messages
SEARCH_STATUS_MESSAGES = [
    "🔍 Need to fact-check this real quick...",
    "🔍 Let me verify that with a quick search...",
    "🔍 Pulling up recent information...",
    "🔍 Checking the latest info...",
    "🔍 Looking up current data...",
    "🔍 Searching for up-to-date details...",
    "🔍 Grabbing fresh info from the web...",
    "🔍 Let me look into that...",
]

# Rotating thinking/processing messages (when not searching)
THINKING_STATUS_MESSAGES = [
    "🤔 Thinking...",
    "💭 Let me think about that...",
    "⏳ One moment...",
    "🧠 Processing...",
    "💬 Working on it...",
    "✨ Give me a sec...",
]


# Rate limiting state for mention handling
MENTION_RATE_STATE = {}
USER_CONCURRENT_REQUESTS = {}
_LAST_CLEANUP_TIME = 0

# Locks for thread-safe access to rate limiting state
_RATE_STATE_LOCK = asyncio.Lock()
_CONCURRENT_REQUESTS_LOCK = asyncio.Lock()

async def cleanup_stale_rate_state():
    """Remove stale entries from rate limiting dictionaries to prevent memory leak"""
    global _LAST_CLEANUP_TIME
    now_ts = datetime.now(timezone.utc).timestamp()

    # Only run cleanup every 5 minutes
    if now_ts - _LAST_CLEANUP_TIME < 300:
        return

    _LAST_CLEANUP_TIME = now_ts
    stale_window = 3600  # Remove entries older than 1 hour

    # Cleanup MENTION_RATE_STATE with lock
    async with _RATE_STATE_LOCK:
        stale_users = [
            uid for uid, bucket in MENTION_RATE_STATE.items()
            if now_ts - bucket["window_start"] > stale_window
        ]
        for uid in stale_users:
            del MENTION_RATE_STATE[uid]

    if stale_users:
        print(f"🧹 Cleaned up {len(stale_users)} stale rate limit entries")

# Initialize visualization tools (module-level, reused across calls)
_visualizer = None
_tool_executor = None

def get_visualizer():
    """Get or create visualizer instance"""
    global _visualizer
    if _visualizer is None:
        _visualizer = GeneralVisualizer()
    return _visualizer

def get_tool_executor(db, wolfram=None, weather=None, search=None):
    """Get or create tool executor instance"""
    global _tool_executor
    if _tool_executor is None:
        visualizer = get_visualizer()
        data_retriever = DataRetriever(db)
        _tool_executor = ToolExecutor(db, visualizer, data_retriever, wolfram, weather, search)
    return _tool_executor


def clean_discord_mentions(content, message):
    """Convert Discord mentions from <@USER_ID> format to @username format"""
    # Find all user mentions in format <@USER_ID> or <@!USER_ID>
    mention_pattern = r'<@!?(\d+)>'

    def replace_mention(match):
        user_id = int(match.group(1))
        # Try to find the user in the message's guild
        if message.guild:
            member = message.guild.get_member(user_id)
            if member:
                return f"@{member.name}"
        # Fallback to just @USER_ID if we can't find the member
        return f"@user_{user_id}"

    return re.sub(mention_pattern, replace_mention, content)


def restore_discord_mentions(content, message):
    """Convert @username mentions back to Discord <@USER_ID> format"""
    if not message.guild:
        return content

    # Find all @username patterns (but not @everyone or @here)
    mention_pattern = r'@([a-zA-Z0-9_\.]{2,32})(?!\w)'

    def replace_mention(match):
        username = match.group(1).lower()

        # Skip special mentions
        if username in ['everyone', 'here']:
            return match.group(0)

        # Try to find member by name (case-insensitive)
        for member in message.guild.members:
            if member.name.lower() == username or member.display_name.lower() == username:
                return f"<@{member.id}>"

        # If not found, return original text
        return match.group(0)

    return re.sub(mention_pattern, replace_mention, content)


async def generate_leaderboard_response(channel, stat_type, days, db, llm):
    """Generate and send leaderboard embed"""
    try:
        embed = discord.Embed(
            title=f"📊 Top Users by {stat_type.title()}",
            description=f"Last {days} days",
            color=discord.Color.gold()
        )

        if stat_type == 'messages':
            results = db.get_message_stats(days=days, limit=10)

            if not results:
                await channel.send("No data available for this period.")
                return

            leaderboard_text = ""
            for i, user in enumerate(results, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                leaderboard_text += f"{medal} **{user['username']}**: {user['message_count']} messages "
                leaderboard_text += f"({user['active_days']} active days)\n"

            embed.add_field(name="Most Active Users", value=leaderboard_text, inline=False)

        elif stat_type == 'questions':
            # Send thinking message
            thinking_msg = await channel.send("🤔 Analyzing messages to detect questions...")

            # Get all messages for the period
            messages = db.get_question_stats(days=days)

            if not messages:
                await thinking_msg.edit(content="No messages available for this period.")
                return

            # Classify questions using LLM
            results = llm.classify_questions(messages)

            if not results:
                await thinking_msg.edit(content="Error analyzing questions.")
                return

            # Sort by question count
            sorted_results = sorted(results.values(), key=lambda x: x['question_count'], reverse=True)[:10]

            leaderboard_text = ""
            for i, user in enumerate(sorted_results, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                percentage = user['question_percentage']
                leaderboard_text += f"{medal} **{user['username']}**: {user['question_count']} questions "
                leaderboard_text += f"({percentage:.1f}% of {user['total_messages']} messages)\n"

            embed.add_field(name="Most Inquisitive Users", value=leaderboard_text, inline=False)
            await thinking_msg.delete()

        elif stat_type == 'profanity':
            results = db.get_profanity_stats(days=days, limit=10)

            if not results:
                await channel.send("No profanity analysis available yet. An admin needs to run `/analyze` first.")
                return

            leaderboard_text = ""
            for i, user in enumerate(results, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                score = user['profanity_score']
                leaderboard_text += f"{medal} **{user['username']}**: {score}/10\n"

            embed.add_field(name="Saltiest Users", value=leaderboard_text, inline=False)
            embed.set_footer(text="Based on most recent behavior analysis")

        await channel.send(embed=embed)

    except Exception as e:
        await channel.send(f"Error generating stats: {str(e)}")
        print(f"Leaderboard generation error: {e}")


async def handle_bot_mention(message, opted_out, bot, db, llm, cost_tracker, search=None,
                             self_knowledge=None, rag=None, wolfram=None, weather=None):
    """Handle when bot is mentioned/tagged"""
    # Track placeholder message for cleanup on error
    placeholder_msg = None
    try:
        # Periodic cleanup of stale rate limiting state
        await cleanup_stale_rate_state()

        # Check if user is admin (bypass all rate limits)
        # Admin IDs from env (comma-separated) or legacy username check
        admin_ids_str = os.getenv('BOT_ADMIN_IDS', '')
        admin_ids = set(int(x.strip()) for x in admin_ids_str.split(',') if x.strip().isdigit())
        admin_username = os.getenv('BOT_ADMIN_USERNAME', '').lower()
        is_admin = message.author.id in admin_ids or (admin_username and str(message.author).lower() == admin_username)

        # Check if this is a text mention ("wompbot") vs @mention only
        # Cost logging will only appear for text mentions to reduce log noise
        message_lower = message.content.lower()
        is_text_mention = 'wompbot' in message_lower or 'womp bot' in message_lower or message_lower.startswith('!wb')

        # Remove bot mention and "wompbot" from message
        content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        content = content.replace(f'<@!{bot.user.id}>', '').strip()  # Also handle nickname mentions
        content = content.replace('wompbot', '').replace('womp bot', '').strip()
        content = content.replace('WompBot', '').replace('Wompbot', '').strip()

        # Remove !wb shorthand from the beginning (case insensitive)
        if content.lower().startswith('!wb'):
            content = content[3:].strip()  # Remove first 3 characters (!wb) and strip whitespace

        # Convert Discord mentions to readable usernames
        content = clean_discord_mentions(content, message)

        if not content or len(content) < 2:
            await message.channel.send("Yeah? What's up?")
            return

        # Input sanitization - enforce max length
        max_input_length = int(os.getenv('MAX_INPUT_LENGTH', '2000'))
        if len(content) > max_input_length:
            content = content[:max_input_length]
            await message.channel.send(
                f"⚠️ Message truncated to {max_input_length} characters for processing."
            )

        # Message frequency rate limiting (skip for admin)
        if not is_admin:
            message_cooldown = int(os.getenv('MESSAGE_COOLDOWN', '3'))  # 3 seconds default
            max_messages_per_minute = int(os.getenv('MAX_MESSAGES_PER_MINUTE', '10'))  # 10/min default

            freq_check = db.check_feature_rate_limit(
                message.author.id,
                'bot_message',
                cooldown_seconds=message_cooldown,
                hourly_limit=max_messages_per_minute * 6  # Convert per-minute to per-hour approximation
            )

            if not freq_check['allowed']:
                if freq_check['reason'] == 'cooldown':
                    # Silent cooldown - just ignore to prevent spam
                    return
                elif freq_check['reason'] == 'hourly_limit':
                    await message.channel.send(
                        f"⏱️ Slow down! You're sending messages too quickly."
                    )
                    return

        # Record message
        db.record_feature_usage(message.author.id, 'bot_message')

        content_lower = content.lower()
        normalized_plain = re.sub(r'[^a-z0-9\s]', ' ', content_lower).strip()
        tokens = [tok for tok in normalized_plain.split() if tok]

        greeting_phrases = {
            "hi",
            "hello",
            "hey",
            "yo",
            "sup",
            "what's up",
            "whats up",
            "what is up",
            "morning",
            "good morning",
            "good evening",
            "good afternoon",
        }
        casual_starts = {"hi", "hello", "hey", "yo"}

        basic_greeting = False
        if normalized_plain in greeting_phrases:
            basic_greeting = True
        elif tokens and tokens[0] in casual_starts and len(tokens) <= 3:
            basic_greeting = True
        elif len(tokens) <= 4 and tokens[:2] in (["whats", "up"], ["what", "up"], ["what", "is"], ["how", "are"]):
            basic_greeting = True

        if basic_greeting:
            responses = [
                "Not much, just spinning up the servers. What's new with you?",
                "All systems go! Need anything?",
                "Living the bot life. How can I help?",
                "Just crunching data and sipping electrons. You?",
            ]
            await message.channel.send(random.choice(responses))
            return

        # Check for leaderboard triggers in natural language
        leaderboard_triggers = {
            'messages': ['who talks the most', 'who messages the most', 'most active', 'most messages', 'who chats the most'],
            'questions': ['who asks the most questions', 'most questions', 'most curious', 'who questions'],
            'profanity': ['who swears the most', 'who curses the most', 'most profanity', 'saltiest', 'who says fuck']
        }

        for stat_type, triggers in leaderboard_triggers.items():
            if any(trigger in content_lower for trigger in triggers):
                # Extract days if mentioned
                days = 7
                if 'month' in content_lower or '30 days' in content_lower:
                    days = 30
                elif 'week' in content_lower or '7 days' in content_lower:
                    days = 7
                elif 'year' in content_lower:
                    days = 365

                # Generate leaderboard
                await generate_leaderboard_response(message.channel, stat_type, days, db, llm)
                return

        # Rate limiting (per user to avoid abuse) - skip for admin
        if not is_admin:
            rate_window = float(os.getenv("MENTION_RATE_WINDOW_SECONDS", "6"))
            max_per_window = int(os.getenv("MENTION_RATE_MAX_CALLS", "3"))
            if rate_window > 0 and max_per_window > 0:
                now_ts = datetime.now(timezone.utc).timestamp()
                rate_limited = False
                async with _RATE_STATE_LOCK:
                    user_bucket = MENTION_RATE_STATE.get(message.author.id)
                    if user_bucket and now_ts - user_bucket["window_start"] <= rate_window:
                        if user_bucket["count"] >= max_per_window:
                            rate_limited = True
                        else:
                            user_bucket["count"] += 1
                    else:
                        MENTION_RATE_STATE[message.author.id] = {
                            "count": 1,
                            "window_start": now_ts,
                        }
                if rate_limited:
                    await message.channel.send(
                        "⏱️ Let's take a breather. Try again in a few seconds."
                    )
                    return

        # Token-based rate limiting check (skip for admin)
        if not is_admin:
            max_tokens_per_request = int(os.getenv('MAX_TOKENS_PER_REQUEST', '1000'))
            rate_limit_check = db.check_rate_limit(
                message.author.id,
                str(message.author),
                max_tokens_per_request
            )

            if not rate_limit_check['allowed']:
                tokens_used = rate_limit_check['tokens_used']
                limit = rate_limit_check['limit']
                reset_minutes = rate_limit_check['reset_seconds'] // 60
                reset_seconds = rate_limit_check['reset_seconds'] % 60

                await message.channel.send(
                    f"⏱️ Token limit reached! You've used {tokens_used:,}/{limit:,} tokens this hour.\n"
                    f"Reset in {reset_minutes}m {reset_seconds}s."
                )
                return

        # Repeated message detection (anti-gaming) - skip for admin
        if not is_admin:
            repeated_check = db.check_repeated_messages(
                message.author.id,
                content
            )

            if not repeated_check['allowed']:
                similar_count = repeated_check['similar_count']
                threshold = repeated_check['threshold']
                window_minutes = repeated_check['window_minutes']

                await message.channel.send(
                    f"🚫 Repeated message detected! You've asked {similar_count} similar questions in the last {window_minutes} minutes.\n"
                    f"Please wait before asking similar questions again. (Limit: {threshold} similar messages per {window_minutes}m)"
                )
                return

        # Concurrent request limiting (with lock for thread safety)
        max_concurrent_requests = int(os.getenv('MAX_CONCURRENT_REQUESTS', '3'))
        concurrent_limited = False
        async with _CONCURRENT_REQUESTS_LOCK:
            current_requests = USER_CONCURRENT_REQUESTS.get(message.author.id, 0)
            if current_requests >= max_concurrent_requests:
                concurrent_limited = True
            else:
                # Increment concurrent request counter atomically
                USER_CONCURRENT_REQUESTS[message.author.id] = current_requests + 1

        if concurrent_limited:
            await message.channel.send(
                f"⏱️ Too many requests at once! Please wait for your current request to finish."
            )
            return

        # Get conversation context - use CONTEXT_WINDOW_MESSAGES env var
        context_window = int(os.getenv('CONTEXT_WINDOW_MESSAGES', '50'))
        conversation_history = db.get_recent_messages(
            message.channel.id,
            limit=context_window,
            exclude_opted_out=True,
            guild_id=message.guild.id if message.guild else None
            # Include bot messages so it can remember what it said
        )

        # Debug: Log conversation history
        print(f"🔍 Retrieved {len(conversation_history)} messages for context (limit={context_window})")
        if len(conversation_history) > 0:
            print(f"   First message: {conversation_history[0].get('username')}: {conversation_history[0].get('content', '')[:50]}")
            print(f"   Last message: {conversation_history[-1].get('username')}: {conversation_history[-1].get('content', '')[:50]}")

        # Always send a placeholder message immediately for better UX
        # Use search message if search is likely needed, otherwise use thinking message
        if search and llm.should_search(content, conversation_history):
            placeholder_msg = await message.channel.send(random.choice(SEARCH_STATUS_MESSAGES))
        else:
            placeholder_msg = await message.channel.send(random.choice(THINKING_STATUS_MESSAGES))

        # Start typing indicator (will be invisible if placeholder_msg was sent, but keeps connection alive)
        async with message.channel.typing():

            # Clean Discord mentions from conversation history
            for msg in conversation_history:
                if msg.get('content'):
                    msg['content'] = clean_discord_mentions(msg['content'], message)

            # Get user context (if not opted out)
            user_context = None if opted_out else db.get_user_context(message.author.id)

            # Check if question is about WompBot itself - load documentation
            bot_docs = None
            if self_knowledge:
                # Get full conversation history (including bot messages) for context-aware detection
                full_conversation_history = db.get_recent_messages(
                    message.channel.id,
                    limit=3,  # Just need last few messages
                    exclude_opted_out=True,
                    exclude_bot_id=None,  # Don't exclude bot messages
                    user_id=message.author.id,
                    guild_id=message.guild.id if message.guild else None
                )
                bot_docs = self_knowledge.format_for_llm(content, full_conversation_history, bot.user.id)
                if bot_docs:
                    print(f"📚 Loading WompBot documentation for self-knowledge question")

            # Check if search is needed (skip if we're using docs)
            search_results = None

            if search and not bot_docs and llm.should_search(content, conversation_history):
                # Check search rate limits (skip for admin)
                search_rate_check = {'allowed': True}
                if not is_admin:
                    search_hourly_limit = int(os.getenv('SEARCH_HOURLY_LIMIT', '5'))
                    search_daily_limit = int(os.getenv('SEARCH_DAILY_LIMIT', '20'))

                    search_rate_check = db.check_feature_rate_limit(
                        message.author.id,
                        'search',
                        hourly_limit=search_hourly_limit,
                        daily_limit=search_daily_limit
                    )

                if not search_rate_check['allowed']:
                    # Delete the placeholder if rate limited
                    if placeholder_msg:
                        await placeholder_msg.delete()
                        placeholder_msg = None

                    if search_rate_check['reason'] == 'hourly_limit':
                        await message.channel.send(
                            f"⏱️ Search limit reached! You've used {search_rate_check['count']}/{search_rate_check['limit']} searches this hour."
                        )
                    elif search_rate_check['reason'] == 'daily_limit':
                        await message.channel.send(
                            f"📊 Daily search limit reached! You've used {search_rate_check['count']}/{search_rate_check['limit']} searches today."
                        )
                    # Skip search but continue with response
                else:
                    # Placeholder already sent, now actually do the search
                    # Build contextual query that considers recent conversation
                    search_query = search.build_contextual_query(content, conversation_history)
                    search_results_raw = await asyncio.to_thread(search.search, search_query)
                    search_results = search.format_results_for_llm(search_results_raw)

                    db.store_search_log(search_query, len(search_results_raw), message.author.id, message.channel.id)
                    db.record_feature_usage(message.author.id, 'search')

            # Get server personality setting
            server_id = message.guild.id if message.guild else None
            personality = db.get_server_personality(server_id) if server_id else 'default'

            # Get RAG context (semantic search, facts, summaries)
            rag_context = None
            if rag:
                rag_context = await rag.get_relevant_context(
                    content,
                    message.channel.id,
                    message.author.id,
                    limit=3
                )

            # Generate response
            # Only pass user info for text mentions ("wompbot") to reduce cost logging noise
            # Use bot docs if available, otherwise use search results
            context_for_llm = bot_docs or search_results

            # Get tool executor for visualization and search
            tool_executor = get_tool_executor(db, wolfram, weather, search)

            response = await asyncio.to_thread(
                llm.generate_response,
                content,
                conversation_history,
                user_context,
                context_for_llm,
                rag_context,
                0,
                bot.user.id,
                message.author.id if is_text_mention else None,
                str(message.author) if is_text_mention else None,
                None,  # max_tokens (use default)
                personality,  # personality setting
                ALL_TOOLS,  # Enable all tools (visualization + computational)
            )

            # Check if LLM wants to use tools
            if isinstance(response, dict) and response.get("type") == "tool_calls":
                # Delete the placeholder message before showing tool-specific status
                if placeholder_msg:
                    await placeholder_msg.delete()
                    placeholder_msg = None

                # Determine what kind of tools are being called
                tool_names = [tc.get("function", {}).get("name", "") for tc in response["tool_calls"]]
                has_search = "web_search" in tool_names
                has_viz = any(name in ["create_bar_chart", "create_line_chart", "create_pie_chart", "create_table", "create_comparison_chart"] for name in tool_names)

                # Show appropriate status message
                if has_search:
                    status_msg = await message.channel.send(random.choice(SEARCH_STATUS_MESSAGES))
                elif has_viz:
                    status_msg = await message.channel.send("📊 Creating visualization...")
                else:
                    status_msg = await message.channel.send("⚙️ Processing...")

                # Execute all tool calls and collect results
                images_to_send = []
                text_responses = []
                tool_results = []  # For feeding back to LLM

                for tool_call in response["tool_calls"]:
                    result = await tool_executor.execute_tool(
                        tool_call,
                        channel_id=message.channel.id,
                        user_id=message.author.id
                    )

                    # Collect tool results for LLM feedback
                    tool_name = tool_call.get("function", {}).get("name", "unknown")
                    if result.get("success"):
                        if result.get("type") == "image":
                            images_to_send.append(result["image"])
                            tool_results.append(f"Successfully created {tool_name} visualization")
                            print(f"✅ Tool {tool_name} created image")
                        elif result.get("type") == "text":
                            text_response = result.get("text", "")
                            # web_search results should only go to LLM for synthesis, not directly to user
                            if tool_name != "web_search":
                                text_responses.append(text_response)
                            # Always include full results for LLM to analyze
                            tool_results.append(f"{tool_name}: {text_response}")
                            print(f"✅ Tool {tool_name} returned text: {text_response[:100]}...")
                    else:
                        error_msg = result.get("error", "Unknown error")
                        tool_results.append(f"Error in {tool_name}: {error_msg}")
                        # Show errors to user immediately
                        text_responses.append(f"❌ {error_msg}")
                        print(f"❌ Tool {tool_name} failed: {error_msg}")

                # Send images to Discord
                if images_to_send:
                    print(f"📤 Sending {len(images_to_send)} image(s) to user")
                    files = []
                    for i, img_buffer in enumerate(images_to_send):
                        files.append(discord.File(img_buffer, filename=f"chart_{i}.png"))
                    await message.channel.send(files=files)
                    print(f"✅ Images sent successfully")

                # Send text responses (from tools like Wolfram/Weather/Search)
                if text_responses:
                    combined_text = "\n\n".join(text_responses)
                    print(f"📤 Sending text response ({len(combined_text)} chars)")
                    # Chunk if longer than Discord's 2000 char limit
                    if len(combined_text) > 2000:
                        chunks = [combined_text[i:i+2000] for i in range(0, len(combined_text), 2000)]
                        for chunk in chunks:
                            if chunk.strip():
                                await message.channel.send(chunk)
                        print(f"✅ Sent {len(chunks)} text chunks")
                    else:
                        await message.channel.send(combined_text)
                        print(f"✅ Text response sent")

                # If tools were executed AND there's no response_text from LLM,
                # ask LLM to provide commentary on the tool results
                initial_response_text = response.get("response_text", "").strip()

                # Check if web_search was used - always synthesize search results
                has_search_results = any("web_search:" in tr for tr in tool_results)

                # Check if only visualization/self-explanatory tools were used
                # These tools don't need LLM commentary (the image/output speaks for itself)
                visualization_tools = ["get_weather", "get_weather_forecast", "create_bar_chart",
                                      "create_line_chart", "create_pie_chart", "create_table",
                                      "create_comparison_chart", "wolfram_query"]
                only_viz_tools = all(any(vt in tn for vt in visualization_tools) for tn in tool_names)

                # Only synthesize if:
                # 1. Web search was used (always needs synthesis), OR
                # 2. Non-visualization tools were used AND no initial response
                needs_synthesis = has_search_results or (not only_viz_tools and not initial_response_text)

                print(f"🤔 Synthesis decision: viz_tools={only_viz_tools}, has_search={has_search_results}, needs_synthesis={needs_synthesis}")

                if tool_results and needs_synthesis:
                    print(f"🧠 Synthesizing {len(tool_results)} tool results...")
                    # Update status to show we're analyzing
                    await status_msg.edit(content="🤔 Analyzing results...")

                    # Feed tool results back to LLM for commentary
                    tool_results_summary = "\n".join(tool_results)

                    # Create a follow-up message to get LLM to synthesize the results
                    follow_up_prompt = f"The user asked: {content}\n\nTool execution results:\n{tool_results_summary}\n\nBased on the tool results above, provide a clear, concise answer to the user's question."

                    response = await asyncio.to_thread(
                        llm.generate_response,
                        follow_up_prompt,
                        conversation_history,
                        user_context,
                        context_for_llm,
                        rag_context,
                        0,
                        bot.user.id,
                        message.author.id if is_text_mention else None,
                        str(message.author) if is_text_mention else None,
                        None,  # max_tokens (use default)
                        personality,  # personality setting
                        None,  # No more tools on follow-up
                    )

                    # Delete status message after synthesis
                    await status_msg.delete()
                    print(f"✅ Synthesis complete")
                elif initial_response_text and not only_viz_tools:
                    # LLM provided commentary along with tool call
                    # But skip for visualization tools (weather, charts, etc.) - the output speaks for itself
                    print(f"💬 Using initial LLM response (non-viz tools)")
                    response = initial_response_text
                    await status_msg.delete()
                else:
                    # No output from tools, or visualization tools completed
                    print(f"✅ Visualization tools complete, skipping synthesis")
                    response = None
                    await status_msg.delete()

            # Check if response is empty (but allow None for tool-only responses)
            if response is not None and (not response or (isinstance(response, str) and len(response.strip()) == 0)):
                response = "I got nothing. Try asking something else?"

            # Ensure response is a string
            if isinstance(response, dict):
                response = response.get("response_text", "Done!")

            # Check if LLM says it needs more info (skip if we used bot docs or response is None)
            if response is not None and search and not bot_docs and not search_results and llm.detect_needs_search_from_response(response):
                # Check search rate limits (second attempt) - skip for admin
                search_rate_check = {'allowed': True}
                if not is_admin:
                    search_hourly_limit = int(os.getenv('SEARCH_HOURLY_LIMIT', '5'))
                    search_daily_limit = int(os.getenv('SEARCH_DAILY_LIMIT', '20'))

                    search_rate_check = db.check_feature_rate_limit(
                        message.author.id,
                        'search',
                        hourly_limit=search_hourly_limit,
                        daily_limit=search_daily_limit
                    )

                if search_rate_check['allowed']:
                    if not placeholder_msg:
                        placeholder_msg = await message.channel.send("🔍 Let me search for that...")
                    else:
                        await placeholder_msg.edit(content="🔍 Let me search for that...")

                    # Build contextual query that considers recent conversation
                    search_query = search.build_contextual_query(content, conversation_history)
                    search_results_raw = await asyncio.to_thread(search.search, search_query)
                    search_results = search.format_results_for_llm(search_results_raw)

                    db.store_search_log(search_query, len(search_results_raw), message.author.id, message.channel.id)
                    db.record_feature_usage(message.author.id, 'search')

                # Regenerate response with search results (or without if rate limited)
                # Update context (bot docs take priority over search)
                context_for_llm = bot_docs or search_results

                response = await asyncio.to_thread(
                    llm.generate_response,
                    content,
                    conversation_history,
                    user_context,
                    context_for_llm,
                    rag_context,
                    0,
                    bot.user.id,
                    message.author.id if is_text_mention else None,
                    str(message.author) if is_text_mention else None,
                    None,  # max_tokens (use default)
                    personality,  # personality setting
                    ALL_TOOLS,  # Enable all tools (visualization + computational) on retry
                )

                # Check for tool calls on retry
                if isinstance(response, dict) and response.get("type") == "tool_calls":
                    # Delete the placeholder message before showing tool-specific status
                    if placeholder_msg:
                        await placeholder_msg.delete()
                        placeholder_msg = None

                    # Determine what kind of tools are being called
                    tool_names = [tc.get("function", {}).get("name", "") for tc in response["tool_calls"]]
                    has_search = "web_search" in tool_names
                    has_viz = any(name in ["create_bar_chart", "create_line_chart", "create_pie_chart", "create_table", "create_comparison_chart"] for name in tool_names)

                    # Show appropriate status message
                    if has_search:
                        status_msg = await message.channel.send(random.choice(SEARCH_STATUS_MESSAGES))
                    elif has_viz:
                        status_msg = await message.channel.send("📊 Creating visualization...")
                    else:
                        status_msg = await message.channel.send("⚙️ Processing...")

                    images_to_send = []
                    text_responses = []
                    tool_results = []

                    for tool_call in response["tool_calls"]:
                        result = await tool_executor.execute_tool(
                            tool_call,
                            channel_id=message.channel.id,
                            user_id=message.author.id
                        )

                        tool_name = tool_call.get("function", {}).get("name", "unknown")
                        if result.get("success"):
                            if result.get("type") == "image":
                                images_to_send.append(result["image"])
                                tool_results.append(f"Successfully created {tool_name} visualization")
                                print(f"✅ Tool {tool_name} created image")
                            elif result.get("type") == "text":
                                text_response = result.get("text", "")
                                # web_search results should only go to LLM for synthesis, not directly to user
                                if tool_name != "web_search":
                                    text_responses.append(text_response)
                                # Always include full results for LLM to analyze
                                tool_results.append(f"{tool_name}: {text_response}")
                                print(f"✅ Tool {tool_name} returned text: {text_response[:100]}...")
                        else:
                            error_msg = result.get("error", "Unknown error")
                            tool_results.append(f"Error in {tool_name}: {error_msg}")
                            # Show errors to user immediately
                            text_responses.append(f"❌ {error_msg}")
                            print(f"❌ Tool {tool_name} failed: {error_msg}")

                    if images_to_send:
                        print(f"📤 Sending {len(images_to_send)} image(s) to user")
                        files = []
                        for i, img_buffer in enumerate(images_to_send):
                            files.append(discord.File(img_buffer, filename=f"chart_{i}.png"))
                        await message.channel.send(files=files)
                        print(f"✅ Images sent successfully")

                    if text_responses:
                        combined_text = "\n\n".join(text_responses)
                        print(f"📤 Sending text response ({len(combined_text)} chars)")
                        # Chunk if longer than Discord's 2000 char limit
                        if len(combined_text) > 2000:
                            chunks = [combined_text[i:i+2000] for i in range(0, len(combined_text), 2000)]
                            for chunk in chunks:
                                if chunk.strip():
                                    await message.channel.send(chunk)
                            print(f"✅ Sent {len(chunks)} text chunks")
                        else:
                            await message.channel.send(combined_text)
                            print(f"✅ Text response sent")

                    # Get LLM commentary on tool results if needed
                    initial_response_text = response.get("response_text", "").strip()

                    # Check if web_search was used - always synthesize search results
                    has_search_results = any("web_search:" in tr for tr in tool_results)

                    if tool_results and (not initial_response_text or has_search_results):
                        # Update status to show we're analyzing
                        await status_msg.edit(content="🤔 Analyzing results...")

                        tool_results_summary = "\n".join(tool_results)
                        follow_up_prompt = f"The user asked: {content}\n\nTool execution results:\n{tool_results_summary}\n\nBased on the tool results above, provide a clear, concise answer to the user's question."

                        response = await asyncio.to_thread(
                            llm.generate_response,
                            follow_up_prompt,
                            conversation_history,
                            user_context,
                            context_for_llm,
                            rag_context,
                            0,
                            bot.user.id,
                            message.author.id if is_text_mention else None,
                            str(message.author) if is_text_mention else None,
                            None,
                            personality,
                            None,  # No more tools
                        )

                        # Delete status message after synthesis
                        await status_msg.delete()
                    elif initial_response_text:
                        response = initial_response_text
                        await status_msg.delete()
                    else:
                        response = None
                        await status_msg.delete()

            # Final check for empty response (but allow None for tool-only responses)
            if response is not None and (not response or (isinstance(response, str) and len(response.strip()) == 0)):
                response = "Error: Got an empty response. Try rephrasing?"

            # Ensure response is string before restoring mentions
            if isinstance(response, dict):
                response = response.get("response_text", "Done!")

            # Only send response if it's not None (None means tool already sent output)
            if response is not None:
                # Restore Discord mentions before sending
                response = restore_discord_mentions(response, message)
                print(f"📝 Final response prepared ({len(response)} chars)")

            # Send or edit response
            if response is not None and placeholder_msg:
                print(f"📤 Editing search message with final response")
                # Edit the search message with the response
                if len(response) > 2000:
                    await placeholder_msg.edit(content=response[:2000])
                    # Store the edited response in database (edit doesn't trigger on_message)
                    db.store_message(placeholder_msg, opted_out=False, content_override=response[:2000])
                    # Send remaining chunks as new messages
                    remaining = response[2000:]
                    chunks = [remaining[i:i+2000] for i in range(0, len(remaining), 2000)]
                    for chunk in chunks:
                        if chunk.strip():
                            await message.channel.send(chunk)
                    print(f"✅ Search message edited, sent {len(chunks)} additional chunks")
                else:
                    await placeholder_msg.edit(content=response)
                    # Store the edited response in database (edit doesn't trigger on_message)
                    db.store_message(placeholder_msg, opted_out=False, content_override=response)
                    print(f"✅ Search message edited")
            elif response is not None:
                print(f"📤 Sending final response as new message")
                # No search, just send normally
                if len(response) > 2000:
                    chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        if chunk.strip():
                            await message.channel.send(chunk)
                    print(f"✅ Sent response in {len(chunks)} chunks")
                else:
                    await message.channel.send(response)
                    print(f"✅ Response sent")
            else:
                print(f"ℹ️ No final response to send (tools already sent output)")

            # Record token usage for rate limiting
            # Estimate: ~4 characters per token (common approximation)
            # Include both input (content) and output (response) tokens
            response_length = len(response) if response is not None else 0
            estimated_tokens = (len(content) + response_length) // 4
            db.record_token_usage(message.author.id, str(message.author), estimated_tokens)

    except Exception as e:
        print(f"❌ Error handling message: {e}")
        import traceback
        traceback.print_exc()

        # Clean up orphaned placeholder message if it exists
        if placeholder_msg:
            try:
                await placeholder_msg.delete()
            except Exception:
                pass  # Ignore deletion errors (message may already be gone)

        await message.channel.send(f"Error processing request: {str(e)}")
    finally:
        # Decrement concurrent request counter (with lock for thread safety)
        try:
            async with _CONCURRENT_REQUESTS_LOCK:
                if message.author.id in USER_CONCURRENT_REQUESTS:
                    USER_CONCURRENT_REQUESTS[message.author.id] -= 1
                    if USER_CONCURRENT_REQUESTS[message.author.id] <= 0:
                        del USER_CONCURRENT_REQUESTS[message.author.id]
        except Exception as cleanup_error:
            print(f"⚠️ Error cleaning up concurrent request counter: {cleanup_error}")
