# Changelog

All notable changes to WompBot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **iRacing Meta Analysis Enhancements**
  - Weather data tracking (temperature, sky conditions, precipitation %, track surface)
  - Color-coded weather display in meta charts
  - Full car names instead of abbreviations
  - Performance caching system for 300-race analysis
  - Season display fixes (2025 S1 format)
- **iRacing Results Visualization**
  - Image-based results table with proper formatting
  - Track name lookup with configuration
  - iRating and Safety Rating gain/loss columns
  - Color-coded performance indicators
- **iRacing Profile Improvements**
  - Fixed license overview display (all 5 categories)
  - Proper license data structure conversion
- **iRacing Performance Dashboard**
  - `/iracing_history` now combines rating history and recent results
  - Timeframe filters for last day, week, month, season, year, or all recent races
  - Summaries include wins, podiums, incidents, IR/SR deltas, and usage charts for series/cars
- **Greeting Intercept**
  - Friendly canned replies for simple greetings prevent the LLM from re-using stale context
- **iRacing History**
  - Rating progression charts for all recent races
  - Simplified interface without category filtering
- GDPR compliance system with all data subject rights (Art. 12-23)
- Privacy commands: `/wompbot_consent`, `/wompbot_noconsent`, `/download_my_data`, `/delete_my_data`, `/privacy_policy`, `/my_privacy_status`, `/privacy_support`
- Data export functionality in machine-readable JSON format (GDPR Art. 15)
- Data deletion with 30-day grace period (GDPR Art. 17)
- Consent management system with version tracking
- Automated daily data retention cleanup
- Complete audit trail for all data operations (7-year retention)
- Privacy policy management with versioning
- Automated database backups (7 daily, 4 weekly, 3 monthly)
- HTTP request timeouts (30s total, 10s connect, 20s read)
- SSL/TLS verification enforcement in HTTP clients
- Container resource limits (CPU/memory)
- **iRacing Team Management System** with 11 new commands
- Team creation and roster management (`/iracing_team_create`, `/iracing_team_invite`, `/iracing_team_leave`)
- Team discovery (`/iracing_team_list`, `/iracing_team_info`, `/iracing_my_teams`)
- Event scheduling with natural language time parsing (`/iracing_event_create`, `/iracing_team_events`)
- Driver availability tracking (`/iracing_event_availability`, `/iracing_event_roster`)
- Official race schedule browser (`/iracing_upcoming_races`)
- Role-based team permissions (manager, driver, crew_chief, spotter)
- Multi-guild support (teams are server-specific)
- Integration with existing iRacing account links
- Discord timestamp support (shows in user's local timezone)
- Natural language date parsing (python-dateutil integration)

### Changed
- **BREAKING**: Users must provide explicit consent via `/wompbot_consent` for most features
- **BREAKING**: Consent commands renamed from `/give_consent` and `/withdraw_consent` to `/wompbot_consent` and `/wompbot_noconsent`
- **BREAKING**: Role-based opt-out system (NoDataCollection role) removed in favor of consent commands
- **iRacing Schedule Visuals** now highlight the current week, show UTC open times, and include season date ranges
- **iRacing API Client** uses an adaptive lock/backoff and only throttles after receiving a 429 response
- Message storage redacts content/usernames for opted-out users and conversation context excludes sanitized rows
- Background jobs persist `job_last_run` timestamps so hourly/daily/weekly tasks resume gracefully after restarts instead of double-running
- Bot personality changed from "sarcastic" Feyd-Rautha persona to "professional but friendly" tone
- Updated all Python dependencies to latest secure versions
- Database port no longer exposed to host network (Docker internal only)
- Containers now run as non-root user (UID 1000) instead of root
- Data retention policies now configurable per data type

### Fixed
- Restored `privacy_manager.get_consent_status` helper so mention handling no longer crashes when GDPR consent is checked
- **SECURITY**: SQL injection vulnerability in `database.py` (CWE-89, CVSS 9.8)
- **SECURITY**: PostgreSQL database publicly exposed (removed port binding)
- **SECURITY**: Containers running as root (privilege escalation risk)
- **SECURITY**: Missing HTTP timeouts (DoS vulnerability)

### Security
- Patched CVE-2024-23334 in aiohttp (HTTP request smuggling)
- Patched CVE-2024-28219 in Pillow (buffer overflow)
- Updated cryptography package (multiple OpenSSL vulnerabilities)
- Updated requests package (multiple security fixes)
- All dependencies updated to versions with no known CVEs

---

## [1.9.0] - 2025-10-24

### Added
- iRacing track assets for enhanced visualization
- Professional iRacing-style charts and graphics
- Car logo integration for iRacing features
- iRacing report preloading for faster responses

### Changed
- Improved iRacing visualization styling to match official iRacing Reports
- Enhanced iRacing data caching strategy
- Updated documentation for iRacing features

---

## [1.8.0] - 2025-10-22

### Added
- iRacing meta analysis feature (`/iracing_meta`)
- Best car recommendations by series with performance statistics
- Win rate analysis for cars in series
- Lap time comparisons across different cars
- Series popularity tracking by participation

### Changed
- Improved iRacing API data parsing
- Enhanced error handling for iRacing features

### Fixed
- iRacing user ID lookup issues
- Season schedule parsing errors
- Stats parsing for iRacing driver profiles

---

## [1.7.0] - 2025-10-20

### Added
- Complete iRacing integration with official API
- Driver profile viewing (`/iracing_profile`)
- Driver comparison charts (`/iracing_compare_drivers`)
- Rating history tracking (`/iracing_history`)
- Server leaderboards for Discord members (`/iracing_server_leaderboard`)
- iRacing race schedule viewer (`/iracing_schedule`)
- Series browser with autocomplete (`/iracing_series`)
- Recent race results (`/iracing_results`)
- Season schedule viewer (`/iracing_season_schedule`)
- Account linking system (`/iracing_link`)
- Encrypted credential storage using Fernet (AES-256)
- Support for all 5 iRacing license categories (Oval, Sports Car Road, Formula Car Road, Dirt Oval, Dirt Road)
- Professional visualizations with matplotlib
- Intelligent API response caching
- Category autocomplete for easy selection

### Added
- Debate Scorekeeper feature (`/debate_start`, `/debate_end`)
- LLM-powered debate analysis with participant scoring
- Logical fallacy detection (ad hominem, strawman, etc.)
- Winner determination by AI judge
- Debate history and statistics tracking
- Debate leaderboards by wins and scores
- Individual participant scoring (0-10 scale)

### Added
- Quote of the Day feature (`/qotd`)
- Multiple viewing modes (daily, weekly, monthly, all-time, random)
- Smart quote selection by reaction count
- Beautiful purple-themed embeds
- Category badges for quotes
- Zero-cost feature using pure database queries

### Added
- Yearly Wrapped feature (`/wrapped`)
- Spotify-style year-end activity summaries
- Comprehensive statistics (messages, social network, claims, quotes)
- Achievement badges (Night Owl, Early Bird, Debate Champion, Quote Machine)
- Year comparison functionality
- User comparison support
- Beautiful gold-themed embeds with profile pictures

### Added
- Event scheduling system (`/schedule_event`)
- Automatic periodic event reminders (1 week, 1 day, 1 hour before)
- Natural language date parsing for events
- Event management (`/events` to list, `/cancel_event` to cancel)
- Channel announcements with Discord timestamps
- Optional role pinging for event notifications

---

## [1.6.0] - 2025-10-19

### Added
- Context-aware reminder system (`/remind`, `/reminders`, `/cancel_reminder`)
- Natural language time parsing ("in 5 minutes", "tomorrow at 3pm", "next Monday")
- Context links to jump back to original message
- Flexible delivery (DM or channel mention)
- Recurring reminder support (daily, weekly, custom intervals)
- Background reminder checker (runs every minute)

### Added
- Hot Takes leaderboard feature (`/hottakes`, `/mystats_hottakes`)
- Automatic controversial claim detection using pattern matching
- Community tracking via reactions and replies
- Multiple leaderboard types (controversial, vindicated, worst, community favorites, combined)
- Vindication system for tracking prediction accuracy (`/vindicate`)
- Personal hot takes statistics
- Three-stage hybrid detection system (pattern → reaction threshold → LLM scoring)
- Cost-optimized approach keeping LLM costs under $1/month

### Added
- Background task for pre-computing statistics
- Automatic stats refresh every hour
- Network graph caching
- Topic trends caching
- Primetime analysis caching
- Engagement metrics caching
- Manual stats refresh command (`!refreshstats`)

### Added
- Claims Tracker Lite feature
- Auto-detection of bold predictions, facts, and guarantees
- Edit tracking with original text preservation
- Deletion tracking for claimed messages
- Contradiction detection across user claims
- `/receipts` command to view tracked claims
- `/verify_claim` admin command for claim verification
- Keyword search in claims
- Two-stage hybrid detection (pattern matching + LLM confirmation)

### Changed
- Updated help command with comprehensive feature list
- Improved bot documentation structure

### Security
- Dependency updates via Dependabot (pip group)

---

## [1.5.0] - 2025-10-19

### Added
- Advanced chat statistics with machine learning
- Network graph visualization (`/stats_server`)
- Topic trend analysis using TF-IDF (`/stats_topics`)
- Activity heatmaps by hour and day (`/stats_primetime`)
- Engagement metrics and patterns (`/stats_engagement`)
- Support for date ranges and custom time periods
- User-specific and server-wide statistics
- Zero-cost ML-based analytics (no LLM needed)

### Added
- Database tables for stats caching
- Message interactions tracking for network graphs
- Topic snapshots over time

---

## [1.4.0] - 2025-10-17

### Added
- Fact-checking feature triggered by ⚠️ emoji reaction
- Web search integration using Tavily API
- LLM-powered claim accuracy analysis
- Verdict system (✅ True, ❌ False, 🔀 Mixed, ⚠️ Misleading, ❓ Unverifiable)
- Source citations with top 3 links
- Beautiful embed formatting for fact-check results
- Database storage for fact-check history

### Changed
- Improved LLM prompt tuning for Feyd-Rautha personality
- Refined response detection to reduce unnecessary processing
- Enhanced personality consistency across conversations
- Optimized response loading time

### Fixed
- Conversation response timing issues
- LLM personality consistency
- Response loading message display

---

## [1.3.0] - 2025-10-17

### Added
- Quote saving system via ☁️ emoji reaction
- `/quotes` command to view saved quotes
- Auto-categorization of quotes by type
- Reaction count tracking
- Context preservation for quotes
- Quote database with timestamps

### Added
- `/help` command with comprehensive feature list
- Detailed command documentation
- Feature categorization in help

---

## [1.2.0] - 2025-10-17

### Added
- User behavior analysis system
- Profanity scoring (0-10 scale)
- Conversational tone analysis
- Honesty pattern detection (fact-based vs exaggeration)
- Communication style assessment
- Privacy opt-out system (replaced by GDPR consent commands in v2.0.0)
- Weekly and on-demand behavior analysis
- Leaderboards for messages, questions, and profanity
- User statistics viewing (`!stats`)

### Added
- Database tables for user profiles and behavior analysis
- Message storage with opt-out flags
- User analytics tracking

---

## [1.1.0] - 2025-10-17

### Added
- Web search integration with Tavily API
- Automatic fact-checking when bot detects factual claims
- Search result caching
- Manual web search command (`!search`)

### Changed
- Enhanced conversation AI to request searches when needed
- Improved context awareness for when facts are required

---

## [1.0.0] - 2025-10-17

### Added
- Initial bot release with Feyd-Rautha Harkonnen personality
- Conversational AI powered by OpenRouter LLMs (Hermes/Dolphin models)
- Context-aware responses with conversation memory
- Smart response detection (mentions and "wompbot" keyword)
- PostgreSQL database for message storage
- Docker containerization with docker-compose
- Cunning, calculating, and sharp-tongued personality
- Eloquent but menacing speech style
- Direct and brutal communication (no customer service energy)
- Occasional Dune universe references

### Added
- Message tracking in PostgreSQL
- Conversation context from recent messages
- Response latency tracking (`!ping`)
- Basic bot commands and event handlers

### Added
- Docker setup with PostgreSQL
- Environment variable configuration
- OpenRouter LLM integration
- Database schema initialization
- WSL2 Debian compatibility

---

## Version History Summary

| Version | Release Date | Major Features |
|---------|--------------|----------------|
| Unreleased | 2025-01-25 | GDPR compliance, critical security fixes, dependency updates |
| 1.9.0 | 2025-10-24 | iRacing visualization enhancements, track assets |
| 1.8.0 | 2025-10-22 | iRacing meta analysis, car performance statistics |
| 1.7.0 | 2025-10-20 | Complete iRacing integration, Debate Scorekeeper, Quote of the Day, Yearly Wrapped, Event Scheduling |
| 1.6.0 | 2025-10-19 | Reminders, Hot Takes leaderboard, Claims Tracker, Background stats |
| 1.5.0 | 2025-10-19 | Advanced chat statistics with ML |
| 1.4.0 | 2025-10-17 | Fact-checking, LLM personality tuning |
| 1.3.0 | 2025-10-17 | Quote system, Help command |
| 1.2.0 | 2025-10-17 | User analytics, Behavior analysis, Privacy controls |
| 1.1.0 | 2025-10-17 | Web search integration |
| 1.0.0 | 2025-10-17 | Initial release with conversational AI |

---

## Feature Categories

### 🤖 Conversational AI
- v1.0.0: Initial Feyd-Rautha personality
- v1.1.0: Web search integration
- v1.4.0: Personality tuning and optimization

### 📋 Claims & Accountability
- v1.6.0: Claims Tracker with auto-detection
- v1.6.0: Edit and deletion tracking
- v1.6.0: Contradiction detection

### ☁️ Quotes System
- v1.3.0: Quote saving via emoji reactions
- v1.3.0: Quote viewing and categorization

### ⚠️ Fact-Checking
- v1.1.0: Web search capability
- v1.4.0: Fact-check feature with verdict system

### 📊 Analytics & Statistics
- v1.2.0: User behavior analysis
- v1.5.0: Advanced chat statistics with ML
- v1.5.0: Network graphs and topic trends

### 🔥 Hot Takes
- v1.6.0: Hot Takes tracker and leaderboard
- v1.6.0: Vindication system

### ⏰ Reminders & Events
- v1.6.0: Context-aware reminders
- v1.7.0: Event scheduling system

### 📊 Year-End Features
- v1.7.0: Yearly Wrapped
- v1.7.0: Quote of the Day

### ⚔️ Debate Features
- v1.7.0: Debate Scorekeeper with LLM analysis

### 🏁 iRacing Integration
- v1.7.0: Complete iRacing integration
- v1.8.0: Meta analysis
- v1.9.0: Enhanced visualizations

### 🔒 Privacy & Security
- v1.2.0: Privacy opt-out system
- Unreleased: Complete GDPR compliance
- Unreleased: Critical security vulnerability fixes

---

## Upcoming Features (Planned)

- 🎲 Polls & Voting system
- 🎂 Birthday tracking and celebrations
- 🎮 Trivia games with leaderboards
- 📊 Voice channel statistics
- 🎯 Custom user commands
- ⚡ Rate limiting per user
- 🔐 CAPTCHA for sensitive operations
- 📊 Admin dashboard for GDPR requests

---

## Migration Notes

### Unreleased → Production
- **BREAKING CHANGE**: Explicit user consent required for most features
- Run GDPR database migration: `sql/gdpr_migration.sql`
- Update Docker containers to use non-root user
- Remove exposed database ports from docker-compose
- Update all dependencies via `requirements.txt`

### 1.6.0 → 1.7.0
- Optional: Configure iRacing credentials with `encrypt_credentials.py`
- New database tables for debates, events, and iRacing links

### 1.5.0 → 1.6.0
- New database tables for reminders, hot_takes, and claims
- Configure background tasks for stats precomputation

---

## Security Advisories

### Critical - 2025-01-25
- **CVE-2024-23334**: HTTP request smuggling in aiohttp < 3.9.5
- **CVE-2024-28219**: Buffer overflow in Pillow < 10.3.0
- **CWE-89**: SQL injection in database.py (fixed in unreleased)
- **Exposed Database**: PostgreSQL port 5432 publicly accessible (fixed in unreleased)
- **Root Containers**: Privilege escalation risk (fixed in unreleased)

### Dependency Updates - 2025-01-25
All packages updated to latest secure versions. Run `pip-audit` to verify.

---

## Deprecation Notices

### None at this time

---

## Contributors

- Primary Developer: [Your Name/Team]
- Security Audit: Claude (AI Assistant) - NIST 800-218 SSDF & OWASP Top 25
- GDPR Implementation: Claude (AI Assistant)

---

## License

[Your License Here]

---

## Support

For issues, questions, or feature requests:
- Check logs: `docker-compose logs -f bot`
- Review documentation in `docs/` directory
- Privacy concerns: Use `/privacy_support` command
- Security issues: Report to bot administrator immediately

---

**Last Updated**: 2025-01-25
**Current Version**: Unreleased (v2.0.0 pending)
**Status**: ✅ Production Ready (pending deployment)
