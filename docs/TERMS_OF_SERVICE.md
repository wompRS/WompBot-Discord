# WompBot Terms of Service

**Last Updated**: November 7, 2025
**Effective Date**: November 7, 2025

By using WompBot ("the Bot"), you agree to these Terms of Service. If you don't agree, don't use the Bot.

---

## 1. What WompBot Does

WompBot is a Discord bot that provides:
- **Conversational AI**: Chat with natural language responses powered by LLM models
- **Fact-Checking**: React with ⚠️ to trigger fact-checking with web search and multi-source verification
- **iRacing Integration**: Link your iRacing account for stats, schedules, and race analysis
- **Claims Tracking**: Track and verify claims made in conversations
- **Statistics**: Server activity, user behavior analysis, debate tracking
- **Reminders & Events**: Schedule reminders and server events
- **Privacy Controls**: GDPR-focused data management commands

---

## 2. Data We Collect

### 2.1 Required Data (Pseudonymous)
- Discord User ID (permanent identifier)
- Server/Channel IDs (for context)

### 2.2 Optional Data (With Your Consent)
- **Message Content**: Your messages for conversation context and features
- **Usernames**: For display and attribution
- **Interaction Patterns**: Network analysis, reply patterns
- **Behavioral Analysis**: Tone, profanity levels, conversation style
- **User-Generated Content**: Claims, quotes, hot takes you create
- **iRacing Data**: Customer ID and stats (only if you link your account)
- **Search Queries**: For fact-checking and service improvement
- **Command Usage**: Analytics and debugging

### 2.3 What We DON'T Collect
- Passwords or authentication tokens
- Private/Direct messages (unless you directly message the Bot)
- Voice chat data
- Screen shares or attachments
- Financial information

---

## 3. How We Use Your Data

### 3.1 Primary Uses
- Provide Bot features (chat, stats, reminders, etc.)
- Generate conversation context for AI responses
- Track claims and enable fact-checking
- Analyze server activity and engagement
- Improve Bot functionality

### 3.2 We DON'T
- Sell your data to anyone
- Use your data for advertising
- Share your data outside the purposes listed above
- Train AI models on your private conversations

### 3.3 Third-Party Processors
We share data with these processors to provide services:
- **OpenRouter/LLM Providers** (US): AI conversation responses (message content, anonymized)
- **Tavily** (US): Web search for fact-checking (search queries only)
- **iRacing** (US): Racing stats (customer IDs, only if linked)

**Note**: Standard Contractual Clauses (SCCs) for EU data transfers are in process.

---

## 4. Your Rights & Controls

### 4.1 Data Processing Model (Opt-Out)
**WompBot operates under Legitimate Interest (GDPR Art. 6.1.f)**

**Default Behavior**: All users are opted-in by default for:
- Message history storage for conversational context
- Behavioral profiling for personalized responses
- Full access to all bot features

**When You Opt Out** (via `/wompbot_optout`):
- Messages are stored with redacted content (metadata only)
- You're excluded from behavioral profiling
- Bot still responds but without personalization

### 4.2 Your Data Rights
- **Access**: `/download_my_data` - Export all your data in JSON format (GDPR Art. 15)
- **Deletion**: `/delete_my_data` - Request deletion with 30-day grace period (GDPR Art. 17)
  - Currently deletes: messages, claims, quotes, reminders, events, iRacing links
  - Not deleted: user_behavior, search_logs, debate records (admin must handle)
- **Opt Out**: `/wompbot_optout` - Stop data collection immediately (GDPR Art. 21)
- **View Status**: `/my_privacy_status` - Check your current opt-out status
- **Cancel Deletion**: `/cancel_deletion` - Undo deletion request within 30 days

### 4.3 Data Retention
See [GDPR Compliance Manual](compliance/GDPR_COMPLIANCE.md) for full details:
- **Messages**: 1 year guideline (no automatic purge, manual review)
- **Behavior Analysis**: 1 year guideline
- **Claims/Quotes**: 5 years (user-generated content)
- **Search Logs**: 90 days guideline
- **Audit Logs**: 7 years (legal requirement)
- **Stats Cache**: 30 days (automatically purged)

---

## 5. Acceptable Use Policy

### 5.1 You MAY
- Use the Bot for legitimate Discord server purposes
- Link your iRacing account for stats
- Create claims, quotes, and engage in debates
- Request fact-checks on statements
- Use crude language and humor (Bot matches your energy)

