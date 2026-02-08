"""
LLM Tool Definitions and Data Retrieval
Defines tools the LLM can call and provides data access
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

# Tool definitions for LLM function calling
# These visualization tools support TWO modes:
# 1. INTERNAL DATA: Use data_query for Discord server stats (message counts, user activity, etc.)
# 2. EXTERNAL DATA: Use web_search FIRST to get data, then pass it via the 'data' parameter
VISUALIZATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_bar_chart",
            "description": "Create a bar chart. For Discord server stats, use data_query. For external data (sports, stocks, etc.), FIRST use web_search to get the data, THEN call this with the 'data' parameter containing the results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_query": {
                        "type": "string",
                        "description": "For INTERNAL Discord stats only: 'top users by messages', 'messages by hour'. Leave empty if using 'data' parameter.",
                    },
                    "data": {
                        "type": "object",
                        "description": "Raw data to visualize as {label: value} pairs. Use this for EXTERNAL data from web_search results. Example: {'Team A': 45, 'Team B': 38}",
                        "additionalProperties": {"type": "number"}
                    },
                    "title": {
                        "type": "string",
                        "description": "Chart title"
                    },
                    "xlabel": {
                        "type": "string",
                        "description": "X-axis label"
                    },
                    "ylabel": {
                        "type": "string",
                        "description": "Y-axis label"
                    },
                    "horizontal": {
                        "type": "boolean",
                        "description": "Create horizontal bar chart (good for long labels)",
                        "default": False
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_line_chart",
            "description": "Create a line chart. For Discord server stats, use data_query. For external data, FIRST use web_search, THEN pass results via 'data' parameter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_query": {
                        "type": "string",
                        "description": "For INTERNAL Discord stats: 'messages per day', 'user activity over time'. Leave empty if using 'data' parameter.",
                    },
                    "data": {
                        "type": "object",
                        "description": "Raw data as {series_name: [values]}. For external data from web_search. Example: {'Points': [45, 42, 38]}",
                        "additionalProperties": {"type": "array", "items": {"type": "number"}}
                    },
                    "x_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels for x-axis when using raw data. Example: ['Jan', 'Feb', 'Mar']"
                    },
                    "title": {
                        "type": "string",
                        "description": "Chart title"
                    },
                    "xlabel": {
                        "type": "string",
                        "description": "X-axis label"
                    },
                    "ylabel": {
                        "type": "string",
                        "description": "Y-axis label"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_pie_chart",
            "description": "Create a pie chart. For Discord stats, use data_query. For external data, FIRST use web_search, THEN pass results via 'data' parameter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_query": {
                        "type": "string",
                        "description": "For INTERNAL Discord stats: 'message distribution by user', 'personality breakdown'. Leave empty if using 'data' parameter.",
                    },
                    "data": {
                        "type": "object",
                        "description": "Raw data as {label: value} pairs. For external data from web_search. Example: {'Category A': 45, 'Category B': 30}",
                        "additionalProperties": {"type": "number"}
                    },
                    "title": {
                        "type": "string",
                        "description": "Chart title"
                    },
                    "show_percentages": {
                        "type": "boolean",
                        "description": "Show percentage labels on pie slices",
                        "default": True
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_table",
            "description": "Create a formatted table. For Discord stats, use data_query. For EXTERNAL data (sports standings, rankings, etc.), FIRST use web_search to get the data, THEN pass it via 'data' parameter as a list of row objects.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_query": {
                        "type": "string",
                        "description": "For INTERNAL Discord stats: 'top users by messages', 'user stats'. Leave empty if using 'data' parameter.",
                    },
                    "data": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Raw table data as list of row objects. Use for EXTERNAL data. Example for Premier League: [{'Position': 1, 'Team': 'Liverpool', 'Points': 45}, {'Position': 2, 'Team': 'Arsenal', 'Points': 42}]"
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Column names in display order. Required when using 'data' parameter. Example: ['Position', 'Team', 'Points']"
                    },
                    "title": {
                        "type": "string",
                        "description": "Table title"
                    },
                    "max_rows": {
                        "type": "integer",
                        "description": "Maximum number of rows to display",
                        "default": 20
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_comparison_chart",
            "description": "Create a comparison chart. For Discord stats, use data_query. For external data, FIRST use web_search, THEN pass results via 'data' parameter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_query": {
                        "type": "string",
                        "description": "For INTERNAL Discord stats: 'compare messages between users'. Leave empty if using 'data' parameter.",
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Category labels for comparison. Example: ['Team A', 'Team B', 'Team C']"
                    },
                    "datasets": {
                        "type": "object",
                        "description": "Named datasets to compare as {name: [values]}. Example: {'Wins': [10, 8, 6], 'Losses': [2, 4, 5]}",
                        "additionalProperties": {"type": "array", "items": {"type": "number"}}
                    },
                    "title": {
                        "type": "string",
                        "description": "Chart title"
                    },
                    "ylabel": {
                        "type": "string",
                        "description": "Y-axis label"
                    }
                },
                "required": ["title"]
            }
        }
    }
]

# Computational and data retrieval tools
COMPUTATIONAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "wolfram_query",
            "description": "Query Wolfram Alpha for calculations, unit conversions, factual information, computational knowledge, AND HISTORICAL WEATHER DATA. ALWAYS use this for: historical weather questions ('when did it last rain', 'weather history', 'past rainfall'), math problems, scientific questions, conversions, astronomy, or any question requiring computational/historical knowledge. PREFERRED over web_search for historical weather and scientific data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question to ask Wolfram Alpha (e.g., 'what is 2^100', 'convert 100 USD to EUR', 'population of Tokyo', 'when did it last rain in Aberdeen Scotland', 'weather history Aberdeen UK', 'rainfall Aberdeen January 2026', 'last dry day in London')"
                    },
                    "units": {
                        "type": "string",
                        "description": "Unit system to use: 'metric' or 'imperial'",
                        "enum": ["metric", "imperial"],
                        "default": "metric"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current time in any timezone. Use this when users ask 'what time is it in Tokyo', 'current time in London', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone name (e.g., 'America/New_York', 'Europe/London', 'Asia/Tokyo', 'US/Pacific') or city name"
                    }
                },
                "required": ["timezone"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "translate",
            "description": "Translate text between languages. Use for 'translate X to Spanish', 'how do you say X in French', 'translate from Japanese to English', etc. Supports 60+ languages. Source language is auto-detected if not specified.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to translate"
                    },
                    "target_language": {
                        "type": "string",
                        "description": "Target language name or code (e.g., 'spanish', 'french', 'japanese', 'es', 'fr', 'ja')"
                    },
                    "source_language": {
                        "type": "string",
                        "description": "Source language name or code (e.g., 'english', 'japanese', 'en', 'ja'). If the user specifies what language to translate FROM, include it here. Leave empty to auto-detect."
                    }
                },
                "required": ["text", "target_language"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wikipedia",
            "description": "Look up information on Wikipedia. Use for factual questions about people, places, events, concepts, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The topic to search for on Wikipedia"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "youtube_search",
            "description": "Search for YouTube videos. Use when users ask for video recommendations, tutorials, music videos, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for YouTube"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (1-5)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "random_choice",
            "description": "Generate random outcomes: dice rolls, coin flips, random numbers, or pick from a list. Use for 'roll a d20', 'flip a coin', 'pick a random number', 'choose between X Y Z'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["dice", "coin", "number", "choice"],
                        "description": "Type of random: 'dice' for dice rolls, 'coin' for coin flip, 'number' for random number, 'choice' for picking from options"
                    },
                    "dice_notation": {
                        "type": "string",
                        "description": "For dice: notation like '1d20', '2d6', '3d8+5'"
                    },
                    "min": {
                        "type": "integer",
                        "description": "For number: minimum value"
                    },
                    "max": {
                        "type": "integer",
                        "description": "For number: maximum value"
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "For choice: list of options to pick from"
                    }
                },
                "required": ["type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "url_preview",
            "description": "Fetch and summarize a webpage URL. Use when users share a link and ask 'what is this', 'summarize this article', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch and summarize"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "iracing_driver_stats",
            "description": "Look up iRacing driver statistics. Use for 'what's my iRating', 'check driver stats for X', 'iRacing stats'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "driver_name": {
                        "type": "string",
                        "description": "The iRacing driver name to look up (optional if user has linked account)"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["road", "oval", "dirt_road", "dirt_oval"],
                        "description": "Racing category to get stats for",
                        "default": "road"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "iracing_series_info",
            "description": "Get information about an iRacing series including schedule, participation, and current week details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "series_name": {
                        "type": "string",
                        "description": "Name of the iRacing series to look up"
                    }
                },
                "required": ["series_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "user_stats",
            "description": "Get Discord activity statistics for a user in this server. Use for 'how many messages has X sent', 'user activity stats'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Discord username to look up (optional, defaults to requesting user)"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look back",
                        "default": 30
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Set a reminder for the user. Use for 'remind me to X in 30 minutes', 'set a reminder for tomorrow at 5pm'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "What to remind the user about"
                    },
                    "time": {
                        "type": "string",
                        "description": "When to send the reminder (e.g., 'in 30 minutes', 'tomorrow at 5pm', 'in 2 hours')"
                    }
                },
                "required": ["message", "time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stock_price",
            "description": "Get current stock or cryptocurrency prices. Accepts ticker symbols (AAPL, TSLA) or company names (Microsoft, Apple, Bitcoin).",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker (AAPL, TSLA) or company/crypto name (Microsoft, Apple, Bitcoin, Ethereum)"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "stock_history",
            "description": "Get historical stock price data AND automatically create a line chart. Use this for requests like 'chart TSLA stock', 'graph of Apple price', 'show me NVDA over time'. Returns a chart image. Supports up to 20 years of data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (AAPL, TSLA, MSFT, NVDA, etc.) or company name (Tesla, Apple, Microsoft)"
                    },
                    "period": {
                        "type": "string",
                        "description": "Time period: '1M', '3M', '6M', '1Y', '2Y', '5Y', '10Y', or 'MAX' (all available data)",
                        "enum": ["1M", "3M", "6M", "1Y", "2Y", "5Y", "10Y", "MAX"],
                        "default": "1Y"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sports_scores",
            "description": "Get live sports scores, recent results, or upcoming games. Use for questions like 'what's the score of the Lakers game', 'NFL scores today', 'did Arsenal win', 'Premier League results', 'F1 results'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sport": {
                        "type": "string",
                        "description": "Sport league/type",
                        "enum": ["nfl", "nba", "mlb", "nhl", "soccer", "f1", "college-football", "college-basketball"]
                    },
                    "league": {
                        "type": "string",
                        "description": "For soccer: specific league (eng.1 for Premier League, esp.1 for La Liga, ger.1 for Bundesliga, ita.1 for Serie A, fra.1 for Ligue 1, usa.1 for MLS, uefa.champions for Champions League)"
                    },
                    "team": {
                        "type": "string",
                        "description": "Team name to filter results (optional)"
                    }
                },
                "required": ["sport"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "movie_info",
            "description": "Get information about a movie or TV show including ratings, cast, plot. Use for 'tell me about the movie X', 'what's the rating of Y'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the movie or TV show"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Release year (optional, helps with accuracy)"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "define_word",
            "description": "Get the dictionary definition of a word. Use for 'define X', 'what does X mean', 'definition of Y'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "word": {
                        "type": "string",
                        "description": "The word to define"
                    }
                },
                "required": ["word"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "currency_convert",
            "description": "Convert between currencies. Use for 'convert 100 USD to EUR', 'how much is 50 pounds in dollars', 'exchange rate USD to JPY'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "Amount to convert"
                    },
                    "from_currency": {
                        "type": "string",
                        "description": "Source currency code (e.g., 'USD', 'EUR', 'GBP', 'JPY')"
                    },
                    "to_currency": {
                        "type": "string",
                        "description": "Target currency code (e.g., 'USD', 'EUR', 'GBP', 'JPY')"
                    }
                },
                "required": ["amount", "from_currency", "to_currency"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather conditions. If user specifies a location, use it. If user just says 'weather' without a location, omit the location parameter to use their saved preference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name, zip code, or 'city,country' (e.g., 'London', 'New York,US', '90210'). OPTIONAL - omit if user doesn't specify a location to use their saved preference."
                    },
                    "units": {
                        "type": "string",
                        "description": "Temperature units: 'metric' (Celsius), 'imperial' (Fahrenheit), or 'standard' (Kelvin)",
                        "enum": ["metric", "imperial", "standard"],
                        "default": "metric"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_forecast",
            "description": "Get weather forecast. If user specifies a location, use it. If not, omit the location parameter to use their saved preference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name, zip code, or 'city,country'. OPTIONAL - omit if user doesn't specify a location to use their saved preference."
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days to forecast (1-5)",
                        "minimum": 1,
                        "maximum": 5,
                        "default": 3
                    },
                    "units": {
                        "type": "string",
                        "description": "Temperature units",
                        "enum": ["metric", "imperial", "standard"],
                        "default": "metric"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information, news, facts, or any information not in your knowledge base. Use for current events, news, sports results, product info. NOTE: For historical weather data, calculations, or scientific questions, use wolfram_query instead - it has better data for those.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g., 'closest F1 championship margins history', 'latest news about...', 'current standings for...')"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "image_search",
            "description": "Search for and display an image. Use when user asks to 'show me', 'picture of', 'image of', 'what does X look like', or any request to see a visual. Returns an image that will be displayed in chat.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for the image (e.g., 'Peter Attia', 'golden retriever puppy', 'Eiffel Tower at night')"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# Combined list of all tools
ALL_TOOLS = VISUALIZATION_TOOLS + COMPUTATIONAL_TOOLS


class DataRetriever:
    """Retrieve data from database based on natural language queries"""

    def __init__(self, db):
        self.db = db

    def retrieve_data(self, query: str, channel_id: Optional[int] = None, guild_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve data based on natural language query

        Args:
            query: Natural language description of data needed
            channel_id: Discord channel ID for context
            guild_id: Discord guild/server ID for server-specific data

        Returns:
            Dictionary with data structure suitable for visualization
        """
        query_lower = query.lower()

        # Parse time range from query
        days = self._extract_time_range(query_lower)

        # Determine query type and fetch data (expanded pattern matching)
        # Top users / most active
        if any(kw in query_lower for kw in ['top user', 'most active', 'most message', 'who chat',
                                              'who talk', 'leaderboard', 'rankings']):
            return self._get_top_users_by_messages(days, limit=self._extract_limit(query_lower), guild_id=guild_id)

        # Messages by hour of day
        elif any(kw in query_lower for kw in ['by hour', 'per hour', 'hourly', 'time of day',
                                                'busiest hour', 'active hour']):
            return self._get_messages_by_hour(days, channel_id, guild_id)

        # Messages by day (trend over time)
        elif any(kw in query_lower for kw in ['per day', 'by day', 'daily', 'over time',
                                                'messages per', 'activity over']):
            return self._get_messages_by_day(days, channel_id, guild_id)

        elif 'activity' in query_lower and 'trend' in query_lower:
            return self._get_activity_trend(days, channel_id, guild_id)

        elif any(kw in query_lower for kw in ['personality', 'distribution', 'mode breakdown']):
            return self._get_personality_distribution()

        else:
            # Return error instead of silently defaulting
            return {
                'type': 'bar',
                'data': {},
                'metadata': {'error': f'Could not understand data query: {query}. Try: "top users by messages", "messages by hour", "messages per day", "personality distribution"'}
            }

    def _extract_time_range(self, query: str) -> int:
        """Extract time range in days from query"""
        if 'today' in query or '24 hour' in query:
            return 1
        elif 'week' in query or '7 day' in query:
            return 7
        elif 'month' in query or '30 day' in query:
            return 30
        elif 'year' in query or '365 day' in query:
            return 365
        else:
            # Default to 7 days
            return 7

    def _extract_limit(self, query: str) -> int:
        """Extract limit/top N from query"""
        import re
        match = re.search(r'top (\d+)', query)
        if match:
            return int(match.group(1))
        match = re.search(r'(\d+) (user|people)', query)
        if match:
            return int(match.group(1))
        return 10  # Default

    def _get_top_users_by_messages(self, days: int, limit: int = 10, guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Get top users by message count for a specific guild"""
        results = self.db.get_message_stats(days=days, limit=limit, guild_id=guild_id, exclude_bots=True)

        data = {}
        for user in results:
            username = user['username'][:20]  # Truncate long names
            data[username] = user['message_count']

        return {
            'type': 'bar',
            'data': data,
            'metadata': {'time_range_days': days, 'limit': limit}
        }

    def _get_messages_by_hour(self, days: int, channel_id: Optional[int], guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Get message distribution by hour of day for a specific guild"""
        query = """
            SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(*) as count
            FROM messages
            WHERE timestamp > NOW() - INTERVAL '1 day' * %s
            AND LOWER(username) NOT LIKE '%%bot%%'
        """
        params = [days]

        if guild_id:
            query += " AND guild_id = %s"
            params.append(guild_id)
        if channel_id:
            query += " AND channel_id = %s"
            params.append(channel_id)

        query += " GROUP BY hour ORDER BY hour"

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()

        data = {f"{int(row[0])}:00": row[1] for row in results}

        return {
            'type': 'bar',
            'data': data,
            'metadata': {'time_range_days': days}
        }

    def _get_messages_by_day(self, days: int, channel_id: Optional[int], guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Get messages per day over time for a specific guild"""
        query = """
            SELECT DATE(timestamp) as day, COUNT(*) as count
            FROM messages
            WHERE timestamp > NOW() - INTERVAL '1 day' * %s
            AND LOWER(username) NOT LIKE '%%bot%%'
        """
        params = [days]

        if guild_id:
            query += " AND guild_id = %s"
            params.append(guild_id)
        if channel_id:
            query += " AND channel_id = %s"
            params.append(channel_id)

        query += " GROUP BY day ORDER BY day"

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()

        data = {'Messages': [row[1] for row in results]}
        x_labels = [row[0].strftime('%m/%d') for row in results]

        return {
            'type': 'line',
            'data': data,
            'x_labels': x_labels,
            'metadata': {'time_range_days': days}
        }

    def _get_activity_trend(self, days: int, channel_id: Optional[int], guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Get activity trend"""
        return self._get_messages_by_day(days, channel_id, guild_id)

    def _get_personality_distribution(self) -> Dict[str, Any]:
        """Get server personality distribution"""
        query = """
            SELECT personality, COUNT(*) as count
            FROM server_settings
            GROUP BY personality
        """

        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                results = cur.fetchall()

        data = {row[0] if row[0] else 'default': row[1] for row in results}

        return {
            'type': 'pie',
            'data': data,
            'metadata': {}
        }
