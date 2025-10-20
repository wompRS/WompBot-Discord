"""
Context-Aware Reminder System
Uses natural language time parsing with dateparser library
Zero cost - no LLM needed
"""

import discord
from datetime import datetime, timedelta
import re
from typing import Optional, Tuple


class ReminderSystem:
    """Manages context-aware reminders for users"""

    def __init__(self, db):
        self.db = db

    def parse_reminder_time(self, time_string: str) -> Optional[datetime]:
        """
        Parse natural language time expressions into datetime.

        Supports:
        - Relative: "in 5 minutes", "in 2 hours", "in 3 days"
        - Simple: "tomorrow", "next week"
        - Time: "at 3pm", "at 15:00"
        - Combined: "tomorrow at 3pm"

        Returns None if parsing fails.
        """
        time_string = time_string.lower().strip()
        now = datetime.now()

        # Pattern 1: "in X minutes/hours/days/weeks" or "X minutes/hours/days/weeks"
        relative_pattern = r'(?:in )?(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs|day|days|week|weeks)'
        match = re.search(relative_pattern, time_string)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)

            if unit in ['minute', 'minutes', 'min', 'mins']:
                return now + timedelta(minutes=amount)
            elif unit in ['hour', 'hours', 'hr', 'hrs']:
                return now + timedelta(hours=amount)
            elif unit in ['day', 'days']:
                return now + timedelta(days=amount)
            elif unit in ['week', 'weeks']:
                return now + timedelta(weeks=amount)

        # Pattern 2: "tomorrow" (at same time, or specific time if combined)
        if 'tomorrow' in time_string:
            target = now + timedelta(days=1)

            # Check for specific time: "tomorrow at 3pm"
            time_match = re.search(r'at (\d{1,2}):?(\d{2})?\s*(am|pm)?', time_string)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                period = time_match.group(3)

                if period == 'pm' and hour < 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0

                target = target.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                # Tomorrow at current time
                target = target.replace(second=0, microsecond=0)

            return target

        # Pattern 3: "next week/monday/tuesday/etc"
        if 'next week' in time_string:
            return now + timedelta(weeks=1)

        # Pattern 4: Days of week (next Monday, Tuesday, etc)
        days_of_week = {
            'monday': 0, 'mon': 0,
            'tuesday': 1, 'tue': 1, 'tues': 1,
            'wednesday': 2, 'wed': 2,
            'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
            'friday': 4, 'fri': 4,
            'saturday': 5, 'sat': 5,
            'sunday': 6, 'sun': 6
        }

        for day_name, day_num in days_of_week.items():
            if day_name in time_string:
                # Find next occurrence of this day
                current_day = now.weekday()
                days_ahead = (day_num - current_day) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next week, not today

                target = now + timedelta(days=days_ahead)

                # Check for specific time
                time_match = re.search(r'at (\d{1,2}):?(\d{2})?\s*(am|pm)?', time_string)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2) or 0)
                    period = time_match.group(3)

                    if period == 'pm' and hour < 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0

                    target = target.replace(hour=hour, minute=minute, second=0, microsecond=0)
                else:
                    # Default to 9am
                    target = target.replace(hour=9, minute=0, second=0, microsecond=0)

                return target

        # Pattern 5: "at 3pm" (today or tomorrow if time passed)
        time_match = re.search(r'at (\d{1,2}):?(\d{2})?\s*(am|pm)?', time_string)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            period = time_match.group(3)

            if period == 'pm' and hour < 12:
                hour += 12
            elif period == 'am' and hour == 12:
                hour = 0

            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # If time already passed today, schedule for tomorrow
            if target <= now:
                target += timedelta(days=1)

            return target

        # Pattern 6: Simple number = minutes
        if time_string.isdigit():
            minutes = int(time_string)
            return now + timedelta(minutes=minutes)

        return None

    async def create_reminder(
        self,
        user_id: int,
        username: str,
        channel_id: int,
        message_id: int,
        reminder_text: str,
        time_string: str,
        recurring: bool = False,
        recurring_interval: Optional[str] = None
    ) -> Optional[Tuple[int, datetime]]:
        """
        Create a new reminder.

        Returns (reminder_id, remind_at) if successful, None otherwise.
        """
        try:
            remind_at = self.parse_reminder_time(time_string)

            if not remind_at:
                return None

            # Don't allow reminders in the past
            if remind_at <= datetime.now():
                return None

            with self.db.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO reminders
                    (user_id, username, channel_id, message_id,
                     reminder_text, time_string, remind_at,
                     recurring, recurring_interval, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    user_id,
                    username,
                    channel_id,
                    message_id,
                    reminder_text,
                    time_string,
                    remind_at,
                    recurring,
                    recurring_interval,
                    datetime.now()
                ))

                result = cur.fetchone()
                if result:
                    reminder_id = result[0]
                    print(f"⏰ Reminder #{reminder_id} created for {username} at {remind_at}")
                    return (reminder_id, remind_at)

            return None

        except Exception as e:
            print(f"❌ Error creating reminder: {e}")
            return None

    async def get_due_reminders(self) -> list:
        """
        Get all reminders that are due (remind_at <= now and not completed).
        """
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, username, channel_id, message_id,
                           reminder_text, time_string, remind_at, recurring, recurring_interval
                    FROM reminders
                    WHERE remind_at <= %s
                    AND completed = FALSE
                    ORDER BY remind_at ASC
                """, (datetime.now(),))

                columns = [desc[0] for desc in cur.description]
                results = cur.fetchall()

                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            print(f"❌ Error fetching due reminders: {e}")
            return []

    async def mark_completed(self, reminder_id: int):
        """Mark a reminder as completed."""
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    UPDATE reminders
                    SET completed = TRUE,
                        completed_at = %s
                    WHERE id = %s
                """, (datetime.now(), reminder_id))

                print(f"✅ Reminder #{reminder_id} marked as completed")

        except Exception as e:
            print(f"❌ Error marking reminder complete: {e}")

    async def reschedule_recurring(self, reminder: dict):
        """
        Reschedule a recurring reminder by creating a new one.
        """
        try:
            if not reminder['recurring'] or not reminder['recurring_interval']:
                return

            # Parse the interval and calculate next time
            next_remind_at = self.parse_reminder_time(reminder['recurring_interval'])

            if not next_remind_at:
                return

            # Create new reminder
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO reminders
                    (user_id, username, channel_id, message_id,
                     reminder_text, time_string, remind_at,
                     recurring, recurring_interval, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    reminder['user_id'],
                    reminder['username'],
                    reminder['channel_id'],
                    reminder['message_id'],
                    reminder['reminder_text'],
                    reminder['time_string'],
                    next_remind_at,
                    True,
                    reminder['recurring_interval'],
                    datetime.now()
                ))

                result = cur.fetchone()
                if result:
                    print(f"🔄 Recurring reminder rescheduled for {next_remind_at}")

        except Exception as e:
            print(f"❌ Error rescheduling recurring reminder: {e}")

    async def get_user_reminders(self, user_id: int) -> list:
        """Get all active reminders for a user."""
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, reminder_text, remind_at, recurring, created_at
                    FROM reminders
                    WHERE user_id = %s
                    AND completed = FALSE
                    ORDER BY remind_at ASC
                """, (user_id,))

                columns = [desc[0] for desc in cur.description]
                results = cur.fetchall()

                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            print(f"❌ Error fetching user reminders: {e}")
            return []

    async def cancel_reminder(self, reminder_id: int, user_id: int) -> bool:
        """
        Cancel a reminder (user can only cancel their own).
        Returns True if successful.
        """
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM reminders
                    WHERE id = %s AND user_id = %s AND completed = FALSE
                """, (reminder_id, user_id))

                if cur.rowcount > 0:
                    print(f"🗑️ Reminder #{reminder_id} cancelled by user {user_id}")
                    return True

            return False

        except Exception as e:
            print(f"❌ Error cancelling reminder: {e}")
            return False

    def format_time_remaining(self, remind_at: datetime) -> str:
        """Format time remaining as human-readable string."""
        delta = remind_at - datetime.now()

        if delta.total_seconds() < 0:
            return "overdue"

        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes = remainder // 60

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}m")

        return " ".join(parts)
