# Conversational AI - Professional Assistant

Context-aware conversations with multiple personality modes and intelligent memory.

## Overview

WompBot uses configurable models via OpenRouter:
- **General Chat**: Configurable via `MODEL_NAME` env var (recommended: `deepseek/deepseek-chat`)
- **Fact-Checking**: Configurable via `FACT_CHECK_MODEL` env var (recommended: `deepseek/deepseek-chat`)

The bot engages in natural conversations with customizable personalities, using the configured model for all interactions.

### Key Features

- Multiple personality modes (conversational, concise, bogan)
- Context-aware conversations with RAG memory system
- Automatic web search integration when facts are needed
- User context awareness (behavior patterns, preferences)
- Smart response triggers (@mentions, "wompbot", "!wb")
- Proper Discord mention support in both directions
- LLMLingua compression for 50-80% token reduction
- Guild isolation for server-specific data separation

## Triggering Conversations

### Method 1: @Mention
```
@WompBot what do you think about pineapple on pizza?
```

### Method 2: Say "wompbot" or "womp bot"
```
hey wompbot, explain quantum physics
wompbot what's the weather like?
```

Case insensitive and works anywhere in the message.

### Method 3: !wb Shorthand
```
!wb quick question
```

### Small Talk and Greetings

Simple greetings like "wompbot whats up" now short-circuit the LLM. The bot replies with a canned greeting instead of consuming context and tokens. Messages that reduce to simple greetings (hi, hello, what's up, etc.) trigger the lightweight handler and never reach the LLM.

## Personality System

WompBot has three personality modes that can be switched per-server using the /personality command (admin only).

### Default (Conversational)

**Characteristics:**
- Helpful and conversational tone
- Provides detailed responses with personality
- Balances information with natural conversation
- Adapts to user's communication style
- Typical response length: 2-4 sentences

**Best for:**
- General server use
- Detailed explanations
- Natural back-and-forth conversations
- When you want personality with substance

### Concise (Brief)

**Characteristics:**
- Very brief responses (1-2 sentences maximum)
- Gets straight to the point without elaboration
- Simple acknowledgments for simple statements
- No unnecessary context or explanation
- Economical with words

**Example responses:**
```
User: "The sky is blue"
Bot: "Yep."

User: "What's 2+2?"
Bot: "4"

User: "How do I restart Docker?"
Bot: "docker restart container_name"
```

**Best for:**
- Quick information lookup
- When you prefer minimal text
- Direct answers without conversation
- High-volume channels where brevity matters

### Bogan (Australian)

**Characteristics:**
- Full Australian slang and working-class dialect
- Casual, pub-style conversation tone
- Uses authentic Aussie expressions and humor
- Still helpful and informative, just with strong personality
- Natural variation to sound authentic, not scripted

**Example phrases:**
- "Yeah nah mate, that's not quite right..."
- "She'll be right, no worries"
- "Righto, here's the go..."

**Best for:**
- Casual server environments
- When you want entertainment with information
- Australian-themed servers or communities
- Adding character to bot responses

### Switching Personalities

Admin users can change the personality mode:
```
/personality <mode>
```

Options: default, concise, bogan

The setting is per-server and persists in the database. All users in that server will see the bot with the selected personality.

## How It Works

### 1. Message Detection

**Triggers:**
- Direct @mention of the bot
- Text contains "wompbot" or "womp bot" (case insensitive)
- Message starts with "!wb"

The bot ignores its own messages to prevent infinite loops.

### 2. Context Building

When triggered, the bot gathers multiple sources of context:

**A. Conversation History**
- Last 50 messages from the channel (configurable)
- LLMLingua compression reduces token usage by 50-80%
- Older messages get compressed, last 8 kept verbatim (keep_recent=8)
- Excludes bot's own old messages
- Excludes opted-out users entirely
- Redacted messages never reach the LLM
- Provides natural conversation flow

**B. RAG Memory System**
- Semantic search finds relevant past conversations by meaning
- Hybrid memory: recent messages plus long-term retrieval
- Automatically learns user preferences and facts
- Background embedding generation every 5 minutes
- AI-generated conversation summaries for broader context
- 40% token reduction compared to full history approach

**C. User Context** (if not opted-out)
- Message count and activity patterns
- Behavioral analysis (tone, profanity levels, style)
- Helps bot tailor responses appropriately
- Improves personalization

**D. Search Results** (if needed)
- Automatic web search for factual questions
- Triggered by LLM assessment or explicit need
- Tavily API integration (5 results, 200-character snippets -- reduced from 7 results)
- Rate limited to prevent abuse

### 3. Response Generation

**Process:**
1. Clean mention text from user message
2. Build context from conversation, RAG, user profile, and search
3. Select appropriate system prompt based on personality
4. Send to configured model via OpenRouter
5. Parse response and handle tool calls if present
6. Split if response exceeds 2000 characters
7. Send to Discord

**Search Placeholder:**
When search is likely needed, the bot sends a placeholder message before entering typing mode:
- "Let me fact-check this real quick..."
- "Pulling up recent information..."
- "Checking the latest info..."
- Multiple variations selected randomly

The placeholder is then edited with the final response.

### 4. Web Search Integration

**When search triggers:**
1. Bot sends placeholder status message
2. Queries Tavily API for current information
3. Formats results for LLM context
4. Regenerates response with search context
5. Edits placeholder with final answer

**Search triggers for:**
- Factual questions about current events
- Statistics, prices, news
- "What is", "who is", "when did" queries
- Product information or comparisons
- When bot detects it needs more information

**Rate limits:**
- 5 searches per hour per user
- 20 searches per day per user
- Admin bypass available for testing

## Configuration

### Context Window Size

File: .env

```bash
# Default: 50 messages with compression
CONTEXT_WINDOW_MESSAGES=50
```

**With LLMLingua Compression (enabled by default):**
- Compresses conversation history by 50-80% tokens
- Allows 3-4x more messages than without compression
- Older messages compressed, last 8 kept verbatim (keep_recent=8)
- Activates automatically when 10+ messages in history (min_messages=10)
- Model downloads once (about 500MB) then caches locally

**Configuration options:**
```bash
# Extended conversations
CONTEXT_WINDOW_MESSAGES=100

# Minimal context
CONTEXT_WINDOW_MESSAGES=20

# Compression settings
ENABLE_COMPRESSION=true
COMPRESSION_RATE=0.5  # 50% token reduction
MIN_MESSAGES_TO_COMPRESS=8
```

**Benefits:**
- 50 compressed messages equals 10-15 uncompressed in token cost
- Longer conversation memory without proportional cost increase
- Graceful fallback to uncompressed if compression fails

### Model Selection

File: .env

**Model Configuration:**
```bash
# General chat - cost-effective and high quality
MODEL_NAME=deepseek/deepseek-chat

# Fact-checking - can use same or different model
FACT_CHECK_MODEL=deepseek/deepseek-chat
```

**Why configurable models?**
- Choose the best quality/cost ratio for your usage
- General chat needs speed and conversational ability
- Fact-checking benefits from maximum accuracy
- All models available via OpenRouter — switch anytime

**Alternative models via OpenRouter:**
```bash
# More economical
MODEL_NAME=anthropic/claude-3-haiku

# More accurate (but slower/expensive)
MODEL_NAME=anthropic/claude-3.5-sonnet

# Experimental
MODEL_NAME=google/gemini-2.0-flash-exp
```

Note: All models must be available on OpenRouter. Check their website for current offerings.

### Personality Customization

**Custom Default Personality:**

The default (conversational) personality can be customized:

1. Copy the sample prompt:
   ```bash
   cp bot/prompts/system_prompt_sample.txt bot/prompts/system_prompt.txt
   ```

2. Edit the file:
   ```bash
   nano bot/prompts/system_prompt.txt
   ```

3. Restart the bot:
   ```bash
   docker-compose restart bot
   ```

Your custom system_prompt.txt is gitignored, so changes stay private.

**Modifying Other Personalities:**

The concise and bogan personalities are in tracked files:
- bot/prompts/system_prompt_concise.txt
- bot/prompts/system_prompt_bogan.txt

Edit these files directly and restart the bot to apply changes.

See [bot/prompts/README.md](../../bot/prompts/README.md) for detailed customization guide.

## Cost Analysis

### Per Conversation

**General chat (configured model):**
- Tokens: 500-1000 (varies by context and compression)
- Cost: varies by model (DeepSeek is very cost-effective at ~$0.001-0.005 per response)
- Time: 1-3 seconds

**With search (configured model):**
- Tokens: 800-1500
- Search cost: approximately $0.001 (Tavily, free tier up to 1,000/month)
- LLM cost: varies by model
- Total: approximately $0.002-0.01 with DeepSeek
- Time: 3-8 seconds

**Fact-check (configured fact-check model):**
- Tokens: approximately 2,500 input + 700 output
- Cost: approximately $0.018 per fact-check
- Time: 4-8 seconds
- Triggered by warning emoji reaction

### Monthly Estimates

**Light usage (30 conversations/day):**
- Chat: 30/day times $0.02 times 30 days = approximately $18/month
- With rate limits: approximately $10/month

**Moderate usage (100 conversations/day):**
- Chat: approximately $60/month
- With rate limits: approximately $20-25/month

**Heavy usage (300 conversations/day):**
- Chat: approximately $180/month
- With rate limits and compression: approximately $40-50/month

Rate limiting significantly reduces costs by preventing abuse and excessive usage.

## Advanced Features

### Admin Bypass

Admin users (configurable by username or ID) can bypass rate limiting for testing:
- No message frequency limits
- No token limits
- No search limits
- No repeated message detection
- Unlimited concurrent requests

Configure in conversations.py:
```python
is_admin = str(message.author).lower() == 'wompie__' or message.author.id == YOUR_ADMIN_USER_ID
```

### Search Detection

**Two-stage detection system:**

Stage 1: Pre-response heuristic
```python
llm.should_search(content, conversation_history)
```

Checks if message contains factual questions before generating response.

Stage 2: Post-response fallback
```python
llm.detect_needs_search_from_response(response)
```

If LLM responds with uncertainty, triggers search and regenerates.

### Tool Calling

The bot can invoke tools through LLM function calling:
- Weather visualizations
- Data charts (bar, line, pie, comparison)
- Wolfram Alpha queries
- Database queries for stats

Tools are defined in llm_tools.py and executed by tool_executor.py.

**Architecture Improvements (February 2026 Refactoring):**
- `conversations.py` refactored to extract helper methods:
  - `_execute_tool_calls()` -- Handles tool call execution with 30-second timeout per tool
  - `_synthesize_tool_response()` -- Handles the synthesis LLM pass for tool results that need accompanying text
- Tool execution has a 30-second timeout; if a tool call exceeds this, it is cancelled and an error message returned
- `SELF_CONTAINED_TOOLS` list (tools whose output IS the answer, needing no synthesis pass) now imported from `constants.py` instead of being hardcoded in conversations.py
- Tool calls run in parallel via `asyncio.gather()` when multiple tools are requested simultaneously

## Troubleshooting

### Bot Not Responding

Check the following:
1. Bot mentioned correctly (@WompBot or text contains "wompbot")
2. Bot has "Read Message History" permission
3. Bot has "Send Messages" permission
4. Channel isn't restricted or bot isn't muted
5. Bot is actually online (check logs)

Test with:
```
@WompBot ping
```

Should respond immediately.

### Responses Too Long

The bot automatically splits responses over 2000 characters into multiple messages. If responses are consistently too long:

1. Switch to concise personality mode
2. Adjust system prompt to encourage brevity
3. Lower MAX_TOKENS_PER_REQUEST in .env

### Search Not Triggering

If search isn't activating when it should:

1. Verify TAVILY_API_KEY is set in .env
2. Check rate limits haven't been exceeded
3. Question must be factual (not opinion-based)
4. Adjust search heuristic in llm.py if needed

Force search by mentioning "search" or "look up" explicitly.

### Out of Character Responses

If bot responds inconsistently with personality:

1. Check correct personality is selected for server
2. Strengthen system prompt with more specific examples
3. Restart bot to reload personality files
4. Verify personality file hasn't been corrupted

### Performance Issues

If bot is slow to respond:

1. Check OpenRouter API status
2. Reduce CONTEXT_WINDOW_MESSAGES for less context
3. Disable compression if causing delays
4. Check database connection (RAG queries can be slow)
5. Monitor rate limits and concurrent requests

## Privacy

- User context only used if user hasn't opted out
- Conversation history excludes opted-out users completely
- Search queries logged in database for rate limiting
- Bot responses not stored (only user messages stored)
- Guild isolation ensures server data separation
- GDPR-compliant with opt-out, export, and deletion commands

## Performance Architecture

WompBot includes several performance optimizations for responsive conversations under load:

**HTTP Connection Pooling:**
- All HTTP clients (LLM, search, weather, Wolfram, tools) use `requests.Session()` for connection reuse
- Eliminates redundant TCP+TLS handshakes, saving 200-400ms per API call

**Concurrent Channel Processing:**
- Each channel allows up to 3 simultaneous requests via `asyncio.Semaphore(3)`
- Prevents response mixing while allowing parallel processing
- 10-second timeout before queuing — users see a clear "channel busy" message if all slots taken

**Parallel Tool Execution:**
- When the LLM requests multiple tools (e.g., web_search + weather + wolfram), they execute concurrently via `asyncio.gather()`
- Reduces multi-tool latency by 50-70% (e.g., 3 tools at 5s each: 15s serial → ~5s parallel)

**GDPR Consent Caching:**
- Consent status cached in memory with 5-minute TTL
- Eliminates a database query on every incoming message

**Thread and Connection Pools:**
- Thread pool: 100 workers (up from default ~40) to handle concurrent LLM calls
- Database pool: 25 max connections (up from 10) for sustained throughput

**Duplicate Call Elimination:**
- `should_search()` result cached from initial check and reused later in the pipeline
- Second `get_recent_messages()` call replaced with a slice of already-fetched data

## Future Enhancements

Potential improvements being considered:

- Per-user personality preferences
- Voice channel integration for audio responses
- Proactive responses to server events
- Custom personality creation interface
- Further conversation memory improvements

## API Reference

### Generate Response

Function: llm.generate_response(...)

Parameters:
```python
llm.generate_response(
    user_message="What is Bitcoin?",
    conversation_history=[...],     # Recent messages
    user_context={...},              # User profile/behavior
    search_results="...",            # Web search results (optional)
    rag_context={...},               # RAG-retrieved context
    retry_count=0,                   # Retry attempt number
    bot_user_id=123,                 # Bot's Discord ID
    user_id=456,                     # Requesting user's Discord ID
    username="User",                 # Requesting user's name
    max_tokens=1000,                 # Max tokens to generate
    personality='default',           # Personality mode
    tools=[...],                     # Available tool definitions
    images=[...],                    # Image URLs for vision model
    base64_images=[...]              # Base64-encoded images
)
```

Returns: String response or dict with tool_calls

## Support

**Check LLM logs:**
```bash
docker-compose logs bot | grep "LLM"
```

**Check personality loading:**
```bash
docker-compose logs bot | grep "personality\|prompt"
```

**Change model on-the-fly:**
```bash
# Edit .env
MODEL_NAME=anthropic/claude-3-haiku

# Restart bot
docker-compose restart bot
```

**Test personality switching:**
```
/personality concise
@WompBot test
/personality default
@WompBot test
```

**Monitor costs:**
The bot tracks costs in real-time and sends DM alerts to the owner when each $1 threshold is crossed.
