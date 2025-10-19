# 🛠️ Development Guide

Guide for developing and extending WompBot.

## Project Structure

```
discord-bot/
├── README.md                    # Main documentation
├── .env                         # Environment variables (not in git)
├── .gitignore                   # Git ignore rules
├── docker-compose.yml           # Docker orchestration
├── Dockerfile                   # Bot container build
│
├── docs/                        # Documentation
│   ├── features/                # Feature-specific docs
│   │   ├── CHAT_STATISTICS.md
│   │   ├── CLAIMS_TRACKING.md
│   │   ├── FACT_CHECK.md
│   │   ├── QUOTES.md
│   │   ├── USER_ANALYTICS.md
│   │   └── CONVERSATIONAL_AI.md
│   ├── CONFIGURATION.md         # Configuration guide
│   └── DEVELOPMENT.md           # This file
│
├── sql/
│   └── init.sql                 # Database schema initialization
│
└── bot/                         # Bot source code
    ├── main.py                  # Main entry point, event handlers
    ├── database.py              # PostgreSQL interface
    ├── llm.py                   # OpenRouter LLM client
    ├── search.py                # Tavily web search
    ├── requirements.txt         # Python dependencies
    └── features/                # Feature modules
        ├── claims.py            # Claims tracking
        ├── fact_check.py        # Fact-checking
        └── chat_stats.py        # Chat statistics
```

---

## Development Setup

### Prerequisites

- WSL2 (Debian/Ubuntu) or Linux
- Docker & Docker Compose
- Python 3.11+ (for local testing)
- Text editor (VS Code recommended)

### Initial Setup

1. **Clone/navigate to project:**
   ```bash
   cd /mnt/e/discord-bot
   ```

2. **Create .env file:**
   ```bash
   cp .env.example .env  # If example exists
   # Or create manually - see docs/CONFIGURATION.md
   ```

3. **Build containers:**
   ```bash
   docker-compose build
   ```

4. **Start bot:**
   ```bash
   docker-compose up -d
   ```

5. **Check logs:**
   ```bash
   docker-compose logs -f bot
   ```

---

## Development Workflow

### Making Changes

**Hot reload is enabled** - edit Python files without rebuilding container:

1. **Edit code:**
   ```bash
   nano bot/main.py
   # or
   code bot/main.py  # VS Code
   ```

2. **Restart bot:**
   ```bash
   docker-compose restart bot
   ```

3. **Check logs:**
   ```bash
   docker-compose logs --tail=50 bot
   ```

**No rebuild needed** unless changing:
- `requirements.txt` (dependencies)
- `Dockerfile`
- `docker-compose.yml`

---

### Testing Changes

**Local testing:**
```bash
# Enter bot container
docker-compose exec bot bash

# Test imports
python3 -c "from features.chat_stats import ChatStatistics"

# Test specific function
python3
>>> from database import Database
>>> db = Database()
>>> db.get_message_stats(days=7)
```

**Discord testing:**
- Use dedicated test server
- Test slash commands with `/command`
- Test prefix commands with `!command`
- Test emoji reactions

---

## Adding New Features

### Step 1: Plan the Feature

**Document:**
- What does it do?
- What commands will it have?
- What database tables are needed?
- What APIs/libraries does it use?
- Cost implications (if using LLM)

**Example planning doc:**
```markdown
# Feature: Reminder System

## Purpose
Allow users to set reminders that bot will DM them

## Commands
- /remind <time> <message> - Set reminder
- /reminders - List active reminders
- /cancel_reminder <id> - Cancel reminder

## Database
- Table: reminders (id, user_id, message, remind_at, created_at)

## Tech Stack
- discord.py tasks for scheduling
- No LLM needed
- Cost: $0
```

---

### Step 2: Database Schema

**Add tables to `sql/init.sql`:**

```sql
-- New feature table
CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    remind_at TIMESTAMP NOT NULL,
    channel_id BIGINT,
    is_complete BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);
CREATE INDEX IF NOT EXISTS idx_reminders_remind_at ON reminders(remind_at);
```

