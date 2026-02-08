"""
Conversation handlers for WompBot Discord bot.

This module contains conversation-related functions including bot mention handling
and leaderboard generation.
"""

import asyncio
import logging
import os
import random
import re

import discord
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Tool system imports
from viz_tools import GeneralVisualizer
from llm_tools import VISUALIZATION_TOOLS, COMPUTATIONAL_TOOLS, ALL_TOOLS, DataRetriever
from tool_executor import ToolExecutor
from media_processor import get_media_processor

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


# Visualization intent signals - user must use one of these to get chart tools
_VIZ_INTENT_KEYWORDS = [
    'chart', 'graph', 'plot', 'visualize', 'visualise', 'visualization',
    'bar chart', 'line chart', 'pie chart', 'table', 'comparison chart',
    'show me a chart', 'show me a graph', 'create a chart', 'create a graph',
    'make a chart', 'make a graph', 'draw a chart', 'draw a graph',
    'server stats', 'server activity', 'message stats', 'user activity',
    'top users', 'most active', 'activity chart', 'leaderboard chart',
]

def _select_tools_for_message(message_content: str) -> list:
    """Select which tools to pass to the LLM based on message intent.

    Only includes visualization tools when the user explicitly asks for
    charts/graphs/data visualization. This prevents the LLM from generating
    charts for knowledge questions like 'what is a write down'.
    """
    content_lower = message_content.lower()

    # Check if the message has data visualization intent
    wants_viz = any(keyword in content_lower for keyword in _VIZ_INTENT_KEYWORDS)

    if wants_viz:
        logger.debug("Visualization intent detected, passing ALL tools")
        return ALL_TOOLS
    else:
        logger.debug("No visualization intent, passing COMPUTATIONAL tools only")
        return COMPUTATIONAL_TOOLS


# Rate limiting state for mention handling
MENTION_RATE_STATE = {}
USER_CONCURRENT_REQUESTS = {}
_LAST_CLEANUP_TIME = 0

# Channel-level semaphores to limit concurrent request processing (prevents response mixing)
# Each channel allows up to 3 concurrent requests
CHANNEL_LOCKS = {}
_CHANNEL_LOCKS_LOCK = asyncio.Lock()

# Locks for thread-safe access to rate limiting state
_RATE_STATE_LOCK = asyncio.Lock()
_CONCURRENT_REQUESTS_LOCK = asyncio.Lock()


async def get_channel_lock(channel_id: int) -> asyncio.Semaphore:
    """Get or create a semaphore for a specific channel to limit concurrent processing to 3 requests"""
    async with _CHANNEL_LOCKS_LOCK:
        if channel_id not in CHANNEL_LOCKS:
            CHANNEL_LOCKS[channel_id] = asyncio.Semaphore(3)
        return CHANNEL_LOCKS[channel_id]

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
        logger.debug("Cleaned up %d stale rate limit entries", len(stale_users))

    # Cleanup CHANNEL_LOCKS - remove semaphores for channels no longer in active rate state
    # and not currently in use (i.e., all 3 slots are free)
    async with _CHANNEL_LOCKS_LOCK:
        active_channels = set()
        # Keep semaphores for channels that are currently in use
        stale_channels = [
            ch_id for ch_id, sem in CHANNEL_LOCKS.items()
            if sem._value == 3  # All slots free, safe to remove
        ]
        # Only clean up if we have more than 1000 entries to avoid unbounded growth
        if len(CHANNEL_LOCKS) > 1000:
            for ch_id in stale_channels:
                del CHANNEL_LOCKS[ch_id]
            if stale_channels:
                logger.debug("Cleaned up %d stale channel semaphores", len(stale_channels))

# Initialize visualization tools (module-level, reused across calls)
_visualizer = None
_tool_executor = None

def get_visualizer():
    """Get or create visualizer instance"""
    global _visualizer
    if _visualizer is None:
        _visualizer = GeneralVisualizer()
    return _visualizer

