# ⚠️ Fact-Check Feature

Emoji-triggered fact-checking with web search and LLM analysis.

## Overview

The Fact-Check feature allows users to quickly fact-check any message by reacting with a ⚠️ emoji. The bot searches the web for evidence and provides a verdict with sources.

### Key Features
- ⚠️ **Emoji Triggered** - React with warning emoji to trigger
- 🔍 **Web Search** - Uses Tavily API to find evidence
- 🤖 **LLM Analysis** - Analyzes claim accuracy against search results
- 📚 **Source Citations** - Links to top 3 sources
- ✅ **Verdict System** - True, False, Partially True, Misleading, Unverifiable

### Technologies
- Tavily API - Web search (7 sources for cross-reference)
- OpenRouter LLM (the configured fact-check model, set via FACT_CHECK_MODEL env var, recommended: deepseek/deepseek-chat) - High-accuracy claim analysis
- Multi-source verification - Requires ≥2 sources to corroborate facts
- Discord reactions - User trigger

---

## Usage

### Trigger Fact-Check

1. Find a message you want to fact-check
2. React with ⚠️ emoji (`:warning:`)
3. Bot will:
   - Show "🔍 Fact-checking this claim..." message
   - Search the web for evidence
   - Analyze the claim against search results
   - Post verdict with sources

### Example Output

```
⚠️ Fact-Check Results

VERDICT: Partially True

EXPLANATION: The claim that "Bitcoin hit $100k in 2024" is partially accurate.
Bitcoin did reach $100k in early 2024, but the claim lacks context about the
subsequent price volatility.

KEY EVIDENCE: Bitcoin briefly touched $100k on Jan 15, 2024, but fell back to
$85k within days. The claim is technically true but misleading without context.

Original Claim:
> Bitcoin hit $100k in 2024

Sources:
• [Bitcoin Price History 2024](https://example.com/btc-2024)
• [Crypto Market Analysis](https://example.com/crypto-analysis)
• [Bitcoin Volatility Report](https://example.com/btc-volatility)

Requested by: @username
```

---

## Verdict System

The bot uses these verdict emojis:

| Emoji | Verdict | Meaning |
|-------|---------|---------|
| ✅ | True | Claim is accurate based on evidence |
| ❌ | False | Claim is false or incorrect |
| 🔀 | Partially True / Mixed | Claim has both true and false elements |
| ⚠️ | Misleading | Technically true but lacks important context |
| ❓ | Unverifiable | Insufficient evidence to verify |

---

## How It Works

### 1. Emoji Detection

**Supported emoji formats:**
- Unicode: `⚠️` or `⚠`
- Discord name: `:warning:`
- Custom server emoji named "warning"

**Code:** `main.py:232-237`

---

### 2. Web Search

**Process:**
1. Extract message content
2. Send to Tavily search API
3. Get top search results with:
   - Title
   - URL
   - Content snippet
   - Relevance score

**Search query:** Uses full message content

---

### 3. LLM Analysis

**Prompt structure:**
```
You are fact-checking a claim. You MUST ONLY use information from the
provided search results below. DO NOT use any other knowledge or make up information.

CRITICAL RULES:
- ONLY cite information that appears in the search results below
- NEVER extrapolate or infer beyond what's explicitly stated in search results
- NEVER make up dates, positions, or events that aren't in the search results

CROSS-REFERENCE REQUIREMENT:
- To declare "True" or "False", you MUST have AT LEAST 2 DIFFERENT sources that agree
- If only 1 source mentions something, verdict is "Unverifiable" (insufficient corroboration)
- If sources contradict each other, verdict is "Conflicting Sources" or "Unverifiable"
- Count the source numbers that support each fact

CLAIM TO FACT-CHECK:
"{message content}"

WEB SEARCH RESULTS:
{formatted search results with source numbers}

Provide a structured fact-check with:
1. VERDICT: True, False, Partially True, Misleading, or Unverifiable
2. EXPLANATION: Brief explanation citing ONLY information from search results above
3. KEY EVIDENCE: Direct quotes or facts from the search results
4. SOURCES CORROBORATION: List which source numbers ([1], [2], etc.) agree on each key fact

REMINDER: Without at least 2 sources agreeing, verdict CANNOT be "True" or "False".
```

