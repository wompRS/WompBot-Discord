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
    
    def get_recent_messages(self, channel_id, limit=10, exclude_opted_out=True, exclude_bot_id=None):
        """Get recent messages from a channel for context"""
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

                if exclude_opted_out:
                    query += " AND COALESCE(m.opted_out, FALSE) = FALSE AND COALESCE(up.opted_out, FALSE) = FALSE"

                if exclude_bot_id:
                    query += " AND m.user_id != %s"
                    params.append(exclude_bot_id)

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

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