def get_tool_executor(db, wolfram=None, weather=None, search=None,
                       iracing_manager=None, reminder_manager=None, bot=None):
    """Get or create tool executor instance"""
    global _tool_executor
    if _tool_executor is None:
        visualizer = get_visualizer()
        data_retriever = DataRetriever(db)
        _tool_executor = ToolExecutor(
            db, visualizer, data_retriever, wolfram, weather, search,
            iracing_manager, reminder_manager, bot
        )
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

            # Classify questions using LLM (run in thread to avoid blocking event loop)
            results = await asyncio.to_thread(llm.classify_questions, messages)

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
        logger.error("Leaderboard generation error: %s", e)


async def handle_bot_mention(message, opted_out, bot, db, llm, cost_tracker, search=None,
                             self_knowledge=None, rag=None, wolfram=None, weather=None,
                             iracing_manager=None, reminder_system=None):
    """Handle when bot is mentioned/tagged"""
    logger.info("handle_bot_mention called for %s in #%s", message.author, getattr(message.channel, 'name', 'DM'))
    # Track placeholder message for cleanup on error
    placeholder_msg = None
    # Track channel lock for cleanup
    channel_lock = None
    try:
        # Periodic cleanup of stale rate limiting state
        await cleanup_stale_rate_state()

        # Check if user is admin (bypass all rate limits)
        # Admin IDs from env (comma-separated)
        admin_ids_str = os.getenv('BOT_ADMIN_IDS', '')
        admin_ids = set(int(x.strip()) for x in admin_ids_str.split(',') if x.strip().isdigit())
        is_admin = message.author.id in admin_ids

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

        # Extract and process media for vision analysis
        media_processor = get_media_processor()

        # Collect raw media URLs and their types
        raw_media = []  # List of (url, type) tuples
        supported_image_types = {'image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'}
        supported_video_types = {'video/mp4', 'video/webm', 'video/quicktime', 'video/mpeg', 'video/avi'}

        # Helper to check if content suggests user is asking about an image
        def is_asking_about_image(text):
            text_lower = text.lower()
            image_question_patterns = [
                'what is this', 'what\'s this', 'whats this',
                'who is this', 'who\'s this', 'whos this',
                'what is that', 'what\'s that', 'whats that',
                'who is that', 'who\'s that', 'whos that',
                'what do you see', 'can you see',
                'describe this', 'describe that',
                'what\'s in this', 'what\'s in the',
                'who is in', 'what is in',
            ]
            return any(pattern in text_lower for pattern in image_question_patterns)

        # Check attachments in current message
        for attachment in message.attachments:
            content_type = attachment.content_type or ''
            filename_lower = attachment.filename.lower()

            is_image = (
                any(img_type in content_type for img_type in supported_image_types) or
                filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
            )
            is_video = (
                any(vid_type in content_type for vid_type in supported_video_types) or
                filename_lower.endswith(('.mp4', '.webm', '.mov', '.mpeg', '.avi', '.mkv'))
            )

            if is_image and attachment.url:
                media_type = 'gif' if filename_lower.endswith('.gif') else 'image'
                raw_media.append((attachment.url, media_type))
                logger.debug("Found %s attachment: %s", media_type, attachment.filename)
            elif is_video and attachment.url:
                raw_media.append((attachment.url, 'video'))
                logger.debug("Found video attachment: %s", attachment.filename)

        # Check for embedded image URLs
        image_url_pattern = r'https?://[^\s<>"]+?\.(?:png|jpg|jpeg|gif|webp)(?:\?[^\s<>"]*)?'
        for url in re.findall(image_url_pattern, content, re.IGNORECASE):
            if not any(url == m[0] for m in raw_media):
                media_type = 'gif' if url.lower().endswith('.gif') else 'image'
                raw_media.append((url, media_type))
                logger.debug("Found embedded %s: %s...", media_type, url[:50])

        # Check for YouTube URLs in message content
        youtube_pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})'
        youtube_matches = re.findall(youtube_pattern, content)
        for video_id in youtube_matches:
            yt_url = f"https://www.youtube.com/watch?v={video_id}"
            if not any(yt_url == m[0] for m in raw_media):
                raw_media.append((yt_url, 'youtube'))
                logger.debug("Found YouTube video: %s", video_id)

        # If no media in current message but user is asking about an image, check recent messages
        if not raw_media and is_asking_about_image(content):
            logger.debug("User asking about image but no media in message - checking recent channel history...")
            try:
                # Look at the last 10 messages for any media
                async for recent_msg in message.channel.history(limit=10, before=message):
                    # Skip bot's own messages
                    if recent_msg.author.id == bot.user.id:
                        continue

                    # Check attachments in recent messages
                    for attachment in recent_msg.attachments:
                        content_type = attachment.content_type or ''
                        filename_lower = attachment.filename.lower()
                        is_image = (
                            any(img_type in content_type for img_type in supported_image_types) or
                            filename_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
                        )
                        if is_image and attachment.url:
                            media_type = 'gif' if filename_lower.endswith('.gif') else 'image'
                            raw_media.append((attachment.url, media_type))
                            logger.debug("Found %s in recent message from %s: %s", media_type, recent_msg.author, attachment.filename)
                            break  # Only get one image

                    # Also check for Tenor/Giphy GIFs in message content or embeds
                    if not raw_media:
                        # Check embeds (Tenor/Giphy show as embeds)
                        for embed in recent_msg.embeds:
                            if embed.image and embed.image.url:
                                raw_media.append((embed.image.url, 'image'))
                                logger.debug("Found embedded image from %s: %s...", recent_msg.author, embed.image.url[:50])
                                break
                            if embed.thumbnail and embed.thumbnail.url:
                                raw_media.append((embed.thumbnail.url, 'image'))
                                logger.debug("Found thumbnail from %s: %s...", recent_msg.author, embed.thumbnail.url[:50])
                                break

                    if raw_media:
                        break  # Found media, stop searching
            except Exception as e:
                logger.warning("Error checking recent messages for media: %s", e)

        # Process media to extract frames/thumbnails
        processed_images = []  # base64 encoded images
        direct_image_urls = []  # URLs that can be passed directly
        media_context_notes = []  # Notes about what media is being analyzed
        transcript_text = None  # For YouTube transcripts

        for url, media_type in raw_media:
            if media_type == 'youtube':
                # Process YouTube video - transcript first (instant), frames only if needed
                video_id = media_processor.extract_youtube_id(url)
                logger.info("Processing YouTube video: %s", video_id)

                # Send processing message (usually quick for transcript-only)
                processing_msg = await message.channel.send("📝 Getting video transcript...")

                yt_result = await media_processor.analyze_youtube_video(video_id, need_visuals=False)

                # Delete processing message
                try:
                    await processing_msg.delete()
                except discord.NotFound:
                    pass

                if yt_result.get('success'):
                    # Get video metadata
                    duration = yt_result.get('duration', 0)
                    duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "unknown"
                    title = yt_result.get('title', 'Unknown')
                    author = yt_result.get('author', 'Unknown')

                    # Add transcript if available (primary source)
                    if yt_result.get('transcript'):
                        transcript_text = yt_result['transcript']
                        # Truncate very long transcripts
                        if len(transcript_text) > 4000:
                            transcript_text = transcript_text[:4000] + "\n[...transcript truncated...]"
                        media_context_notes.append(
                            f"[YouTube Video: \"{title}\" by {author} ({duration_str}) - transcript available below]"
                        )
                        logger.info("Got video transcript (%d chars)", len(transcript_text))

                    # Add thumbnail/frames for visual reference
                    if yt_result.get('frames'):
                        processed_images.extend(yt_result['frames'])
                        frame_count = len(yt_result['frames'])
                        timestamps = yt_result.get('frame_timestamps', [])
                        if not yt_result.get('transcript'):
                            # No transcript - rely on visual frames
                            media_context_notes.append(
                                f"[YouTube Video: \"{title}\" by {author} ({duration_str}) - "
                                f"no transcript available, showing {frame_count} frames at: {', '.join(timestamps)}]"
                            )
                        logger.info("Got %d visual frames from video", frame_count)
                else:
                    media_context_notes.append(f"[YouTube video processing failed: {yt_result.get('error', 'unknown error')}]")
                    logger.warning("YouTube processing failed: %s", yt_result.get('error'))

            elif media_type == 'gif':
                # Process GIF - extract multiple frames
                logger.debug("Extracting frames from GIF...")
                gif_result = await media_processor.extract_gif_frames(url, max_frames=6)
                if gif_result.get('success'):
                    if gif_result.get('is_animated'):
                        processed_images.extend(gif_result['frames'])
                        frame_count = len(gif_result['frames'])
                        total_frames = gif_result.get('total_frames', 0)
                        media_context_notes.append(
                            f"[Animated GIF: showing {frame_count} frames from {total_frames} total frames to capture the full animation]"
                        )
                        logger.info("Extracted %d frames from animated GIF (%d total)", frame_count, total_frames)
                    else:
                        processed_images.extend(gif_result['frames'])
                        logger.debug("GIF is static, extracted single frame")
                else:
                    # Fallback: pass URL directly
                    direct_image_urls.append(url)
                    logger.warning("GIF extraction failed, passing URL directly: %s", gif_result.get('error'))

            elif media_type == 'video':
                # Process Discord/attached videos - transcription first, frames as fallback
                logger.info("Processing video attachment...")

                processing_msg = await message.channel.send("🎤 Transcribing video audio...")

                video_result = await media_processor.analyze_video_file(url, need_visuals=False)

                try:
                    await processing_msg.delete()
                except discord.NotFound:
                    pass

                if video_result.get('success'):
                    duration = video_result.get('duration', 0)
                    duration_str = f"{duration:.1f}s" if duration else "unknown"

                    # Add transcript if available (primary source)
                    if video_result.get('transcript'):
                        transcript_text = video_result['transcript']
                        if len(transcript_text) > 4000:
                            transcript_text = transcript_text[:4000] + "\n[...transcript truncated...]"
                        media_context_notes.append(f"[Video ({duration_str}) - transcript available below]")
                        logger.info("Got video transcription (%d chars)", len(transcript_text))

                    # Add frames for visual reference
                    if video_result.get('frames'):
                        processed_images.extend(video_result['frames'])
                        frame_count = len(video_result['frames'])
                        timestamps = video_result.get('frame_timestamps', [])
                        if not video_result.get('transcript'):
                            # No transcript - rely on visual frames
                            media_context_notes.append(
                                f"[Video ({duration_str}): no audio transcript, showing {frame_count} frames at: {', '.join(timestamps)}]"
                            )
                        logger.info("Got %d visual frames from video", frame_count)
                else:
                    media_context_notes.append(f"[Video processing failed: {video_result.get('error', 'unknown')}]")
                    logger.warning("Video processing failed: %s", video_result.get('error'))

            else:
                # Regular image - pass URL directly
                direct_image_urls.append(url)

        # Build final image_urls list for the LLM
        # Combine direct URLs with base64 images
        image_urls = direct_image_urls.copy()
        base64_images = processed_images

        # Track what we have
        has_video = any(m[1] in ('video', 'youtube') for m in raw_media)
        has_animated_gif = any(m[1] == 'gif' for m in raw_media)
        has_media = len(raw_media) > 0

        if has_media:
            types_found = set(m[1] for m in raw_media)
            logger.info("Total media to analyze: %d (%s)", len(raw_media), ', '.join(types_found))
            if processed_images:
                logger.debug("Processed %d frames/thumbnails to base64", len(processed_images))

        # Allow media-only messages (no text but has images/videos)
        if (not content or len(content) < 2) and not has_media:
            await message.channel.send("Yeah? What's up?")
            return

        # If no text but has media, use an appropriate default prompt
        if (not content or len(content) < 2) and has_media:
            if has_video:
                content = "What's happening in this video? Describe what you can see."
            elif has_animated_gif:
                content = "What's happening in this GIF? Describe the animation/action."
            else:
                content = "What's in this image?"

        # Add specific context notes about the media being analyzed
        if media_context_notes:
            content = content + "\n\n" + "\n".join(media_context_notes)

        # Add video transcript if available (YouTube videos)
        if transcript_text:
            content = content + "\n\n--- VIDEO TRANSCRIPT ---\n" + transcript_text + "\n--- END TRANSCRIPT ---"

        # Input sanitization - enforce max length
        # Use higher limit when we have media context (transcripts, etc.)
        base_max_length = int(os.getenv('MAX_INPUT_LENGTH', '2000'))
        max_input_length = base_max_length + 6000 if (transcript_text or media_context_notes) else base_max_length

        if len(content) > max_input_length:
            content = content[:max_input_length]
            await message.channel.send(
                f"⚠️ Message truncated to {max_input_length} characters for processing."
            )

        # Record message for analytics
        db.record_feature_usage(message.author.id, 'bot_message')

        content_lower = content.lower()

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

        # Repeated message detection (anti-spam) - blocks same question spam - skip for admin
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

        # Get channel semaphore to limit concurrent processing (prevents response mixing)
        channel_lock = await get_channel_lock(message.channel.id)

        # Try to acquire semaphore slot with timeout - if all 3 slots are busy, queue the request
        try:
            # Wait up to 10 seconds for a slot to be free
            async with asyncio.timeout(10):
                await channel_lock.acquire()
        except asyncio.TimeoutError:
            await message.channel.send("⏳ Channel has too many concurrent requests (3 max), please wait a moment and try again.")
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
        logger.debug("Retrieved %d messages for context (limit=%d)", len(conversation_history), context_window)
        if len(conversation_history) > 0:
            logger.debug("   First message: %s: %s", conversation_history[0].get('username'), conversation_history[0].get('content', '')[:50])
            logger.debug("   Last message: %s: %s", conversation_history[-1].get('username'), conversation_history[-1].get('content', '')[:50])

        # Always send a placeholder message immediately for better UX
        # Use search message if search is likely needed, otherwise use thinking message
        # Cache should_search result to avoid calling it again later (P15 fix)
        needs_search = search and llm.should_search(content, conversation_history)
        if needs_search:
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
                # Reuse already-fetched conversation_history instead of a second DB query (P14 fix)
                # Take last 3 messages as context for self-knowledge detection
                recent_context = conversation_history[-3:] if conversation_history else []
                bot_docs = self_knowledge.format_for_llm(content, recent_context, bot.user.id)
                if bot_docs:
                    logger.info("Loading WompBot documentation for self-knowledge question")

            # Check if search is needed (skip if we're using docs)
            search_results = None

            if needs_search and not bot_docs:
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
            tool_executor = get_tool_executor(db, wolfram, weather, search,
                                              iracing_manager, reminder_system, bot)

            # Intent-based tool filtering: only pass visualization tools when the user
            # explicitly asks for charts/graphs/data visualization. This prevents the
            # LLM from generating charts for knowledge questions like "what is a write down"
            tools_for_request = _select_tools_for_message(content)

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
                tools_for_request,  # Intent-filtered tools (viz only when explicitly requested)
                image_urls if image_urls else None,  # Direct image URLs
                base64_images if base64_images else None,  # Processed frames (GIFs, YouTube thumbnails)
            )

            # Check if LLM wants to use tools
            if isinstance(response, dict) and response.get("type") == "tool_calls":
                # Determine what kind of tools are being called
                tool_names = [tc.get("function", {}).get("name", "") for tc in response["tool_calls"]]
                has_search = "web_search" in tool_names
                has_viz = any(name in ["create_bar_chart", "create_line_chart", "create_pie_chart", "create_table", "create_comparison_chart"] for name in tool_names)

                # Edit the existing placeholder to show tool-specific status (avoids flicker)
                if has_search:
                    status_text = random.choice(SEARCH_STATUS_MESSAGES)
                elif has_viz:
                    status_text = "📊 Creating visualization..."
                else:
                    status_text = "⚙️ Processing..."

                if placeholder_msg:
                    await placeholder_msg.edit(content=status_text)
                    status_msg = placeholder_msg
                    placeholder_msg = None
                else:
                    status_msg = await message.channel.send(status_text)

                # Execute all tool calls in parallel for better latency (P12 fix)
                images_to_send = []
                text_responses = []
                tool_results = []  # For feeding back to LLM

                # Run all tool calls concurrently with asyncio.gather
                tool_call_coros = [
                    tool_executor.execute_tool(
                        tool_call,
                        channel_id=message.channel.id,
                        user_id=message.author.id,
                        guild_id=message.guild.id if message.guild else None
                    )
                    for tool_call in response["tool_calls"]
                ]
                all_results = await asyncio.gather(*tool_call_coros, return_exceptions=True)

                for tool_call, result in zip(response["tool_calls"], all_results):
                    tool_name = tool_call.get("function", {}).get("name", "unknown")

                    # Handle exceptions from gather
                    if isinstance(result, Exception):
                        error_msg = f"{type(result).__name__}: {result}"
                        tool_results.append(f"Error in {tool_name}: {error_msg}")
                        text_responses.append(f"❌ {error_msg}")
                        logger.error("Tool %s raised exception: %s", tool_name, error_msg)
                        continue

                    # Collect tool results for LLM feedback
                    if result.get("success"):
                        if result.get("type") == "image":
                            images_to_send.append(result["image"])
                            tool_results.append(f"Successfully created {tool_name} visualization")
                            logger.info("Tool %s created image", tool_name)
                        elif result.get("type") == "image_url":
                            # Send image as Discord embed
                            image_url = result.get("url")
                            image_title = result.get("title", "Image")
                            if image_url:
                                embed = discord.Embed(title=image_title, color=0x3498db)
                                embed.set_image(url=image_url)
                                await message.channel.send(embed=embed)
                                tool_results.append(f"Successfully found and displayed image of {image_title}")
                                logger.info("Tool %s sent image embed: %s...", tool_name, image_url[:50])
                        elif result.get("type") == "text":
                            text_response = result.get("text", "")
                            # web_search results should only go to LLM for synthesis, not directly to user
                            if tool_name != "web_search":
                                text_responses.append(text_response)
                            # Always include full results for LLM to analyze
                            tool_results.append(f"{tool_name}: {text_response}")
                            logger.info("Tool %s returned text: %s...", tool_name, text_response[:100])
                    else:
                        error_msg = result.get("error", "Unknown error")
                        tool_results.append(f"Error in {tool_name}: {error_msg}")
                        # Show errors to user immediately
                        text_responses.append(f"❌ {error_msg}")
                        logger.error("Tool %s failed: %s", tool_name, error_msg)

                # Send images to Discord
                if images_to_send:
                    logger.info("Sending %d image(s) to user", len(images_to_send))
                    files = []
                    for i, img_buffer in enumerate(images_to_send):
                        files.append(discord.File(img_buffer, filename=f"chart_{i}.png"))
                    await message.channel.send(files=files)
                    logger.info("Images sent successfully")

                # Send text responses (from tools like Wolfram/Weather/Search)
                if text_responses:
                    combined_text = "\n\n".join(text_responses)
                    logger.info("Sending text response (%d chars)", len(combined_text))
                    # Chunk if longer than Discord's 2000 char limit
                    if len(combined_text) > 2000:
                        chunks = [combined_text[i:i+2000] for i in range(0, len(combined_text), 2000)]
                        for chunk in chunks:
                            if chunk.strip():
                                await message.channel.send(chunk)
                        logger.info("Sent %d text chunks", len(chunks))
                    else:
                        await message.channel.send(combined_text)
                        logger.info("Text response sent")

                # If tools were executed AND there's no response_text from LLM,
                # ask LLM to provide commentary on the tool results
                initial_response_text = response.get("response_text", "").strip()

                # Check if web_search was used - always synthesize search results
                has_search_results = any("web_search:" in tr for tr in tool_results)

                # Identify self-contained tools that DON'T need LLM commentary
                # Weather cards and wolfram results already display their own output
                self_contained_tools = ["get_weather", "get_weather_forecast", "wolfram_query"]
                only_self_contained = all(any(st in tn for st in self_contained_tools) for tn in tool_names)

                # Synthesis decision:
                # 1. Web search was used → always synthesize (LLM must interpret results)
                # 2. Self-contained tools (weather, wolfram) → skip synthesis (output speaks for itself)
                # 3. Visualization tools (charts) → synthesize a brief text accompaniment
                # 4. Other tools → synthesize if no initial response text
                needs_synthesis = has_search_results or (not only_self_contained and not initial_response_text)

                logger.debug("Synthesis decision: self_contained=%s, has_search=%s, needs_synthesis=%s", only_self_contained, has_search_results, needs_synthesis)

                if tool_results and needs_synthesis:
                    logger.info("Synthesizing %d tool results...", len(tool_results))
                    # Update status to show we're analyzing
                    await status_msg.edit(content="🤔 Analyzing results...")

                    # Feed tool results back to LLM for commentary
                    tool_results_summary = "\n".join(tool_results)

                    # For chart tools, ask for a brief text accompaniment
                    if has_viz:
                        follow_up_prompt = f"The user asked: {content}\n\nYou created a visualization. Tool results:\n{tool_results_summary}\n\nProvide a brief 1-2 sentence text summary to accompany the chart. Keep it short since the chart is already shown."
                    else:
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
                    logger.info("Synthesis complete")
                elif initial_response_text:
                    # LLM provided commentary along with tool call - use it
                    logger.debug("Using initial LLM response text")
                    response = initial_response_text
                    await status_msg.delete()
                else:
                    # Self-contained tools completed (weather, wolfram) - output speaks for itself
                    logger.debug("Self-contained tools complete, skipping synthesis")
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

                # Regenerate response with search results
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
                    image_urls if image_urls else None,  # Direct image URLs
                    base64_images if base64_images else None,  # Processed frames
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
                            user_id=message.author.id,
                            guild_id=message.guild.id if message.guild else None
                        )

                        tool_name = tool_call.get("function", {}).get("name", "unknown")
                        if result.get("success"):
                            if result.get("type") == "image":
                                images_to_send.append(result["image"])
                                tool_results.append(f"Successfully created {tool_name} visualization")
                                logger.info("Tool %s created image", tool_name)
                            elif result.get("type") == "image_url":
                                # Send image as Discord embed
                                image_url = result.get("url")
                                image_title = result.get("title", "Image")
                                if image_url:
                                    embed = discord.Embed(title=image_title, color=0x3498db)
                                    embed.set_image(url=image_url)
                                    await message.channel.send(embed=embed)
                                    tool_results.append(f"Successfully found and displayed image of {image_title}")
                                    logger.info("Tool %s sent image embed: %s...", tool_name, image_url[:50])
                            elif result.get("type") == "text":
                                text_response = result.get("text", "")
                                # web_search results should only go to LLM for synthesis, not directly to user
                                if tool_name != "web_search":
                                    text_responses.append(text_response)
                                # Always include full results for LLM to analyze
                                tool_results.append(f"{tool_name}: {text_response}")
                                logger.info("Tool %s returned text: %s...", tool_name, text_response[:100])
                        else:
                            error_msg = result.get("error", "Unknown error")
                            tool_results.append(f"Error in {tool_name}: {error_msg}")
                            # Show errors to user immediately
                            text_responses.append(f"❌ {error_msg}")
                            logger.error("Tool %s failed: %s", tool_name, error_msg)

                    if images_to_send:
                        logger.info("Sending %d image(s) to user", len(images_to_send))
                        files = []
                        for i, img_buffer in enumerate(images_to_send):
                            files.append(discord.File(img_buffer, filename=f"chart_{i}.png"))
                        await message.channel.send(files=files)
                        logger.info("Images sent successfully")

                    if text_responses:
                        combined_text = "\n\n".join(text_responses)
                        logger.info("Sending text response (%d chars)", len(combined_text))
                        # Chunk if longer than Discord's 2000 char limit
                        if len(combined_text) > 2000:
                            chunks = [combined_text[i:i+2000] for i in range(0, len(combined_text), 2000)]
                            for chunk in chunks:
                                if chunk.strip():
                                    await message.channel.send(chunk)
                            logger.info("Sent %d text chunks", len(chunks))
                        else:
                            await message.channel.send(combined_text)
                            logger.info("Text response sent")

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
                logger.info("Final response prepared (%d chars)", len(response))

            # Send or edit response
            if response is not None and placeholder_msg:
                logger.debug("Editing search message with final response")
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
                    logger.info("Search message edited, sent %d additional chunks", len(chunks))
                else:
                    await placeholder_msg.edit(content=response)
                    # Store the edited response in database (edit doesn't trigger on_message)
                    db.store_message(placeholder_msg, opted_out=False, content_override=response)
                    logger.info("Search message edited")
            elif response is not None:
                logger.debug("Sending final response as new message")
                # No search, just send normally
                if len(response) > 2000:
                    chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                    for chunk in chunks:
                        if chunk.strip():
                            await message.channel.send(chunk)
                    logger.info("Sent response in %d chunks", len(chunks))
                else:
                    await message.channel.send(response)
                    logger.info("Response sent")
            else:
                logger.info("No final response to send (tools already sent output)")

            # Record token usage for rate limiting
            # Estimate: ~4 characters per token (common approximation)
            # Include both input (content) and output (response) tokens
            response_length = len(response) if response is not None else 0
            estimated_tokens = (len(content) + response_length) // 4
            db.record_token_usage(message.author.id, str(message.author), estimated_tokens)

    except Exception as e:
        logger.error("Error handling message: %s", e, exc_info=True)

        # Clean up orphaned placeholder message if it exists
        if placeholder_msg:
            try:
                await placeholder_msg.delete()
            except Exception:
                pass  # Ignore deletion errors (message may already be gone)

        await message.channel.send(f"Error processing request: {str(e)}")
    finally:
        # Release channel semaphore slot to allow next request
        try:
            if channel_lock is not None:
                channel_lock.release()
        except ValueError:
            pass  # Semaphore was not acquired (e.g., timeout path)
        except Exception as lock_error:
            logger.warning("Error releasing channel semaphore: %s", lock_error)

        # Decrement concurrent request counter (with lock for thread safety)
        try:
            async with _CONCURRENT_REQUESTS_LOCK:
                if message.author.id in USER_CONCURRENT_REQUESTS:
                    USER_CONCURRENT_REQUESTS[message.author.id] -= 1
                    if USER_CONCURRENT_REQUESTS[message.author.id] <= 0:
                        del USER_CONCURRENT_REQUESTS[message.author.id]
        except Exception as cleanup_error:
            logger.warning("Error cleaning up concurrent request counter: %s", cleanup_error)
