import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
import os
import time
from difflib import SequenceMatcher
from contextlib import contextmanager
import logging

# Get logger for this module
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool = None
        self.connect()
        self.current_guild_id = None  # Track current guild context
        self.bot_user_id = None  # Store bot's user ID to exclude from rankings

    def set_bot_user_id(self, user_id: int):
        """Set the bot's user ID to exclude from rankings (call after bot is ready)"""
        self.bot_user_id = user_id
        logger.info(f"🤖 Bot user ID set for ranking exclusion: {user_id}")

    def connect(self):
        """Create PostgreSQL connection pool with retry logic"""
        max_retries = 5
        retry_delay = 5

        # Get pool size from environment or use sensible defaults
        min_connections = int(os.getenv('DB_POOL_MIN', '2'))
        max_connections = int(os.getenv('DB_POOL_MAX', '10'))

        for attempt in range(max_retries):
            try:
                self.pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=min_connections,
                    maxconn=max_connections,
                    host=os.getenv('DB_HOST', 'postgres'),
                    port=os.getenv('DB_PORT', '5432'),
                    database=os.getenv('DB_NAME', 'discord_bot'),
                    user=os.getenv('DB_USER', 'botuser'),
                    password=os.getenv('DB_PASSWORD'),
                    connect_timeout=10
                )
                logger.info(f"✅ Database connection pool created ({min_connections}-{max_connections} connections)")
                return
            except Exception as e:
                logger.warning(f"⚠️  Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error("✗ Failed to connect to database after all retries")
                    raise

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool (context manager for automatic return)"""
        conn = self.pool.getconn()
        conn.autocommit = True
        try:
            yield conn
        finally:
            self.pool.putconn(conn)
    
    def get_job_last_run(self, job_name: str):
        """Return the last recorded run time for a scheduled job."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT last_run
                        FROM job_last_run
                        WHERE job_name = %s
                    """, (job_name,))
                    result = cur.fetchone()
                    return result[0] if result else None
        except Exception as e:
            print(f"⚠️ Error fetching last run for {job_name}: {e}")
            return None

    def update_job_last_run(self, job_name: str, run_time: datetime | None = None):
        """Persist the completion timestamp for a scheduled job."""
        run_time = run_time or datetime.now(timezone.utc)
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO job_last_run (job_name, last_run)
                        VALUES (%s, %s)
                        ON CONFLICT (job_name) DO UPDATE SET
                            last_run = EXCLUDED.last_run
                    """, (job_name, run_time))
        except Exception as e:
            print(f"⚠️ Error updating last run for {job_name}: {e}")

    def should_run_job(self, job_name: str, interval: timedelta):
        """
        Determine whether a scheduled job should execute based on the persisted last run time.

        Returns:
            (should_run: bool, last_run: datetime | None)
        """
        if not isinstance(interval, timedelta):
            raise ValueError("interval must be a datetime.timedelta instance")

        last_run = self.get_job_last_run(job_name)
        if not last_run:
            return True, None

        now = datetime.now(timezone.utc)
        elapsed = now - last_run
        if elapsed >= interval:
            return True, last_run

        return False, last_run
    
    def store_message(self, message, opted_out=False, content_override=None):
        """Store a Discord message while respecting privacy settings.

        Args:
            message: Discord message object
            opted_out: Whether user has opted out of data storage
            content_override: Optional content to store instead of message.content (for edited messages)
        """
        try:
            profile_username = str(message.author) if not opted_out else "[redacted]"
            timestamp = message.created_at
            guild_id = message.guild.id if message.guild else None
            content = content_override if content_override is not None else message.content

            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    stored_id = None

                    if not opted_out:
                        cur.execute("""
                            INSERT INTO messages (message_id, user_id, username, channel_id, channel_name, content, timestamp, opted_out, guild_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, %s)
                            ON CONFLICT (message_id) DO UPDATE SET content = EXCLUDED.content
                            RETURNING message_id
                        """, (
                            message.id,
                            message.author.id,
                            profile_username,
                            message.channel.id,
                            message.channel.name if hasattr(message.channel, 'name') else str(message.channel.id),
                            content,
                            timestamp,
                            guild_id
                        ))
                        fetch = cur.fetchone()
                        stored_id = fetch[0] if fetch else None

                    cur.execute("""
                        INSERT INTO user_profiles (user_id, username, total_messages, first_seen, last_seen, opted_out)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (user_id) DO UPDATE SET
                            username = EXCLUDED.username,
                            total_messages = CASE
                                WHEN EXCLUDED.opted_out THEN user_profiles.total_messages
                                ELSE user_profiles.total_messages + 1
                            END,
                            last_seen = CASE
                                WHEN EXCLUDED.opted_out THEN user_profiles.last_seen
                                ELSE EXCLUDED.last_seen
                            END,
                            opted_out = EXCLUDED.opted_out,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        message.author.id,
                        profile_username,
                        1 if not opted_out else 0,
                        timestamp,
                        timestamp,
                        opted_out
                    ))

                    if stored_id:
                        preview = (content or "")[:50]
                        print(f"📥 Stored message {stored_id} from {message.author}: {preview}")

        except Exception as e:
            print(f"⚠️ Error storing message: {e}")
    
    def get_recent_messages(self, channel_id, limit=10, exclude_opted_out=True, exclude_bot_id=None, user_id=None, guild_id=None):
        """Get recent messages from a channel for context

        Args:
            channel_id: Channel to fetch messages from
            limit: Max number of messages to return
            exclude_opted_out: Exclude users who opted out
            exclude_bot_id: Exclude messages from this bot user ID
            user_id: If provided, only get messages from this user (and bot responses to them)
            guild_id: Guild/server ID for data isolation (optional but recommended)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Build query with parameterized statements (SECURE - prevents SQL injection)
                    query = """
                        SELECT m.message_id, m.user_id, m.username, m.content, m.timestamp
                        FROM messages m
                        LEFT JOIN user_profiles up ON up.user_id = m.user_id
                        WHERE m.channel_id = %s
                    """
                    params = [channel_id]

                    # Add guild_id filter for data isolation
                    if guild_id is not None:
                        query += " AND m.guild_id = %s"
                        params.append(guild_id)

                    # Filter to specific user's conversation (their messages + bot responses)
                    if user_id is not None:
                        query += " AND (m.user_id = %s"
                        params.append(user_id)
                        if exclude_bot_id:
                            query += " OR m.user_id = %s"
                            params.append(exclude_bot_id)
                        query += ")"
                    elif exclude_bot_id:
                        # If no user_id filter, still exclude bot messages
                        query += " AND m.user_id != %s"
                        params.append(exclude_bot_id)

                    if exclude_opted_out:
                        query += " AND COALESCE(m.opted_out, FALSE) = FALSE AND COALESCE(up.opted_out, FALSE) = FALSE"

                    query += " ORDER BY m.timestamp DESC LIMIT %s"
                    params.append(limit)

                    cur.execute(query, tuple(params))
                    messages = cur.fetchall()
                    return list(reversed(messages))  # Return chronological order
        except Exception as e:
            print(f"❌ Error fetching messages: {e}")
            return []
    
    def get_user_context(self, user_id):
        """Get user profile and recent behavior"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM user_profiles WHERE user_id = %s
                    """, (user_id,))
                    profile = cur.fetchone()

                    cur.execute("""
                        SELECT * FROM user_behavior
                        WHERE user_id = %s
                        ORDER BY analyzed_at DESC
                        LIMIT 1
                    """, (user_id,))
                    behavior = cur.fetchone()

                    return {'profile': profile, 'behavior': behavior}
        except Exception as e:
            print(f"❌ Error fetching user context: {e}")
            return {'profile': None, 'behavior': None}
    
    def store_search_log(self, query, results_count, user_id, channel_id):
        """Log search queries"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO search_logs (query, results_count, triggered_by_user_id, channel_id)
                        VALUES (%s, %s, %s, %s)
                    """, (query, results_count, user_id, channel_id))
        except Exception as e:
            print(f"❌ Error storing search log: {e}")
    
    def store_behavior_analysis(self, user_id, username, analysis_data, period_start, period_end):
        """Store user behavior analysis results"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO user_behavior
                        (user_id, username, analysis_period_start, analysis_period_end,
                         profanity_score, message_count, tone_analysis, honesty_patterns, conversation_style)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        user_id,
                        username,
                        period_start,
                        period_end,
                        analysis_data.get('profanity_score', 0),
                        analysis_data.get('message_count', 0),
                        analysis_data.get('tone_analysis', ''),
                        analysis_data.get('honesty_patterns', ''),
                        analysis_data.get('conversation_style', '')
                    ))
        except Exception as e:
            print(f"❌ Error storing behavior analysis: {e}")
    
    def get_user_messages_for_analysis(self, user_id, days=7):
        """Get user messages for behavior analysis"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT m.content, m.timestamp
                        FROM messages m
                        LEFT JOIN user_profiles up ON up.user_id = m.user_id
                        WHERE m.user_id = %s
                        AND COALESCE(m.opted_out, FALSE) = FALSE
                        AND COALESCE(up.opted_out, FALSE) = FALSE
                        AND m.timestamp > CURRENT_TIMESTAMP - INTERVAL '%s days'
                        ORDER BY m.timestamp DESC
                    """, (user_id, days))
                    return cur.fetchall()
        except Exception as e:
            print(f"❌ Error fetching messages for analysis: {e}")
            return []
    
    def get_all_active_users(self, days=7):
        """Get all users who have been active recently"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT DISTINCT m.user_id, m.username
                        FROM messages m
                        LEFT JOIN user_profiles up ON up.user_id = m.user_id
                        WHERE COALESCE(m.opted_out, FALSE) = FALSE
                        AND COALESCE(up.opted_out, FALSE) = FALSE
                        AND m.timestamp > CURRENT_TIMESTAMP - INTERVAL '%s days'
                    """, (days,))
                    return cur.fetchall()
        except Exception as e:
            print(f"❌ Error fetching active users: {e}")
            return []
    
    def get_message_stats(self, days=7, limit=10, guild_id=None, exclude_bots=True, exclude_user_ids=None):
        """Get top users by message count for a specific guild

        Args:
            days: Number of days to look back
            limit: Max number of users to return
            guild_id: Filter to specific Discord server (required for accurate stats)
            exclude_bots: Exclude bot users from results
            exclude_user_ids: List of specific user IDs to exclude (e.g., [bot_user_id])
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Build query with optional guild filter and bot exclusion
                    query = """
                        SELECT
                            m.user_id,
                            m.username,
                            COUNT(*) as message_count,
                            COUNT(DISTINCT DATE(m.timestamp)) as active_days
                        FROM messages m
                        LEFT JOIN user_profiles up ON up.user_id = m.user_id
                        WHERE COALESCE(m.opted_out, FALSE) = FALSE
                        AND COALESCE(up.opted_out, FALSE) = FALSE
                        AND m.timestamp > CURRENT_TIMESTAMP - INTERVAL '%s days'
                    """
                    params = [days]

                    # Filter by guild if specified
                    if guild_id:
                        query += " AND m.guild_id = %s"
                        params.append(guild_id)

                    # Exclude bot messages by name pattern
                    if exclude_bots:
                        query += " AND LOWER(m.username) NOT LIKE '%%bot%%'"
                        query += " AND LOWER(m.username) NOT LIKE '%%[app]%%'"

                    # Exclude specific user IDs (e.g., bot's own user ID)
                    # Auto-exclude bot_user_id if set on this Database instance
                    ids_to_exclude = list(exclude_user_ids) if exclude_user_ids else []
                    if self.bot_user_id and self.bot_user_id not in ids_to_exclude:
                        ids_to_exclude.append(self.bot_user_id)

                    if ids_to_exclude:
                        query += " AND m.user_id NOT IN %s"
                        params.append(tuple(ids_to_exclude))

                    query += """
                        GROUP BY m.user_id, m.username
                        ORDER BY message_count DESC
                        LIMIT %s
                    """
                    params.append(limit)

                    cur.execute(query, params)
                    return cur.fetchall()
        except Exception as e:
            print(f"❌ Error fetching message stats: {e}")
            return []

    def get_bot_message_stats(self, days=7, guild_id=None):
        """Get message stats for the bot itself (for tracking bot activity per server)

        Args:
            days: Number of days to look back
            guild_id: Filter to specific Discord server

        Returns:
            Dict with bot's message count and active days, or None if bot_user_id not set
        """
        if not self.bot_user_id:
            return None

        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    query = """
                        SELECT
                            m.user_id,
                            m.username,
                            COUNT(*) as message_count,
                            COUNT(DISTINCT DATE(m.timestamp)) as active_days
                        FROM messages m
                        WHERE m.user_id = %s
                        AND m.timestamp > CURRENT_TIMESTAMP - INTERVAL '%s days'
                    """
                    params = [self.bot_user_id, days]

                    if guild_id:
                        query += " AND m.guild_id = %s"
                        params.append(guild_id)

                    query += " GROUP BY m.user_id, m.username"

                    cur.execute(query, params)
                    result = cur.fetchone()
                    return dict(result) if result else {
                        'user_id': self.bot_user_id,
                        'username': 'WompBot',
                        'message_count': 0,
                        'active_days': 0
                    }
        except Exception as e:
            print(f"❌ Error fetching bot message stats: {e}")
            return None

    def get_question_stats(self, days=7, limit=10):
        """Get all messages for question analysis (will be classified by LLM)"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT
                            m.user_id,
                            m.username,
                            m.content,
                            m.timestamp
                        FROM messages m
                        LEFT JOIN user_profiles up ON up.user_id = m.user_id
                        WHERE COALESCE(m.opted_out, FALSE) = FALSE
                        AND COALESCE(up.opted_out, FALSE) = FALSE
                        AND m.timestamp > CURRENT_TIMESTAMP - INTERVAL '%s days'
                        ORDER BY m.timestamp DESC
                    """, (days,))
                    return cur.fetchall()
        except Exception as e:
            print(f"❌ Error fetching messages for question analysis: {e}")
            return []
    
    def get_profanity_stats(self, days=7, limit=10):
        """Get users with highest profanity scores from behavior analysis"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT DISTINCT ON (ub.user_id)
                            ub.username,
                            ub.profanity_score,
                            ub.message_count,
                            ub.analyzed_at
                        FROM user_behavior ub
                        WHERE ub.analysis_period_end > CURRENT_TIMESTAMP - INTERVAL '%s days'
                        ORDER BY ub.user_id, ub.analyzed_at DESC
                    """, (days,))
                    results = cur.fetchall()
                    # Sort by profanity score and limit
                    sorted_results = sorted(results, key=lambda x: x['profanity_score'], reverse=True)
                    return sorted_results[:limit]
        except Exception as e:
            print(f"❌ Error fetching profanity stats: {e}")
            return []
    
    def store_fact_check(self, message_id, user_id, username, channel_id, claim_text,
                         fact_check_result, search_results, requested_by_user_id, requested_by_username):
        """Store fact-check results"""
        try:
            import json
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO fact_checks
                        (message_id, user_id, username, channel_id, claim_text,
                         fact_check_result, search_results, requested_by_user_id, requested_by_username)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        message_id,
                        user_id,
                        username,
                        channel_id,
                        claim_text,
                        fact_check_result,
                        json.dumps(search_results),
                        requested_by_user_id,
                        requested_by_username
                    ))
                    fact_check_id = cur.fetchone()[0]
                    print(f"✅ Stored fact-check #{fact_check_id} for message {message_id}")
                    return fact_check_id
        except Exception as e:
            print(f"❌ Error storing fact-check: {e}")
            return None

    def get_iracing_meta_cache(self, cache_key: str):
        """Get cached meta analysis data if not expired"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT meta_data, expires_at
                        FROM iracing_meta_cache
                        WHERE cache_key = %s
                        AND expires_at > NOW()
                    """, (cache_key,))

                    result = cur.fetchone()
                    if result:
                        # Update last_accessed timestamp
                        cur.execute("""
                            UPDATE iracing_meta_cache
                            SET last_accessed = NOW()
                            WHERE cache_key = %s
                        """, (cache_key,))

                        meta_data = result['meta_data']
                        return meta_data

                    return None
        except Exception as e:
            print(f"⚠️ Error reading meta cache: {e}")
            return None

    def store_iracing_meta_cache(self, cache_key: str, series_id: int, season_id: int,
                                  week_num: int, meta_data: dict, track_id: int = None,
                                  ttl_hours: int = 6):
        """Store meta analysis data in cache"""
        try:
            import json
            from datetime import timedelta

            expires_at = datetime.now() + timedelta(hours=ttl_hours)

            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO iracing_meta_cache
                            (cache_key, series_id, season_id, week_num, track_id, meta_data, expires_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (cache_key)
                        DO UPDATE SET
                            meta_data = EXCLUDED.meta_data,
                            last_accessed = NOW(),
                            expires_at = EXCLUDED.expires_at
                    """, (
                        cache_key,
                        series_id,
                        season_id,
                        week_num,
                        track_id,
                        json.dumps(meta_data),
                        expires_at
                    ))

                    has_weather = 'weather' in meta_data
                    print(f"✅ Stored meta cache for {cache_key} (expires in {ttl_hours}h), has_weather: {has_weather}")
                    if has_weather:
                        print(f"  Weather data being stored: {meta_data['weather']}")
                    return True
        except Exception as e:
            print(f"❌ Error storing meta cache: {e}")
            return False

    def cleanup_expired_meta_cache(self):
        """Remove expired cache entries"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM iracing_meta_cache
                        WHERE expires_at < NOW()
                        RETURNING cache_key
                    """)

                    deleted = cur.fetchall()
                    if deleted:
                        print(f"Cleaned up {len(deleted)} expired meta cache entries")

                    return len(deleted)
        except Exception as e:
            print(f"⚠️ Error cleaning meta cache: {e}")
            return 0

    def get_iracing_history_cache(self, cust_id: int, timeframe: str):
        """Retrieve cached rating history if fresh."""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT payload
                        FROM iracing_history_cache
                        WHERE cust_id = %s
                          AND timeframe = %s
                          AND expires_at > NOW()
                    """, (cust_id, timeframe))

                    row = cur.fetchone()
                    if not row:
                        return None

                    import json
                    return json.loads(row['payload'])
        except Exception as e:
            print(f"⚠️ Error reading history cache: {e}")
            return None

    def store_iracing_history_cache(self, cust_id: int, timeframe: str, payload: dict, ttl_hours: float = 2.0):
        """Persist rating history analysis results for reuse."""
        try:
            from datetime import timedelta
            import json

            expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO iracing_history_cache (cust_id, timeframe, payload, expires_at, cached_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        ON CONFLICT (cust_id, timeframe)
                        DO UPDATE SET
                            payload = EXCLUDED.payload,
                            expires_at = EXCLUDED.expires_at,
                            cached_at = NOW()
                    """, (cust_id, timeframe, json.dumps(payload), expires_at))
        except Exception as e:
            print(f"⚠️ Error storing history cache: {e}")

    def cleanup_expired_history_cache(self):
        """Remove stale history cache rows."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM iracing_history_cache
                        WHERE expires_at < NOW()
                        RETURNING cust_id
                    """)
                    deleted = cur.fetchall()
                    return len(deleted)
        except Exception as e:
            print(f"⚠️ Error cleaning history cache: {e}")
            return 0

    def get_consent_summary(self):
        """Return aggregated consent statistics for privacy reporting."""
        summary = {
            "total_profiles": 0,
            "active_consent": 0,
            "withdrawn": 0,
            "pending": 0,
            "opted_out_profiles": 0,
        }
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT COUNT(*) AS total_profiles, SUM(CASE WHEN opted_out THEN 1 ELSE 0 END) AS opted_out FROM user_profiles")
                    profile_row = cur.fetchone() or {}
                    summary["total_profiles"] = profile_row.get("total_profiles", 0) or 0
                    summary["opted_out_profiles"] = profile_row.get("opted_out", 0) or 0

                    cur.execute("""
                        SELECT
                            SUM(CASE WHEN consent_given AND COALESCE(consent_withdrawn, FALSE) = FALSE THEN 1 ELSE 0 END) AS active_consent,
                            SUM(CASE WHEN NOT consent_given OR consent_withdrawn THEN 1 ELSE 0 END) AS withdrawn
                        FROM user_consent
                    """)
                    consent_row = cur.fetchone() or {}
                    summary["active_consent"] = consent_row.get("active_consent", 0) or 0
                    summary["withdrawn"] = consent_row.get("withdrawn", 0) or 0

                    summary["pending"] = max(
                        summary["total_profiles"] - (summary["active_consent"] + summary["withdrawn"]),
                        0,
                    )

        except Exception as e:
            print(f"⚠️ Error building consent summary: {e}")

        return summary

    def get_data_storage_overview(self):
        """Return approximate row counts and recent activity for major tables."""
        overview = {}
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT COUNT(*) AS count, MAX(timestamp) AS last_entry
                        FROM messages
                    """)
                    overview["messages"] = cur.fetchone() or {"count": 0, "last_entry": None}

                    cur.execute("SELECT COUNT(*) AS count FROM claims")
                    overview["claims"] = cur.fetchone() or {"count": 0}

                    cur.execute("SELECT COUNT(*) AS count FROM user_behavior")
                    overview["user_behavior"] = cur.fetchone() or {"count": 0}

                    cur.execute("SELECT COUNT(*) AS count FROM stats_cache")
                    overview["stats_cache"] = cur.fetchone() or {"count": 0}

                    cur.execute("SELECT COUNT(*) AS count FROM iracing_meta_cache")
                    overview["iracing_meta_cache"] = cur.fetchone() or {"count": 0}

                    cur.execute("SELECT COUNT(*) AS count FROM iracing_history_cache")
                    overview["iracing_history_cache"] = cur.fetchone() or {"count": 0}

        except Exception as e:
            print(f"⚠️ Error getting storage overview: {e}")

        return overview

    def store_participation_snapshot(self, series_name: str, series_id: int, season_id: int,
                                     season_year: int, season_quarter: int, participant_count: int,
                                     snapshot_date=None):
        """Store a daily snapshot of series participation"""
        try:
            if snapshot_date is None:
                snapshot_date = datetime.now().date()

            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO iracing_participation_history
                            (series_name, series_id, season_id, season_year, season_quarter,
                             participant_count, snapshot_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (series_name, season_id, snapshot_date)
                        DO UPDATE SET
                            participant_count = EXCLUDED.participant_count
                    """, (
                        series_name,
                        series_id,
                        season_id,
                        season_year,
                        season_quarter,
                        participant_count,
                        snapshot_date
                    ))
                    return True
        except Exception as e:
            print(f"Error storing participation snapshot: {e}")
            return False

    def get_participation_data(self, time_range: str, season_year: int, season_quarter: int, limit: int = 10):
        """
        Get historical participation data for a time range.

        Args:
            time_range: 'season', 'yearly', or 'all_time'
            season_year: Current season year
            season_quarter: Current season quarter
            limit: Number of top series to return

        Returns:
            List of (series_name, total_participants) tuples, or None if insufficient data
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if time_range == 'season':
                        # Current quarter only - need at least 7 days of data
                        cur.execute("""
                            SELECT COUNT(DISTINCT snapshot_date) as days_of_data
                            FROM iracing_participation_history
                            WHERE season_year = %s AND season_quarter = %s
                        """, (season_year, season_quarter))

                        result = cur.fetchone()
                        if not result or result['days_of_data'] < 7:
                            return None  # Not enough data yet

                        # Get aggregated data for current quarter
                        cur.execute("""
                            SELECT series_name,
                                   MAX(participant_count) as max_participants
                            FROM iracing_participation_history
                            WHERE season_year = %s AND season_quarter = %s
                            GROUP BY series_name
                            ORDER BY max_participants DESC
                            LIMIT %s
                        """, (season_year, season_quarter, limit))

                    elif time_range == 'yearly':
                        # All quarters of current year - need at least 30 days
                        cur.execute("""
                            SELECT COUNT(DISTINCT snapshot_date) as days_of_data
                            FROM iracing_participation_history
                            WHERE season_year = %s
                        """, (season_year,))

                        result = cur.fetchone()
                        if not result or result['days_of_data'] < 30:
                            return None

                        # Aggregate across all quarters of the year
                        cur.execute("""
                            SELECT series_name,
                                   SUM(max_participants) as total_participants
                            FROM (
                                SELECT series_name, season_quarter,
                                       MAX(participant_count) as max_participants
                                FROM iracing_participation_history
                                WHERE season_year = %s
                                GROUP BY series_name, season_quarter
                            ) subquery
                            GROUP BY series_name
                            ORDER BY total_participants DESC
                            LIMIT %s
                        """, (season_year, limit))

                    else:  # all_time
                        # Need at least 90 days of historical data
                        cur.execute("""
                            SELECT COUNT(DISTINCT snapshot_date) as days_of_data
                            FROM iracing_participation_history
                        """)

                        result = cur.fetchone()
                        if not result or result['days_of_data'] < 90:
                            return None

                        # Aggregate across all years and quarters
                        cur.execute("""
                            SELECT series_name,
                                   SUM(max_participants) as total_participants
                            FROM (
                                SELECT series_name, season_year, season_quarter,
                                       MAX(participant_count) as max_participants
                                FROM iracing_participation_history
                                GROUP BY series_name, season_year, season_quarter
                            ) subquery
                            GROUP BY series_name
                            ORDER BY total_participants DESC
                            LIMIT %s
                        """, (limit,))

                    results = cur.fetchall()
                    if not results:
                        return None

                    # Convert to list of tuples
                    return [(row['series_name'], int(row.get('max_participants') or row.get('total_participants', 0)))
                            for row in results]

        except Exception as e:
            print(f"❌ Error getting participation data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_data_availability_info(self, season_year: int, season_quarter: int):
        """Get information about available historical data"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Check days of data for current quarter
                    cur.execute("""
                        SELECT COUNT(DISTINCT snapshot_date) as days_of_data,
                               MIN(snapshot_date) as first_snapshot,
                               MAX(snapshot_date) as last_snapshot
                        FROM iracing_participation_history
                        WHERE season_year = %s AND season_quarter = %s
                    """, (season_year, season_quarter))

                    quarter_data = cur.fetchone()

                    # Check total days across all data
                    cur.execute("""
                        SELECT COUNT(DISTINCT snapshot_date) as total_days,
                               MIN(snapshot_date) as first_snapshot,
                               MAX(snapshot_date) as last_snapshot
                        FROM iracing_participation_history
                    """)

                    total_data = cur.fetchone()

                    return {
                        'quarter_days': quarter_data['days_of_data'] if quarter_data else 0,
                        'quarter_first': quarter_data['first_snapshot'] if quarter_data else None,
                        'quarter_last': quarter_data['last_snapshot'] if quarter_data else None,
                        'total_days': total_data['total_days'] if total_data else 0,
                        'total_first': total_data['first_snapshot'] if total_data else None,
                        'total_last': total_data['last_snapshot'] if total_data else None,
                    }
        except Exception as e:
            print(f"Error checking data availability: {e}")
            return None

    def check_rate_limit(self, user_id, username, tokens_requested):
        """Check if user is within rate limits for the hour

        Returns:
            dict with 'allowed' (bool), 'tokens_used' (int), 'limit' (int), 'reset_seconds' (int)
        """
        try:
            hourly_limit = int(os.getenv('HOURLY_TOKEN_LIMIT', '10000'))

            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get tokens used in the last hour
                    cur.execute("""
                        SELECT COALESCE(SUM(tokens_used), 0) as total_tokens,
                               MIN(request_timestamp) as oldest_request
                        FROM rate_limits
                        WHERE user_id = %s
                          AND request_timestamp >= NOW() - INTERVAL '1 hour'
                    """, (user_id,))

                    result = cur.fetchone()
                    tokens_used = result['total_tokens']
                    oldest_request = result['oldest_request']

                    # Calculate when the limit resets
                    if oldest_request:
                        reset_time = oldest_request + timedelta(hours=1)
                        reset_seconds = int((reset_time - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds())
                        reset_seconds = max(0, reset_seconds)
                    else:
                        reset_seconds = 3600

                    # Check if adding this request would exceed the limit
                    would_exceed = (tokens_used + tokens_requested) > hourly_limit

                    return {
                        'allowed': not would_exceed,
                        'tokens_used': tokens_used,
                        'tokens_requested': tokens_requested,
                        'limit': hourly_limit,
                        'reset_seconds': reset_seconds
                    }

        except Exception as e:
            print(f"Error checking rate limit: {e}")
            # Fail open - allow the request if there's a database error
            return {
                'allowed': True,
                'tokens_used': 0,
                'tokens_requested': tokens_requested,
                'limit': 10000,
                'reset_seconds': 3600
            }

    def check_repeated_messages(self, user_id, message_content):
        """Check if user is repeating similar messages to game the bot

        Returns:
            dict with 'allowed' (bool), 'similar_count' (int), 'most_similar' (str or None)
        """
        try:
            window_seconds = int(os.getenv('REPEATED_MESSAGE_WINDOW', '3600'))
            threshold = int(os.getenv('REPEATED_MESSAGE_THRESHOLD', '3'))
            similarity_threshold = float(os.getenv('SIMILARITY_THRESHOLD', '0.80'))

            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Get recent messages from this user in the time window
                    cur.execute("""
                        SELECT content, timestamp
                        FROM messages
                        WHERE user_id = %s
                          AND timestamp >= NOW() - INTERVAL '%s seconds'
                          AND content IS NOT NULL
                          AND content != ''
                        ORDER BY timestamp DESC
                        LIMIT 20
                    """, (user_id, window_seconds))

                    recent_messages = cur.fetchall()

                    # Compare current message to recent messages
                    similar_count = 0
                    most_similar = None
                    highest_similarity = 0.0

                    current_msg_lower = message_content.lower().strip()

                    for row in recent_messages:
                        past_msg_lower = row['content'].lower().strip()

                        # Calculate similarity using SequenceMatcher
                        similarity = SequenceMatcher(None, current_msg_lower, past_msg_lower).ratio()

                        if similarity >= similarity_threshold:
                            similar_count += 1

                            if similarity > highest_similarity:
                                highest_similarity = similarity
                                most_similar = row['content'][:100]  # First 100 chars

                    # Check if exceeded threshold
                    allowed = similar_count < threshold

                    return {
                        'allowed': allowed,
                        'similar_count': similar_count,
                        'threshold': threshold,
                        'most_similar': most_similar,
                        'window_minutes': window_seconds // 60
                    }

        except Exception as e:
            print(f"Error checking repeated messages: {e}")
            # Fail open - allow the request if there's a database error
            return {
                'allowed': True,
                'similar_count': 0,
                'threshold': 3,
                'most_similar': None,
                'window_minutes': 60
            }

    def record_token_usage(self, user_id, username, tokens_used):
        """Record token usage for rate limiting"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO rate_limits (user_id, username, tokens_used)
                        VALUES (%s, %s, %s)
                    """, (user_id, username, tokens_used))

                    # Clean up old records (older than 1 hour)
                    cur.execute("""
                        DELETE FROM rate_limits
                        WHERE request_timestamp < NOW() - INTERVAL '1 hour'
                    """)

        except Exception as e:
            print(f"Error recording token usage: {e}")

    def record_api_cost(self, model, input_tokens, output_tokens, cost_usd, request_type, user_id=None, username=None):
        """Record API cost for monitoring spending"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO api_costs (model, input_tokens, output_tokens, cost_usd, request_type, user_id, username)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (model, input_tokens, output_tokens, cost_usd, request_type, user_id, username))
        except Exception as e:
            print(f"Error recording API cost: {e}")

    def get_total_cost(self, since_timestamp=None):
        """Get total API costs, optionally since a specific timestamp"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    if since_timestamp:
                        cur.execute("""
                            SELECT COALESCE(SUM(cost_usd), 0) as total_cost
                            FROM api_costs
                            WHERE timestamp >= %s
                        """, (since_timestamp,))
                    else:
                        cur.execute("""
                            SELECT COALESCE(SUM(cost_usd), 0) as total_cost
                            FROM api_costs
                        """)
                    result = cur.fetchone()
                    return float(result[0]) if result else 0.0
        except Exception as e:
            print(f"Error getting total cost: {e}")
            return 0.0

    def check_cost_alert_threshold(self, threshold_usd):
        """Check if we've crossed a cost threshold that hasn't been alerted yet"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get last alerted threshold
                    cur.execute("""
                        SELECT MAX(threshold_usd) as last_threshold
                        FROM cost_alerts
                    """)
                    result = cur.fetchone()
                    last_threshold = float(result[0]) if result and result[0] else 0.0

                    # Get total cost
                    total_cost = self.get_total_cost()

                    # Calculate which $1 thresholds have been crossed
                    current_threshold_floor = int(total_cost)
                    last_threshold_floor = int(last_threshold)

                    # If we've crossed a new $1 threshold
                    if current_threshold_floor > last_threshold_floor:
                        return {
                            'should_alert': True,
                            'threshold': current_threshold_floor,
                            'total_cost': total_cost
                        }

                    return {'should_alert': False, 'total_cost': total_cost}

        except Exception as e:
            print(f"Error checking cost alert threshold: {e}")
            return {'should_alert': False, 'total_cost': 0.0}

    def record_cost_alert(self, threshold_usd, total_cost_usd):
        """Record that a cost alert has been sent"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO cost_alerts (threshold_usd, total_cost_usd)
                        VALUES (%s, %s)
                    """, (threshold_usd, total_cost_usd))
        except Exception as e:
            print(f"Error recording cost alert: {e}")

    def check_feature_rate_limit(self, user_id, feature_type, cooldown_seconds=None, hourly_limit=None, daily_limit=None):
        """
        Check if user is within rate limits for a specific feature

        Args:
            user_id: Discord user ID
            feature_type: Type of feature ('fact_check', 'search', etc.)
            cooldown_seconds: Minimum seconds between requests
            hourly_limit: Maximum requests per hour
            daily_limit: Maximum requests per day

        Returns:
            dict with 'allowed' (bool), 'reason' (str), 'wait_seconds' (int)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Check cooldown
                    if cooldown_seconds:
                        cur.execute("""
                            SELECT MAX(request_timestamp) as last_request
                            FROM feature_rate_limits
                            WHERE user_id = %s AND feature_type = %s
                              AND request_timestamp >= NOW() - INTERVAL '%s seconds'
                        """, (user_id, feature_type, cooldown_seconds))

                        result = cur.fetchone()
                        if result and result['last_request']:
                            last_request = result['last_request']
                            elapsed = (datetime.now(timezone.utc).replace(tzinfo=None) - last_request).total_seconds()
                            wait_time = max(0, cooldown_seconds - elapsed)

                            if wait_time > 0:
                                return {
                                    'allowed': False,
                                    'reason': 'cooldown',
                                    'wait_seconds': int(wait_time)
                                }

                    # Check hourly limit
                    if hourly_limit:
                        cur.execute("""
                            SELECT COUNT(*) as count
                            FROM feature_rate_limits
                            WHERE user_id = %s AND feature_type = %s
                              AND request_timestamp >= NOW() - INTERVAL '1 hour'
                        """, (user_id, feature_type))

                        result = cur.fetchone()
                        if result['count'] >= hourly_limit:
                            return {
                                'allowed': False,
                                'reason': 'hourly_limit',
                                'count': result['count'],
                                'limit': hourly_limit
                            }

                    # Check daily limit
                    if daily_limit:
                        cur.execute("""
                            SELECT COUNT(*) as count
                            FROM feature_rate_limits
                            WHERE user_id = %s AND feature_type = %s
                              AND request_timestamp >= NOW() - INTERVAL '24 hours'
                        """, (user_id, feature_type))

                        result = cur.fetchone()
                        if result['count'] >= daily_limit:
                            return {
                                'allowed': False,
                                'reason': 'daily_limit',
                                'count': result['count'],
                                'limit': daily_limit
                            }

                    # All checks passed
                    return {'allowed': True}

        except Exception as e:
            print(f"Error checking feature rate limit: {e}")
            # Fail open
            return {'allowed': True}

    def record_feature_usage(self, user_id, feature_type):
        """Record usage of a rate-limited feature"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO feature_rate_limits (user_id, feature_type)
                        VALUES (%s, %s)
                    """, (user_id, feature_type))

                    # Clean up old records (older than 24 hours)
                    cur.execute("""
                        DELETE FROM feature_rate_limits
                        WHERE request_timestamp < NOW() - INTERVAL '24 hours'
                    """)
        except Exception as e:
            print(f"Error recording feature usage: {e}")

    def get_server_personality(self, server_id):
        """
        Get personality mode for a server

        Args:
            server_id: Discord server ID

        Returns:
            'default' or 'bogan' (defaults to 'default' if not set)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT personality
                        FROM server_personality
                        WHERE server_id = %s
                    """, (server_id,))
                    result = cur.fetchone()

                    if result:
                        return result['personality']
                    else:
                        return 'default'  # Default personality
        except Exception as e:
            print(f"Error getting server personality: {e}")
            return 'default'  # Fail safe to default

    def set_server_personality(self, server_id, personality, user_id):
        """
        Set personality mode for a server

        Args:
            server_id: Discord server ID
            personality: 'default' or 'bogan'
            user_id: ID of user who changed the setting

        Returns:
            True if successful
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO server_personality (server_id, personality, enabled_by, enabled_at)
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (server_id)
                        DO UPDATE SET
                            personality = EXCLUDED.personality,
                            enabled_by = EXCLUDED.enabled_by,
                            enabled_at = CURRENT_TIMESTAMP
                    """, (server_id, personality, user_id))
                    conn.commit()
                    return True
        except Exception as e:
            print(f"Error setting server personality: {e}")
            return False

    def get_weather_preference(self, user_id: int):
        """Get user's saved weather location preference"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT location, units FROM weather_preferences WHERE user_id = %s",
                        (user_id,)
                    )
                    return cur.fetchone()
        except Exception as e:
            print(f"Error getting weather preference: {e}")
            return None

    def set_weather_preference(self, user_id: int, location: str, units: str = 'imperial'):
        """Set user's default weather location"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO weather_preferences (user_id, location, units)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id)
                        DO UPDATE SET location = EXCLUDED.location,
                                      units = EXCLUDED.units,
                                      updated_at = CURRENT_TIMESTAMP
                        """,
                        (user_id, location, units)
                    )
                    return True
        except Exception as e:
            print(f"Error setting weather preference: {e}")
            return False

    def delete_weather_preference(self, user_id: int):
        """Remove user's weather location preference"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM weather_preferences WHERE user_id = %s",
                        (user_id,)
                    )
                    return cur.rowcount > 0
        except Exception as e:
            print(f"Error deleting weather preference: {e}")
            return False

    # ===== TRIVIA SYSTEM METHODS =====

    def create_trivia_session(self, guild_id, channel_id, topic, difficulty,
                             question_count, time_per_question, user_id, username):
        """Create new trivia session"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trivia_sessions
                    (guild_id, channel_id, topic, difficulty, question_count,
                     time_per_question, started_by_user_id, started_by_username)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (guild_id, channel_id, topic, difficulty, question_count,
                      time_per_question, user_id, username))
                return cur.fetchone()[0]

    def create_trivia_question(self, session_id, question_number, question_text,
                              correct_answer, acceptable_answers, difficulty):
        """Store trivia question"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trivia_questions
                    (session_id, question_number, question_text, correct_answer,
                     acceptable_answers, difficulty)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (session_id, question_number, question_text, correct_answer,
                      acceptable_answers, difficulty))
                return cur.fetchone()[0]

    def get_trivia_question_id(self, session_id, question_number):
        """Get question ID"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM trivia_questions
                    WHERE session_id = %s AND question_number = %s
                """, (session_id, question_number))
                row = cur.fetchone()
                return row[0] if row else None

    def store_trivia_answer(self, session_id, question_id, user_id, username,
                           answer_text, is_correct, similarity, time_taken, points):
        """Store trivia answer"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trivia_answers
                    (session_id, question_id, user_id, username, answer_text,
                     is_correct, similarity_score, time_taken, points_earned)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (session_id, question_id, user_id, username, answer_text,
                      is_correct, similarity, time_taken, points))

    def end_trivia_session(self, session_id):
        """Mark session as completed"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE trivia_sessions
                    SET ended_at = CURRENT_TIMESTAMP, status = 'completed'
                    WHERE id = %s
                """, (session_id,))

    def get_trivia_user_stats(self, guild_id, user_id):
        """Get user trivia stats"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM trivia_stats
                    WHERE guild_id = %s AND user_id = %s
                """, (guild_id, user_id))
                return cur.fetchone()

    def update_trivia_user_stats(self, guild_id, user_id, username,
                                 questions_answered, correct_answers, points,
                                 avg_time, streak, topic, is_winner):
        """Update or create user stats"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO trivia_stats
                    (guild_id, user_id, username, total_sessions, total_questions_answered,
                     total_correct, total_points, avg_time_per_question, best_streak,
                     favorite_topic, wins)
                    VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (guild_id, user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        total_sessions = trivia_stats.total_sessions + 1,
                        total_questions_answered = trivia_stats.total_questions_answered + EXCLUDED.total_questions_answered,
                        total_correct = trivia_stats.total_correct + EXCLUDED.total_correct,
                        total_points = trivia_stats.total_points + EXCLUDED.total_points,
                        avg_time_per_question = (trivia_stats.avg_time_per_question * trivia_stats.total_questions_answered +
                                                 EXCLUDED.avg_time_per_question * EXCLUDED.total_questions_answered) /
                                                NULLIF(trivia_stats.total_questions_answered + EXCLUDED.total_questions_answered, 0),
                        best_streak = GREATEST(trivia_stats.best_streak, EXCLUDED.best_streak),
                        wins = trivia_stats.wins + EXCLUDED.wins
                """, (guild_id, user_id, username, questions_answered, correct_answers,
                      points, avg_time, streak, topic, 1 if is_winner else 0))

    def get_trivia_leaderboard(self, guild_id, days=30, limit=10):
        """Get trivia leaderboard"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT ts.user_id, ts.username, ts.total_points,
                           ts.total_questions_answered, ts.total_correct, ts.wins
                    FROM trivia_stats ts
                    WHERE ts.guild_id = %s
                      AND ts.updated_at > (NOW() - make_interval(days := %s))
                    ORDER BY ts.total_points DESC
                    LIMIT %s
                """, (guild_id, days, limit))
                return cur.fetchall()

    def get_trivia_user_rank(self, guild_id, user_id, days=30):
        """Get a user's rank on the trivia leaderboard"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    WITH ranked AS (
                        SELECT ts.user_id, ts.username, ts.total_points,
                               ts.total_questions_answered, ts.total_correct, ts.wins,
                               RANK() OVER (ORDER BY ts.total_points DESC) as rank,
                               COUNT(*) OVER () as total_players
                        FROM trivia_stats ts
                        WHERE ts.guild_id = %s
                          AND ts.updated_at > (NOW() - make_interval(days := %s))
                    )
                    SELECT * FROM ranked WHERE user_id = %s
                """, (guild_id, days, user_id))
                return cur.fetchone()

    # ==================== Server Admin Methods ====================

    def get_server_admins(self, guild_id):
        """Get list of bot admins for a server"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT user_id, added_by, added_at
                    FROM server_admins
                    WHERE guild_id = %s
                    ORDER BY added_at
                """, (guild_id,))
                return cur.fetchall()

    def is_server_admin(self, guild_id, user_id):
        """Check if a user is a bot admin for a server"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM server_admins
                    WHERE guild_id = %s AND user_id = %s
                """, (guild_id, user_id))
                return cur.fetchone() is not None

    def add_server_admin(self, guild_id, user_id, added_by):
        """Add a bot admin for a server. Returns True if added, False if already exists."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("""
                        INSERT INTO server_admins (guild_id, user_id, added_by)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (guild_id, user_id) DO NOTHING
                        RETURNING id
                    """, (guild_id, user_id, added_by))
                    conn.commit()
                    return cur.fetchone() is not None
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Error adding server admin: {e}")
                    return False

    def remove_server_admin(self, guild_id, user_id):
        """Remove a bot admin from a server. Returns True if removed, False if not found."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM server_admins
                    WHERE guild_id = %s AND user_id = %s
                    RETURNING id
                """, (guild_id, user_id))
                conn.commit()
                return cur.fetchone() is not None

    def close(self):
        """Close database connection pool"""
        if self.pool:
            self.pool.closeall()
