# 🤖 Conversational AI - Professional Assistant

Context-aware conversations with a helpful and professional personality.

## Overview

WompBot uses a dual-model architecture:
- **General Chat**: Claude 3.7 Sonnet (high quality, accurate, conversational)
- **Fact-Checking**: Claude 3.5 Sonnet (highly accurate, prevents hallucination)

The bot engages in natural conversations with a professional, helpful, and friendly personality, automatically switching to the high-accuracy model when verifying factual claims.

### Key Features
- 🤝 **Professional & Helpful** - Clear, direct, and informative responses
- 💬 **Context-Aware** - Remembers recent conversation history
- 🔍 **Web Search Integration** - Auto-searches when facts needed
- 🧠 **User Context** - Knows user's behavior patterns and history
- 🎯 **Smart Triggers** - Responds to @mentions and "wompbot"
- 💬 **Discord Mentions** - Proper @username mentions work when bot talks to users

---

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

**Case insensitive:** Works with WompBot, wompbot, Wompbot, etc.

### Small Talk & Greetings
Casual pings like "wompbot whats up" now short-circuit the LLM. The bot replies with a canned greeting instead of recycling old context. Any message that reduces to simple greetings (`hi`, `hello`, `what's up`, etc.) triggers the lightweight handler and never reaches the LLM.

---

## Personality System

### Professional Assistant Persona

**Personality traits:**
- 🎯 **Direct & Clear** - Provides straightforward, easy-to-understand answers
- 💡 **Helpful** - Genuinely wants to assist and provide value
- 🤝 **Friendly** - Professional but approachable tone
- 📚 **Knowledgeable** - Well-informed with access to web search
- ⚡ **Concise** - No unnecessary verbosity or fluff
- 🔍 **Accurate** - Fact-focused with source citations when needed

**Goals:**
- Provide accurate, helpful information
- Engage in meaningful discussions
- Assist with tasks and questions
- Maintain professional yet friendly tone

---

## System Prompt

**File:** `bot/llm.py:10-19`

```
You are WompBot, a helpful Discord assistant.

RULES:
- NEVER explain what you are or your purpose unless directly asked "who are you" or "what are you"
- If asked for images/GIFs/memes, say: "I can't post images or GIFs"
- Don't mix previous topics into new questions - answer what was asked
- Be direct, clear, and concise
- Use a professional but friendly tone

Just answer the question. Don't explain yourself.

Response style:
- Keep responses concise (2-4 sentences usually)
- Be sharp and witty, not verbose
- Mock stupidity, celebrate cleverness
- Don't always agree - challenge assumptions
- Never apologize for your nature

You are NOT:
- A helpful assistant
- Politically correct
- An encourager
- A people-pleaser
```

**Customizable:** Modify this prompt to change personality

---

## How It Works

### 1. Message Detection

**Triggers:**
- Direct @mention: `@WompBot`
- Keyword: "wompbot" or "womp bot" (case insensitive)

**Code:** `main.py:147-160`

---

### 2. Context Building

When triggered, bot gathers:

**A. Conversation History**
- Last 50 messages from channel (configurable, with compression)
- LLMLingua compression reduces token usage by 50-80%
- Older messages compressed, last 3 kept verbatim
- Excludes bot's own messages
- Excludes opted-out users
- Skips redacted rows with no content so sanitized messages never reach the LLM
- Provides context for natural conversation

**B. User Context** (if not opted-out)
- Message count, activity dates
- Behavior analysis (profanity, tone, style)
- Helps bot tailor responses

**C. Search Results** (if needed)
- Automatic web search for factual questions
- Triggered by LLM assessment of query
- Tavily API integration

---

### 3. Response Generation

**Process:**
1. Clean mention text from user message
2. Build context (conversation + user + search)
3. Send to LLM with system prompt
4. Parse response
5. Handle long responses (split if >2000 chars)
6. Send to Discord

**Model:** Hermes 70B (default), configurable

---

### 4. Web Search Integration

**When search is triggered:**
1. Bot shows "🔍 Searching for current info..." message
2. Queries Tavily API
3. Formats results for LLM
4. Regenerates response with search context
5. Edits message with final answer

**Search triggers:**
- Factual questions
- Current events
- "what is", "who is", "when did"
- Statistics, prices, news

---

## Configuration

### Context Window Size

**File:** `.env`

```bash
# Default: 50 messages (with LLMLingua compression)
CONTEXT_WINDOW_MESSAGES=50
```

