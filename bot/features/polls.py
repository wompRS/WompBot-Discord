"""
Poll System
Create and manage polls with single-choice, multi-choice, and ranked voting.
Supports anonymous voting, time limits, and result visualization.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from psycopg2.extras import RealDictCursor
import discord
from discord.ui import View, Button
import logging

logger = logging.getLogger(__name__)


class PollView(View):
    """Discord UI View with buttons for poll voting."""

    def __init__(self, poll_system, poll_id: int, options: List[str],
                 poll_type: str = 'single', timeout_seconds: int = None):
        super().__init__(timeout=timeout_seconds or 86400)  # Default 24h timeout
        self.poll_system = poll_system
        self.poll_id = poll_id
        self.poll_type = poll_type

        # Create buttons for each option (max 25 buttons, but practical limit ~10)
        # Use different colors for visual variety
        colors = [
            discord.ButtonStyle.primary,    # Blue
            discord.ButtonStyle.success,    # Green
            discord.ButtonStyle.secondary,  # Grey
            discord.ButtonStyle.primary,
            discord.ButtonStyle.success,
        ]

        for i, option in enumerate(options[:10]):  # Max 10 options
            label = f"{option[:75]}"  # Button label max ~80 chars
            button = Button(
                label=label,
                style=colors[i % len(colors)],
                custom_id=f"poll_{poll_id}_opt_{i}"
            )
            button.callback = self._make_callback(i)
            self.add_item(button)

    def _make_callback(self, option_index: int):
        async def callback(interaction: discord.Interaction):
            result = await self.poll_system.cast_vote(
                self.poll_id, interaction.user.id, option_index
            )
            if result.get('error'):
                await interaction.response.send_message(
                    f"❌ {result['error']}", ephemeral=True
                )
            elif result.get('changed'):
                await interaction.response.send_message(
                    f"✅ Vote changed to: **{result['option']}**", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"✅ Voted for: **{result['option']}**", ephemeral=True
                )
        return callback


class PollSystem:
    """Manage polls with voting and result analytics."""

    def __init__(self, db):
        self.db = db

    async def create_poll(self, guild_id: int, channel_id: int, created_by: int,
                          question: str, options: List[str], poll_type: str = 'single',
                          anonymous: bool = False, duration_minutes: int = None) -> Dict:
        """
        Create a new poll.

        Args:
            guild_id: Discord guild ID
            channel_id: Channel to post in
            created_by: User who created it
            question: Poll question
            options: List of option strings (2-10)
            poll_type: 'single' or 'multi'
            anonymous: Whether votes are anonymous
            duration_minutes: Auto-close after N minutes (None = manual close)

        Returns:
            Dict with poll_id, or error
        """
        if len(options) < 2:
            return {'error': 'Need at least 2 options'}
        if len(options) > 10:
            return {'error': 'Maximum 10 options'}

        closes_at = None
        if duration_minutes:
            closes_at = datetime.now() + timedelta(minutes=duration_minutes)

        try:
            poll_id = await asyncio.to_thread(
                self._create_poll_sync,
                guild_id, channel_id, created_by, question,
                options, poll_type, anonymous, duration_minutes, closes_at
            )
            return {
                'poll_id': poll_id,
                'question': question,
                'options': options,
                'poll_type': poll_type,
                'anonymous': anonymous,
                'closes_at': closes_at
            }
        except Exception as e:
            logger.error("Error creating poll: %s", e)
            return {'error': str(e)}

    def _create_poll_sync(self, guild_id, channel_id, created_by, question,
                          options, poll_type, anonymous, duration_minutes, closes_at):
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO polls (guild_id, channel_id, created_by, question,
                                      poll_type, options, anonymous, duration_minutes, closes_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (guild_id, channel_id, created_by, question,
                      poll_type, json.dumps(options), anonymous,
                      duration_minutes, closes_at))
                poll_id = cur.fetchone()[0]
                conn.commit()
                return poll_id

    async def set_message_id(self, poll_id: int, message_id: int):
        """Store the Discord message ID for a poll (for editing later)."""
        try:
            await asyncio.to_thread(self._set_message_id_sync, poll_id, message_id)
        except Exception as e:
            logger.error("Error setting poll message_id: %s", e)

    def _set_message_id_sync(self, poll_id, message_id):
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE polls SET message_id = %s WHERE id = %s",
                           (message_id, poll_id))
                conn.commit()

    async def cast_vote(self, poll_id: int, user_id: int, option_index: int) -> Dict:
        """
        Cast or change a vote.

        Returns:
            Dict with 'option' name, 'changed' bool, or 'error'
        """
        try:
            return await asyncio.to_thread(
                self._cast_vote_sync, poll_id, user_id, option_index
            )
        except Exception as e:
            logger.error("Error casting vote: %s", e)
            return {'error': str(e)}

    def _cast_vote_sync(self, poll_id, user_id, option_index):
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check poll exists and is open
                cur.execute("SELECT * FROM polls WHERE id = %s", (poll_id,))
                poll = cur.fetchone()
                if not poll:
                    return {'error': 'Poll not found'}
                if poll['is_closed']:
                    return {'error': 'This poll is closed'}

                options = json.loads(poll['options']) if isinstance(poll['options'], str) else poll['options']
                if option_index < 0 or option_index >= len(options):
                    return {'error': 'Invalid option'}

                option_name = options[option_index]

                # For single-choice: remove existing vote first
                if poll['poll_type'] == 'single':
                    cur.execute("SELECT id FROM poll_votes WHERE poll_id = %s AND user_id = %s",
                               (poll_id, user_id))
                    existing = cur.fetchone()
                    if existing:
                        cur.execute("UPDATE poll_votes SET option_index = %s, voted_at = NOW() WHERE id = %s",
                                   (option_index, existing['id']))
                        conn.commit()
                        return {'option': option_name, 'changed': True}

                # Insert new vote
                try:
                    cur.execute("""
                        INSERT INTO poll_votes (poll_id, user_id, option_index)
                        VALUES (%s, %s, %s)
                    """, (poll_id, user_id, option_index))
                    conn.commit()
                    return {'option': option_name, 'changed': False}
                except Exception:
                    # Duplicate vote for multi-choice (already voted this option)
                    conn.rollback()
                    return {'error': 'Already voted for this option'}

    async def close_poll(self, poll_id: int, user_id: int = None) -> Dict:
        """
        Close a poll. Only creator can close manually.

        Returns:
            Dict with results, or error
        """
        try:
            return await asyncio.to_thread(self._close_poll_sync, poll_id, user_id)
        except Exception as e:
            logger.error("Error closing poll: %s", e)
            return {'error': str(e)}

    def _close_poll_sync(self, poll_id, user_id=None):
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM polls WHERE id = %s", (poll_id,))
                poll = cur.fetchone()
                if not poll:
                    return {'error': 'Poll not found'}
                if poll['is_closed']:
                    return {'error': 'Poll already closed'}
                if user_id and poll['created_by'] != user_id:
                    return {'error': 'Only the poll creator can close it'}

                cur.execute("UPDATE polls SET is_closed = TRUE WHERE id = %s", (poll_id,))
                conn.commit()
                return self._get_results_sync(poll_id, conn)

    async def get_results(self, poll_id: int) -> Dict:
        """Get current poll results."""
        try:
            return await asyncio.to_thread(self._get_results_thread, poll_id)
        except Exception as e:
            logger.error("Error getting poll results: %s", e)
            return {'error': str(e)}

    def _get_results_thread(self, poll_id):
        with self.db.get_connection() as conn:
            return self._get_results_sync(poll_id, conn)

    def _get_results_sync(self, poll_id, conn):
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM polls WHERE id = %s", (poll_id,))
            poll = cur.fetchone()
            if not poll:
                return {'error': 'Poll not found'}

            options = json.loads(poll['options']) if isinstance(poll['options'], str) else poll['options']

            # Count votes per option
            cur.execute("""
                SELECT option_index, COUNT(*) as vote_count
                FROM poll_votes
                WHERE poll_id = %s
                GROUP BY option_index
                ORDER BY option_index
            """, (poll_id,))
            vote_rows = cur.fetchall()
            vote_counts = {r['option_index']: r['vote_count'] for r in vote_rows}

            # Total voters
            cur.execute("""
                SELECT COUNT(DISTINCT user_id) as total_voters
                FROM poll_votes WHERE poll_id = %s
            """, (poll_id,))
            total_voters = cur.fetchone()['total_voters']

            results = []
            total_votes = sum(vote_counts.values())
            for i, option in enumerate(options):
                count = vote_counts.get(i, 0)
                pct = round(count / total_votes * 100, 1) if total_votes > 0 else 0
                results.append({
                    'option': option,
                    'index': i,
                    'votes': count,
                    'percentage': pct
                })

            # Sort by votes descending
            results.sort(key=lambda x: x['votes'], reverse=True)
            winner = results[0] if results else None

            return {
                'poll_id': poll_id,
                'question': poll['question'],
                'is_closed': poll['is_closed'],
                'anonymous': poll['anonymous'],
                'total_voters': total_voters,
                'total_votes': total_votes,
                'results': results,
                'winner': winner,
                'created_by': poll['created_by']
            }

    async def get_due_polls(self) -> List[Dict]:
        """Get polls that should be auto-closed."""
        try:
            return await asyncio.to_thread(self._get_due_polls_sync)
        except Exception as e:
            logger.error("Error getting due polls: %s", e)
            return []

    def _get_due_polls_sync(self):
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, channel_id, message_id
                    FROM polls
                    WHERE closes_at IS NOT NULL
                        AND closes_at <= NOW()
                        AND is_closed = FALSE
                """)
                return cur.fetchall()

    async def get_user_polls(self, guild_id: int, user_id: int = None,
                              limit: int = 5) -> List[Dict]:
        """Get recent polls for a guild."""
        try:
            return await asyncio.to_thread(
                self._get_user_polls_sync, guild_id, user_id, limit
            )
        except Exception as e:
            logger.error("Error getting user polls: %s", e)
            return []

    def _get_user_polls_sync(self, guild_id, user_id, limit):
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if user_id:
                    cur.execute("""
                        SELECT id, question, is_closed, created_at
                        FROM polls
                        WHERE guild_id = %s AND created_by = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (guild_id, user_id, limit))
                else:
                    cur.execute("""
                        SELECT id, question, is_closed, created_at
                        FROM polls
                        WHERE guild_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (guild_id, limit))
                return cur.fetchall()
