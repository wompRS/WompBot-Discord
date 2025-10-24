import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
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
    
    def store_message(self, message, opted_out=False):
        """Store a Discord message"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO messages (message_id, user_id, username, channel_id, channel_name, content, timestamp, opted_out)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (message_id) DO NOTHING
                    RETURNING message_id
                """, (
                    message.id,
                    message.author.id,
                    str(message.author),
                    message.channel.id,
                    message.channel.name,
                    message.content,
                    message.created_at,
                    opted_out
                ))
                
                result = cur.fetchone()
                if result:
                    print(f"💾 Stored message from {message.author}: {message.content[:50]}")
                
                # Update user profile
                cur.execute("""
                    INSERT INTO user_profiles (user_id, username, total_messages, first_seen, last_seen, opted_out)
                    VALUES (%s, %s, 1, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        total_messages = user_profiles.total_messages + 1,
                        last_seen = EXCLUDED.last_seen,
                        opted_out = EXCLUDED.opted_out,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    message.author.id,
                    str(message.author),
                    message.created_at,
                    message.created_at,
                    opted_out
                ))
        except Exception as e:
            print(f"❌ Error storing message: {e}")
    
    def get_recent_messages(self, channel_id, limit=10, exclude_opted_out=True, exclude_bot_id=None):
        """Get recent messages from a channel for context"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT message_id, user_id, username, content, timestamp
                    FROM messages
                    WHERE channel_id = %s
                """
                if exclude_opted_out:
                    query += " AND opted_out = FALSE"
                if exclude_bot_id:
                    query += f" AND user_id != {exclude_bot_id}"
                query += " ORDER BY timestamp DESC LIMIT %s"

                cur.execute(query, (channel_id, limit))
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
                    SELECT content, timestamp
                    FROM messages
                    WHERE user_id = %s 
                    AND opted_out = FALSE
                    AND timestamp > CURRENT_TIMESTAMP - INTERVAL '%s days'
                    ORDER BY timestamp DESC
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
                    SELECT DISTINCT user_id, username
                    FROM messages
                    WHERE opted_out = FALSE
                    AND timestamp > CURRENT_TIMESTAMP - INTERVAL '%s days'
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
                        username,
                        COUNT(*) as message_count,
                        COUNT(DISTINCT DATE(timestamp)) as active_days
                    FROM messages
                    WHERE opted_out = FALSE
                    AND timestamp > CURRENT_TIMESTAMP - INTERVAL '%s days'
                    GROUP BY user_id, username
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
                        user_id,
                        username,
                        content,
                        timestamp
                    FROM messages
                    WHERE opted_out = FALSE
                    AND timestamp > CURRENT_TIMESTAMP - INTERVAL '%s days'
                    ORDER BY timestamp DESC
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

                    print(f"✅ Using database cached meta for {cache_key}")
                    return result['meta_data']

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

                print(f"✅ Stored meta cache for {cache_key} (expires in {ttl_hours}h)")
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

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