**Apply to running database:**
```bash
docker-compose exec -T postgres psql -U botuser -d discord_bot << 'EOF'
-- Paste your CREATE TABLE statement here
EOF
```

Or restart with fresh database:
```bash
docker-compose down -v  # WARNING: Deletes all data
docker-compose up -d
```

---

### Step 3: Create Feature Module

**Create file:** `bot/features/reminders.py`

```python
"""
Reminder System
Users can set reminders that bot will DM them
"""

from datetime import datetime
import discord

class ReminderSystem:
    def __init__(self, db, bot):
        self.db = db
        self.bot = bot

    async def create_reminder(self, user_id, username, message, remind_at, channel_id):
        """Create a new reminder"""
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO reminders
                    (user_id, username, message, remind_at, channel_id)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (user_id, username, message, remind_at, channel_id))

                reminder_id = cur.fetchone()[0]
                print(f"✅ Reminder #{reminder_id} created for {username}")
                return reminder_id

        except Exception as e:
            print(f"❌ Error creating reminder: {e}")
            return None

    async def get_user_reminders(self, user_id):
        """Get all active reminders for user"""
        try:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    SELECT id, message, remind_at, created_at
                    FROM reminders
                    WHERE user_id = %s AND is_complete = FALSE
                    ORDER BY remind_at ASC
                """, (user_id,))

                columns = [desc[0] for desc in cur.description]
                results = cur.fetchall()
                return [dict(zip(columns, row)) for row in results]

        except Exception as e:
            print(f"❌ Error fetching reminders: {e}")
            return []

    # Add more methods...
```

---

### Step 4: Integrate into main.py

**Import the feature:**
```python
# bot/main.py (top of file)
from features.reminders import ReminderSystem
```

**Initialize:**
```python
# bot/main.py (after other feature init)
reminder_system = ReminderSystem(db, bot)
```

**Add commands:**
```python
# bot/main.py (slash command section)
@bot.tree.command(name="remind", description="Set a reminder")
@app_commands.describe(
    time="When to remind (e.g., '30m', '2h', '1d')",
    message="What to remind you about"
)
async def remind(interaction: discord.Interaction, time: str, message: str):
    """Set a reminder"""
    await interaction.response.defer()

    try:
        # Parse time string to datetime
        remind_at = parse_time_string(time)

        # Create reminder
        reminder_id = await reminder_system.create_reminder(
            interaction.user.id,
            str(interaction.user),
            message,
            remind_at,
            interaction.channel.id
        )

        if reminder_id:
            await interaction.followup.send(
                f"✅ Reminder set for {remind_at.strftime('%Y-%m-%d %H:%M')}"
            )
        else:
            await interaction.followup.send("❌ Failed to create reminder")

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
```

**Add background task (if needed):**
```python
# bot/main.py (with other tasks)
@tasks.loop(minutes=1)
async def check_reminders():
    """Check and send due reminders"""
    try:
        # Get due reminders
        # Send DMs
        # Mark as complete
        ...
    except Exception as e:
        print(f"❌ Reminder check error: {e}")

@check_reminders.before_loop
async def before_check_reminders():
    await bot.wait_until_ready()

# Start in on_ready
check_reminders.start()
```

---

### Step 5: Add Database Methods

**In `bot/database.py` (if needed):**

```python
def store_reminder(self, user_id, username, message, remind_at, channel_id):
    """Store reminder in database"""
    # Implementation...

def get_due_reminders(self):
    """Get reminders that are due"""
    # Implementation...
```

---

### Step 6: Update Help Command

**In `bot/main.py` help command:**

```python
embed.add_field(
    name="/remind <time> <message>",
    value="Set a reminder. Examples: '30m', '2h', 'tomorrow 9am'",
    inline=False
)
```

---

### Step 7: Test Thoroughly

