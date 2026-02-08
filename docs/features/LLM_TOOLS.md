# LLM Tools

WompBot has access to various tools through LLM function calling. When you ask questions, the bot can automatically invoke these tools to provide accurate, real-time information.

## Overview

Instead of relying solely on training data, WompBot can:
- Search the web for current information
- Look up weather forecasts
- Convert currencies
- Perform calculations
- Query databases for visualizations
- And more

The LLM decides when to use tools based on your question.

## Available Tools

### Weather & Science

| Tool | Description | Example |
|------|-------------|---------|
| `get_weather` | Current weather conditions | "What's the weather in Paris?" |
| `get_weather_forecast` | 5-day weather forecast | "Will it rain this weekend in London?" |
| `wolfram_query` | Math, science, conversions, historical data | "What's the square root of 144?", "When did it last rain in NYC?" |

### Search & Information

| Tool | Description | Example |
|------|-------------|---------|
| `web_search` | Current events, news, recent information | "What happened in the news today?" |
| `wikipedia` | Factual info about people, places, events | "Tell me about the Eiffel Tower" |
| `define_word` | Dictionary definitions | "Define 'serendipity'" |
| `url_preview` | Fetch and summarize a webpage | "What's on this page? [URL]" |

### Time, Translation & Currency

| Tool | Description | Example |
|------|-------------|---------|
| `get_time` | Current time in any timezone | "What time is it in Tokyo?" |
| `translate` | Translate text between languages | "How do you say 'hello' in Spanish?" |
| `currency_convert` | Convert between currencies | "Convert 100 USD to EUR" |

### Entertainment & Media

| Tool | Description | Example |
|------|-------------|---------|
| `youtube_search` | Search for YouTube videos | "Find videos about cooking pasta" |
| `movie_info` | Movie/TV show info and ratings | "What's the rating for Inception?" |
| `stock_price` | Stock or crypto prices | "What's the price of Microsoft?", "Bitcoin price" |
| `stock_history` | Historical stock price charts | "Show me AAPL stock over the last year" |
| `sports_scores` | Live sports scores and schedules | "What's the score of the Lakers game?" |
| `image_search` | Search for images on the web | "Find me a picture of a golden retriever" |

### Utility

| Tool | Description | Example |
|------|-------------|---------|
| `random_choice` | Dice rolls, coin flips, random picks | "Roll a d20", "Flip a coin" |
| `create_reminder` | Set a reminder | "Remind me in 30 minutes to check the oven" |

### Visualization

| Tool | Description | Example |
|------|-------------|---------|
| `create_bar_chart` | Bar chart visualization | "Show me who talks the most as a bar chart" |
| `create_line_chart` | Line chart visualization | "Graph my activity over time" |
| `create_pie_chart` | Pie chart visualization | "Show message distribution as a pie chart" |
| `create_table` | Table visualization | "List the top 10 users in a table" |
| `create_comparison_chart` | Comparison visualization | "Compare user activity" |

### iRacing

| Tool | Description | Example |
|------|-------------|---------|
| `iracing_driver_stats` | Look up driver statistics | "What's my iRacing iRating?" |
| `iracing_series_info` | Series schedule and info | "When does the next GT3 race start?" |

### Discord

| Tool | Description | Example |
|------|-------------|---------|
| `user_stats` | Discord activity stats | "How many messages has @user sent?" |

## How Tools Work

1. **You ask a question:** "What's the weather in Tokyo?"
2. **LLM recognizes the need:** Detects this requires real-time data
3. **Tool is invoked:** `get_weather` is called with location "Tokyo"
4. **Result is processed:** Weather data is fetched from API
5. **Response is generated:** LLM synthesizes the data into a natural response

## Architecture

### Tool Executor: Dict Registry Pattern

The tool executor (`bot/tool_executor.py`) uses a **dictionary registry pattern** instead of a long `if-elif` chain to route tool calls to their implementations. Each tool name maps directly to a handler function in a registry dict:

```python
self._tool_registry = {
    "get_weather": self._handle_weather,
    "web_search": self._handle_web_search,
    "wolfram_query": self._handle_wolfram,
    # ... all tools registered here
}
```

**Benefits:**
- O(1) lookup instead of O(n) if-elif traversal
- Easier to add new tools (just add a dict entry)
- Cleaner, more maintainable code
- Tool names can be introspected programmatically

