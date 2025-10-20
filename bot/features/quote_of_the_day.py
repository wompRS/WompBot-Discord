"""
Quote of the Day Feature
Highlights the best quotes from various time periods
"""

import discord
from datetime import datetime, timedelta
from typing import Dict, Optional
import random


class QuoteOfTheDay:
    """Select and display featured quotes from different time periods"""

    def __init__(self, db):
        self.db = db

    async def get_quote(self, mode: str = 'daily') -> Optional[Dict]:
        """
        Get a quote based on the specified mode.

        Args:
            mode: 'daily', 'weekly', 'monthly', 'alltime', or 'random'

        Returns:
            Dictionary with quote data, or None if no quotes found
        """
        now = datetime.now()

        if mode == 'daily':
            start_date = now - timedelta(days=1)
            return await self._get_top_quote(start_date, now)
        elif mode == 'weekly':
            start_date = now - timedelta(days=7)
            return await self._get_top_quote(start_date, now)
        elif mode == 'monthly':
            start_date = now - timedelta(days=30)
            return await self._get_top_quote(start_date, now)
        elif mode == 'alltime':
            return await self._get_random_top_quote()
        elif mode == 'random':
            return await self._get_random_quote()
        else:
            return None

    async def _get_top_quote(self, start_date: datetime, end_date: datetime) -> Optional[Dict]:
        """Get the top quote by reaction count in a time period"""
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        q.id,
                        q.user_id,
                        q.username,
                        q.quote_text,
                        q.context,
                        q.timestamp,
                        q.added_by_user_id,
                        q.added_by_username,
                        q.category,
                        q.reaction_count,
                        q.channel_name,
                        q.message_id
                    FROM quotes q
                    WHERE q.timestamp BETWEEN %s AND %s
                    ORDER BY q.reaction_count DESC, q.timestamp DESC
                    LIMIT 1
                """, (start_date, end_date))

                result = cur.fetchone()
                if not result:
                    return None

                return {
                    'id': result[0],
                    'user_id': result[1],
                    'username': result[2],
                    'quote_text': result[3],
                    'context': result[4],
                    'timestamp': result[5],
                    'added_by_user_id': result[6],
                    'added_by_username': result[7],
                    'category': result[8],
                    'reaction_count': result[9],
                    'channel_name': result[10],
                    'message_id': result[11]
                }

        except Exception as e:
            print(f"❌ Error getting top quote: {e}")
            return None

    async def _get_random_top_quote(self) -> Optional[Dict]:
        """Get a random quote from the top 20 most reacted quotes of all time"""
        try:
            with self.db.conn.cursor() as cur:
                # Get top 20 quotes by reaction count
                cur.execute("""
                    SELECT
                        q.id,
                        q.user_id,
                        q.username,
                        q.quote_text,
                        q.context,
                        q.timestamp,
                        q.added_by_user_id,
                        q.added_by_username,
                        q.category,
                        q.reaction_count,
                        q.channel_name,
                        q.message_id
                    FROM quotes q
                    ORDER BY q.reaction_count DESC, q.timestamp DESC
                    LIMIT 20
                """)

                results = cur.fetchall()
                if not results:
                    return None

                # Pick a random one from the top 20
                result = random.choice(results)

                return {
                    'id': result[0],
                    'user_id': result[1],
                    'username': result[2],
                    'quote_text': result[3],
                    'context': result[4],
                    'timestamp': result[5],
                    'added_by_user_id': result[6],
                    'added_by_username': result[7],
                    'category': result[8],
                    'reaction_count': result[9],
                    'channel_name': result[10],
                    'message_id': result[11]
                }

        except Exception as e:
            print(f"❌ Error getting random top quote: {e}")
            return None

    async def _get_random_quote(self) -> Optional[Dict]:
        """Get a completely random quote from all quotes"""
        try:
            with self.db.conn.cursor() as cur:
                # Get total count
                cur.execute("SELECT COUNT(*) FROM quotes")
                total = cur.fetchone()[0]

                if total == 0:
                    return None

                # Get random offset
                offset = random.randint(0, total - 1)

                cur.execute("""
                    SELECT
                        q.id,
                        q.user_id,
                        q.username,
                        q.quote_text,
                        q.context,
                        q.timestamp,
                        q.added_by_user_id,
                        q.added_by_username,
                        q.category,
                        q.reaction_count,
                        q.channel_name,
                        q.message_id
                    FROM quotes q
                    ORDER BY q.id
                    LIMIT 1 OFFSET %s
                """, (offset,))

                result = cur.fetchone()
                if not result:
                    return None

                return {
                    'id': result[0],
                    'user_id': result[1],
                    'username': result[2],
                    'quote_text': result[3],
                    'context': result[4],
                    'timestamp': result[5],
                    'added_by_user_id': result[6],
                    'added_by_username': result[7],
                    'category': result[8],
                    'reaction_count': result[9],
                    'channel_name': result[10],
                    'message_id': result[11]
                }

        except Exception as e:
            print(f"❌ Error getting random quote: {e}")
            return None

    async def get_quote_stats(self) -> Dict:
        """Get overall statistics about quotes in the database"""
        try:
            with self.db.conn.cursor() as cur:
                # Total quotes
                cur.execute("SELECT COUNT(*) FROM quotes")
                total_quotes = cur.fetchone()[0] or 0

                # Most quoted user
                cur.execute("""
                    SELECT username, COUNT(*) as count
                    FROM quotes
                    GROUP BY username
                    ORDER BY count DESC
                    LIMIT 1
                """)
                most_quoted_result = cur.fetchone()
                most_quoted_user = most_quoted_result[0] if most_quoted_result else None
                most_quoted_count = most_quoted_result[1] if most_quoted_result else 0

                # Most active quote saver
                cur.execute("""
                    SELECT added_by_username, COUNT(*) as count
                    FROM quotes
                    GROUP BY added_by_username
                    ORDER BY count DESC
                    LIMIT 1
                """)
                most_active_result = cur.fetchone()
                most_active_saver = most_active_result[0] if most_active_result else None
                most_active_count = most_active_result[1] if most_active_result else 0

                # Total reaction count
                cur.execute("SELECT SUM(reaction_count) FROM quotes")
                total_reactions = cur.fetchone()[0] or 0

                return {
                    'total_quotes': total_quotes,
                    'most_quoted_user': most_quoted_user,
                    'most_quoted_count': most_quoted_count,
                    'most_active_saver': most_active_saver,
                    'most_active_count': most_active_count,
                    'total_reactions': total_reactions
                }

        except Exception as e:
            print(f"❌ Error getting quote stats: {e}")
            return {
                'total_quotes': 0,
                'most_quoted_user': None,
                'most_quoted_count': 0,
                'most_active_saver': None,
                'most_active_count': 0,
                'total_reactions': 0
            }

    def get_mode_title(self, mode: str) -> str:
        """Get the display title for a mode"""
        titles = {
            'daily': '📅 Quote of the Day',
            'weekly': '📆 Quote of the Week',
            'monthly': '📊 Quote of the Month',
            'alltime': '⭐ All-Time Great Quote',
            'random': '🎲 Random Quote'
        }
        return titles.get(mode, '💬 Quote')

    def get_mode_description(self, mode: str) -> str:
        """Get the description for a mode"""
        descriptions = {
            'daily': 'Top quote from the last 24 hours',
            'weekly': 'Most popular quote from the last 7 days',
            'monthly': 'Best quote from the last 30 days',
            'alltime': 'A legendary quote from the archives',
            'random': 'A random gem from the collection'
        }
        return descriptions.get(mode, 'A featured quote')