**Model:** The configured fact-check model (set via FACT_CHECK_MODEL env var, recommended: deepseek/deepseek-chat)
**Temperature:** 0.1 (minimal hallucination risk)

---

### 4. Response Formatting

- Verdict parsed from LLM response
- Emoji added based on verdict keywords
- Sources formatted as clickable links
- Original claim quoted for context
- Attribution to requesting user

---

## Configuration

### Search API Settings

**File:** `bot/search.py`

**Tavily API configuration:**
```python
def search(self, query: str, max_results: int = 7):
    # Adjust max_results for more/fewer sources
    results = self.client.search(
        query=query,
        search_depth="advanced",  # Deep search for accuracy
        max_results=max_results  # Default: 7 (for cross-referencing)
    )
```

**More results = better cross-reference accuracy but slower**
**Minimum 2 sources required to declare True/False**

---

### LLM Settings

**File:** `bot/features/fact_check.py`

Fact checking now uses `LLMClient.simple_completion()` instead of making direct `requests.post()` calls to the OpenRouter API. This centralizes all LLM communication through the `LLMClient` class, providing:

- Consistent error handling and retry logic
- Centralized model configuration and cost tracking
- Easier model switching without modifying feature code

**Adjust analysis quality:**
```python
# Uses LLMClient.simple_completion() with the configured fact-check model
fact_check_model = os.getenv('FACT_CHECK_MODEL', self.llm.model)
result = await self.llm.simple_completion(
    prompt,
    model=fact_check_model,
    max_tokens=700,
    temperature=0.1
)
```

**Temperature effects:**
- `0.1` - **Default:** Very strict, minimal hallucination
- `0.3` - More balanced (not recommended for fact-checking)
- `0.5` - Too creative, higher hallucination risk

---

### Timeout Settings

Timeout is now managed by `LLMClient.simple_completion()` internally. The LLMClient handles request timeouts and retries centrally, so there is no longer a need to configure timeouts per-feature.

**If fact-checks fail with timeout errors**, check the LLMClient timeout configuration in `bot/llm.py`.

---

### Sources Displayed

**File:** `main.py:272-276`

**Number of sources shown:**
```python
sources_text = "\n".join([
    f"• [{s['title'][:60]}]({s['url']})"
    for s in result['sources'][:3]  # Default: Top 3
])
```

**Change `:3` to show more/fewer sources**

---

## Cost Analysis

### Per Fact-Check
- **Tavily API**: 1 search (7 results) = 1 credit (~$0.001)
- **LLM tokens** (deepseek/deepseek-chat): ~2,500 input + 700 output tokens
  - Costs vary by configured model; see OpenRouter pricing
  - **LLM subtotal**: model-dependent
- **Total per fact-check**: ~$0.001-0.019 depending on model

### Monthly Estimate
For 50 fact-checks per month (typical usage):
- Tavily: $0.05
- LLM (varies by model): ~$0.05-0.90
- **Total: ~$0.10-0.95/month**

For 100 fact-checks per month:
- Tavily: $0.10
- LLM (varies by model): ~$0.10-1.80
- **Total: ~$0.20-1.90/month**

### Model Comparison
**DeepSeek Chat** (recommended, cost-effective):
- Cost: very low per fact-check
- Accuracy: Excellent
- Speed: Fast (~2-4 seconds)

**Alternative: anthropic/claude-3.5-sonnet** (premium via OpenRouter):
- Cost: ~$0.018 per fact-check
- Accuracy: Excellent (minimal hallucination)
- Speed: Moderate (~3-5 seconds)
- More expensive but highly reliable

### Free Tier
- **Tavily**: 1,000 searches/month free (sufficient for most servers)
- **OpenRouter**: Pay-as-you-go, no free tier

---

## Database Schema

