# Event Scheduling System

The Event Scheduling System allows you to schedule events with automatic periodic reminders sent to channels. Perfect for game nights, movie watches, clan meetings, or any scheduled community activity.

## Overview

- Schedule events with natural language date/time
- Automatic reminders at configurable intervals (default: 1 week, 1 day, 1 hour before)
- Channel announcements with optional role mentions
- Discord timestamp formatting for automatic timezone conversion
- Event management (list, cancel)

## Commands

### `/schedule_event`
Schedule an event with automatic reminders.

**Parameters:**
- `name` - Name of the event (required)
- `date` - When the event happens (required)
- `description` - Optional description of the event
- `reminders` - Optional comma-separated reminder intervals

**Examples:**
```
/schedule_event name:"Game Night" date:"Friday at 8pm" description:"Valorant 5-stack"

/schedule_event name:"Movie Watch Party" date:"tomorrow at 7pm" description:"Watching Inception" reminders:"1 day, 1 hour"

/schedule_event name:"Clan Meeting" date:"next Monday at 6pm" reminders:"1 week, 3 days, 1 day, 1 hour"

/schedule_event name:"Tournament" date:"in 5 days at 3pm" description:"Monthly 1v1 tournament"
```

### `/events`
View upcoming scheduled events.

**Parameters:**
- `limit` - Maximum number of events to show (default: 10)

**Example:**
```
/events
/events limit:20
```

### `/cancel_event`
Cancel a scheduled event.

**Parameters:**
- `event_id` - ID of the event to cancel (shown in event embed footer)

**Example:**
```
/cancel_event event_id:5
```

## Supported Date/Time Formats

The event system uses natural language parsing for dates and times:

### Relative Time
- `in 5 days`
- `in 2 weeks`
- `in 3 hours`
- `in 30 minutes`

### Tomorrow
- `tomorrow` - Tomorrow at current time
- `tomorrow at 7pm` - Tomorrow at specific time
- `tomorrow at 15:00` - Tomorrow at specific time (24-hour format)

### Days of Week
- `Monday` - Next Monday at current time
- `Friday at 8pm` - Next Friday at 8pm
- `next Wednesday at 6:30pm` - Next Wednesday at 6:30pm

### Specific Times
- `at 3pm` - Today at 3pm (or tomorrow if time has passed)
- `at 15:00` - Today at 15:00 (24-hour format)

### Combined
- `in 3 days at 6pm`
- `next Friday at 8:30pm`
- `tomorrow at 7:00pm`

## Reminder Intervals

Events support configurable reminder intervals. If not specified, defaults to: **1 week, 1 day, 1 hour**

### Default Intervals
1. **1 week before** - Initial heads-up
2. **1 day before** - Day-before reminder
3. **1 hour before** - Final reminder

### Custom Intervals
You can specify custom intervals when creating an event:

**Examples:**
```
reminders:"1 week, 1 day, 1 hour"          (default)
reminders:"3 days, 1 day, 2 hours"         (shorter notice period)
reminders:"2 weeks, 1 week, 1 day, 1 hour" (longer notice period)
reminders:"24 hours, 1 hour"               (day-of reminders only)
reminders:"1 day"                          (single reminder)
```

**Supported units:**
- `minutes` - 30 minutes, 45 minutes
- `hours` - 1 hour, 2 hours, 6 hours
- `days` - 1 day, 3 days, 7 days
- `weeks` - 1 week, 2 weeks

### How Reminders Work

1. The bot checks every 5 minutes for events needing reminders
2. Reminders are sent in order from longest to shortest interval
3. Each reminder is only sent once
4. Reminders are posted in the channel where the event was created
5. The last reminder sent is tracked to ensure no duplicates

**Example Timeline:**
- Event scheduled: "Game Night" on Friday at 8pm
- Intervals: "1 week, 1 day, 1 hour"
- Monday 8pm: "1 week" reminder sent
- Thursday 8pm: "1 day" reminder sent
- Friday 7pm: "1 hour" reminder sent
- Friday 8pm: Event time!

## Channel Announcements

Event reminders are posted to the channel where the event was created. They include:

