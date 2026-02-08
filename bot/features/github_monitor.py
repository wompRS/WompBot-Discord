"""
GitHub Repository Monitoring
Track releases, issues, and PRs from GitHub repos.
Admin only. 5-minute polling via GitHub REST API.
Optional GITHUB_TOKEN env var for higher rate limits.
"""

import os
import asyncio
import hashlib
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubMonitor:
    """Monitor GitHub repositories for new releases, issues, and PRs."""

    def __init__(self, db, cache=None):
        self.db = db
        self.cache = cache
        self.token = os.getenv('GITHUB_TOKEN')
        self._session = None

    def _get_headers(self) -> Dict:
        """Get request headers with optional auth."""
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'WompBot-Discord'
        }
        if self.token:
            headers['Authorization'] = f'token {self.token}'
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._get_headers())
        return self._session

    async def add_watch(self, guild_id: int, channel_id: int,
                        repo: str, watch_type: str,
                        added_by: int) -> Dict:
        """
        Add a GitHub repo to watch.

        Args:
            guild_id: Discord guild ID
            channel_id: Channel to post updates in
            repo: "owner/repo" format
            watch_type: 'releases', 'issues', 'prs', or 'all'
            added_by: Admin user ID

        Returns:
            Dict with watch info or error
        """
        # Validate repo format
        parts = repo.strip().split('/')
        if len(parts) != 2:
            return {'error': 'Repo must be in "owner/repo" format (e.g. "discord/discord-api-docs")'}

        repo_full = f"{parts[0]}/{parts[1]}"

        # Validate watch_type
        valid_types = ['releases', 'issues', 'prs', 'all']
        if watch_type not in valid_types:
            return {'error': f'Watch type must be one of: {", ".join(valid_types)}'}

        # Verify repo exists
        try:
            session = await self._get_session()
            async with session.get(f"{GITHUB_API}/repos/{repo_full}") as resp:
                if resp.status == 404:
                    return {'error': f'Repository "{repo_full}" not found (or is private without token)'}
                if resp.status == 403:
                    return {'error': 'GitHub API rate limit exceeded. Set GITHUB_TOKEN env var for higher limits.'}
                if resp.status != 200:
                    return {'error': f'GitHub API error: {resp.status}'}

                repo_data = await resp.json()
                repo_name = repo_data.get('full_name', repo_full)
        except aiohttp.ClientError as e:
            return {'error': f'Failed to connect to GitHub: {str(e)}'}

        # Get latest event ID to avoid posting old items
        last_event_id = await self._get_latest_event_id(repo_full, watch_type)

        # Save to database
        try:
            result = await asyncio.to_thread(
                self._add_watch_sync, guild_id, channel_id,
                repo_name, watch_type, added_by, last_event_id
            )
            return result
        except Exception as e:
            logger.error("Error adding GitHub watch: %s", e)
            return {'error': str(e)}

    async def _get_latest_event_id(self, repo: str, watch_type: str) -> Optional[str]:
        """Get the ID of the most recent event to skip old items."""
        try:
            session = await self._get_session()

            if watch_type in ('releases', 'all'):
                async with session.get(f"{GITHUB_API}/repos/{repo}/releases?per_page=1") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            return str(data[0].get('id', ''))

            if watch_type in ('issues', 'all'):
                async with session.get(f"{GITHUB_API}/repos/{repo}/issues?per_page=1&state=all&sort=created") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            return str(data[0].get('id', ''))

            if watch_type in ('prs', 'all'):
                async with session.get(f"{GITHUB_API}/repos/{repo}/pulls?per_page=1&state=all&sort=created") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            return str(data[0].get('id', ''))

        except Exception as e:
            logger.warning("Could not get latest event ID for %s: %s", repo, e)

        return None

    def _add_watch_sync(self, guild_id: int, channel_id: int,
                        repo: str, watch_type: str,
                        added_by: int, last_event_id: str) -> Dict:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                # Check for duplicate
                cur.execute("""
                    SELECT id, is_active FROM github_watches
                    WHERE guild_id = %s AND repo_full_name = %s AND watch_type = %s
                """, (guild_id, repo, watch_type))
                existing = cur.fetchone()

                if existing:
                    if existing[1]:  # is_active
                        return {'error': f'Already watching {repo} for {watch_type}!'}
                    else:
                        cur.execute("""
                            UPDATE github_watches SET is_active = TRUE, channel_id = %s,
                                last_event_id = %s, last_checked = NOW()
                            WHERE id = %s
                        """, (channel_id, last_event_id, existing[0]))
                        conn.commit()
                        return {
                            'watch_id': existing[0],
                            'repo': repo,
                            'watch_type': watch_type,
                            'reactivated': True
                        }

                cur.execute("""
                    INSERT INTO github_watches (guild_id, channel_id, repo_full_name,
                                                 watch_type, added_by, last_event_id, last_checked)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id
                """, (guild_id, channel_id, repo, watch_type,
                      added_by, last_event_id))
                watch_id = cur.fetchone()[0]
                conn.commit()

                return {
                    'watch_id': watch_id,
                    'repo': repo,
                    'watch_type': watch_type
                }

    async def remove_watch(self, guild_id: int, watch_id: int) -> Dict:
        """Remove a GitHub watch."""
        try:
            return await asyncio.to_thread(
                self._remove_watch_sync, guild_id, watch_id
            )
        except Exception as e:
            logger.error("Error removing GitHub watch: %s", e)
            return {'error': str(e)}

    def _remove_watch_sync(self, guild_id: int, watch_id: int) -> Dict:
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE github_watches SET is_active = FALSE
                    WHERE id = %s AND guild_id = %s AND is_active = TRUE
                    RETURNING repo_full_name, watch_type
                """, (watch_id, guild_id))
                row = cur.fetchone()
                conn.commit()

                if not row:
                    return {'error': f'Watch #{watch_id} not found or already removed.'}

                return {
                    'removed': True,
                    'watch_id': watch_id,
                    'repo': row[0],
                    'watch_type': row[1]
                }

    async def list_watches(self, guild_id: int) -> List[Dict]:
        """List active watches for a guild."""
        try:
            return await asyncio.to_thread(self._list_watches_sync, guild_id)
        except Exception as e:
            logger.error("Error listing GitHub watches: %s", e)
            return []

    def _list_watches_sync(self, guild_id: int) -> List[Dict]:
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, channel_id, repo_full_name, watch_type, last_checked, created_at
                    FROM github_watches
                    WHERE guild_id = %s AND is_active = TRUE
                    ORDER BY created_at DESC
                """, (guild_id,))
                return cur.fetchall()

    async def check_repos(self) -> List[Dict]:
        """
        Check all active watches for new events.

        Returns:
            List of dicts with channel_id and events to post
        """
        try:
            watches = await asyncio.to_thread(self._get_all_active_watches)
        except Exception as e:
            logger.error("Error fetching active watches: %s", e)
            return []

        if not watches:
            return []

        results = []
        session = await self._get_session()

        for watch in watches:
            try:
                # Cache check
                cache_key = f"gh:{hashlib.sha256(f'{watch["repo_full_name"]}:{watch["watch_type"]}'.encode()).hexdigest()[:16]}"
                if self.cache and self.cache.get(cache_key):
                    continue

                new_events = []
                last_event_id = watch.get('last_event_id', '')

                if watch['watch_type'] in ('releases', 'all'):
                    events = await self._check_releases(session, watch['repo_full_name'], last_event_id)
                    new_events.extend(events)

                if watch['watch_type'] in ('issues', 'all'):
                    events = await self._check_issues(session, watch['repo_full_name'], last_event_id)
                    new_events.extend(events)

                if watch['watch_type'] in ('prs', 'all'):
                    events = await self._check_prs(session, watch['repo_full_name'], last_event_id)
                    new_events.extend(events)

                # Cache for 5 minutes
                if self.cache:
                    self.cache.set(cache_key, 'checked', ttl=300)

                if new_events:
                    # Limit to 3 events per check
                    new_events = new_events[:3]

                    # Update last_event_id with the most recent
                    latest_id = str(new_events[0].get('id', ''))
                    if latest_id:
                        await asyncio.to_thread(
                            self._update_last_event, watch['id'], latest_id
                        )

                    results.append({
                        'watch_id': watch['id'],
                        'repo': watch['repo_full_name'],
                        'channel_id': watch['channel_id'],
                        'events': new_events
                    })

            except Exception as e:
                logger.error("Error checking repo %s: %s", watch.get('repo_full_name', '?'), e)
                continue

        return results

    async def _check_releases(self, session: aiohttp.ClientSession,
                               repo: str, last_id: str) -> List[Dict]:
        """Check for new releases."""
        try:
            async with session.get(f"{GITHUB_API}/repos/{repo}/releases?per_page=5") as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

                new_events = []
                for release in data:
                    if str(release.get('id', '')) == last_id:
                        break
                    new_events.append({
                        'type': 'release',
                        'id': release['id'],
                        'title': release.get('name') or release.get('tag_name', 'Unknown'),
                        'tag': release.get('tag_name', ''),
                        'url': release.get('html_url', ''),
                        'body': (release.get('body', '') or '')[:300],
                        'prerelease': release.get('prerelease', False),
                        'author': release.get('author', {}).get('login', 'unknown')
                    })
                return new_events

        except Exception as e:
            logger.error("Error checking releases for %s: %s", repo, e)
            return []

    async def _check_issues(self, session: aiohttp.ClientSession,
                             repo: str, last_id: str) -> List[Dict]:
        """Check for new issues."""
        try:
            async with session.get(
                f"{GITHUB_API}/repos/{repo}/issues?per_page=5&state=all&sort=created&direction=desc"
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

                new_events = []
                for issue in data:
                    # Skip PRs (GitHub API returns PRs in issues endpoint)
                    if issue.get('pull_request'):
                        continue
                    if str(issue.get('id', '')) == last_id:
                        break
                    new_events.append({
                        'type': 'issue',
                        'id': issue['id'],
                        'number': issue.get('number', 0),
                        'title': issue.get('title', 'No title'),
                        'url': issue.get('html_url', ''),
                        'state': issue.get('state', 'open'),
                        'author': issue.get('user', {}).get('login', 'unknown'),
                        'labels': [l['name'] for l in issue.get('labels', [])][:5]
                    })
                return new_events

        except Exception as e:
            logger.error("Error checking issues for %s: %s", repo, e)
            return []

    async def _check_prs(self, session: aiohttp.ClientSession,
                          repo: str, last_id: str) -> List[Dict]:
        """Check for new pull requests."""
        try:
            async with session.get(
                f"{GITHUB_API}/repos/{repo}/pulls?per_page=5&state=all&sort=created&direction=desc"
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()

                new_events = []
                for pr in data:
                    if str(pr.get('id', '')) == last_id:
                        break
                    new_events.append({
                        'type': 'pr',
                        'id': pr['id'],
                        'number': pr.get('number', 0),
                        'title': pr.get('title', 'No title'),
                        'url': pr.get('html_url', ''),
                        'state': pr.get('state', 'open'),
                        'merged': pr.get('merged', False),
                        'author': pr.get('user', {}).get('login', 'unknown'),
                        'draft': pr.get('draft', False)
                    })
                return new_events

        except Exception as e:
            logger.error("Error checking PRs for %s: %s", repo, e)
            return []

    def _get_all_active_watches(self) -> List[Dict]:
        with self.db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, guild_id, channel_id, repo_full_name, watch_type, last_event_id
                    FROM github_watches
                    WHERE is_active = TRUE
                    ORDER BY last_checked ASC NULLS FIRST
                """)
                return cur.fetchall()

    def _update_last_event(self, watch_id: int, last_event_id: str):
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE github_watches SET last_event_id = %s, last_checked = NOW()
                    WHERE id = %s
                """, (last_event_id, watch_id))
                conn.commit()

    def format_event_embed(self, event: Dict, repo: str) -> Dict:
        """Format an event for Discord embed data."""
        if event['type'] == 'release':
            return {
                'title': f"🏷️ New Release: {event['title']}",
                'description': event.get('body', ''),
                'url': event['url'],
                'color': 0x2ea44f,  # GitHub green
                'footer': f"{repo} • {event['tag']} • by {event['author']}"
            }
        elif event['type'] == 'issue':
            state_emoji = "🟢" if event['state'] == 'open' else "🔴"
            labels = " ".join(f"`{l}`" for l in event.get('labels', []))
            return {
                'title': f"{state_emoji} Issue #{event['number']}: {event['title']}",
                'description': labels if labels else None,
                'url': event['url'],
                'color': 0xd73a49 if event['state'] == 'open' else 0x6a737d,
                'footer': f"{repo} • by {event['author']}"
            }
        elif event['type'] == 'pr':
            if event.get('merged'):
                emoji = "🟣"
                color = 0x6f42c1
            elif event['state'] == 'open':
                emoji = "🟢"
                color = 0x2ea44f
            else:
                emoji = "🔴"
                color = 0xd73a49
            draft = " [Draft]" if event.get('draft') else ""
            return {
                'title': f"{emoji} PR #{event['number']}: {event['title']}{draft}",
                'description': None,
                'url': event['url'],
                'color': color,
                'footer': f"{repo} • by {event['author']}"
            }

        return {
            'title': event.get('title', 'Unknown event'),
            'description': None,
            'url': event.get('url', ''),
            'color': 0x24292e,
            'footer': repo
        }
