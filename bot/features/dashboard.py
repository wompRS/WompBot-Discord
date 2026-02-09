"""
Server Health Dashboard
Generates server-wide analytics: activity trends, top users, topics,
engagement metrics, and claim/debate activity using Plotly charts.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


class ServerDashboard:
    """Generates server-wide health and activity metrics."""

    def __init__(self, db, chat_stats):
        self.db = db
        self.chat_stats = chat_stats

    async def generate_dashboard(self, guild_id: int, days: int = 7) -> Optional[Dict]:
        """
        Generate comprehensive server dashboard data.

        Args:
            guild_id: Discord guild/server ID
            days: Number of days to analyze

        Returns:
            Dict with all dashboard data, or None if no data
        """
        start_date = datetime.now() - timedelta(days=days)
        end_date = datetime.now()

        # Check cache first
        cache_scope = f"server:{guild_id}"
        cached = self.chat_stats.get_cached_stats('dashboard', cache_scope, start_date, end_date)
        if cached:
            return cached

        # Fetch messages for analysis (filtered at DB layer)
        guild_messages = self.chat_stats.get_messages_for_analysis(
            None, start_date, end_date, exclude_opted_out=True, guild_id=guild_id
        )

        if not guild_messages:
            return None

        result = {
            'guild_id': guild_id,
            'days': days,
            'total_messages': len(guild_messages),
        }

        # 1. Activity trend (messages per day)
        result['activity_trend'] = self._compute_activity_trend(guild_messages, start_date, days)

        # 2. Top users by message count
        result['top_users'] = self._compute_top_users(guild_id, days)

        # 3. Topic trends
        topics = self.chat_stats.extract_topics_tfidf(guild_messages, top_n=10)
        result['topics'] = {t['keyword']: t['count'] for t in topics} if topics else {}

        # 4. Primetime (hourly activity)
        primetime = self.chat_stats.calculate_primetime(guild_messages)
        result['primetime'] = primetime

        # 5. Engagement metrics
        engagement = self.chat_stats.calculate_engagement(guild_messages)
        result['engagement'] = engagement

        # 6. Claim and debate activity
        result['claim_debate_stats'] = self._get_claim_debate_stats(guild_id, start_date, end_date)

        # Cache for 2 hours
        try:
            self.chat_stats.cache_stats('dashboard', cache_scope, start_date, end_date, result, cache_hours=2)
        except Exception as e:
            logger.warning("Failed to cache dashboard: %s", e)

        return result

    def _compute_activity_trend(self, messages: List[dict], start_date: datetime, days: int) -> Dict:
        """Compute daily message counts over the period."""
        from collections import Counter

        day_counts = Counter()
        for msg in messages:
            ts = msg.get('timestamp')
            if ts:
                day_key = ts.strftime('%m/%d')
                day_counts[day_key] += 1

        # Build ordered list for the full date range
        labels = []
        values = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            key = d.strftime('%m/%d')
            labels.append(key)
            values.append(day_counts.get(key, 0))

        return {'labels': labels, 'values': values}

    def _compute_top_users(self, guild_id: int, days: int, limit: int = 10) -> Dict[str, int]:
        """Get top users by message count."""
        try:
            stats = self.db.get_message_stats(days=days, limit=limit, guild_id=guild_id)
            return {s['username']: s['message_count'] for s in stats}
        except Exception as e:
            logger.warning("Failed to get top users: %s", e)
            return {}

    def _get_claim_debate_stats(self, guild_id: int, start_date: datetime,
                                 end_date: datetime) -> Dict:
        """Get claim and debate counts for the period."""
        stats = {'claims': 0, 'hot_takes': 0, 'debates': 0, 'fact_checks': 0}
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Claims count
                    cur.execute("""
                        SELECT COUNT(*) FROM claims
                        WHERE timestamp BETWEEN %s AND %s
                    """, (start_date, end_date))
                    row = cur.fetchone()
                    stats['claims'] = row[0] if row else 0

                    # Hot takes
                    cur.execute("""
                        SELECT COUNT(*) FROM hot_takes ht
                        JOIN claims c ON ht.claim_id = c.id
                        WHERE c.timestamp BETWEEN %s AND %s
                    """, (start_date, end_date))
                    row = cur.fetchone()
                    stats['hot_takes'] = row[0] if row else 0

                    # Debates
                    cur.execute("""
                        SELECT COUNT(*) FROM debates
                        WHERE guild_id = %s AND started_at BETWEEN %s AND %s
                    """, (guild_id, start_date, end_date))
                    row = cur.fetchone()
                    stats['debates'] = row[0] if row else 0

                    # Fact checks
                    cur.execute("""
                        SELECT COUNT(*) FROM fact_checks
                        WHERE created_at BETWEEN %s AND %s
                    """, (start_date, end_date))
                    row = cur.fetchone()
                    stats['fact_checks'] = row[0] if row else 0

        except Exception as e:
            logger.warning("Failed to get claim/debate stats: %s", e)

        return stats