**Test checklist:**
- ✅ Command appears in Discord autocomplete
- ✅ Command executes without errors
- ✅ Database is updated correctly
- ✅ Error handling works (invalid input)
- ✅ Help text is clear
- ✅ Permissions work correctly (if admin-only)
- ✅ Background tasks run (if applicable)
- ✅ Edge cases handled

---

### Step 8: Document the Feature

**Create:** `docs/features/REMINDERS.md`

**Include:**
- Overview
- Commands with examples
- How it works
- Configuration options
- Database schema
- Cost analysis (if applicable)
- Troubleshooting
- API reference

**See existing feature docs for format**

---

### Step 9: Update Main README

**Add to features list:**

```markdown
### ⏰ Reminder System
- **Set Reminders**: `/remind <time> <message>` - Get DM at specified time
- **List Reminders**: `/reminders` - View active reminders
- **Cancel**: `/cancel_reminder <id>` - Cancel a reminder
```

**Link to docs:**
```markdown
See [docs/features/REMINDERS.md](docs/features/REMINDERS.md) for details.
```

---

## Database Migrations

### Adding Columns

**Option 1: Direct ALTER (for running database):**
```bash
docker-compose exec -T postgres psql -U botuser -d discord_bot << 'EOF'
ALTER TABLE existing_table ADD COLUMN new_column VARCHAR(255);
EOF
```

**Option 2: Update init.sql (for fresh installs):**
```sql
-- sql/init.sql
CREATE TABLE existing_table (
    id SERIAL PRIMARY KEY,
    existing_column TEXT,
    new_column VARCHAR(255)  -- Added
);
```

---

### Adding Indexes

```bash
docker-compose exec -T postgres psql -U botuser -d discord_bot << 'EOF'
CREATE INDEX IF NOT EXISTS idx_table_column ON table_name(column_name);
EOF
```

---

### Migration Best Practices

1. **Always use IF NOT EXISTS** for idempotent migrations
2. **Add to init.sql** for new installations
3. **Test on dev database** before production
4. **Backup before migration:**
   ```bash
   docker-compose exec postgres pg_dump -U botuser discord_bot > backup_before_migration.sql
   ```
5. **Document migration** in commit message

---

## Testing

### Unit Testing

**Create:** `bot/tests/test_feature.py`

```python
import pytest
from features.reminders import ReminderSystem

def test_create_reminder():
    """Test reminder creation"""
    # Setup
    reminder_system = ReminderSystem(mock_db, mock_bot)

    # Execute
    result = reminder_system.create_reminder(...)

    # Assert
    assert result is not None
```

**Run tests:**
```bash
# In bot container
pytest bot/tests/
```

---

### Integration Testing

**Test Discord commands:**
1. Create test server
2. Invite bot
3. Test each command manually
4. Verify database updates
5. Check logs for errors

---

## Debugging

### Enable Debug Logging

**Add to `bot/main.py`:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

### Common Issues

**Import errors:**
```bash
# Check Python path
docker-compose exec bot python3 -c "import sys; print('\n'.join(sys.path))"

# Test import
docker-compose exec bot python3 -c "from features.new_feature import NewFeature"
```

**Database errors:**
```bash
# Check connection
docker-compose exec bot python3 -c "from database import Database; db = Database(); print('Connected')"

# Query database directly
docker-compose exec postgres psql -U botuser -d discord_bot
> SELECT * FROM your_table LIMIT 5;
```

**Discord API errors:**
```bash
# Check logs
docker-compose logs bot | grep -i error

# Verify token
docker-compose exec bot env | grep DISCORD_TOKEN
```

---

## Code Style

### Python Conventions

- **PEP 8** style guide
- **Type hints** encouraged
- **Docstrings** for all functions
- **Error handling** with try/except
- **Logging** instead of print statements (for production)

**Example:**
```python
async def create_reminder(
    self,
    user_id: int,
    message: str,
    remind_at: datetime
) -> Optional[int]:
    """
    Create a new reminder for a user.

    Args:
        user_id: Discord user ID
        message: Reminder message text
        remind_at: When to send reminder

    Returns:
        Reminder ID if successful, None otherwise
    """
    try:
        # Implementation
        return reminder_id
    except Exception as e:
        logging.error(f"Failed to create reminder: {e}")
        return None
```

