# Bug Tracking System

Internal bug tracking system for bot administrators to report, track, and resolve issues.

## Overview

The bug tracking system provides a simple way for bot administrators to track issues, feature requests, and improvements directly within Discord. It's designed for development teams managing the bot across multiple servers.

## Features

- **Priority Levels**: Critical, High, Medium, Low
- **Status Tracking**: Open, In Progress, Resolved, Won't Fix
- **Notes System**: Add updates and progress notes to bugs
- **Server Context**: Bugs tagged with originating server
- **Admin-Only Access**: Restricted to bot administrators

## Commands

### `!bug`

Report a new bug or issue.

**Parameters:**
- `description` (required): Description of the bug
- `priority` (optional): critical, high, medium, low (default: medium)

**Example:**
```
!bug description:Weather command fails with non-US locations priority:high
!bug description:Typo in help message for !remind command
```

### `!bugs`

List tracked bugs.

**Parameters:**
- `status` (optional): Filter by status (all, open, resolved)
- `limit` (optional): Number of bugs to show (default: 10)

**Example:**
```
!bugs
!bugs status:open
!bugs status:resolved limit:20
```

### `!bugfix`

Mark a bug as resolved.

**Parameters:**
- `bug_id` (required): ID of the bug to resolve
- `resolution` (required): Resolution status (fixed, wont_fix, duplicate, invalid)

**Example:**
```
!bugfix bug_id:42 resolution:fixed
!bugfix bug_id:15 resolution:wont_fix
```

*Note: The `/bug_note` command has been removed. Bug notes are no longer supported as a standalone command.*

## Priority Levels

| Priority | Description | Response Time |
|----------|-------------|---------------|
| **Critical** | Bot is down or major feature broken | Immediate |
| **High** | Feature significantly impaired | 24-48 hours |
| **Medium** | Bug affects functionality but workaround exists | 1 week |
| **Low** | Minor issues, cosmetic problems | When convenient |

## Status Values

| Status | Description |
|--------|-------------|
| **Open** | Bug reported, awaiting investigation |
| **In Progress** | Actively being worked on |
| **Resolved** | Bug has been fixed |
| **Won't Fix** | Intentional behavior or not feasible to fix |

## Resolution Types

| Resolution | When to Use |
|------------|-------------|
| **Fixed** | Bug was fixed in code |
| **Won't Fix** | Intentional behavior or too complex to fix |
| **Duplicate** | Already reported under different ID |
| **Invalid** | Not actually a bug, user error, or cannot reproduce |

## Example Workflow

```
1. User reports issue in support channel

Admin: !bug description:Translation command returns error for Japanese priority:high

Bot: 🐛 Bug #47 created
     Priority: High
     Status: Open
     Description: Translation command returns error for Japanese
     Reporter: AdminUser
     Server: Main Server

2. Admin investigates and adds notes

3. Admin fixes and resolves

Admin: !bugfix bug_id:47 resolution:fixed

Bot: ✅ Bug #47 resolved
     Resolution: Fixed
     Resolution notes: Updated API endpoint for Japanese language support
```

## Database Table

```sql
bugs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT,
    reported_by BIGINT,
    description TEXT,
    priority VARCHAR(20),
    status VARCHAR(20) DEFAULT 'open',
    resolution VARCHAR(20),
    notes TEXT[],
    created_at TIMESTAMP,
    resolved_at TIMESTAMP
)
```

## Access Control

Bug tracking commands are restricted to:
- Bot administrators (server admins with manage_guild permission)
- Super admins defined in SUPER_ADMIN_IDS environment variable

Regular users cannot access bug tracking commands.

## Cost

Zero cost - pure database operations with no LLM involvement.

## Related Features

- [Conversational AI](CONVERSATIONAL_AI.md) - Main bot functionality
- [Configuration](../CONFIGURATION.md) - Admin settings