### Cache Key Generation: SHA-256

Cache keys for tool results are generated using **SHA-256** (previously MD5). This applies to the Redis caching layer in `tool_executor.py` that caches external API results (weather, search, stocks, etc.).

**Why the change:**
- SHA-256 is cryptographically stronger and avoids theoretical collision risks
- Consistent with modern best practices for hashing
- No meaningful performance difference for cache key generation

### Token Estimation

Token counting has been improved with a tiered approach:

1. **tiktoken** (optional) -- If the `tiktoken` library is installed, it provides accurate token counts matching the model's actual tokenizer
2. **Fallback: len/4** -- If `tiktoken` is not available, the estimator uses `len(text) / 4` as a reasonable approximation for English text
3. **Image tokens** -- Images are estimated at **170 tokens** each for cost tracking and context window management

This tiered approach avoids making `tiktoken` a hard dependency while still providing accurate estimates when available.

## Currency Conversion

The currency converter supports:

**Major Currencies:**
- USD (US Dollar)
- EUR (Euro)
- GBP (British Pound)
- JPY (Japanese Yen)
- CNY (Chinese Yuan)
- CHF (Swiss Franc)

**Regional Currencies:**
- CAD (Canadian Dollar)
- AUD (Australian Dollar)
- INR (Indian Rupee)
- MXN (Mexican Peso)
- KRW (South Korean Won)
- BRL (Brazilian Real)
- RUB (Russian Ruble)

**And many more...**

**Natural Language Support:**
- "Convert 100 dollars to euros"
- "How much is 50 pounds in yen?"
- "What's 1000 bucks in Canadian?"

**Aliases Recognized:**
- DOLLAR, DOLLARS, BUCK, BUCKS → USD
- POUND, POUNDS, STERLING → GBP
- EURO, EUROS → EUR
- YEN → JPY
- And many more...

## Weather Tools

### Current Weather
Shows current conditions including:
- Temperature (Celsius and Fahrenheit)
- "Feels like" temperature
- Humidity
- Wind speed and direction
- Weather description

### Forecast
Shows 5-day forecast with:
- Daily high/low temperatures
- Weather conditions
- Precipitation probability

### Save Your Location
Use `!weatherset` to save your default location:
```
!weatherset London
!weatherset "New York" imperial
```

Then just say "wompbot weather" for quick updates.

## Web Search

The bot uses Tavily API for web searches:
- Searches 7+ sources automatically
- Returns current, factual information
- Rate limited: 5/hour, 20/day per user

**When search is triggered:**
- Questions about current events
- Recent news or updates
- Real-time data (scores, prices, etc.)
- When the bot is uncertain

## Visualization Tools

Create charts and graphs from server data:

```
"wompbot show me a bar chart of who talks the most"
"wompbot graph my message activity over the last 30 days"
"wompbot create a pie chart of message distribution"
```

**Features:**
- Dark theme matching Discord
- Automatic data retrieval from database
- Sent as image attachments
- Zero additional LLM cost (tool output is self-explanatory)

## Rate Limits

| Tool | Limit |
|------|-------|
| Web Search | 5/hour, 20/day per user |
| Weather | Included in message limits |
| Currency | Included in message limits |
| Wolfram Alpha | 2,000/month (free tier) |
| Visualizations | Included in message limits |

## Cost

Most tools are **zero additional LLM cost**:
- Weather, currency, time → API calls only
- Visualizations → Direct image output
- Wolfram → Free tier API

**Variable cost tools:**
- Web search → Tavily API (free up to 1,000/month)
- LLM synthesis → Token cost for processing results

## Configuration

Tools are automatically available. Some require API keys:

```env
# Required for weather
OPENWEATHER_API_KEY=your_key

# Required for web search
TAVILY_API_KEY=your_key

# Optional for Wolfram Alpha
WOLFRAM_APP_ID=your_app_id

# Required for stock/crypto prices
# (Uses yfinance, no key needed)

# Required for movie info
OMDB_API_KEY=your_key
```

## Files

- `bot/llm_tools.py` - Tool definitions for LLM
- `bot/tool_executor.py` - Tool execution logic
- `bot/weather.py` - Weather API client
- `bot/wolfram.py` - Wolfram Alpha client
- `bot/viz_tools.py` - Visualization engine