```sql
CREATE TABLE fact_checks (
    id SERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,           -- Author of original message
    username VARCHAR(255) NOT NULL,
    channel_id BIGINT NOT NULL,
    claim_text TEXT NOT NULL,
    fact_check_result TEXT NOT NULL,   -- LLM analysis
    search_results JSONB,              -- Top 3 search results
    requested_by_user_id BIGINT NOT NULL,  -- Who triggered fact-check
    requested_by_username VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fact_checks_message_id ON fact_checks(message_id);
CREATE INDEX idx_fact_checks_user_id ON fact_checks(user_id);
```

---

## Troubleshooting

### Emoji Not Triggering

**Check:**
1. Emoji is exactly ⚠️ (warning symbol)
2. Message is >10 characters long
3. Bot has "Read Message History" permission

**Test:**
React with ⚠️ to any message >10 chars

---

### "No search results found"

**Causes:**
- Message too vague
- No internet connection
- Tavily API key invalid
- Search query returned 0 results

**Fix:**
1. Check Tavily API key in `.env`
2. Try more specific message
3. Check logs: `docker-compose logs bot | grep "Fact-check"`

---

### Timeout Errors

**Cause:** Search or LLM taking too long

**Solutions:**
1. Increase timeout (see Configuration)
2. Reduce `max_tokens` for faster LLM response
3. Check Tavily API status

---

### Wrong Verdict

**Causes:**
- Misleading search results
- Complex nuanced claim
- LLM temperature too high/low

**Solutions:**
1. Adjust temperature (see Configuration)
2. Use `/verify_claim` to manually correct
3. Report false verdicts to improve prompts

---

## Best Practices

### When to Fact-Check
✅ **Good candidates:**
- Factual claims ("Bitcoin hit $100k")
- Statistics ("70% of people...")
- News events ("X happened on Y date")
- Scientific claims

❌ **Poor candidates:**
- Opinions ("I think X is better")
- Predictions about future
- Sarcasm or jokes
- Personal experiences

### Search Quality
- **Specific claims** = better results
- **Vague claims** = unreliable verdicts
- **Recent events** = better than old events (fresher sources)

---

## Privacy

- Fact-checks are **public** (posted in channel)
- Original message author attribution shown
- Requester attribution shown
- All fact-checks stored in database
- **No opt-out** (anyone can trigger on any message)

---

## Future Enhancements

1. **Private fact-checks** - DM results instead of public
2. **Fact-check history** - `/factchecks @user` command
3. **Confidence scores** - Show LLM certainty %
4. **Multiple sources** - Cross-reference multiple search engines
5. **Image fact-check** - Verify images with reverse search
6. **Voting system** - Users vote on verdict accuracy

---

## Advanced: Custom Verdict Parser

**File:** `bot/features/fact_check.py:120-134`

**Modify verdict detection:**
```python
def parse_verdict(self, analysis_text):
    verdict_lower = analysis_text.lower()

    # Add custom verdict keywords
    if 'verdict: true' in verdict_lower or 'accurate' in verdict_lower:
        return '✅'
    elif 'verdict: false' in verdict_lower or 'incorrect' in verdict_lower:
        return '❌'
    elif 'partially' in verdict_lower or 'mixed' in verdict_lower:
        return '🔀'
    elif 'misleading' in verdict_lower:
        return '⚠️'
    elif 'unverifiable' in verdict_lower or 'cannot verify' in verdict_lower:
        return '❓'
    else:
        return '❓'  # Default to unverifiable
```

---

## Support

**Check fact-check logs:**
```bash
docker-compose logs bot | grep "Fact-check"
```

**View recent fact-checks:**
```sql
SELECT username, claim_text, fact_check_result, requested_by_username
FROM fact_checks
ORDER BY created_at DESC
LIMIT 10;
```

**Test fact-check manually:**
```python
# In bot container
python3
>>> from features.fact_check import FactChecker
>>> fc = FactChecker(db, llm, search)
>>> result = await fc.fact_check_message(message, user)
```