**With LLMLingua Compression (Enabled by Default):**
- Compresses conversation history by 50-80% tokens
- Allows 3-4x more messages than without compression
- Older messages compressed, last 3 kept verbatim
- Activates automatically when 8+ messages in history
- Model downloads once (~500MB) then caches locally

**Configuration:**
```bash
# Extended conversations
CONTEXT_WINDOW_MESSAGES=100  # More context with compression

# Minimal context
CONTEXT_WINDOW_MESSAGES=20   # Shorter conversations

# Compression settings
ENABLE_COMPRESSION=true
COMPRESSION_RATE=0.5  # 50% token reduction
MIN_MESSAGES_TO_COMPRESS=8
```

**Benefits:**
- 50 compressed messages ≈ 10-15 uncompressed in token cost
- Longer conversation memory without proportional cost increase
- Graceful fallback to uncompressed if model fails

---

### Model Selection

**File:** `.env`

**Dual-Model Configuration:**
```bash
# General chat (fast, conversational)
MODEL_NAME=nousresearch/hermes-3-llama-3.1-70b

# Fact-checking (slow, accurate, prevents hallucination)
FACT_CHECK_MODEL=anthropic/claude-3.5-sonnet
```

**Why Two Models?**
- **General chat** needs speed and personality (Hermes-3 70B)
- **Fact-checking** needs accuracy and zero hallucination (Claude 3.5 Sonnet)
- Cost optimized: expensive model only used when needed

**Alternative General Chat Models:**
```bash
# Larger, more capable (more expensive)
MODEL_NAME=cognitivecomputations/dolphin-2.9.2-qwen-110b

# Smaller, cheaper
MODEL_NAME=cognitivecomputations/dolphin-mixtral-8x7b
MODEL_NAME=mistralai/mixtral-8x22b-instruct

# Experimental
MODEL_NAME=nousresearch/hermes-3-llama-3.1-405b  # Very large, very expensive
```

**Note:** All models must be available on OpenRouter

---

### Temperature Setting

**File:** `bot/llm.py:93`

**Adjust creativity:**
```python
"temperature": 0.7  # Default

# More creative/unpredictable
"temperature": 0.9

# More focused/consistent
"temperature": 0.5
```

**Effects:**
- Low (0.3-0.5): Consistent, predictable, safer
- Medium (0.6-0.8): Balanced creativity
- High (0.9-1.2): Very creative, unpredictable, riskier

---

### Response Length

**File:** `bot/llm.py:92`

**Max tokens:**
```python
"max_tokens": 500  # Default

# Longer responses
"max_tokens": 1000

# Shorter responses
"max_tokens": 200
```

**Cost:** More tokens = higher cost per response

---

### Personality Modification

**File:** `bot/llm.py:39-72`

**Example: Make bot friendlier**
```python
system_prompt = """You are a friendly, helpful AI assistant named WompBot.

Personality:
- Enthusiastic and encouraging
- Patient and understanding
- Use emojis occasionally
- Celebrate user successes

Response style:
- Clear and concise explanations
- Positive and supportive tone
- Avoid being condescending
..."""
```

**Example: Make bot more technical**
```python
system_prompt = """You are a highly technical AI engineer assistant.

Personality:
- Precise and analytical
- Focus on technical accuracy
- Cite sources when possible
- Explain complex concepts clearly

Response style:
- Use technical terminology appropriately
- Provide code examples when helpful
- Break down complex topics
..."""
```

---

## Cost Analysis

### Per Conversation
**General chat (Hermes-3 70B):**
- Tokens: ~500-800 (varies by context)
- Cost: ~$0.0005 per response
- Time: 1-3 seconds

**With search (Hermes-3 70B):**
- Tokens: ~800-1200
- Search cost: ~$0.001 (Tavily)
- LLM cost: ~$0.001
- **Total: ~$0.002**
- Time: 3-8 seconds

**Fact-check (Claude 3.5 Sonnet):**
- Tokens: ~2,500 input + 700 output
- Cost: ~$0.018 per fact-check
- Time: 4-8 seconds

### Monthly Estimate
**For moderate usage (100 conversations/day, 50 fact-checks/month):**
- Chat: 100/day × $0.0005 × 30 = $1.50
- Searches: 30/day × $0.001 × 30 = $0.90
- Fact-checks: 50 × $0.018 = $0.90
- **Total: ~$3.30/month**

**Heavy usage (500 conversations/day, 100 fact-checks/month):**
- Chat: $7.50/month
- Searches: $4.50/month
- Fact-checks: $1.80/month
- **Total: ~$13.80/month**