- Event name
- Event date/time with Discord timestamps (auto-converts to user's timezone)
- Time remaining until event
- Description (if provided)
- Event ID (for cancellation)

### Discord Timestamps

The bot uses Discord's timestamp formatting, which means:
- Times automatically display in each user's local timezone
- Multiple format options: relative ("in 2 days"), absolute ("Friday, May 12, 2025 8:00 PM")
- Updates automatically as time passes

## Role Mentions (Future Feature)

Future versions will support pinging a specific role when reminders are sent:

```
/schedule_event name:"Raid Night" date:"Saturday at 9pm" notify_role:@Raiders
```

This will ping @Raiders when each reminder is sent.

## Use Cases

### Game Sessions
```
/schedule_event name:"Ranked Grind" date:"tonight at 10pm" description:"Let's climb!" reminders:"2 hours, 30 minutes"
```

### Movie Nights
```
/schedule_event name:"Movie Watch Party" date:"Friday at 8pm" description:"Watching The Matrix" reminders:"1 day, 2 hours"
```

### Tournaments
```
/schedule_event name:"Monthly 1v1 Tournament" date:"in 2 weeks at 6pm" description:"Sign up in #tournaments" reminders:"2 weeks, 1 week, 3 days, 1 day, 2 hours"
```

### Meetings
```
/schedule_event name:"Officer Meeting" date:"next Monday at 7pm" reminders:"3 days, 1 day, 1 hour"
```

### Community Events
```
/schedule_event name:"Community Game Night" date:"Saturday at 8pm" description:"Among Us, Jackbox, and more!" reminders:"1 week, 3 days, 1 day, 4 hours"
```

## Managing Events

### Viewing Upcoming Events

Use `/events` to see all upcoming events:

```
/events
```

This shows:
- Event name
- When it happens (Discord timestamp)
- Time remaining
- Description
- Who created it
- Event ID

### Cancelling Events

Anyone can cancel an event using its ID:

```
/cancel_event event_id:5
```

The event will be marked as cancelled and no further reminders will be sent.

**Note:** In future versions, only the event creator or admins will be able to cancel events.

## Tips & Best Practices

### Clear Event Names
Use descriptive names that make it clear what the event is:
- ✅ "Valorant Ranked Session"
- ✅ "Movie Night: Inception"
- ✅ "Weekly Clan Meeting"
- ❌ "Event"
- ❌ "Thing"

### Useful Descriptions
Include relevant details in the description:
- What game/activity
- Who should attend
- Where to sign up
- What to bring/prepare

### Appropriate Reminder Intervals
Match intervals to the event type:
- **Short-notice events** (tonight, tomorrow): `2 hours, 30 minutes`
- **Same-week events**: `3 days, 1 day, 2 hours`
- **Next-week events**: `1 week, 1 day, 1 hour`
- **Long-term events**: `2 weeks, 1 week, 3 days, 1 day, 2 hours`

### Testing
Test with a short interval first:
```
/schedule_event name:"Test Event" date:"in 10 minutes" reminders:"5 minutes, 1 minute"
```

This helps verify the bot is working correctly before scheduling real events.

## Technical Details

### Database Schema

Events are stored in the `events` table:

```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_name VARCHAR(255) NOT NULL,
    description TEXT,
    event_date TIMESTAMP NOT NULL,
    created_by_user_id BIGINT NOT NULL,
    created_by_username VARCHAR(255) NOT NULL,
    channel_id BIGINT NOT NULL,
    guild_id BIGINT NOT NULL,
    reminder_intervals JSONB DEFAULT '["1 week", "1 day", "1 hour"]',
    last_reminder_sent VARCHAR(50),
    notify_role_id BIGINT,
    cancelled BOOLEAN DEFAULT FALSE,
    cancelled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Background Task

The event reminder checker runs every 5 minutes:
1. Queries for non-cancelled future events
2. Determines which reminders are due based on `last_reminder_sent`
3. Sends reminders in order (longest to shortest interval)
4. Updates `last_reminder_sent` after each reminder

### Time Parsing

Natural language time parsing is handled by `EventSystem.parse_event_time()`:
- Regex-based parsing (no external dependencies)
- Supports relative times, days of week, tomorrow, specific times
- Returns `datetime` object or `None` if parsing fails

## Limitations & Known Issues

### Current Limitations

1. **No Recurring Events** - Each event is one-time only
2. **No Edit Function** - Events cannot be edited after creation (must cancel and recreate)
3. **No Permission Checks** - Anyone can cancel any event (will be fixed)
4. **No Role Mentions** - Role pinging not yet implemented (database field exists)
5. **Fixed Check Interval** - Reminders checked every 5 minutes (may be up to 5 minutes late)

### Time Parsing Edge Cases

- "next Monday" might mean today if run on a Monday
- Times without AM/PM assume 24-hour format if > 12
- Month-based relative times use 30-day approximation

### Future Improvements

- [ ] Recurring events (weekly, monthly)
- [ ] Event editing
- [ ] Permission checks (only creator/admin can cancel)
- [ ] Role mentions in reminders
- [ ] Custom check intervals per event
- [ ] Event attendance tracking (RSVPs)
- [ ] Multiple notification channels
- [ ] Event history/past events view

## Troubleshooting

### "Could not parse time"

Try one of the supported formats:
- `tomorrow at 7pm`
- `Friday at 8pm`
- `in 3 days at 6pm`
- `next Monday at 5pm`

Make sure to include both date and time if needed.

### "Event date must be in the future"

The parsed time is in the past. Check:
- If using "at 3pm", is it currently past 3pm? (will schedule for tomorrow)
- If using "Monday", are you on Monday? (will schedule for next Monday)

### Reminders Not Sending

Check:
1. Bot has permission to post in the channel
2. Event hasn't been cancelled (`/events` to check)
3. Reminder intervals are properly formatted
4. Current time is actually past the reminder time

### Wrong Timezone

Discord timestamps automatically convert to user's timezone. If the event time looks wrong:
- Check the server's system timezone
- The bot stores times in server local time
- Discord will display in each user's local timezone

## Example Workflow

Here's a complete workflow for scheduling a community event:

```
# 1. Schedule the event
/schedule_event
  name:"Friday Night Valorant"
  date:"Friday at 9pm"
  description:"5-stack ranked grind. Iron to Radiant, all welcome!"
  reminders:"3 days, 1 day, 2 hours"

# Bot responds with:
# 📅 Event Scheduled
# **Friday Night Valorant**
# When: Friday, May 12, 2025 9:00 PM (in 3 days)
# Description: 5-stack ranked grind. Iron to Radiant, all welcome!
# Reminders: 3 days, 1 day, 2 hours
# Event ID: 12 • Created by YourName

# 2. Check upcoming events
/events

# 3. If needed, cancel the event
/cancel_event event_id:12

# Bot responds with:
# ✅ Event #12 cancelled
```

## Integration with Other Features

### Reminders vs Events

**Use Reminders when:**
- It's a personal task
- You want a DM notification
- It's a one-time reminder
- You don't need to notify others

**Use Events when:**
- It's a community activity
- You want channel announcements
- You need periodic reminders
- Multiple people should be notified

Both systems work independently and can be used together!
