"""
GDPR Privacy Compliance Module
Handles data subject rights per GDPR Articles 15, 17, 20, 21
"""

import json
import io
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import psycopg2.extras


class GDPRPrivacyManager:
    """Manages GDPR compliance features for user data"""

    CURRENT_POLICY_VERSION = "1.0"

    def __init__(self, database):
        """
        Initialize GDPR Privacy Manager

        Args:
            database: Database instance
        """
        self.db = database

    def log_audit_action(self, user_id: int, action: str, details: str = None,
                        performed_by: int = None, success: bool = True, error: str = None):
        """
        Log data processing action for GDPR compliance audit trail

        Args:
            user_id: User whose data was accessed/modified
            action: Type of action ('export', 'delete', 'consent_given', etc.)
            details: Additional action details
            performed_by: User ID who performed the action (None = self-service)
            success: Whether the action succeeded
            error: Error message if action failed
        """
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO data_audit_log
                    (user_id, action, action_details, performed_by_user_id, success, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, action, details, performed_by or user_id, success, error))
                print(f"📝 Audit log: {action} for user {user_id}")
        except Exception as e:
            print(f"❌ Failed to log audit action: {e}")

    def record_consent(self, user_id: int, username: str, consent_given: bool = True,
                      consent_method: str = 'command', extended_retention: bool = False) -> bool:
        """
        Record user consent for data processing (GDPR Art. 6, 7)

        Args:
            user_id: Discord user ID
            username: Discord username
            consent_given: Whether consent was given
            consent_method: How consent was obtained
            extended_retention: User opted in for extended data retention

        Returns:
            Success boolean
        """
        try:
            with self.db.conn.cursor() as cur:
                if consent_given:
                    cur.execute("""
                        INSERT INTO user_consent
                        (user_id, username, consent_given, consent_date, consent_version,
                         consent_method, extended_retention)
                        VALUES (%s, %s, TRUE, NOW(), %s, %s, %s)
                        ON CONFLICT (user_id) DO UPDATE SET
                            consent_given = TRUE,
                            consent_date = NOW(),
                            consent_withdrawn = FALSE,
                            consent_withdrawn_date = NULL,
                            consent_version = EXCLUDED.consent_version,
                            consent_method = EXCLUDED.consent_method,
                            extended_retention = EXCLUDED.extended_retention,
                            updated_at = NOW()
                    """, (user_id, username, self.CURRENT_POLICY_VERSION, consent_method, extended_retention))

                    # Also update user_profiles
                    cur.execute("""
                        UPDATE user_profiles
                        SET consent_given = TRUE,
                            consent_date = NOW(),
                            data_processing_allowed = TRUE,
                            opted_out = FALSE
                        WHERE user_id = %s
                    """, (user_id,))
                else:
                    # Withdrawing consent
                    cur.execute("""
                        UPDATE user_consent
                        SET consent_given = FALSE,
                            consent_withdrawn = TRUE,
                            consent_withdrawn_date = NOW(),
                            updated_at = NOW()
                        WHERE user_id = %s
                    """, (user_id,))

                    cur.execute("""
                        UPDATE user_profiles
                        SET consent_given = FALSE,
                            data_processing_allowed = FALSE,
                            opted_out = TRUE
                        WHERE user_id = %s
                    """, (user_id,))

                action = 'consent_given' if consent_given else 'consent_withdrawn'
                self.log_audit_action(user_id, action, f"Method: {consent_method}")
                return True
        except Exception as e:
            print(f"❌ Error recording consent: {e}")
            self.log_audit_action(user_id, 'consent_error', str(e), success=False, error=str(e))
            return False

    def check_consent(self, user_id: int) -> Optional[Dict]:
        """
        Check if user has given consent for data processing

        Returns:
            Dict with consent info or None
        """
        try:
            with self.db.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT consent_given, consent_date, consent_withdrawn,
                           extended_retention, consent_version
                    FROM user_consent
                    WHERE user_id = %s
                """, (user_id,))
                return cur.fetchone()
        except Exception as e:
            print(f"❌ Error checking consent: {e}")
            return None

    def get_consent_status(self, user_id: int) -> Dict:
        """
        Convenience wrapper used by runtime pathways.

        Returns:
            dict with `has_consent` and other metadata keys.
        """
        record = self.check_consent(user_id)
        if not record:
            return {
                'has_consent': False,
                'extended_retention': False,
                'consent_date': None,
                'consent_version': None,
            }

        has_consent = bool(record.get('consent_given')) and not record.get('consent_withdrawn')
        return {
            'has_consent': has_consent,
            'consent_date': record.get('consent_date'),
            'extended_retention': record.get('extended_retention', False),
            'consent_version': record.get('consent_version'),
            'consent_withdrawn': record.get('consent_withdrawn', False),
        }

    def export_user_data(self, user_id: int) -> Optional[Dict]:
        """
        Export all user data in machine-readable format (GDPR Art. 15 - Right of Access)

        Args:
            user_id: Discord user ID

        Returns:
            Dict containing all user data or None if error
        """
        try:
            self.log_audit_action(user_id, 'data_export_started', 'Full data export requested')

            data_export = {
                'export_date': datetime.now().isoformat(),
                'user_id': user_id,
                'gdpr_article': 'Article 15 - Right of Access',
                'data_format': 'JSON (machine-readable)',
                'profile': None,
                'consent_record': None,
                'messages': [],
                'claims': [],
                'quotes': [],
                'hot_takes': [],
                'behavior_analysis': [],
                'debates': [],
                'search_logs': [],
                'reminders': [],
                'events': [],
                'fact_checks': [],
                'iracing_link': None,
                'audit_logs': []
            }

            with self.db.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # User profile
                cur.execute("SELECT * FROM user_profiles WHERE user_id = %s", (user_id,))
                data_export['profile'] = dict(cur.fetchone()) if cur.rowcount > 0 else None

                # Consent record
                cur.execute("SELECT * FROM user_consent WHERE user_id = %s", (user_id,))
                data_export['consent_record'] = dict(cur.fetchone()) if cur.rowcount > 0 else None

                # Messages (limit to last 10,000 for performance)
                cur.execute("""
                    SELECT message_id, channel_id, channel_name, content, timestamp
                    FROM messages
                    WHERE user_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 10000
                """, (user_id,))
                data_export['messages'] = [dict(row) for row in cur.fetchall()]

                # Claims
                cur.execute("""
                    SELECT id, message_id, channel_name, claim_text, claim_type,
                           confidence_level, timestamp, verification_status,
                           verification_date, is_edited, is_deleted
                    FROM claims
                    WHERE user_id = %s
                    ORDER BY timestamp DESC
                """, (user_id,))
                data_export['claims'] = [dict(row) for row in cur.fetchall()]

                # Quotes
                cur.execute("""
                    SELECT id, message_id, channel_name, quote_text, category,
                           timestamp, added_by_username, reaction_count
                    FROM quotes
                    WHERE user_id = %s
                    ORDER BY timestamp DESC
                """, (user_id,))
                data_export['quotes'] = [dict(row) for row in cur.fetchall()]

                # Hot takes
                cur.execute("""
                    SELECT ht.*, c.claim_text
                    FROM hot_takes ht
                    JOIN claims c ON ht.claim_id = c.id
                    WHERE c.user_id = %s
                    ORDER BY ht.created_at DESC
                """, (user_id,))
                data_export['hot_takes'] = [dict(row) for row in cur.fetchall()]

                # Behavior analysis
                cur.execute("""
                    SELECT analysis_period_start, analysis_period_end,
                           profanity_score, message_count, tone_analysis,
                           honesty_patterns, conversation_style, analyzed_at
                    FROM user_behavior
                    WHERE user_id = %s
                    ORDER BY analyzed_at DESC
                """, (user_id,))
                data_export['behavior_analysis'] = [dict(row) for row in cur.fetchall()]

                # Debates participated in
                cur.execute("""
                    SELECT d.id, d.topic, d.started_at, d.ended_at,
                           dp.message_count, dp.score, dp.is_winner
                    FROM debate_participants dp
                    JOIN debates d ON dp.debate_id = d.id
                    WHERE dp.user_id = %s
                    ORDER BY d.started_at DESC
                """, (user_id,))
                data_export['debates'] = [dict(row) for row in cur.fetchall()]

                # Search logs
                cur.execute("""
                    SELECT query, results_count, timestamp
                    FROM search_logs
                    WHERE triggered_by_user_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 1000
                """, (user_id,))
                data_export['search_logs'] = [dict(row) for row in cur.fetchall()]

                # Reminders
                cur.execute("""
                    SELECT id, reminder_text, time_string, remind_at,
                           recurring, recurring_interval, completed, created_at
                    FROM reminders
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                """, (user_id,))
                data_export['reminders'] = [dict(row) for row in cur.fetchall()]

                # Events created
                cur.execute("""
                    SELECT id, event_name, description, event_date,
                           reminder_intervals, cancelled, created_at
                    FROM events
                    WHERE created_by_user_id = %s
                    ORDER BY created_at DESC
                """, (user_id,))
                data_export['events'] = [dict(row) for row in cur.fetchall()]

                # Fact checks requested
                cur.execute("""
                    SELECT message_id, claim_text, fact_check_result, created_at
                    FROM fact_checks
                    WHERE requested_by_user_id = %s
                    ORDER BY created_at DESC
                    LIMIT 100
                """, (user_id,))
                data_export['fact_checks'] = [dict(row) for row in cur.fetchall()]

                # iRacing link
                cur.execute("""
                    SELECT iracing_cust_id, iracing_name, linked_at
                    FROM iracing_links
                    WHERE discord_user_id = %s
                """, (user_id,))
                data_export['iracing_link'] = dict(cur.fetchone()) if cur.rowcount > 0 else None

                # Recent audit logs (last 100 actions)
                cur.execute("""
                    SELECT action, action_details, timestamp, success
                    FROM data_audit_log
                    WHERE user_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 100
                """, (user_id,))
                data_export['audit_logs'] = [dict(row) for row in cur.fetchall()]

                # Add summary statistics
                data_export['summary'] = {
                    'total_messages': len(data_export['messages']),
                    'total_claims': len(data_export['claims']),
                    'total_quotes': len(data_export['quotes']),
                    'total_hot_takes': len(data_export['hot_takes']),
                    'total_debates': len(data_export['debates']),
                    'account_age_days': (datetime.now() - data_export['profile']['first_seen']).days if data_export['profile'] else 0
                }

            # Record successful export
            cur.execute("""
                INSERT INTO data_export_requests
                (user_id, username, status, completed_date, expires_at)
                VALUES (%s, %s, 'completed', NOW(), NOW() + INTERVAL '48 hours')
            """, (user_id, data_export['profile'].get('username', 'Unknown') if data_export['profile'] else 'Unknown'))

            self.log_audit_action(user_id, 'data_export_completed',
                                f"Exported {data_export['summary']['total_messages']} messages")

            return data_export

        except Exception as e:
            print(f"❌ Error exporting user data: {e}")
            self.log_audit_action(user_id, 'data_export_failed', str(e), success=False, error=str(e))
            import traceback
            traceback.print_exc()
            return None

    def delete_user_data(self, user_id: int, anonymize_only: bool = False) -> bool:
        """
        Delete all user data (GDPR Art. 17 - Right to Erasure)

        Args:
            user_id: Discord user ID
            anonymize_only: If True, anonymize instead of delete (for legal retention)

        Returns:
            Success boolean
        """
        try:
            self.log_audit_action(user_id, 'data_deletion_started',
                                f"Anonymize only: {anonymize_only}")

            with self.db.conn.cursor() as cur:
                if anonymize_only:
                    # Use the anonymization function from SQL migration
                    cur.execute("SELECT anonymize_user_data(%s)", (user_id,))
                else:
                    # Full deletion (CASCADE will handle related records)
                    # Delete in order to respect foreign keys

                    # Delete interactions
                    cur.execute("DELETE FROM message_interactions WHERE user_id = %s OR replied_to_user_id = %s",
                              (user_id, user_id))

                    # Delete fact checks
                    cur.execute("DELETE FROM fact_checks WHERE user_id = %s OR requested_by_user_id = %s",
                              (user_id, user_id))

                    # Delete reminders
                    cur.execute("DELETE FROM reminders WHERE user_id = %s", (user_id,))

                    # Delete events
                    cur.execute("DELETE FROM events WHERE created_by_user_id = %s", (user_id,))

                    # Delete debate participants (debates cascade)
                    cur.execute("DELETE FROM debate_participants WHERE user_id = %s", (user_id,))

                    # Delete hot takes (through claims cascade)
                    # Delete claims (hot_takes will cascade)
                    cur.execute("DELETE FROM claims WHERE user_id = %s", (user_id,))

                    # Delete quotes
                    cur.execute("DELETE FROM quotes WHERE user_id = %s", (user_id,))

                    # Delete search logs
                    cur.execute("DELETE FROM search_logs WHERE triggered_by_user_id = %s", (user_id,))

                    # Delete behavior analysis
                    cur.execute("DELETE FROM user_behavior WHERE user_id = %s", (user_id,))

                    # Delete messages
                    cur.execute("DELETE FROM messages WHERE user_id = %s", (user_id,))

                    # Delete iRacing link
                    cur.execute("DELETE FROM iracing_links WHERE discord_user_id = %s", (user_id,))

                    # Keep audit logs for legal compliance (7 years retention)
                    # Keep consent records for proof of consent

                    # Mark user profile as deleted but keep for audit
                    cur.execute("""
                        UPDATE user_profiles
                        SET username = 'Deleted_User_' || user_id,
                            opted_out = TRUE,
                            data_processing_allowed = FALSE
                        WHERE user_id = %s
                    """, (user_id,))

                    # Record deletion in audit log
                    cur.execute("""
                        INSERT INTO data_deletion_requests
                        (user_id, username, status, completed_date, deletion_reason)
                        VALUES (%s, %s, 'completed', NOW(), 'User requested deletion (GDPR Art. 17)')
                    """, (user_id, f'User_{user_id}'))

                print(f"🗑️ User {user_id} data {'anonymized' if anonymize_only else 'deleted'}")

            self.log_audit_action(user_id, 'data_deletion_completed',
                                f"Anonymize only: {anonymize_only}")

            return True

        except Exception as e:
            print(f"❌ Error deleting user data: {e}")
            self.log_audit_action(user_id, 'data_deletion_failed', str(e), success=False, error=str(e))
            import traceback
            traceback.print_exc()
            return False

    def get_privacy_policy(self, version: str = None) -> Optional[Dict]:
        """
        Get privacy policy text

        Args:
            version: Policy version (defaults to current)

        Returns:
            Dict with policy info or None
        """
        try:
            with self.db.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if version:
                    cur.execute("""
                        SELECT * FROM privacy_policy_versions WHERE version = %s
                    """, (version,))
                else:
                    cur.execute("""
                        SELECT * FROM privacy_policy_versions WHERE is_active = TRUE
                        ORDER BY effective_date DESC LIMIT 1
                    """, )

                result = cur.fetchone()
                return dict(result) if result else None
        except Exception as e:
            print(f"❌ Error fetching privacy policy: {e}")
            return None

    def schedule_data_deletion(self, user_id: int, grace_period_days: int = 30) -> bool:
        """
        Schedule user data deletion with grace period

        Args:
            user_id: Discord user ID
            grace_period_days: Days before permanent deletion

        Returns:
            Success boolean
        """
        try:
            with self.db.conn.cursor() as cur:
                scheduled_date = datetime.now() + timedelta(days=grace_period_days)

                cur.execute("""
                    INSERT INTO data_deletion_requests
                    (user_id, username, status, scheduled_deletion_date, deletion_reason)
                    VALUES (%s, (SELECT username FROM user_profiles WHERE user_id = %s),
                            'scheduled', %s, 'User requested deletion with grace period')
                """, (user_id, user_id, scheduled_date))

                # Mark user as opted out immediately
                cur.execute("""
                    UPDATE user_profiles
                    SET opted_out = TRUE,
                        data_processing_allowed = FALSE
                    WHERE user_id = %s
                """, (user_id,))

                self.log_audit_action(user_id, 'data_deletion_scheduled',
                                    f"Scheduled for {scheduled_date.isoformat()}")

                print(f"📅 User {user_id} deletion scheduled for {scheduled_date}")
                return True

        except Exception as e:
            print(f"❌ Error scheduling deletion: {e}")
            self.log_audit_action(user_id, 'deletion_schedule_failed', str(e), success=False, error=str(e))
            return False

    def cancel_scheduled_deletion(self, user_id: int) -> bool:
        """
        Cancel a scheduled deletion request

        Args:
            user_id: Discord user ID

        Returns:
            Success boolean
        """
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    UPDATE data_deletion_requests
                    SET status = 'cancelled',
                        cancelled_date = NOW()
                    WHERE user_id = %s AND status = 'scheduled'
                """, (user_id,))

                if cur.rowcount > 0:
                    # Restore data processing
                    cur.execute("""
                        UPDATE user_profiles
                        SET opted_out = FALSE,
                            data_processing_allowed = TRUE
                        WHERE user_id = %s
                    """, (user_id,))

                    self.log_audit_action(user_id, 'data_deletion_cancelled',
                                        'User cancelled scheduled deletion')
                    print(f"✅ User {user_id} deletion cancelled")
                    return True
                else:
                    print(f"⚠️ No scheduled deletion found for user {user_id}")
                    return False

        except Exception as e:
            print(f"❌ Error cancelling deletion: {e}")
            return False

    def process_scheduled_deletions(self) -> int:
        """
        Process all scheduled deletions that are due

        Returns:
            Number of deletions processed
        """
        try:
            with self.db.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Find all due deletions
                cur.execute("""
                    SELECT user_id, username
                    FROM data_deletion_requests
                    WHERE status = 'scheduled'
                    AND scheduled_deletion_date <= NOW()
                """)

                due_deletions = cur.fetchall()

                count = 0
                for deletion in due_deletions:
                    user_id = deletion['user_id']
                    if self.delete_user_data(user_id, anonymize_only=False):
                        count += 1

                print(f"🗑️ Processed {count} scheduled deletions")
                return count

        except Exception as e:
            print(f"❌ Error processing scheduled deletions: {e}")
            return 0

    def cleanup_old_data(self) -> Dict[str, int]:
        """
        Clean up old data based on retention policies

        Returns:
            Dict with counts of deleted records per data type
        """
        try:
            deleted_counts = {}

            with self.db.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Get retention policies
                cur.execute("""
                    SELECT data_type, retention_days, auto_delete_enabled
                    FROM data_retention_config
                    WHERE auto_delete_enabled = TRUE
                """)

                policies = cur.fetchall()

                for policy in policies:
                    data_type = policy['data_type']
                    retention_days = policy['retention_days']
                    cutoff_date = datetime.now() - timedelta(days=retention_days)

                    # Delete based on data type
                    if data_type == 'messages':
                        cur.execute("""
                            DELETE FROM messages
                            WHERE timestamp < %s
                            AND opted_out = FALSE
                            AND user_id NOT IN (
                                SELECT user_id FROM user_consent
                                WHERE extended_retention = TRUE
                            )
                        """, (cutoff_date,))
                        deleted_counts['messages'] = cur.rowcount

                    elif data_type == 'user_behavior':
                        cur.execute("""
                            DELETE FROM user_behavior
                            WHERE analyzed_at < %s
                        """, (cutoff_date,))
                        deleted_counts['user_behavior'] = cur.rowcount

                    elif data_type == 'search_logs':
                        cur.execute("""
                            DELETE FROM search_logs
                            WHERE timestamp < %s
                        """, (cutoff_date,))
                        deleted_counts['search_logs'] = cur.rowcount

                    elif data_type == 'stats_cache':
                        cur.execute("""
                            DELETE FROM stats_cache
                            WHERE computed_at < %s
                        """, (cutoff_date,))
                        deleted_counts['stats_cache'] = cur.rowcount

                    elif data_type == 'debate_records':
                        cur.execute("""
                            DELETE FROM debates
                            WHERE ended_at < %s
                        """, (cutoff_date,))
                        deleted_counts['debate_records'] = cur.rowcount

                    # Update last cleanup time
                    cur.execute("""
                        UPDATE data_retention_config
                        SET last_cleanup_run = NOW()
                        WHERE data_type = %s
                    """, (data_type,))

                print(f"🧹 Data cleanup complete: {deleted_counts}")
                return deleted_counts

        except Exception as e:
            print(f"❌ Error during data cleanup: {e}")
            import traceback
            traceback.print_exc()
            return {}