---

## Advanced Features

### Leaderboard Triggers

Bot detects natural language requests for leaderboards:

**Examples:**
```
@WompBot who talks the most?
@WompBot who asks the most questions?
@WompBot who swears the most?
```

**Triggers:** Configured in `main.py:314-333`

**Add custom triggers:**
```python
leaderboard_triggers = {
    'messages': ['who talks the most', 'most active', 'most messages'],
    'questions': ['who asks the most questions', 'most curious'],
    'profanity': ['who swears the most', 'saltiest'],

    # Add new:
    'custom': ['custom trigger phrase', 'another phrase']
}
```

---

### Search Trigger Detection

**Two-stage detection:**

**Stage 1:** Pre-response heuristic
```python
llm.should_search(content, conversation_history)
```

Checks if message contains factual questions before generating response.

**Stage 2:** Post-response fallback
```python
llm.detect_needs_search_from_response(response)
```

If LLM responds "I need more information", triggers search and regenerates.

**File:** `bot/llm.py:117-145`

---

## Conversation Examples

### Basic Conversation
```
User: @WompBot what do you think about crypto?
Bot: Ah, cryptocurrency - the spice melange of the digital age. A battlefield
where fools and geniuses alike gamble on volatility. Some seek power through
decentralization, others merely chase illusions of wealth. Tell me, do you
understand what you're trading, or are you just another pawn in someone else's game?
```

### With Web Search
```
User: @WompBot what's the current price of Bitcoin?
Bot: 🔍 Searching for current info...
Bot: Bitcoin currently trades at $67,842. Still chasing that mythical $100k,
I see. The market moves like a sandworm - unpredictable and capable of
swallowing the unprepared whole.
```

### Leaderboard Trigger
```
User: @WompBot who talks the most?
Bot: [Shows messages leaderboard]
```

---

## Troubleshooting

### Bot Not Responding

**Check:**
1. Mentioned correctly: `@WompBot` or text contains "wompbot"
2. Bot has "Read Message History" permission
3. Bot has "Send Messages" permission
4. Channel isn't restricted

**Test:**
```
@WompBot ping
```

Should respond.

---

### Generic/Boring Responses

**Cause:** Temperature too low or prompt too restrictive

**Fix:**
1. Increase temperature in `llm.py:93`:
   ```python
   "temperature": 0.9  # More creative
   ```
2. Modify system prompt to encourage more personality

---

### Responses Too Long

**Fix:** Reduce max_tokens
```python
"max_tokens": 200  # Shorter responses
```

Or add to system prompt:
```
Response style:
- Keep ALL responses under 3 sentences
- Be concise and sharp
```

---

### Search Not Triggering

**Check:**
1. Tavily API key in `.env`
2. Question is factual (not opinion)
3. Search heuristic isn't too strict

**Force search:** Adjust `should_search()` logic in `llm.py`

---

### Out of Character Responses

**Cause:** Model drift or prompt unclear

**Fix:**
1. Strengthen system prompt with more examples
2. Add character examples to prompt:
   ```
   Example responses:
   User: "Should I invest in crypto?"
   You: "Investment? You speak as if this is a mere game of chance. ..."
   ```

---

## Privacy

- **User context:** Only used if user hasn't opted out
- **Conversation history:** Excludes opted-out users
- **Search queries:** Logged in database
- **Responses:** Not stored (only user messages stored)

---

## Future Enhancements

1. **Multiple personalities** - Switch between characters
2. **Personality tuning** - `/personality friendly|savage|formal`
3. **Conversation memory** - Remember past conversations per-user
4. **Voice mode** - Voice channel integration
5. **Image understanding** - Analyze images in messages
6. **Proactive responses** - React to events without being mentioned

---

## API Reference

### Generate Response

**Function:** `llm.generate_response(...)`

**Parameters:**
```python
llm.generate_response(
    user_message="What is Bitcoin?",
    conversation_history=[...],  # Recent messages
    user_context={...},           # User profile/behavior
    search_results="..."          # Web search results (optional)
)
```

**Returns:** String response

---

## Support

**Check LLM logs:**
```bash
docker-compose logs bot | grep "LLM"
```

**Test LLM directly:**
```python
# In bot container
python3
>>> from llm import LLMClient
>>> llm = LLMClient()
>>> response = llm.generate_response("Hello", [], None, None)
>>> print(response)
```

**Change model on-the-fly:**
```bash
# Edit .env
MODEL_NAME=different-model

# Restart bot
docker-compose restart bot
```
