# ⏰ Context-Aware Reminders

A natural language reminder system that preserves message context and supports flexible scheduling with zero monthly cost.

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Time Parsing](#time-parsing)
- [Commands](#commands)
- [Delivery Methods](#delivery-methods)
- [Recurring Reminders](#recurring-reminders)
- [Database Schema](#database-schema)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Overview

**Key Features:**
1. **Natural language time parsing** - No need for exact formats
2. **Context preservation** - Links back to original message
3. **Flexible delivery** - DM or channel mention
4. **Recurring support** - Set daily/weekly reminders
5. **Zero cost** - Pure time parsing, no LLM needed
6. **Background checker** - Runs every minute

**Cost:** $0/month

## How It Works

### Setting a Reminder

```
/remind time:"in 5 minutes" message:"Check the oven"
```

**Process:**
1. Bot parses the time string ("in 5 minutes")
2. Calculates exact datetime (current time + 5 minutes)
3. Stores reminder in database with context link
4. Confirms with formatted timestamp
5. Background task checks every minute
6. Sends notification when due

### Context Preservation

Every reminder includes:
- Original message link
- Channel where it was set
- Timestamp of creation
- User who set it

When reminder fires, you get a link to jump back to the original conversation.

## Time Parsing

### Supported Formats

#### Relative Time

```
in 5 minutes
in 2 hours
in 3 days
in 1 week
```

**Syntax:** `in <number> <unit>`

**Units:**
- minutes, mins, min
- hours, hrs, hr
- days
- weeks

**Examples:**
- `/remind time:"in 30 minutes" message:"Meeting"`
- `/remind time:"in 2 hours" message:"Call Mom"`
- `/remind time:"in 3 days" message:"Check on project"`

#### Tomorrow

```
tomorrow
tomorrow at 3pm
tomorrow at 15:00
```

**Default:** Tomorrow at current time
**With time:** Tomorrow at specified time

**Examples:**
- `/remind time:"tomorrow" message:"Morning standup"`
- `/remind time:"tomorrow at 9am" message:"Doctor appointment"`
- `/remind time:"tomorrow at 14:30" message:"Team meeting"`

#### Days of Week

```
next Monday
next Tuesday at 3pm
Friday at 10am
```

**Format:** `next <day>` or `<day> at <time>`

**Supported days:**
- Monday/Mon
- Tuesday/Tue/Tues
- Wednesday/Wed
- Thursday/Thu/Thur/Thurs
- Friday/Fri
- Saturday/Sat
- Sunday/Sun

**Default time:** 9:00 AM if not specified

**Examples:**
- `/remind time:"next Monday" message:"Weekly report"`
- `/remind time:"Friday at 5pm" message:"Happy hour"`
- `/remind time:"next Wednesday at 2pm" message:"Review PR"`

#### Specific Time (Today or Tomorrow)

```
at 3pm
at 15:00
at 9:30am
```

**Behavior:**
- If time hasn't passed today → schedules for today
- If time already passed → schedules for tomorrow

**Examples:**
- `/remind time:"at 5pm" message:"End of workday"`
- `/remind time:"at 08:00" message:"Start work"`

#### Simple Numbers (Minutes)

```
5
30
120
```

**Interprets as minutes from now**

**Examples:**
- `/remind time:"5" message:"Quick break over"` (5 minutes)
- `/remind time:"30" message:"Pomodoro done"` (30 minutes)

### Combined Formats

```
tomorrow at 3pm
next Monday at 10am
Friday at 2:30pm
```

## Commands

### `/remind <time> <message> [recurring]`

Set a reminder with natural language time.

**Parameters:**
- `time` (required): When to remind
  - Examples: "in 5 minutes", "tomorrow at 3pm", "next Monday"
- `message` (required): What to remind about
  - Up to 2000 characters
- `recurring` (optional): Make it repeat
  - Default: `false`

**Examples:**

```
/remind time:"in 10 minutes" message:"Take meds"

/remind time:"tomorrow at 9am" message:"Morning standup"

/remind time:"next Friday at 5pm" message:"Submit timesheet" recurring:true

/remind time:"in 1 hour" message:"Check on build" recurring:true
```

**Success Response:**
```
✅ Reminder set! I'll remind you in 10 minutes (at 2:45 PM)
**Message:** Take meds
_Reminder ID: 42_
```

**Error Response (unparseable time):**
```
❌ Could not parse time 'yesterday'. Try formats like:
• `in 5 minutes`
• `in 2 hours`
• `tomorrow at 3pm`
• `next Monday`
• `at 15:00`
```

### `/reminders`

View all your active reminders.

**Shows:**
- Reminder ID
- Message content
- When it will trigger (relative and absolute)
- Time remaining
- Recurring status

**Example Output:**
```
⏰ YourName's Reminders

ID: 42
**Message:** Take medication
**When:** in 5 minutes (at 2:45 PM)
**Time left:** 5m
🔄 Recurring

ID: 43
**Message:** Weekly team meeting
**When:** in 2 days (at Monday 10:00 AM)
**Time left:** 2d 18h 15m

Showing 2 of 2 reminders
```

**Limit:** Shows first 10 reminders if you have more

### `/cancel_reminder <reminder_id>`

Cancel one of your reminders.

**Parameters:**
- `reminder_id` (required): ID of reminder to cancel
  - Get from `/reminders` command

**Examples:**
```
/cancel_reminder reminder_id:42
```

**Success:**
```
✅ Reminder #42 cancelled
```

**Error:**
```
❌ Could not cancel reminder #42. It may not exist or you don't own it.
```

**Note:** You can only cancel your own reminders.

## Delivery Methods

### Priority Order

1. **Direct Message (DM)** - Preferred
2. **Channel Mention** - Fallback if DM fails
3. **Skipped** - If both fail (logs warning)

### DM Delivery

**When it works:**
- User has DMs enabled for server members
- User hasn't blocked the bot

**Format:**
```
⏰ Reminder
Your message here

Set: 5 minutes ago
Context: [Jump to message](link)

Reminder ID: 42
```

### Channel Mention

**When it happens:**
- DM fails (user has DMs disabled)
- Same message as DM but with @mention

**Format:**
```
@YourName
⏰ Reminder
Your message here
...
```

### Context Links

If reminder was set in response to a message, includes link:
```
Context: [Jump to message](https://discord.com/channels/xxx/yyy/zzz)
```

Click to return to original conversation.

## Recurring Reminders

### How They Work

1. Set reminder with `recurring:true`
2. When first reminder fires:
   - Sends notification
   - Marks original as completed
   - Creates new reminder with same interval
3. Repeats indefinitely until cancelled

### Examples

**Daily Standup:**
```
/remind time:"tomorrow at 9am" message:"Daily standup" recurring:true
```
Triggers every day at 9 AM.

**Weekly Report:**
```
/remind time:"next Friday at 4pm" message:"Submit weekly report" recurring:true
```
Triggers every Friday at 4 PM.

**Hourly Check:**
```
/remind time:"in 1 hour" message:"Check build status" recurring:true
```
Triggers every hour.

### Stopping Recurring Reminders

Use `/reminders` to get the ID, then `/cancel_reminder`:

```
/reminders
// See: ID: 42, 🔄 Recurring

/cancel_reminder reminder_id:42
```

**Note:** Cancelling stops future occurrences.

## Database Schema

### `reminders` Table

```sql
CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    channel_id BIGINT NOT NULL,
    message_id BIGINT,                    -- Original message for context
    reminder_text TEXT NOT NULL,
    time_string VARCHAR(255) NOT NULL,    -- Original input
    remind_at TIMESTAMP NOT NULL,
    recurring BOOLEAN DEFAULT FALSE,
    recurring_interval VARCHAR(255),      -- "in 1 hour", "tomorrow at 9am"
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
```sql
CREATE INDEX idx_reminders_user_id ON reminders(user_id);
CREATE INDEX idx_reminders_remind_at ON reminders(remind_at);
CREATE INDEX idx_reminders_completed ON reminders(completed);
CREATE INDEX idx_reminders_due ON reminders(remind_at, completed) WHERE completed = FALSE;
```

**Partial index** on due reminders for fast background task queries.

## Configuration

### Check Frequency

Edit `main.py`:

```python
@tasks.loop(minutes=1)  # Change this value
async def check_reminders():
```

**Options:**
- `minutes=1` - Every minute (default, recommended)
- `seconds=30` - Every 30 seconds (more responsive, slightly higher CPU)
- `minutes=5` - Every 5 minutes (less precise)

**Recommendation:** Keep at 1 minute. Precision is within 60 seconds.

### Time Parsing Customization

Edit `bot/features/reminders.py`:

**Add custom time patterns:**

```python
def parse_reminder_time(self, time_string: str) -> Optional[datetime]:
    # ... existing code ...

    # Add your custom pattern
    if 'eod' in time_string or 'end of day' in time_string:
        target = now.replace(hour=17, minute=0, second=0)
        if target <= now:
            target += timedelta(days=1)
        return target
```

**Supported customizations:**
- Custom keywords ("eod", "noon", "midnight")
- Different time zones
- Custom default times
- Date formats beyond supported ones

### Default Time for Days

When no time specified (e.g., "next Monday"), defaults to 9:00 AM.

Change in `reminders.py`:

```python
# Default to 9am
target = target.replace(hour=9, minute=0, second=0)
```

Change `hour=9` to your preferred default.

## Troubleshooting

### Reminders Not Firing

**Check background task:**
```python
# In logs, should see:
⏰ Reminder checker task started
```

If not, task didn't start. Check `on_ready` in `main.py`.

**Check database:**
```sql
SELECT * FROM reminders WHERE completed = FALSE ORDER BY remind_at;
```

If empty, no active reminders.

**Check logs for errors:**
```
docker-compose logs -f bot | grep -i reminder
```

### DMs Not Working

**Symptom:** Reminders sent in channel instead of DM

**Cause:** User has DMs disabled or blocked bot

**Solution:**
1. Enable DMs in Privacy Settings
2. Unblock bot if blocked
3. Stay in server with bot

**Workaround:** Channel mentions still work.

### Time Parsing Failures

**Common mistakes:**

❌ "reminder me in 5 minutes" - Don't include "reminder"
✅ "in 5 minutes"

❌ "05/15/2024" - Date formats not supported
✅ "next Monday", "tomorrow"

❌ "2 weeks and 3 days" - Complex formats not supported
✅ "in 17 days" (manually calculate)

**Test parsing:**
```python
from features.reminders import ReminderSystem
rs = ReminderSystem(None)
result = rs.parse_reminder_time("your time string")
print(result)  # Should be datetime or None
```

### Recurring Reminders Not Rescheduling

**Check:**
1. `recurring = TRUE` in database
2. `recurring_interval` has value
3. Interval is parseable

**Query:**
```sql
SELECT id, recurring, recurring_interval, completed
FROM reminders
WHERE id = <your_id>;
```

**Fix:**
If `recurring_interval` is NULL, cancel and recreate with interval.

### Database Migration Issues

**Create table manually:**
```bash
docker-compose exec -T postgres psql -U botuser -d discord_bot << 'EOF'
CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    channel_id BIGINT NOT NULL,
    message_id BIGINT,
    reminder_text TEXT NOT NULL,
    time_string VARCHAR(255) NOT NULL,
    remind_at TIMESTAMP NOT NULL,
    recurring BOOLEAN DEFAULT FALSE,
    recurring_interval VARCHAR(255),
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_reminders_user_id ON reminders(user_id);
CREATE INDEX idx_reminders_remind_at ON reminders(remind_at);
CREATE INDEX idx_reminders_completed ON reminders(completed);
CREATE INDEX idx_reminders_due ON reminders(remind_at, completed) WHERE completed = FALSE;
EOF
```

Then restart bot.

### Reminders Firing Late

**Tolerance:** ±60 seconds (check interval is 1 minute)

**If consistently late:**
1. Check server time: `date`
2. Check database time: `SELECT NOW();`
3. Verify timezone consistency

**Improve precision:**
```python
@tasks.loop(seconds=30)  # Check every 30 seconds
```

Trade-off: Slightly higher CPU usage.

## Best Practices

### For Users

1. **Use simple language** - "in 5 minutes" is clearer than "5 mins"
2. **Check /reminders** - Verify reminder was set correctly
3. **Enable DMs** - Get reminders privately
4. **Use recurring wisely** - Don't forget to cancel when done
5. **Keep messages concise** - Easier to read when reminder fires

### For Admins

1. **Monitor logs** - Watch for parsing failures
2. **Educate users** - Share supported formats
3. **Test time parsing** - Try edge cases before deployment
4. **Back up database** - Reminders are valuable user data
5. **Clean up old data** - Periodically delete old completed reminders

**Cleanup query (run monthly):**
```sql
DELETE FROM reminders
WHERE completed = TRUE
AND completed_at < NOW() - INTERVAL '30 days';
```

### For Developers

1. **Add custom patterns** - Tailor to your community's language
2. **Test timezone handling** - Ensure consistency
3. **Log parsing failures** - Debug and improve patterns
4. **Handle edge cases** - Leap years, DST, etc.
5. **Validate user input** - Prevent SQL injection

## Future Enhancements

Potential improvements (not yet implemented):

- **Snooze functionality** - "Snooze for 10 minutes"
- **Reminder templates** - Save common reminders
- **Timezone support** - User-specific timezones
- **Natural date parsing** - "May 15th", "Christmas"
- **Smart scheduling** - "every weekday at 9am"
- **Reminder groups** - Batch related reminders
- **Shared reminders** - Remind multiple users
- **Voice reminders** - TTS in voice channels

## Examples

### Common Use Cases

**Medication:**
```
/remind time:"in 8 hours" message:"Take evening meds" recurring:true
```

**Meetings:**
```
/remind time:"tomorrow at 2pm" message:"Client call with Acme Corp"
```

**Breaks:**
```
/remind time:"in 25 minutes" message:"Pomodoro break"
```

**Deadlines:**
```
/remind time:"next Friday at 5pm" message:"Submit project proposal"
```

**Follow-ups:**
```
/remind time:"in 2 days" message:"Follow up with Sarah about PR review"
```

**Weekly Tasks:**
```
/remind time:"next Monday at 9am" message:"Review team metrics" recurring:true
```

---

**Related Documentation:**
- [Configuration Guide](../CONFIGURATION.md) - Environment variables and settings
- [Development Guide](../DEVELOPMENT.md) - Adding features and database changes
