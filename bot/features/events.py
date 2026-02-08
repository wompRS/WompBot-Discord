"""
Event Scheduling System with Periodic Reminders
Supports scheduled events with configurable reminder intervals
"""

import discord
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import json
from typing import Optional, List, Dict, Union
import re

logger = logging.getLogger(__name__)


class EventSystem:
    """Manages scheduled events with periodic reminders"""

    def __init__(self, db):
        self.db = db

    def _get_guild_timezone(self, guild_id: int) -> ZoneInfo:
        """Get the timezone configured for a guild, defaulting to UTC."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT timezone FROM guild_config WHERE guild_id = %s", (guild_id,))
                    result = cur.fetchone()
                    if result and result[0]:
                        return ZoneInfo(result[0])
        except (ZoneInfoNotFoundError, Exception) as e:
            logger.warning("Failed to get guild timezone for %s: %s", guild_id, e)
        return ZoneInfo('UTC')

    def parse_event_time(self, time_string: str, guild_id: int = None) -> Union[datetime, str, None]:
        """
        Parse natural language time expressions into datetime for event scheduling.
        Reuses logic from reminder system but focuses on future dates.

        Supports:
        - Relative: "in 5 days", "in 2 weeks"
        - Tomorrow: "tomorrow", "tomorrow at 3pm"
        - Days of week: "next Monday", "Friday at 5pm"
        - Specific time: "at 3pm tomorrow"

        Returns None if parsing fails.
        """
        time_string = time_string.lower().strip()

        if not time_string:
            return "Please provide a date/time for the event."

        tz = self._get_guild_timezone(guild_id) if guild_id else ZoneInfo('UTC')
        now = datetime.now(tz)

        # Pattern 1: "in X minutes/hours/days/weeks"
        relative_pattern = r'(?:in )?(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs|day|days|week|weeks|month|months)'
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
            elif unit in ['month', 'months']:
                return now + timedelta(days=amount * 30)  # Approximate

        # Pattern 2: "tomorrow"
        if 'tomorrow' in time_string:
            target = now + timedelta(days=1)

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
                # Tomorrow at current time
                target = target.replace(second=0, microsecond=0)

            return target

        # Pattern 3: Days of week
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
                # Calculate next occurrence of this day
                current_day = now.weekday()
                days_ahead = (day_num - current_day) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next week if same day

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

                return target

        # Pattern 4: Month + Day (e.g., "october 20", "may 15 at 7pm", "dec 25")
        months = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sept': 9, 'sep': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }

        for month_name, month_num in months.items():
            # Match "october 20" or "oct 20"
            month_pattern = rf'\b{month_name}\s+(\d{{1,2}})\b'
            month_match = re.search(month_pattern, time_string)

            if month_match:
                day = int(month_match.group(1))

                # Validate day
                if day < 1 or day > 31:
                    return f"Invalid day: {day}. Day must be between 1 and 31."

                # Determine year (this year or next year)
                year = now.year
                month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                               'July', 'August', 'September', 'October', 'November', 'December']
                try:
                    target = datetime(year, month_num, day, tzinfo=tz)
                except ValueError:
                    # Invalid date (e.g., Feb 30)
                    return f"{month_names[month_num]} doesn't have {day} days."

                # If date has passed this year, use next year
                if target.date() < now.date():
                    year += 1
                    try:
                        target = datetime(year, month_num, day, tzinfo=tz)
                    except ValueError:
                        return f"{month_names[month_num]} {year} doesn't have {day} days."

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
                    # Default to noon if no time specified
                    target = target.replace(hour=12, minute=0, second=0, microsecond=0)

                return target

        # Pattern 5: Specific time today
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

            # If time has passed today, schedule for tomorrow
            if target < now:
                target += timedelta(days=1)

            return target

        return None

    def parse_reminder_intervals(self, intervals_string: Optional[str]) -> List[str]:
        """
        Parse reminder interval string into list of intervals.

        Examples:
        - "1 week, 1 day, 1 hour" -> ["1 week", "1 day", "1 hour"]
        - "7 days, 24 hours, at event time" -> ["7 days", "24 hours", "at event time"]
        - None -> ["1 week", "1 day", "1 hour"] (default)
        """
        if not intervals_string:
            return ["1 week", "1 day", "1 hour"]

        # Split by comma and clean up
        intervals = [i.strip() for i in intervals_string.split(',')]

        # Validate each interval
        valid_intervals = []
        for interval in intervals:
            if interval.lower() in ['at event time', 'now']:
                valid_intervals.append('at event time')
            elif re.match(r'\d+\s*(minute|minutes|hour|hours|day|days|week|weeks)', interval.lower()):
                valid_intervals.append(interval)

        return valid_intervals if valid_intervals else ["1 week", "1 day", "1 hour"]

    def interval_to_timedelta(self, interval: str) -> Optional[timedelta]:
        """Convert interval string to timedelta (e.g., '1 week' -> timedelta(weeks=1))"""
        if interval.lower() in ['at event time', 'now']:
            return timedelta(0)

        match = re.match(r'(\d+)\s*(minute|minutes|hour|hours|day|days|week|weeks)', interval.lower())
        if not match:
            return None

        amount = int(match.group(1))
        unit = match.group(2)

        if unit in ['minute', 'minutes']:
            return timedelta(minutes=amount)
        elif unit in ['hour', 'hours']:
            return timedelta(hours=amount)
        elif unit in ['day', 'days']:
            return timedelta(days=amount)
        elif unit in ['week', 'weeks']:
            return timedelta(weeks=amount)

        return None

    async def create_event(
        self,
        event_name: str,
        event_date: datetime,
        created_by_user_id: int,
        created_by_username: str,
        channel_id: int,
        guild_id: int,
        description: Optional[str] = None,
        reminder_intervals: Optional[List[str]] = None,
        notify_role_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Create a new scheduled event.

        Returns event ID if successful, None otherwise.
        """
        if not reminder_intervals:
            reminder_intervals = ["1 week", "1 day", "1 hour"]

        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO events (
                            event_name, description, event_date,
                            created_by_user_id, created_by_username,
                            channel_id, guild_id,
                            reminder_intervals, notify_role_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        event_name,
                        description,
                        event_date,
                        created_by_user_id,
                        created_by_username,
                        channel_id,
                        guild_id,
                        json.dumps(reminder_intervals),
                        notify_role_id
                    ))

                    event_id = cur.fetchone()[0]
                    conn.commit()
                    return event_id

        except Exception as e:
            print(f"❌ Error creating event: {e}")
            conn.rollback()
            return None

    async def get_upcoming_events(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Get upcoming events for a guild, sorted by event date"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            id, event_name, description, event_date,
                            created_by_user_id, created_by_username,
                            channel_id, reminder_intervals, notify_role_id,
                            created_at
                        FROM events
                        WHERE guild_id = %s
                          AND cancelled = FALSE
                          AND event_date > NOW()
                        ORDER BY event_date ASC
                        LIMIT %s
                    """, (guild_id, limit))

                    events = []
                    for row in cur.fetchall():
                        events.append({
                            'id': row[0],
                            'event_name': row[1],
                            'description': row[2],
                            'event_date': row[3],
                            'created_by_user_id': row[4],
                            'created_by_username': row[5],
                            'channel_id': row[6],
                            'reminder_intervals': json.loads(row[7]) if row[7] else [],
                            'notify_role_id': row[8],
                            'created_at': row[9]
                        })

                    return events

        except Exception as e:
            print(f"❌ Error getting upcoming events: {e}")
            return []

    async def cancel_event(self, event_id: int, user_id: int) -> bool:
        """
        Cancel an event. Only the creator or admin can cancel.
        Returns True if successful, False if not found or not authorized.
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    # Only allow the event creator to cancel their own event
                    cur.execute("""
                        UPDATE events
                        SET cancelled = TRUE, cancelled_at = NOW()
                        WHERE id = %s AND cancelled = FALSE AND created_by = %s
                        RETURNING id
                    """, (event_id, user_id))

                    result = cur.fetchone()
                    conn.commit()
                    return result is not None

        except Exception as e:
            print(f"❌ Error cancelling event: {e}")
            conn.rollback()
            return False

    async def get_events_needing_reminders(self) -> List[Dict]:
        """
        Get events that need reminders sent.

        Logic:
        - Find events that haven't been cancelled
        - For each event, determine if any reminder interval is due
        - Only return events where a reminder should be sent now
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            id, event_name, description, event_date,
                            channel_id, guild_id, reminder_intervals,
                            last_reminder_sent, notify_role_id
                        FROM events
                        WHERE cancelled = FALSE
                          AND event_date > NOW()
                        ORDER BY event_date ASC
                    """)

                    events_needing_reminders = []
                    now = datetime.now()

                    for row in cur.fetchall():
                        event_id = row[0]
                        event_name = row[1]
                        description = row[2]
                        event_date = row[3]
                        channel_id = row[4]
                        guild_id = row[5]
                        reminder_intervals = json.loads(row[6]) if row[6] else []
                        last_reminder_sent = row[7]
                        notify_role_id = row[8]

                        # Determine which reminder to send
                        reminder_to_send = None

                        # Sort intervals by duration (longest first)
                        sorted_intervals = sorted(
                            reminder_intervals,
                            key=lambda x: (self.interval_to_timedelta(x) or timedelta(0)),
                            reverse=True
                        )

                        for interval in sorted_intervals:
                            delta = self.interval_to_timedelta(interval)
                            if delta is None:
                                continue

                            # Calculate when this reminder should be sent
                            reminder_time = event_date - delta

                            # Check if this reminder is due and hasn't been sent
                            if now >= reminder_time:
                                # Check if this is a new reminder to send
                                if not last_reminder_sent or interval != last_reminder_sent:
                                    # Make sure we don't skip intervals
                                    if not last_reminder_sent:
                                        # First reminder - send if due
                                        reminder_to_send = interval
                                        break
                                    else:
                                        # Check if this is the next interval after last sent
                                        last_delta = self.interval_to_timedelta(last_reminder_sent) or timedelta(0)
                                        if delta < last_delta:
                                            reminder_to_send = interval
                                            break

                        if reminder_to_send:
                            events_needing_reminders.append({
                                'id': event_id,
                                'event_name': event_name,
                                'description': description,
                                'event_date': event_date,
                                'channel_id': channel_id,
                                'guild_id': guild_id,
                                'reminder_interval': reminder_to_send,
                                'notify_role_id': notify_role_id
                            })

                    return events_needing_reminders

        except Exception as e:
            print(f"❌ Error getting events needing reminders: {e}")
            return []

    async def mark_reminder_sent(self, event_id: int, interval: str) -> bool:
        """Mark that a reminder has been sent for an event"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE events
                        SET last_reminder_sent = %s
                        WHERE id = %s
                    """, (interval, event_id))

                    conn.commit()
                    return True

        except Exception as e:
            print(f"❌ Error marking reminder sent: {e}")
            conn.rollback()
            return False

    def format_time_until(self, event_date: datetime) -> str:
        """Format time remaining until event in human-readable format"""
        now = datetime.now()
        delta = event_date - now

        if delta.total_seconds() < 0:
            return "Event has passed"

        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60

        if days > 0:
            if hours > 0:
                return f"{days} day{'s' if days != 1 else ''}, {hours} hour{'s' if hours != 1 else ''}"
            return f"{days} day{'s' if days != 1 else ''}"
        elif hours > 0:
            if minutes > 0:
                return f"{hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
