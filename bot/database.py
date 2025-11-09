import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
import os
import time

class Database:
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self):
        """Connect to PostgreSQL with retry logic"""
        max_retries = 5
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                self.conn = psycopg2.connect(
                    host=os.getenv('DB_HOST', 'postgres'),
                    port=os.getenv('DB_PORT', '5432'),
                    database=os.getenv('DB_NAME', 'discord_bot'),
                    user=os.getenv('DB_USER', 'botuser'),
                    password=os.getenv('DB_PASSWORD'),
                    connect_timeout=10
                )
                self.conn.autocommit = True
                print("✅ Database connected successfully")
                return
            except Exception as e:
                print(f"⚠️  Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise
    
    def get_job_last_run(self, job_name: str):
        """Return the last recorded run time for a scheduled job."""
        try:
            with self.conn.cursor() as cur:
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
            with self.conn.cursor() as cur:
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
    
    def store_message(self, message, opted_out=False):
        """Store a Discord message while respecting privacy settings."""
        try:
            profile_username = str(message.author) if not opted_out else "[redacted]"
            timestamp = message.created_at

            with self.conn.cursor() as cur:
                stored_id = None

                if not opted_out:
                    cur.execute("""
                        INSERT INTO messages (message_id, user_id, username, channel_id, channel_name, content, timestamp, opted_out)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
                        ON CONFLICT (message_id) DO NOTHING
                        RETURNING message_id
                    """, (
                        message.id,
                        message.author.id,
                        profile_username,
                        message.channel.id,
                        message.channel.name,
                        message.content,
                        timestamp
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
                    preview = (message.content or "")[:50]
                    print(f"📥 Stored message {stored_id} from {message.author}: {preview}")

        except Exception as e:
            print(f"⚠️ Error storing message: {e}")
    
    def get_recent_messages(self, channel_id, limit=10, exclude_opted_out=True, exclude_bot_id=None, user_id=None):
        """Get recent messages from a channel for context

        Args:
            channel_id: Channel to fetch messages from
            limit: Max number of messages to return
            exclude_opted_out: Exclude users who opted out
            exclude_bot_id: Exclude messages from this bot user ID
            user_id: If provided, only get messages from this user (and bot responses to them)
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Build query with parameterized statements (SECURE - prevents SQL injection)
                query = """
                    SELECT m.message_id, m.user_id, m.username, m.content, m.timestamp
                    FROM messages m
                    LEFT JOIN user_profiles up ON up.user_id = m.user_id
                    WHERE m.channel_id = %s
                """
                params = [channel_id]

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
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO search_logs (query, results_count, triggered_by_user_id, channel_id)
                    VALUES (%s, %s, %s, %s)
                """, (query, results_count, user_id, channel_id))
        except Exception as e:
            print(f"❌ Error storing search log: {e}")
    
    def store_behavior_analysis(self, user_id, username, analysis_data, period_start, period_end):
        """Store user behavior analysis results"""
        try:
            with self.conn.cursor() as cur:
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
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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
    
    def get_message_stats(self, days=7, limit=10):
        """Get top users by message count"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        m.username,
                        COUNT(*) as message_count,
                        COUNT(DISTINCT DATE(m.timestamp)) as active_days
                    FROM messages m
                    LEFT JOIN user_profiles up ON up.user_id = m.user_id
                    WHERE COALESCE(m.opted_out, FALSE) = FALSE
                    AND COALESCE(up.opted_out, FALSE) = FALSE
                    AND m.timestamp > CURRENT_TIMESTAMP - INTERVAL '%s days'
                    GROUP BY m.user_id, m.username
                    ORDER BY message_count DESC
                    LIMIT %s
                """, (days, limit))
                return cur.fetchall()
        except Exception as e:
            print(f"❌ Error fetching message stats: {e}")
            return []
    
    def get_question_stats(self, days=7, limit=10):
        """Get all messages for question analysis (will be classified by LLM)"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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
            with self.conn.cursor() as cur:
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
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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

            with self.conn.cursor() as cur:
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
            with self.conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM iracing_meta_cache
                    WHERE expires_at < NOW()
                    RETURNING cache_key
                """)

                deleted = cur.fetchall()
                if deleted:
                    print(f"🧹 Cleaned up {len(deleted)} expired meta cache entries")

                return len(deleted)
        except Exception as e:
            print(f"⚠️ Error cleaning meta cache: {e}")
            return 0

    def get_iracing_history_cache(self, cust_id: int, timeframe: str):
        """Retrieve cached rating history if fresh."""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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

            with self.conn.cursor() as cur:
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
            with self.conn.cursor() as cur:
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
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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

            with self.conn.cursor() as cur:
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
            print(f"❌ Error storing participation snapshot: {e}")
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
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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
            print(f"❌ Error checking data availability: {e}")
            return None

    def check_rate_limit(self, user_id, username, tokens_requested):
        """Check if user is within rate limits for the hour

        Returns:
            dict with 'allowed' (bool), 'tokens_used' (int), 'limit' (int), 'reset_seconds' (int)
        """
        try:
            hourly_limit = int(os.getenv('HOURLY_TOKEN_LIMIT', '10000'))

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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
            print(f"❌ Error checking rate limit: {e}")
            # Fail open - allow the request if there's a database error
            return {
                'allowed': True,
                'tokens_used': 0,
                'tokens_requested': tokens_requested,
                'limit': 10000,
                'reset_seconds': 3600
            }

    def record_token_usage(self, user_id, username, tokens_used):
        """Record token usage for rate limiting"""
        try:
            with self.conn.cursor() as cur:
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
            print(f"❌ Error recording token usage: {e}")

    def record_api_cost(self, model, input_tokens, output_tokens, cost_usd, request_type, user_id=None, username=None):
        """Record API cost for monitoring spending"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO api_costs (model, input_tokens, output_tokens, cost_usd, request_type, user_id, username)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (model, input_tokens, output_tokens, cost_usd, request_type, user_id, username))
        except Exception as e:
            print(f"❌ Error recording API cost: {e}")

    def get_total_cost(self, since_timestamp=None):
        """Get total API costs, optionally since a specific timestamp"""
        try:
            with self.conn.cursor() as cur:
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
            print(f"❌ Error getting total cost: {e}")
            return 0.0

    def check_cost_alert_threshold(self, threshold_usd):
        """Check if we've crossed a cost threshold that hasn't been alerted yet"""
        try:
            with self.conn.cursor() as cur:
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
            print(f"❌ Error checking cost alert threshold: {e}")
            return {'should_alert': False, 'total_cost': 0.0}

    def record_cost_alert(self, threshold_usd, total_cost_usd):
        """Record that a cost alert has been sent"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO cost_alerts (threshold_usd, total_cost_usd)
                    VALUES (%s, %s)
                """, (threshold_usd, total_cost_usd))
        except Exception as e:
            print(f"❌ Error recording cost alert: {e}")

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
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
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
            print(f"❌ Error checking feature rate limit: {e}")
            # Fail open
            return {'allowed': True}

    def record_feature_usage(self, user_id, feature_type):
        """Record usage of a rate-limited feature"""
        try:
            with self.conn.cursor() as cur:
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
            print(f"❌ Error recording feature usage: {e}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