---

### SQL Conventions

- Use **prepared statements** (parameterized queries)
- Always use **IF NOT EXISTS** for schema
- Add **indexes** for commonly queried columns
- Use **RETURNING** for INSERT operations
- **Foreign keys** for relational integrity

**Example:**
```python
# Good: Parameterized query
cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))

# Bad: String interpolation (SQL injection risk)
cur.execute(f"SELECT * FROM users WHERE user_id = {user_id}")
```

---

## Performance Optimization

### Database Optimization

**Indexes:**
```sql
-- Add indexes for frequently queried columns
CREATE INDEX idx_messages_timestamp ON messages(timestamp);
CREATE INDEX idx_messages_user_channel ON messages(user_id, channel_id);
```

**Query optimization:**
```sql
-- Use LIMIT for large result sets
SELECT * FROM messages ORDER BY timestamp DESC LIMIT 100;

-- Use EXISTS instead of COUNT when checking existence
SELECT EXISTS(SELECT 1 FROM claims WHERE message_id = %s);
```

**Vacuum regularly:**
```bash
docker-compose exec postgres psql -U botuser -d discord_bot -c "VACUUM ANALYZE;"
```

---

### LLM Optimization

**Reduce token usage:**
- Lower context window
- Shorter system prompts
- Smaller max_tokens
- Use cheaper models where possible

**Cache results:**
- Cache LLM responses for common queries
- Cache search results
- Use background tasks to pre-compute

**Batch processing:**
- Process multiple items in one LLM call
- Use async/await for parallel processing

---

## Git Workflow

### Branching

```bash
# Create feature branch
git checkout -b feature/reminder-system

# Make changes
git add .
git commit -m "Add reminder system feature"

# Push to remote
git push origin feature/reminder-system

# Create pull request (if using GitHub/GitLab)
```

---

### Commit Messages

**Format:**
```
<type>: <description>

[optional body]
[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```
feat: add reminder system with /remind command

fix: resolve database connection timeout issue

docs: update CHAT_STATISTICS.md with new configuration options

refactor: extract stats caching to separate module
```

---

## Deployment

### Production Checklist

- [ ] Remove database port exposure in `docker-compose.yml`
- [ ] Use strong passwords in `.env`
- [ ] Enable logging to file
- [ ] Set up automated backups
- [ ] Monitor resource usage
- [ ] Test all commands in production environment
- [ ] Document any production-specific configuration

---

### Updating Production

```bash
# Pull latest code
git pull origin main

# Rebuild if dependencies changed
docker-compose build bot

# Restart bot
docker-compose up -d bot

# Check logs
docker-compose logs -f bot
```

---

## Contributing

### Pull Request Process

1. Create feature branch
2. Make changes
3. Test thoroughly
4. Update documentation
5. Create pull request
6. Address review comments
7. Merge when approved

---

### Code Review Checklist

- [ ] Code follows style conventions
- [ ] All functions have docstrings
- [ ] Error handling is comprehensive
- [ ] Database queries are parameterized
- [ ] Feature is documented
- [ ] README is updated
- [ ] No sensitive data in code
- [ ] Tests pass (if applicable)

---

## Resources

### Documentation
- [Discord.py Docs](https://discordpy.readthedocs.io/)
- [OpenRouter API](https://openrouter.ai/docs)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
- [Docker Compose](https://docs.docker.com/compose/)

### Libraries
- discord.py
- psycopg2 (PostgreSQL)
- scikit-learn (ML/TF-IDF)
- networkx (graphs)
- pandas (data)

---

## Support

**Development questions:**
- Check existing feature implementations in `bot/features/`
- Review database schema in `sql/init.sql`
- Examine `main.py` for event handlers and command structure

**Debugging:**
- Use `docker-compose logs -f bot` for real-time logs
- Add print statements for debugging (replace with logging later)
- Test in isolated Discord test server
