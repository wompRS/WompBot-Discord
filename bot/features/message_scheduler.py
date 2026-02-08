"""
Message Scheduling System
Schedule messages to be sent later. Abuse prevention:
- Max 5 pending per user
- No more than 1 message per 5 minutes per channel
- Must be in the future, max 30 days out
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)


class MessageScheduler:
    """Manage scheduled messages."""

    def __init__(self, db):
        self.db = db

    async def schedule_message(self, guild_id: int, channel_id: int,
                                user_id: int, content: str,
                                send_at: datetime) -> Dict:
        """
        Schedule a message to be sent later.

        Args:
            guild_id: Discord guild ID
            channel_id: Target channel ID
            user_id: Who is scheduling
            content: Message content
            send_at: When to send it

        Returns:
            Dict with message_id or error
        """
        now = datetime.now()

        # Validate: must be in the future
        if send_at <= now:
            return {'error': 'Scheduled time must be in the future!'}

        # Validate: max 30 days out
        if send_at > now + timedelta(days=30):
            return {'error': 'Cannot schedule more than 30 days in advance!'}

        # Validate: content length
        if len(content) > 2000:
            return {'error': 'Message content too long (max 2000 characters)!'}

        if len(content.strip()) == 0:
            return {'error': 'Message content cannot be empty!'}

        # Check abuse limits
        try:
            limits = await asyncio.to_thread(
                self._check_limits, guild_id, channel_id, user_id, send_at
            )
            if limits.get('error'):
                return limits

            # Create the scheduled message
            msg_id = await asyncio.to_thread(
                self._create_scheduled_message,
                guild_id, channel_id, user_id, content, send_at
            )

            return {
                'message_id': msg_id,
                'send_at': send_at.isoformat(),
                'content_preview': content[:100] + ('...' if len(content) > 100 else '')
            }

        except Exception as e:
            logger.error("Error scheduling message: %s", e)
            return {'error': str(e)}

    def _check_limits(self, guild_id: int, channel_id: int,
                      user_id: int, send_at: datetime) -> Dict:
        """Check abuse prevention limits."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Check max 5 pending per user
                    cur.execute("""
                        SELECT COUNT(*) FROM scheduled_messages
                        WHERE user_id = %s AND guild_id = %s
                            AND sent = FALSE AND cancelled = FALSE
                    """, (user_id, guild_id))
                    pending_count = cur.fetchone()[0]

                    if pending_count >= 5:
                        return {'error': 'You already have 5 pending scheduled messages! Cancel one first.'}

                    # Check no scheduled message within 5 minutes in same channel
                    cur.execute("""
                        SELECT id, send_at FROM scheduled_messages
                        WHERE channel_id = %s AND guild_id = %s
                            AND sent = FALSE AND cancelled = FALSE
                            AND ABS(EXTRACT(EPOCH FROM (send_at - %s))) < 300
                        LIMIT 1
                    """, (channel_id, guild_id, send_at))
                    conflict = cur.fetchone()

                    if conflict:
                        return {
                            'error': 'Another message is already scheduled within 5 minutes of that time in this channel!'
                        }

                    return {}

        except Exception as e:
            logger.error("Error checking schedule limits: %s", e)
            return {'error': str(e)}

    def _create_scheduled_message(self, guild_id: int, channel_id: int,
                                   user_id: int, content: str,
                                   send_at: datetime) -> int:
        """Create a scheduled message in the database."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO scheduled_messages (guild_id, channel_id, user_id, content, send_at)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (guild_id, channel_id, user_id, content, send_at))
                msg_id = cur.fetchone()[0]
                conn.commit()
                return msg_id

    async def get_due_messages(self) -> List[Dict]:
        """Get messages that are due to be sent."""
        try:
            return await asyncio.to_thread(self._get_due_messages_sync)
        except Exception as e:
            logger.error("Error getting due messages: %s", e)
            return []

    def _get_due_messages_sync(self) -> List[Dict]:
        """Sync: fetch due messages."""
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, guild_id, channel_id, user_id, content, send_at
                    FROM scheduled_messages
                    WHERE send_at <= NOW()
                        AND sent = FALSE
                        AND cancelled = FALSE
                    ORDER BY send_at ASC
                    LIMIT 10
                """)
                return cur.fetchall()

    async def mark_sent(self, message_id: int):
        """Mark a scheduled message as sent."""
        try:
            await asyncio.to_thread(self._mark_sent_sync, message_id)
        except Exception as e:
            logger.error("Error marking message %s as sent: %s", message_id, e)

    def _mark_sent_sync(self, message_id: int):
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE scheduled_messages SET sent = TRUE WHERE id = %s",
                    (message_id,)
                )
                conn.commit()

    async def cancel_message(self, message_id: int, user_id: int) -> Dict:
        """Cancel a scheduled message (creator only)."""
        try:
            result = await asyncio.to_thread(
                self._cancel_message_sync, message_id, user_id
            )
            return result
        except Exception as e:
            logger.error("Error cancelling message: %s", e)
            return {'error': str(e)}

    def _cancel_message_sync(self, message_id: int, user_id: int) -> Dict:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, content, send_at, sent, cancelled
                    FROM scheduled_messages WHERE id = %s
                """, (message_id,))
                row = cur.fetchone()

                if not row:
                    return {'error': f'Scheduled message #{message_id} not found!'}

                if row[1] != user_id:
                    return {'error': 'You can only cancel your own scheduled messages!'}

                if row[4]:  # sent
                    return {'error': 'This message has already been sent!'}

                if row[5]:  # cancelled
                    return {'error': 'This message was already cancelled!'}

                cur.execute(
                    "UPDATE scheduled_messages SET cancelled = TRUE WHERE id = %s",
                    (message_id,)
                )
                conn.commit()

                return {'cancelled': True, 'message_id': message_id}

    async def get_user_scheduled(self, user_id: int, guild_id: int) -> List[Dict]:
        """Get a user's pending scheduled messages."""
        try:
            return await asyncio.to_thread(
                self._get_user_scheduled_sync, user_id, guild_id
            )
        except Exception as e:
            logger.error("Error getting user scheduled: %s", e)
            return []

    def _get_user_scheduled_sync(self, user_id: int, guild_id: int) -> List[Dict]:
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, channel_id, content, send_at, created_at
                    FROM scheduled_messages
                    WHERE user_id = %s AND guild_id = %s
                        AND sent = FALSE AND cancelled = FALSE
                    ORDER BY send_at ASC
                """, (user_id, guild_id))
                return cur.fetchall()
