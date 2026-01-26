"""
LLM Tool Definitions and Data Retrieval
Defines tools the LLM can call and provides data access
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

# Tool definitions for LLM function calling
VISUALIZATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_bar_chart",
            "description": "Create a bar chart for INTERNAL BOT DATA ONLY (Discord message stats, user activity). Do NOT use for external web search data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_query": {
                        "type": "string",
                        "description": "INTERNAL data only: 'top 10 users by messages', 'messages by hour'. NOT for external data.",
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
                "required": ["data_query", "title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_line_chart",
            "description": "Create a line chart for INTERNAL BOT DATA trends. Do NOT use for external web search data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_query": {
                        "type": "string",
                        "description": "INTERNAL data only: 'messages per day', 'user activity trend'. NOT for external data.",
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
                "required": ["data_query", "title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_pie_chart",
            "description": "Create a pie chart for INTERNAL BOT DATA distributions. Do NOT use for external web search data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_query": {
                        "type": "string",
                        "description": "INTERNAL data only: 'message distribution by user', 'personality breakdown'. NOT for external data.",
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
                "required": ["data_query", "title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_table",
            "description": "Create a formatted table for INTERNAL BOT DATA ONLY (Discord message stats, user activity). Do NOT use for external data from web searches - present that as text instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_query": {
                        "type": "string",
                        "description": "INTERNAL bot data only: 'top users by messages', 'user stats', 'activity by day'. NOT for external web data.",
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
                "required": ["data_query", "title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_comparison_chart",
            "description": "Create a comparison chart for INTERNAL BOT DATA ONLY. Do NOT use for external web search data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_query": {
                        "type": "string",
                        "description": "INTERNAL data only: 'compare messages between users', 'activity by day'. NOT for external data.",
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
                "required": ["data_query", "title"]
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
            "description": "Query Wolfram Alpha for calculations, unit conversions, factual information, or computational knowledge. Use this for math problems, scientific questions, conversions, or any question requiring computational knowledge.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or calculation to ask Wolfram Alpha (e.g., 'what is 2^100', 'convert 100 USD to EUR', 'population of Tokyo', 'solve x^2 + 5x + 6 = 0')"
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
            "description": "Search the web for current information, news, facts, or any information not in your knowledge base. Use this when you need up-to-date information about current events, recent data, sports results, or anything you're not certain about.",
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
    }
]

# Combined list of all tools
ALL_TOOLS = VISUALIZATION_TOOLS + COMPUTATIONAL_TOOLS


class DataRetriever:
    """Retrieve data from database based on natural language queries"""

    def __init__(self, db):
        self.db = db

    def retrieve_data(self, query: str, channel_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieve data based on natural language query

        Args:
            query: Natural language description of data needed
            channel_id: Discord channel ID for context

        Returns:
            Dictionary with data structure suitable for visualization
        """
        query_lower = query.lower()

        # Parse time range from query
        days = self._extract_time_range(query_lower)

        # Determine query type and fetch data
        if 'top' in query_lower and 'user' in query_lower and 'message' in query_lower:
            return self._get_top_users_by_messages(days, limit=self._extract_limit(query_lower))

        elif 'message' in query_lower and 'hour' in query_lower:
            return self._get_messages_by_hour(days, channel_id)

        elif 'message' in query_lower and 'day' in query_lower:
            return self._get_messages_by_day(days, channel_id)

        elif 'activity' in query_lower and 'trend' in query_lower:
            return self._get_activity_trend(days, channel_id)

        elif 'personality' in query_lower or 'distribution' in query_lower:
            return self._get_personality_distribution()

        else:
            # Default: top users
            return self._get_top_users_by_messages(days, limit=10)

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

    def _get_top_users_by_messages(self, days: int, limit: int = 10) -> Dict[str, Any]:
        """Get top users by message count"""
        results = self.db.get_message_stats(days=days, limit=limit)

        data = {}
        for user in results:
            username = user['username'][:20]  # Truncate long names
            data[username] = user['message_count']

        return {
            'type': 'bar',
            'data': data,
            'metadata': {'time_range_days': days, 'limit': limit}
        }

    def _get_messages_by_hour(self, days: int, channel_id: Optional[int]) -> Dict[str, Any]:
        """Get message distribution by hour of day"""
        query = """
            SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(*) as count
            FROM messages
            WHERE timestamp > NOW() - INTERVAL '%s days'
            """ + (" AND channel_id = %s" if channel_id else "") + """
            GROUP BY hour
            ORDER BY hour
        """

        params = [days]
        if channel_id:
            params.append(channel_id)

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

    def _get_messages_by_day(self, days: int, channel_id: Optional[int]) -> Dict[str, Any]:
        """Get messages per day over time"""
        query = """
            SELECT DATE(timestamp) as day, COUNT(*) as count
            FROM messages
            WHERE timestamp > NOW() - INTERVAL '%s days'
            """ + (" AND channel_id = %s" if channel_id else "") + """
            GROUP BY day
            ORDER BY day
        """

        params = [days]
        if channel_id:
            params.append(channel_id)

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

    def _get_activity_trend(self, days: int, channel_id: Optional[int]) -> Dict[str, Any]:
        """Get activity trend"""
        return self._get_messages_by_day(days, channel_id)

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
