"""
RSS Feed Monitoring
Monitor RSS feeds and post new items to designated channels.
Admin only. 5-minute polling interval.
"""

import asyncio
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)


class RSSMonitor:
    """Monitor RSS feeds and post new entries."""

    def __init__(self, db, cache=None):
        self.db = db
        self.cache = cache

    async def add_feed(self, guild_id: int, channel_id: int,
                       feed_url: str, added_by: int) -> Dict:
        """
        Add a new RSS feed to monitor.

        Args:
            guild_id: Discord guild ID
            channel_id: Channel to post updates in
            feed_url: RSS feed URL
            added_by: Admin user ID

        Returns:
            Dict with feed info or error
        """
        # Validate URL format
        if not feed_url.startswith(('http://', 'https://')):
            return {'error': 'Invalid URL. Must start with http:// or https://'}

        # Try to fetch the feed to validate it
        try:
            import feedparser
            feed = await asyncio.to_thread(feedparser.parse, feed_url)

            if feed.bozo and not feed.entries:
                return {'error': f'Could not parse RSS feed: {feed.bozo_exception}'}

            feed_title = feed.feed.get('title', 'Unknown Feed')

            # Get the latest entry ID to avoid posting old items
            last_entry_id = None
            if feed.entries:
                entry = feed.entries[0]
                last_entry_id = entry.get('id') or entry.get('link') or entry.get('title', '')

        except Exception as e:
            logger.error("Error fetching RSS feed: %s", e)
            return {'error': f'Failed to fetch feed: {str(e)}'}

        # Save to database
        try:
            result = await asyncio.to_thread(
                self._add_feed_sync, guild_id, channel_id,
                feed_url, feed_title, added_by, last_entry_id
            )
            return result
        except Exception as e:
            logger.error("Error adding RSS feed: %s", e)
            return {'error': str(e)}

    def _add_feed_sync(self, guild_id: int, channel_id: int,
                       feed_url: str, feed_title: str,
                       added_by: int, last_entry_id: str) -> Dict:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                # Check for duplicate
                cur.execute("""
                    SELECT id, is_active FROM rss_feeds
                    WHERE guild_id = %s AND feed_url = %s
                """, (guild_id, feed_url))
                existing = cur.fetchone()

                if existing:
                    if existing[1]:  # is_active
                        return {'error': 'This feed is already being monitored!'}
                    else:
                        # Reactivate
                        cur.execute("""
                            UPDATE rss_feeds SET is_active = TRUE, channel_id = %s,
                                last_entry_id = %s, last_checked = NOW()
                            WHERE id = %s
                        """, (channel_id, last_entry_id, existing[0]))
                        conn.commit()
                        return {
                            'feed_id': existing[0],
                            'title': feed_title,
                            'url': feed_url,
                            'reactivated': True
                        }

                cur.execute("""
                    INSERT INTO rss_feeds (guild_id, channel_id, feed_url, feed_title,
                                           added_by, last_entry_id, last_checked)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id
                """, (guild_id, channel_id, feed_url, feed_title,
                      added_by, last_entry_id))
                feed_id = cur.fetchone()[0]
                conn.commit()

                return {
                    'feed_id': feed_id,
                    'title': feed_title,
                    'url': feed_url
                }

    async def remove_feed(self, guild_id: int, feed_id: int) -> Dict:
        """Remove (deactivate) an RSS feed."""
        try:
            return await asyncio.to_thread(
                self._remove_feed_sync, guild_id, feed_id
            )
        except Exception as e:
            logger.error("Error removing RSS feed: %s", e)
            return {'error': str(e)}

    def _remove_feed_sync(self, guild_id: int, feed_id: int) -> Dict:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE rss_feeds SET is_active = FALSE
                    WHERE id = %s AND guild_id = %s AND is_active = TRUE
                    RETURNING feed_title, feed_url
                """, (feed_id, guild_id))
                row = cur.fetchone()
                conn.commit()

                if not row:
                    return {'error': f'Feed #{feed_id} not found or already removed.'}

                return {
                    'removed': True,
                    'feed_id': feed_id,
                    'title': row[0],
                    'url': row[1]
                }

    async def list_feeds(self, guild_id: int) -> List[Dict]:
        """List active feeds for a guild."""
        try:
            return await asyncio.to_thread(self._list_feeds_sync, guild_id)
        except Exception as e:
            logger.error("Error listing RSS feeds: %s", e)
            return []

    def _list_feeds_sync(self, guild_id: int) -> List[Dict]:
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, channel_id, feed_url, feed_title, last_checked, created_at
                    FROM rss_feeds
                    WHERE guild_id = %s AND is_active = TRUE
                    ORDER BY created_at DESC
                """, (guild_id,))
                return cur.fetchall()

    async def check_feeds(self) -> List[Dict]:
        """
        Check all active feeds for new entries.

        Returns:
            List of dicts with channel_id, entries to post
        """
        try:
            feeds = await asyncio.to_thread(self._get_all_active_feeds)
        except Exception as e:
            logger.error("Error fetching active feeds: %s", e)
            return []

        if not feeds:
            return []

        import feedparser
        results = []

        for feed_row in feeds:
            try:
                # Check cache first
                cache_key = f"rss:{hashlib.sha256(feed_row['feed_url'].encode()).hexdigest()[:16]}"
                cached = None
                if self.cache:
                    cached = self.cache.get(cache_key)

                if not cached:
                    feed = await asyncio.to_thread(feedparser.parse, feed_row['feed_url'])

                    if feed.bozo and not feed.entries:
                        continue

                    # Cache for 5 minutes
                    if self.cache:
                        self.cache.set(cache_key, 'checked', ttl=300)
                else:
                    continue  # Skip if recently checked

                if not feed.entries:
                    continue

                # Find new entries since last check
                last_entry_id = feed_row.get('last_entry_id', '')
                new_entries = []

                for entry in feed.entries:
                    entry_id = entry.get('id') or entry.get('link') or entry.get('title', '')
                    if entry_id == last_entry_id:
                        break  # We've reached entries we've already seen
                    new_entries.append(entry)

                if new_entries:
                    # Limit to 3 new entries per check to avoid spam
                    new_entries = new_entries[:3]

                    # Update last_entry_id
                    latest_id = new_entries[0].get('id') or new_entries[0].get('link') or new_entries[0].get('title', '')
                    await asyncio.to_thread(
                        self._update_last_entry, feed_row['id'], latest_id
                    )

                    results.append({
                        'feed_id': feed_row['id'],
                        'feed_title': feed_row['feed_title'],
                        'channel_id': feed_row['channel_id'],
                        'entries': [self._format_entry(e) for e in new_entries]
                    })

            except Exception as e:
                logger.error("Error checking feed %s: %s", feed_row.get('feed_url', '?'), e)
                continue

        return results

    def _get_all_active_feeds(self) -> List[Dict]:
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, guild_id, channel_id, feed_url, feed_title, last_entry_id
                    FROM rss_feeds
                    WHERE is_active = TRUE
                    ORDER BY last_checked ASC NULLS FIRST
                """)
                return cur.fetchall()

    def _update_last_entry(self, feed_id: int, last_entry_id: str):
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE rss_feeds SET last_entry_id = %s, last_checked = NOW()
                    WHERE id = %s
                """, (last_entry_id, feed_id))
                conn.commit()

    def _format_entry(self, entry) -> Dict:
        """Format an RSS entry for Discord display."""
        title = entry.get('title', 'No title')
        link = entry.get('link', '')
        summary = entry.get('summary', entry.get('description', ''))

        # Clean HTML from summary
        import re
        summary = re.sub(r'<[^>]+>', '', summary)
        summary = summary.strip()

        # Truncate summary
        if len(summary) > 200:
            summary = summary[:197] + '...'

        published = entry.get('published', entry.get('updated', ''))

        return {
            'title': title,
            'link': link,
            'summary': summary,
            'published': published
        }
