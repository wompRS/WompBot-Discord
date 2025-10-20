"""
Yearly Wrapped Feature
End-of-year statistics summary for Discord users
Like Spotify Wrapped but for server activity
"""

import discord
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json


class YearlyWrapped:
    """Generate comprehensive year-end statistics for users"""

    def __init__(self, db):
        self.db = db

    async def generate_wrapped(self, user_id: int, year: Optional[int] = None) -> Optional[Dict]:
        """
        Generate yearly wrapped statistics for a user.

        Args:
            user_id: Discord user ID
            year: Year to generate stats for (defaults to current year)

        Returns:
            Dictionary containing all wrapped statistics, or None if no data
        """
        if year is None:
            year = datetime.now().year

        # Define date range for the year
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)

        # If it's the current year, use today as end date
        if year == datetime.now().year:
            end_date = datetime.now()

        # Get all statistics
        wrapped_data = {
            'year': year,
            'user_id': user_id,
            'message_stats': await self._get_message_stats(user_id, start_date, end_date),
            'social_stats': await self._get_social_stats(user_id, start_date, end_date),
            'claims_stats': await self._get_claims_stats(user_id, start_date, end_date),
            'quotes_stats': await self._get_quotes_stats(user_id, start_date, end_date),
            'personality': await self._get_personality_insights(user_id, start_date, end_date),
            'achievements': await self._get_achievements(user_id, start_date, end_date)
        }

        # Check if user had any activity this year
        if wrapped_data['message_stats']['total_messages'] == 0:
            return None

        return wrapped_data

    async def _get_message_stats(self, user_id: int, start_date: datetime, end_date: datetime) -> Dict:
        """Get message activity statistics"""
        try:
            with self.db.conn.cursor() as cur:
                # Total messages
                cur.execute("""
                    SELECT COUNT(*)
                    FROM messages
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                      AND opted_out = FALSE
                """, (user_id, start_date, end_date))
                total_messages = cur.fetchone()[0] or 0

                # Server rank
                cur.execute("""
                    SELECT COUNT(*) + 1 as rank
                    FROM (
                        SELECT user_id, COUNT(*) as msg_count
                        FROM messages
                        WHERE timestamp BETWEEN %s AND %s
                          AND opted_out = FALSE
                        GROUP BY user_id
                        HAVING COUNT(*) > (
                            SELECT COUNT(*)
                            FROM messages
                            WHERE user_id = %s
                              AND timestamp BETWEEN %s AND %s
                              AND opted_out = FALSE
                        )
                    ) ranked
                """, (start_date, end_date, user_id, start_date, end_date))
                server_rank = cur.fetchone()[0] or 1

                # Most active month
                cur.execute("""
                    SELECT EXTRACT(MONTH FROM timestamp) as month, COUNT(*) as count
                    FROM messages
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                      AND opted_out = FALSE
                    GROUP BY EXTRACT(MONTH FROM timestamp)
                    ORDER BY count DESC
                    LIMIT 1
                """, (user_id, start_date, end_date))
                month_result = cur.fetchone()
                most_active_month = int(month_result[0]) if month_result else None

                # Most active day of week
                cur.execute("""
                    SELECT EXTRACT(DOW FROM timestamp) as dow, COUNT(*) as count
                    FROM messages
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                      AND opted_out = FALSE
                    GROUP BY EXTRACT(DOW FROM timestamp)
                    ORDER BY count DESC
                    LIMIT 1
                """, (user_id, start_date, end_date))
                dow_result = cur.fetchone()
                most_active_dow = int(dow_result[0]) if dow_result else None

                # Most active hour
                cur.execute("""
                    SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(*) as count
                    FROM messages
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                      AND opted_out = FALSE
                    GROUP BY EXTRACT(HOUR FROM timestamp)
                    ORDER BY count DESC
                    LIMIT 1
                """, (user_id, start_date, end_date))
                hour_result = cur.fetchone()
                most_active_hour = int(hour_result[0]) if hour_result else None

                # First and last message dates
                cur.execute("""
                    SELECT MIN(timestamp), MAX(timestamp)
                    FROM messages
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                      AND opted_out = FALSE
                """, (user_id, start_date, end_date))
                first_msg, last_msg = cur.fetchone()

                return {
                    'total_messages': total_messages,
                    'server_rank': server_rank,
                    'most_active_month': most_active_month,
                    'most_active_day_of_week': most_active_dow,
                    'most_active_hour': most_active_hour,
                    'first_message': first_msg,
                    'last_message': last_msg
                }

        except Exception as e:
            print(f"❌ Error getting message stats: {e}")
            return {
                'total_messages': 0,
                'server_rank': 0,
                'most_active_month': None,
                'most_active_day_of_week': None,
                'most_active_hour': None,
                'first_message': None,
                'last_message': None
            }

    async def _get_social_stats(self, user_id: int, start_date: datetime, end_date: datetime) -> Dict:
        """Get social interaction statistics"""
        try:
            with self.db.conn.cursor() as cur:
                # Top conversation partner (who they reply to most)
                cur.execute("""
                    SELECT replied_to_user_id, COUNT(*) as count
                    FROM message_interactions
                    WHERE user_id = %s
                      AND replied_to_user_id IS NOT NULL
                      AND timestamp BETWEEN %s AND %s
                    GROUP BY replied_to_user_id
                    ORDER BY count DESC
                    LIMIT 1
                """, (user_id, start_date, end_date))
                top_partner_result = cur.fetchone()
                top_conversation_partner = top_partner_result[0] if top_partner_result else None
                top_partner_count = top_partner_result[1] if top_partner_result else 0

                # Who replies to them most
                cur.execute("""
                    SELECT user_id, COUNT(*) as count
                    FROM message_interactions
                    WHERE replied_to_user_id = %s
                      AND timestamp BETWEEN %s AND %s
                    GROUP BY user_id
                    ORDER BY count DESC
                    LIMIT 1
                """, (user_id, start_date, end_date))
                top_replier_result = cur.fetchone()
                top_replier = top_replier_result[0] if top_replier_result else None
                top_replier_count = top_replier_result[1] if top_replier_result else 0

                # Total replies sent and received
                cur.execute("""
                    SELECT
                        (SELECT COUNT(*) FROM message_interactions
                         WHERE user_id = %s AND replied_to_user_id IS NOT NULL
                         AND timestamp BETWEEN %s AND %s) as replies_sent,
                        (SELECT COUNT(*) FROM message_interactions
                         WHERE replied_to_user_id = %s
                         AND timestamp BETWEEN %s AND %s) as replies_received
                """, (user_id, start_date, end_date, user_id, start_date, end_date))
                replies_sent, replies_received = cur.fetchone()

                return {
                    'top_conversation_partner': top_conversation_partner,
                    'top_partner_count': top_partner_count,
                    'top_replier': top_replier,
                    'top_replier_count': top_replier_count,
                    'replies_sent': replies_sent or 0,
                    'replies_received': replies_received or 0
                }

        except Exception as e:
            print(f"❌ Error getting social stats: {e}")
            return {
                'top_conversation_partner': None,
                'top_partner_count': 0,
                'top_replier': None,
                'top_replier_count': 0,
                'replies_sent': 0,
                'replies_received': 0
            }

    async def _get_claims_stats(self, user_id: int, start_date: datetime, end_date: datetime) -> Dict:
        """Get claims and hot takes statistics"""
        try:
            with self.db.conn.cursor() as cur:
                # Total claims
                cur.execute("""
                    SELECT COUNT(*)
                    FROM claims
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                """, (user_id, start_date, end_date))
                total_claims = cur.fetchone()[0] or 0

                # Hot takes stats
                cur.execute("""
                    SELECT
                        COUNT(*) as hot_take_count,
                        AVG(ht.controversy_score) as avg_controversy,
                        SUM(CASE WHEN ht.vindication_status = 'won' THEN 1 ELSE 0 END) as vindicated,
                        SUM(CASE WHEN ht.vindication_status = 'lost' THEN 1 ELSE 0 END) as wrong
                    FROM hot_takes ht
                    JOIN claims c ON c.id = ht.claim_id
                    WHERE c.user_id = %s
                      AND c.timestamp BETWEEN %s AND %s
                """, (user_id, start_date, end_date))
                ht_result = cur.fetchone()
                hot_take_count = ht_result[0] or 0
                avg_controversy = float(ht_result[1]) if ht_result[1] else 0.0
                vindicated = ht_result[2] or 0
                wrong = ht_result[3] or 0

                # Controversy rank in server
                cur.execute("""
                    SELECT COUNT(*) + 1 as rank
                    FROM (
                        SELECT c.user_id, AVG(ht.controversy_score) as avg_score
                        FROM hot_takes ht
                        JOIN claims c ON c.id = ht.claim_id
                        WHERE c.timestamp BETWEEN %s AND %s
                        GROUP BY c.user_id
                        HAVING AVG(ht.controversy_score) > (
                            SELECT AVG(ht2.controversy_score)
                            FROM hot_takes ht2
                            JOIN claims c2 ON c2.id = ht2.claim_id
                            WHERE c2.user_id = %s
                              AND c2.timestamp BETWEEN %s AND %s
                        )
                    ) ranked
                """, (start_date, end_date, user_id, start_date, end_date))
                controversy_rank = cur.fetchone()[0] or 1 if hot_take_count > 0 else None

                return {
                    'total_claims': total_claims,
                    'hot_take_count': hot_take_count,
                    'avg_controversy_score': round(avg_controversy, 2),
                    'vindicated': vindicated,
                    'wrong': wrong,
                    'controversy_rank': controversy_rank
                }

        except Exception as e:
            print(f"❌ Error getting claims stats: {e}")
            return {
                'total_claims': 0,
                'hot_take_count': 0,
                'avg_controversy_score': 0.0,
                'vindicated': 0,
                'wrong': 0,
                'controversy_rank': None
            }

    async def _get_quotes_stats(self, user_id: int, start_date: datetime, end_date: datetime) -> Dict:
        """Get quotes statistics"""
        try:
            with self.db.conn.cursor() as cur:
                # Quotes from this user saved by others
                cur.execute("""
                    SELECT COUNT(*)
                    FROM quotes
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                """, (user_id, start_date, end_date))
                quotes_received = cur.fetchone()[0] or 0

                # Quotes this user saved from others
                cur.execute("""
                    SELECT COUNT(*)
                    FROM quotes
                    WHERE added_by_user_id = %s
                      AND created_at BETWEEN %s AND %s
                """, (user_id, start_date, end_date))
                quotes_saved = cur.fetchone()[0] or 0

                # Most quoted person by this user
                cur.execute("""
                    SELECT user_id, COUNT(*) as count
                    FROM quotes
                    WHERE added_by_user_id = %s
                      AND created_at BETWEEN %s AND %s
                    GROUP BY user_id
                    ORDER BY count DESC
                    LIMIT 1
                """, (user_id, start_date, end_date))
                most_quoted_result = cur.fetchone()
                most_quoted_person = most_quoted_result[0] if most_quoted_result else None
                most_quoted_count = most_quoted_result[1] if most_quoted_result else 0

                return {
                    'quotes_received': quotes_received,
                    'quotes_saved': quotes_saved,
                    'most_quoted_person': most_quoted_person,
                    'most_quoted_count': most_quoted_count
                }

        except Exception as e:
            print(f"❌ Error getting quotes stats: {e}")
            return {
                'quotes_received': 0,
                'quotes_saved': 0,
                'most_quoted_person': None,
                'most_quoted_count': 0
            }

    async def _get_personality_insights(self, user_id: int, start_date: datetime, end_date: datetime) -> Dict:
        """Get personality insights"""
        try:
            with self.db.conn.cursor() as cur:
                # Question rate (messages ending with ?)
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN content LIKE '%?' THEN 1 ELSE 0 END) as questions
                    FROM messages
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                      AND opted_out = FALSE
                """, (user_id, start_date, end_date))
                total, questions = cur.fetchone()
                question_rate = round((questions / total * 100), 1) if total > 0 else 0

                # Profanity score (if behavior analysis exists)
                cur.execute("""
                    SELECT profanity_score
                    FROM user_behavior
                    WHERE user_id = %s
                    ORDER BY analyzed_at DESC
                    LIMIT 1
                """, (user_id,))
                profanity_result = cur.fetchone()
                profanity_score = profanity_result[0] if profanity_result else 0

                # Fact checks triggered by this user
                cur.execute("""
                    SELECT COUNT(*)
                    FROM fact_checks
                    WHERE requested_by_user_id = %s
                      AND created_at BETWEEN %s AND %s
                """, (user_id, start_date, end_date))
                fact_checks_requested = cur.fetchone()[0] or 0

                return {
                    'question_rate': question_rate,
                    'profanity_score': profanity_score,
                    'fact_checks_requested': fact_checks_requested
                }

        except Exception as e:
            print(f"❌ Error getting personality insights: {e}")
            return {
                'question_rate': 0,
                'profanity_score': 0,
                'fact_checks_requested': 0
            }

    async def _get_achievements(self, user_id: int, start_date: datetime, end_date: datetime) -> List[str]:
        """Determine which achievements/badges the user earned"""
        achievements = []

        try:
            with self.db.conn.cursor() as cur:
                # Night Owl (most active between 12am-6am)
                cur.execute("""
                    SELECT
                        SUM(CASE WHEN EXTRACT(HOUR FROM timestamp) BETWEEN 0 AND 5 THEN 1 ELSE 0 END) as night,
                        COUNT(*) as total
                    FROM messages
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                      AND opted_out = FALSE
                """, (user_id, start_date, end_date))
                night, total = cur.fetchone()
                if total > 0 and (night / total) > 0.3:
                    achievements.append("🦉 Night Owl")

                # Early Bird (most active between 6am-10am)
                cur.execute("""
                    SELECT
                        SUM(CASE WHEN EXTRACT(HOUR FROM timestamp) BETWEEN 6 AND 9 THEN 1 ELSE 0 END) as morning,
                        COUNT(*) as total
                    FROM messages
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                      AND opted_out = FALSE
                """, (user_id, start_date, end_date))
                morning, total = cur.fetchone()
                if total > 0 and (morning / total) > 0.3:
                    achievements.append("🌅 Early Bird")

                # Debate Champion (5+ hot takes)
                cur.execute("""
                    SELECT COUNT(*)
                    FROM hot_takes ht
                    JOIN claims c ON c.id = ht.claim_id
                    WHERE c.user_id = %s
                      AND c.timestamp BETWEEN %s AND %s
                """, (user_id, start_date, end_date))
                hot_takes = cur.fetchone()[0] or 0
                if hot_takes >= 5:
                    achievements.append("⚔️ Debate Champion")

                # Quote Machine (5+ quotes saved by others)
                cur.execute("""
                    SELECT COUNT(*)
                    FROM quotes
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                """, (user_id, start_date, end_date))
                quotes = cur.fetchone()[0] or 0
                if quotes >= 5:
                    achievements.append("☁️ Quote Machine")

                # Fact Checker (3+ fact checks requested)
                cur.execute("""
                    SELECT COUNT(*)
                    FROM fact_checks
                    WHERE requested_by_user_id = %s
                      AND created_at BETWEEN %s AND %s
                """, (user_id, start_date, end_date))
                fact_checks = cur.fetchone()[0] or 0
                if fact_checks >= 3:
                    achievements.append("⚠️ Fact Checker")

                # Conversationalist (1000+ messages)
                cur.execute("""
                    SELECT COUNT(*)
                    FROM messages
                    WHERE user_id = %s
                      AND timestamp BETWEEN %s AND %s
                      AND opted_out = FALSE
                """, (user_id, start_date, end_date))
                messages = cur.fetchone()[0] or 0
                if messages >= 1000:
                    achievements.append("💬 Conversationalist")

                # Prophecy Master (3+ vindicated hot takes)
                cur.execute("""
                    SELECT COUNT(*)
                    FROM hot_takes ht
                    JOIN claims c ON c.id = ht.claim_id
                    WHERE c.user_id = %s
                      AND ht.vindication_status = 'won'
                      AND c.timestamp BETWEEN %s AND %s
                """, (user_id, start_date, end_date))
                vindicated = cur.fetchone()[0] or 0
                if vindicated >= 3:
                    achievements.append("🔮 Prophecy Master")

        except Exception as e:
            print(f"❌ Error getting achievements: {e}")

        return achievements

    def format_month_name(self, month: int) -> str:
        """Convert month number to name"""
        months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']
        return months[month] if 1 <= month <= 12 else ''

    def format_day_name(self, dow: int) -> str:
        """Convert day of week number to name"""
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        return days[dow] if 0 <= dow <= 6 else ''