### 5.2 You MAY NOT
- Abuse or spam Bot commands
- Attempt to extract other users' data
- Use the Bot to harass or harm others
- Reverse engineer or exploit the Bot
- Use the Bot for illegal activities
- Attempt to bypass rate limits or restrictions
- Make false GDPR/privacy requests to disrupt service

### 5.3 Enforcement
Violations may result in:
- Rate limiting
- Feature restrictions
- Permanent ban from using the Bot
- Reporting to Discord Trust & Safety (for serious violations)

---

## 6. Bot Behavior & Personality

### 6.1 Conversational Style
WompBot is designed to be:
- Sharp, witty, and sarcastic
- Conversational, not formal
- Able to match your energy (including crude humor when appropriate)
- Direct about what it doesn't know

### 6.2 NOT Guaranteed
WompBot is NOT:
- Always correct (despite fact-checking safeguards)
- Appropriate for all audiences (uses adult language when contextually appropriate)
- A professional service (no SLA or uptime guarantees)
- Politically correct or sanitized

### 6.3 Fact-Checking Accuracy
While WompBot uses:
- Multi-source verification (requires ≥2 sources)
- The configured LLM model via OpenRouter for high-accuracy fact-checking
- Web search for current information
- Anti-hallucination safeguards

**It can still be wrong.** Always verify critical information independently.

---

## 7. Disclaimers & Limitations

### 7.1 No Warranties
The Bot is provided "AS IS" without warranties of any kind:
- No guarantee of accuracy, reliability, or availability
- No guarantee of data security (though we implement reasonable measures)
- No guarantee features will work as expected

### 7.2 Limitation of Liability
The Bot operators are NOT liable for:
- Decisions made based on Bot information
- Data breaches despite reasonable security measures
- Service interruptions or data loss
- Third-party processor actions
- Damages from Bot use

### 7.3 Age Requirements
You must be at least 13 years old to use the Bot (per Discord Terms of Service).

---

## 8. Service Changes

### 8.1 Modifications
We may:
- Modify these Terms at any time
- Add or remove Bot features
- Change data retention policies
- Discontinue the Bot entirely

### 8.2 Notice
Material changes will be announced via:
- Updated "Last Updated" date in this document
- Discord announcement (if applicable)
- Bot notification message (for major changes)

Continued use after changes = acceptance of new Terms.

---

## 9. Privacy & GDPR Compliance

### 9.1 Current Status
**⚠️ Partial Compliance - Action Required**

The Bot implements:
- ✅ Consent management and audit trail
- ✅ Data export functionality (Art. 15)
- ✅ Partial deletion capability (Art. 17)
- ⚠️ Incomplete automated retention enforcement
- ⚠️ Deletion missing some data categories
- ⚠️ SCCs in process for international transfers

### 9.2 Full Details
See comprehensive documentation:
- [GDPR Compliance Manual](compliance/GDPR_COMPLIANCE.md)
- [GDPR Self-Attestation](compliance/GDPR_SELF_ATTESTATION.md)
- `/privacy_policy` command for full privacy policy

---

## 10. Open Source & Code

### 10.1 License
WompBot's code may be open source (check repository for license).

### 10.2 Modifications
If you run your own instance:
- These Terms apply to the official instance only
- You're responsible for your own instance's compliance
- You must provide your own Terms of Service

---

## 11. Contact & Support

### 11.1 Commands
- `/privacy_support` - Privacy and data questions
- `/help` - General Bot help
- `/privacy_policy` - Full privacy policy
- `/tos` - View these Terms of Service

### 11.2 Administrator Contact
For serious issues:
- Contact your Discord server administrator
- They can contact the Bot operator
- For GDPR complaints: Contact your Data Protection Authority

### 11.3 No SLA
There is no Service Level Agreement. The Bot is provided on a best-effort basis.

---

## 12. Governing Law

These Terms are governed by the laws of [INSERT JURISDICTION].

For EU users: GDPR (EU Regulation 2016/679) applies to data processing.

---

## 13. Severability

If any provision is found unenforceable, the remaining provisions continue in full effect.

---

## 14. Acceptance

By using WompBot, you acknowledge:
- You've read and understood these Terms
- You agree to be bound by these Terms
- You understand the Bot collects and processes data as described
- You're at least 13 years old
- You understand the Bot is not always accurate
- You use the Bot at your own risk

---

**Questions?** Use `/privacy_support` or `/help`

**Full Privacy Policy**: `/privacy_policy`

**Your Data Rights**: `/download_my_data`, `/delete_my_data`, `/my_privacy_status`
