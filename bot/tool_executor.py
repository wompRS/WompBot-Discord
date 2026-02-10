"""
Tool Execution Handler
Executes tools requested by the LLM and returns results
"""

import asyncio
import hashlib
import json
import logging
import random
import re
from typing import Dict, Any, Optional
from io import BytesIO
from datetime import datetime, timedelta
import discord
import pytz
import requests
from bs4 import BeautifulSoup
from redis_cache import get_cache
from constants import TIMEZONE_ALIASES, LANGUAGE_CODES, STOCK_TICKERS, CRYPTO_TICKERS

logger = logging.getLogger(__name__)

class ToolExecutor:
    """Execute tools requested by LLM"""

    def __init__(self, db, visualizer, data_retriever, wolfram=None, weather=None, search=None,
                 iracing_manager=None, reminder_manager=None, bot=None):
        """
        Args:
            db: Database instance
            visualizer: GeneralVisualizer instance
            data_retriever: DataRetriever instance
            wolfram: WolframAlpha instance (optional)
            weather: Weather instance (optional)
            search: SearchClient instance (optional)
            iracing_manager: iRacingManager instance (optional)
            reminder_manager: ReminderManager instance (optional)
            bot: Discord bot instance (optional, for user lookups)
        """
        self.db = db
        self.viz = visualizer
        self.data = data_retriever
        self.wolfram = wolfram
        self.weather = weather
        self.search = search
        self.iracing_manager = iracing_manager
        self.reminder_manager = reminder_manager
        self.bot = bot
        self.cache = get_cache()

        # Reusable HTTP session for connection pooling (avoids redundant TCP+TLS handshakes)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "WompBot/1.0"})

        # Common timezone aliases (centralised in constants.py)
        self.timezone_aliases = TIMEZONE_ALIASES

        # Tool registry: maps function name to (handler, extra_args_needed)
        # extra_args_needed is a tuple of context keys the handler requires beyond `arguments`
        self._registry = {
            # Visualization tools (need channel_id, guild_id)
            "create_bar_chart":       (self._create_bar_chart, ("channel_id", "guild_id")),
            "create_line_chart":      (self._create_line_chart, ("channel_id", "guild_id")),
            "create_pie_chart":       (self._create_pie_chart, ("channel_id", "guild_id")),
            "create_table":           (self._create_table, ("channel_id", "guild_id")),
            "create_comparison_chart": (self._create_comparison_chart, ("channel_id", "guild_id")),
            # Computational tools (no extra context)
            "wolfram_query":          (self._wolfram_query, ()),
            "web_search":             (self._web_search, ()),
            "image_search":           (self._image_search, ()),
            "get_time":               (self._get_time, ()),
            "translate":              (self._translate, ()),
            "wikipedia":              (self._wikipedia, ()),
            "youtube_search":         (self._youtube_search, ()),
            "random_choice":          (self._random_choice, ()),
            "url_preview":            (self._url_preview, ()),
            "iracing_series_info":    (self._iracing_series_info, ()),
            "stock_price":            (self._stock_price, ()),
            "stock_history":          (self._stock_history, ()),
            "movie_info":             (self._movie_info, ()),
            "define_word":            (self._define_word, ()),
            "currency_convert":       (self._currency_convert, ()),
            "sports_scores":          (self._sports_scores, ()),
            # Tools needing user_id
            "get_weather":            (self._get_weather, ("user_id",)),
            "get_weather_forecast":   (self._get_weather_forecast, ("user_id",)),
            "iracing_driver_stats":   (self._iracing_driver_stats, ("user_id",)),
            # Tools needing user_id + channel_id
            "create_reminder":        (self._create_reminder, ("user_id", "channel_id")),
            # Tools needing all context
            "user_stats":             (self._user_stats, ("channel_id", "user_id", "guild_id")),
        }

    def _cache_key(self, prefix: str, *args) -> str:
        """Generate a deterministic cache key from a prefix and arguments."""
        raw = f"{prefix}:{':'.join(str(a).lower().strip() for a in args)}"
        # Use hash for long keys to stay within Redis key limits
        if len(raw) > 100:
            return f"{prefix}:{hashlib.sha256(raw.encode()).hexdigest()}"
        return raw

    async def execute_tool(
        self,
        tool_call: Dict[str, Any],
        channel_id: Optional[int] = None,
        user_id: Optional[int] = None,
        guild_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute a single tool call

        Args:
            tool_call: Tool call from LLM
            channel_id: Discord channel ID for context
            user_id: Discord user ID for user-specific preferences
            guild_id: Discord guild/server ID for server-specific data

        Returns:
            Dictionary with execution result
        """
        try:
            function_name = tool_call["function"]["name"]
            arguments_raw = tool_call["function"].get("arguments", "{}")
            # Handle both JSON string and dict formats (different models return different formats)
            if isinstance(arguments_raw, dict):
                arguments = arguments_raw
            elif isinstance(arguments_raw, str):
                arguments = json.loads(arguments_raw) if arguments_raw else {}
            else:
                arguments = {}

            logger.info("Executing tool: %s", function_name)
            logger.debug("Tool arguments: %s", arguments)

        except (KeyError, json.JSONDecodeError, TypeError) as e:
            logger.error("Tool call parse error: %s (type: %s)", e, type(e).__name__)
            logger.error("Raw tool_call object: %s", tool_call)
            return {
                "success": False,
                "error": "Invalid tool call format. Please try your request again.",
                "parse_error": True
            }

        try:
            # Registry-based dispatch: look up handler and required context args
            registry_entry = self._registry.get(function_name)
            if registry_entry:
                handler, extra_keys = registry_entry
                # Build positional args: arguments first, then any needed context
                context_map = {
                    "channel_id": channel_id,
                    "user_id": user_id,
                    "guild_id": guild_id,
                }
                call_args = [arguments] + [context_map[k] for k in extra_keys]
                return await handler(*call_args)
            else:
                return {
                    "success": False,
                    "error": f"Unknown tool: {function_name}"
                }
        except Exception as e:
            logger.error("Tool execution error: %s", e, exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def _create_bar_chart(self, args: Dict[str, Any], channel_id: Optional[int], guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Create bar chart"""
        # Check if raw data was provided (for external data)
        if "data" in args and args["data"]:
            data = args["data"]
        elif "data_query" in args and args["data_query"]:
            # Retrieve data based on query (for internal Discord stats)
            data_result = self.data.retrieve_data(args["data_query"], channel_id, guild_id)
            data = data_result["data"]
        else:
            return {"success": False, "error": "Either 'data' or 'data_query' must be provided"}

        # Create visualization
        image_buffer = self.viz.create_bar_chart(
            data=data,
            title=args["title"],
            xlabel=args.get("xlabel", ""),
            ylabel=args.get("ylabel", ""),
            horizontal=args.get("horizontal", False)
        )

        return {
            "success": True,
            "type": "image",
            "image": image_buffer,
            "description": f"Created bar chart: {args['title']}"
        }

    async def _create_line_chart(self, args: Dict[str, Any], channel_id: Optional[int], guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Create line chart"""
        # Check if raw data was provided (for external data)
        if "data" in args and args["data"]:
            data = args["data"]
            x_labels = args.get("x_labels")
        elif "data_query" in args and args["data_query"]:
            # Retrieve data based on query (for internal Discord stats)
            data_result = self.data.retrieve_data(args["data_query"], channel_id, guild_id)
            data = data_result["data"]
            x_labels = data_result.get("x_labels")
        else:
            return {"success": False, "error": "Either 'data' or 'data_query' must be provided"}

        image_buffer = self.viz.create_line_chart(
            data=data,
            title=args["title"],
            xlabel=args.get("xlabel", ""),
            ylabel=args.get("ylabel", "Value"),
            x_labels=x_labels
        )

        return {
            "success": True,
            "type": "image",
            "image": image_buffer,
            "description": f"Created line chart: {args['title']}"
        }

    async def _create_pie_chart(self, args: Dict[str, Any], channel_id: Optional[int], guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Create pie chart"""
        # Check if raw data was provided (for external data)
        if "data" in args and args["data"]:
            data = args["data"]
        elif "data_query" in args and args["data_query"]:
            # Retrieve data based on query (for internal Discord stats)
            data_result = self.data.retrieve_data(args["data_query"], channel_id, guild_id)
            data = data_result["data"]
        else:
            return {"success": False, "error": "Either 'data' or 'data_query' must be provided"}

        image_buffer = self.viz.create_pie_chart(
            data=data,
            title=args["title"],
            show_percentages=args.get("show_percentages", True)
        )

        return {
            "success": True,
            "type": "image",
            "image": image_buffer,
            "description": f"Created pie chart: {args['title']}"
        }

    async def _create_table(self, args: Dict[str, Any], channel_id: Optional[int], guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Create table"""
        # Check if raw data was provided (for external data like sports standings)
        if "data" in args and args["data"]:
            table_data = args["data"]
            # Use provided columns or extract from first row
            if "columns" in args and args["columns"]:
                columns = args["columns"]
            elif table_data and isinstance(table_data[0], dict):
                columns = list(table_data[0].keys())
            else:
                columns = []
        elif "data_query" in args and args["data_query"]:
            # Retrieve data based on query (for internal Discord stats)
            data_result = self.data.retrieve_data(args["data_query"], channel_id, guild_id)

            # For tables, data should be list of dicts
            if isinstance(data_result["data"], dict):
                # Convert dict to list of dicts
                table_data = [{"name": k, "value": v} for k, v in data_result["data"].items()]
                columns = ["name", "value"]
            else:
                table_data = data_result["data"]
                columns = list(table_data[0].keys()) if table_data else []
        else:
            return {"success": False, "error": "Either 'data' or 'data_query' must be provided"}

        image_buffer = self.viz.create_table(
            data=table_data,
            columns=columns,
            title=args["title"],
            max_rows=args.get("max_rows", 20)
        )

        return {
            "success": True,
            "type": "image",
            "image": image_buffer,
            "description": f"Created table: {args['title']}"
        }

    async def _create_comparison_chart(self, args: Dict[str, Any], channel_id: Optional[int], guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Create comparison chart"""
        # Check if raw data was provided (for external data)
        if "categories" in args and args["categories"] and "datasets" in args and args["datasets"]:
            categories = args["categories"]
            datasets = args["datasets"]
        elif "data_query" in args and args["data_query"]:
            # Retrieve data based on query (for internal Discord stats)
            data_result = self.data.retrieve_data(args["data_query"], channel_id, guild_id)

            # Extract categories and datasets from result
            if "categories" in data_result and "datasets" in data_result:
                categories = data_result["categories"]
                datasets = data_result["datasets"]
            else:
                # Fallback: use data as-is
                categories = list(data_result["data"].keys())
                datasets = {"Values": list(data_result["data"].values())}
        else:
            return {"success": False, "error": "Either 'categories'+'datasets' or 'data_query' must be provided"}

        image_buffer = self.viz.create_comparison_chart(
            categories=categories,
            datasets=datasets,
            title=args["title"],
            ylabel=args.get("ylabel", "Value")
        )

        return {
            "success": True,
            "type": "image",
            "image": image_buffer,
            "description": f"Created comparison chart: {args['title']}"
        }

    # ========== Computational Tools ==========

    async def _wolfram_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Wolfram Alpha query with both metric and imperial units (cached 1 hour)"""
        if not self.wolfram:
            return {"success": False, "error": "Wolfram Alpha not configured"}

        query = args["query"]

        # Check cache first (1-hour TTL)
        cache_key = self._cache_key("wolfram", query)
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Wolfram cache hit: %s", query)
            return cached

        # Query with both metric and imperial units (run in threads to not block event loop)
        import asyncio
        metric_result, imperial_result = await asyncio.gather(
            asyncio.to_thread(self.wolfram.query, query, "metric"),
            asyncio.to_thread(self.wolfram.query, query, "imperial")
        )

        # If metric query failed, just return the error
        if not metric_result["success"]:
            return {"success": False, "error": metric_result.get("error", "Query failed")}

        # If both succeeded and answers are different, show both
        if imperial_result["success"] and metric_result["answer"] != imperial_result["answer"]:
            # Answers differ, likely unit-dependent - show both
            combined_answer = f"**Metric:** {metric_result['answer']}\n**Imperial:** {imperial_result['answer']}"
            result = {"success": True, "type": "text", "text": combined_answer, "description": f"Wolfram Alpha: {query}"}
        else:
            # Answers are the same or imperial failed - just show metric
            result = {"success": True, "type": "text", "text": metric_result["answer"], "description": f"Wolfram Alpha: {query}"}

        self.cache.set(cache_key, result, ttl=3600)  # 1 hour
        return result

    async def _get_weather(self, args: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get current weather as a visual card (weather data cached 30 min)"""
        if not self.weather:
            return {"success": False, "error": "Weather API not configured"}

        # Check if location was provided, otherwise use saved preference
        location = args.get("location")
        units = args.get("units", "imperial")

        if not location and user_id:
            # Try to get saved preference
            pref = self.db.get_weather_preference(user_id)
            if pref:
                location = pref['location']
                units = pref['units']  # Use saved unit preference
            else:
                return {
                    "success": False,
                    "error": "No location provided. Please specify a location (e.g., 'weather in Tokyo') or set a default location using `!weatherset`."
                }
        elif not location:
            return {
                "success": False,
                "error": "No location provided. Please specify a location (e.g., 'weather in Tokyo')."
            }

        # Cache the raw weather API data (30-min TTL) to avoid repeated API calls
        cache_key = self._cache_key("weather", location, units)
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.debug("Weather cache hit: %s", location)
            result = cached_data
        else:
            result = await asyncio.to_thread(self.weather.get_current_weather, location, units)
            if result.get("success"):
                self.cache.set(cache_key, result, ttl=1800)  # 30 minutes

        if result["success"]:
            # Extract temperatures and convert for dual unit display
            temp = result["temperature"]
            feels = result["feels_like"]
            high = result["temp_max"]
            low = result["temp_min"]

            if units == "metric":
                temp_c, temp_f = temp, round(temp * 9/5 + 32, 1)
                feels_c, feels_f = feels, round(feels * 9/5 + 32, 1)
                high_c, high_f = high, round(high * 9/5 + 32, 1)
                low_c, low_f = low, round(low * 9/5 + 32, 1)
                wind_ms, wind_mph = result["wind_speed"], round(result["wind_speed"] * 2.237, 1)
            else:
                temp_c, temp_f = round((temp - 32) * 5/9, 1), temp
                feels_c, feels_f = round((feels - 32) * 5/9, 1), feels
                high_c, high_f = round((high - 32) * 5/9, 1), high
                low_c, low_f = round((low - 32) * 5/9, 1), low
                wind_ms, wind_mph = round(result["wind_speed"] / 2.237, 1), result["wind_speed"]

            # Get state/region from reverse geocoding if coordinates available
            state = None
            if result.get("latitude") and result.get("longitude"):
                state = self.weather.reverse_geocode(result["latitude"], result["longitude"])

            # Create weather card visualization with icon
            image_buffer = self.viz.create_weather_card(
                location=result["location"],
                country=result["country"],
                state=state,
                latitude=result.get("latitude"),
                longitude=result.get("longitude"),
                station_id=result.get("station_id"),
                description=result["description"],
                icon_code=result["icon"],  # OpenWeatherMap icon code
                temp_c=temp_c,
                temp_f=temp_f,
                feels_c=feels_c,
                feels_f=feels_f,
                high_c=high_c,
                high_f=high_f,
                low_c=low_c,
                low_f=low_f,
                humidity=result["humidity"],
                wind_ms=wind_ms,
                wind_mph=wind_mph,
                clouds=result["clouds"]
            )

            return {"success": True, "type": "image", "image": image_buffer, "description": f"Weather for {location}"}
        else:
            return {"success": False, "error": result.get("error", "Weather query failed")}

    async def _get_weather_forecast(self, args: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get weather forecast"""
        if not self.weather:
            return {"success": False, "error": "Weather API not configured"}

        # Check if location was provided, otherwise use saved preference
        location = args.get("location")
        days = args.get("days", 3)
        units = args.get("units", "imperial")

        if not location and user_id:
            # Try to get saved preference
            pref = self.db.get_weather_preference(user_id)
            if pref:
                location = pref['location']
                units = pref['units']  # Use saved unit preference
            else:
                return {
                    "success": False,
                    "error": "No location provided. Please specify a location (e.g., 'weather in Tokyo') or set a default location using `!weatherset`."
                }
        elif not location:
            return {
                "success": False,
                "error": "No location provided. Please specify a location (e.g., 'weather in Tokyo')."
            }

        # Cache forecast data (30-min TTL)
        cache_key = self._cache_key("forecast", location, units, days)
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Forecast cache hit: %s", location)
            return cached

        result = await asyncio.to_thread(self.weather.get_forecast, location, units, days)

        if result["success"]:
            response = {"success": True, "type": "text", "text": result["summary"], "description": f"{days}-day forecast for {location}"}
            self.cache.set(cache_key, response, ttl=1800)  # 30 minutes
            return response
        else:
            return {"success": False, "error": result.get("error", "Forecast query failed")}

    async def _web_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform web search and return formatted results (cached 2 hours)"""
        import asyncio

        if not self.search:
            return {"success": False, "error": "Web search not configured"}

        query = args["query"]

        # Check cache first (2-hour TTL)
        cache_key = self._cache_key("search", query)
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Search cache hit: %s", query)
            return cached

        try:
            # Run search in thread pool (search.search() is blocking)
            search_results_raw = await asyncio.to_thread(self.search.search, query)

            if not search_results_raw:
                return {"success": False, "error": "No search results found"}

            # Format results for display
            search_results = self.search.format_results_for_llm(search_results_raw)

            result = {
                "success": True,
                "type": "text",
                "text": search_results,
                "description": f"Web search: {query}"
            }
            self.cache.set(cache_key, result, ttl=7200)  # 2 hours
            return result
        except Exception as e:
            return {"success": False, "error": f"Search failed: {str(e)}"}

    async def _image_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search for an image and return URL for embedding"""
        import asyncio

        query = args.get("query", "")
        if not query:
            return {"success": False, "error": "No search query provided"}

        try:
            def search_images():
                from duckduckgo_search import DDGS

                # Use duckduckgo-search library with safe search ON
                with DDGS() as ddgs:
                    # safesearch='on' enables strict filtering
                    results = list(ddgs.images(query, max_results=5, safesearch='on'))

                    if results:
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                        # Try to find a working image URL
                        for result in results:
                            image_url = result.get('image')
                            if image_url and image_url.startswith('http'):
                                # Verify the image is accessible
                                try:
                                    check = self.session.head(image_url, headers=headers, timeout=5, allow_redirects=True)
                                    if check.status_code == 200:
                                        return {
                                            'url': image_url,
                                            'title': result.get('title', query),
                                            'source': result.get('source', '')
                                        }
                                except Exception:
                                    continue
                return None

            result = await asyncio.to_thread(search_images)

            if result:
                return {
                    "success": True,
                    "type": "image_url",
                    "url": result['url'],
                    "title": result['title'],
                    "description": f"Image of {query}"
                }
            else:
                return {"success": False, "error": f"No images found for '{query}'"}

        except Exception as e:
            logger.error("Image search error: %s", e)
            return {"success": False, "error": f"Image search failed: {str(e)}"}

    # ========== New Utility Tools ==========

    async def _get_time(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get current time in a timezone"""
        timezone_input = args.get("timezone", "UTC").lower().strip()

        # Check aliases first
        tz_name = self.timezone_aliases.get(timezone_input, timezone_input)

        try:
            # Try direct timezone name
            tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            # Try to find a matching timezone
            tz_name_upper = timezone_input.upper()
            for tz_str in pytz.all_timezones:
                if timezone_input.lower() in tz_str.lower():
                    tz = pytz.timezone(tz_str)
                    break
            else:
                return {"success": False, "error": f"Unknown timezone: {timezone_input}. Try formats like 'America/New_York', 'Europe/London', or city names like 'Tokyo', 'London'."}

        now = datetime.now(tz)
        formatted_time = now.strftime("%I:%M %p on %A, %B %d, %Y")
        timezone_display = now.strftime("%Z")

        return {
            "success": True,
            "type": "text",
            "text": f"The current time in {timezone_display} is {formatted_time}",
            "description": f"Time in {timezone_input}"
        }

    async def _translate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Translate text using MyMemory API (free, no API key needed)"""
        import asyncio

        text = args["text"]
        target = args["target_language"].lower().strip()
        source = args.get("source_language", "").lower().strip() or "auto"

        # Language code mapping (centralised in constants.py)
        target = LANGUAGE_CODES.get(target, target)
        if source != "auto":
            source = LANGUAGE_CODES.get(source, source)

        # Reverse lookup for display names
        code_to_name = {v: k.title() for k, v in LANGUAGE_CODES.items()}

        # Use MyMemory API (free, no API key needed for low volume)
        try:
            def do_translate():
                url = "https://api.mymemory.translated.net/get"
                # MyMemory supports "autodetect" as source language
                source_param = source if source != "auto" else "autodetect"
                params = {
                    "q": text[:500],  # Limit text length
                    "langpair": f"{source_param}|{target}",
                    "de": "wompbot@discord.bot"  # Email for higher rate limits
                }
                return self.session.get(url, params=params, timeout=15)

            response = await asyncio.to_thread(do_translate)

            if response.status_code == 200:
                data = response.json()
                translated = data.get('responseData', {}).get('translatedText', '')
                match_quality = data.get('responseData', {}).get('match', 0)
                detected_lang = data.get('responseData', {}).get('detectedLanguage', '')

                # Check for API error messages
                if data.get('responseStatus') == 403:
                    return {"success": False, "error": "Translation rate limit reached. Try again in a minute."}

                if translated and translated.upper() != text.upper():
                    # Build source display name
                    if source == "auto" and detected_lang:
                        source_display = code_to_name.get(detected_lang, detected_lang.upper())
                    elif source != "auto":
                        source_display = code_to_name.get(source, source.upper())
                    else:
                        source_display = "Auto"

                    target_display = code_to_name.get(target, target.upper())

                    return {
                        "success": True,
                        "type": "text",
                        "text": f"**Translation ({source_display} → {target_display}):**\n{translated}",
                        "description": f"Translated from {source_display} to {target_display}"
                    }
                else:
                    target_display = code_to_name.get(target, target.upper())
                    return {"success": False, "error": f"Could not translate text to {target_display}. The text may already be in the target language, or the language pair is not supported."}

        except requests.Timeout:
            return {"success": False, "error": "Translation request timed out. Try again."}
        except Exception as e:
            logger.error("Translation error: %s", e)

        return {"success": False, "error": "Translation service unavailable. Try again later."}

    async def _wikipedia(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Look up information on Wikipedia (cached 1 hour)"""
        import asyncio

        query = args["query"]

        # Check cache first (1-hour TTL — Wikipedia content is stable)
        cache_key = self._cache_key("wiki", query)
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Wikipedia cache hit: %s", query)
            return cached

        try:
            headers = {'User-Agent': 'WompBot/1.0 (Discord Bot; educational project)'}

            def do_search():
                # Search for the article
                search_url = "https://en.wikipedia.org/w/api.php"
                search_params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": 1
                }
                resp = self.session.get(search_url, params=search_params, headers=headers, timeout=10)
                return resp

            search_response = await asyncio.to_thread(do_search)
            search_data = search_response.json()

            if not search_data.get("query", {}).get("search"):
                return {"success": False, "error": f"No Wikipedia article found for '{query}'"}

            title = search_data["query"]["search"][0]["title"]

            # Get the summary
            def do_summary():
                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"
                resp = self.session.get(summary_url, headers=headers, timeout=10)
                return resp

            summary_response = await asyncio.to_thread(do_summary)
            summary_data = summary_response.json()

            extract = summary_data.get("extract", "No summary available.")
            page_url = summary_data.get("content_urls", {}).get("desktop", {}).get("page", "")

            # Truncate if too long
            if len(extract) > 1000:
                extract = extract[:997] + "..."

            text = f"**{title}**\n\n{extract}"
            if page_url:
                text += f"\n\n[Read more on Wikipedia]({page_url})"

            result = {
                "success": True,
                "type": "text",
                "text": text,
                "description": f"Wikipedia: {title}"
            }
            self.cache.set(cache_key, result, ttl=3600)  # 1 hour
            return result

        except Exception as e:
            return {"success": False, "error": f"Wikipedia lookup failed: {str(e)}"}

    async def _youtube_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search for YouTube videos (scrapes results, no API key needed)"""
        import asyncio
        import urllib.parse

        query = args["query"]
        max_results = min(args.get("max_results", 3), 5)

        try:
            def do_search():
                # Use YouTube search URL and parse results
                search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                resp = self.session.get(search_url, headers=headers, timeout=10)
                return resp.text

            html = await asyncio.to_thread(do_search)

            # Extract video IDs and titles from the page
            video_pattern = r'"videoId":"([^"]+)".*?"title":\{"runs":\[\{"text":"([^"]+)"\}'
            matches = re.findall(video_pattern, html)

            if not matches:
                return {"success": False, "error": "No YouTube results found"}

            # Deduplicate and limit
            seen_ids = set()
            results = []
            for video_id, title in matches:
                if video_id not in seen_ids and len(results) < max_results:
                    seen_ids.add(video_id)
                    results.append({
                        "title": title,
                        "url": f"https://www.youtube.com/watch?v={video_id}"
                    })

            if not results:
                return {"success": False, "error": "No YouTube results found"}

            result_text = f"**YouTube results for '{query}':**\n\n"
            for i, vid in enumerate(results, 1):
                result_text += f"{i}. [{vid['title']}]({vid['url']})\n"

            return {
                "success": True,
                "type": "text",
                "text": result_text,
                "description": f"YouTube search: {query}"
            }

        except Exception as e:
            return {"success": False, "error": f"YouTube search failed: {str(e)}"}

    async def _random_choice(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Generate random outcomes"""
        choice_type = args.get("type", "dice")

        if choice_type == "coin":
            result = random.choice(["Heads", "Tails"])
            return {
                "success": True,
                "type": "text",
                "text": f"Coin flip: **{result}**",
                "description": "Coin flip"
            }

        elif choice_type == "dice":
            notation = args.get("dice_notation", "1d6")
            # Parse dice notation like "2d6+5"
            match = re.match(r'(\d+)?d(\d+)([+-]\d+)?', notation.lower())
            if not match:
                return {"success": False, "error": f"Invalid dice notation: {notation}. Use format like '2d6' or '1d20+5'"}

            num_dice = int(match.group(1) or 1)
            die_size = int(match.group(2))
            modifier = int(match.group(3) or 0)

            if num_dice > 100 or die_size > 1000:
                return {"success": False, "error": "Too many dice or die size too large"}

            rolls = [random.randint(1, die_size) for _ in range(num_dice)]
            total = sum(rolls) + modifier

            if num_dice == 1 and modifier == 0:
                result_text = f"Rolling {notation}: **{total}**"
            else:
                rolls_str = ", ".join(str(r) for r in rolls)
                modifier_str = f" {'+' if modifier >= 0 else ''}{modifier}" if modifier else ""
                result_text = f"Rolling {notation}: [{rolls_str}]{modifier_str} = **{total}**"

            return {
                "success": True,
                "type": "text",
                "text": result_text,
                "description": f"Dice roll: {notation}"
            }

        elif choice_type == "number":
            min_val = args.get("min", 1)
            max_val = args.get("max", 100)
            if min_val > max_val:
                min_val, max_val = max_val, min_val
            result = random.randint(min_val, max_val)
            return {
                "success": True,
                "type": "text",
                "text": f"Random number ({min_val}-{max_val}): **{result}**",
                "description": f"Random number {min_val}-{max_val}"
            }

        elif choice_type == "choice":
            options = args.get("options", [])
            if not options:
                return {"success": False, "error": "No options provided to choose from"}
            result = random.choice(options)
            return {
                "success": True,
                "type": "text",
                "text": f"I choose: **{result}**",
                "description": "Random choice"
            }

        return {"success": False, "error": f"Unknown random type: {choice_type}"}

    def _is_internal_url(self, url: str) -> bool:
        """Check if URL points to an internal/private IP address (SSRF protection)"""
        from urllib.parse import urlparse
        import ipaddress
        import socket

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname

            if not hostname:
                return True  # No hostname = invalid

            # Block obvious internal hostnames
            if hostname.lower() in ['localhost', '127.0.0.1', '0.0.0.0', '::1']:
                return True

            # Try to resolve hostname and check if it's a private IP
            try:
                ip_str = socket.gethostbyname(hostname)
                ip = ipaddress.ip_address(ip_str)

                # Block private, loopback, link-local, and reserved addresses
                if (ip.is_private or ip.is_loopback or ip.is_link_local or
                    ip.is_reserved or ip.is_multicast):
                    return True

                # Block AWS metadata endpoint
                if ip_str.startswith('169.254.'):
                    return True

            except (socket.gaierror, ValueError):
                return True  # Can't resolve = block it (fail-closed for safety)

            return False
        except Exception:
            return True  # On error, assume it's internal for safety

    async def _url_preview(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch and summarize a URL"""
        import asyncio

        url = args["url"]

        # Validate URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # SECURITY: Check for SSRF - block internal/private URLs
        if self._is_internal_url(url):
            return {"success": False, "error": "Cannot fetch internal or private URLs"}

        try:
            def do_fetch():
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                resp = self.session.get(url, headers=headers, timeout=15, allow_redirects=False)
                return resp

            response = await asyncio.to_thread(do_fetch)

            if response.status_code != 200:
                return {"success": False, "error": f"Failed to fetch URL (status {response.status_code})"}

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract title
            title = soup.title.string if soup.title else "No title"
            title = title.strip()[:200] if title else "No title"

            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if not meta_desc:
                meta_desc = soup.find('meta', attrs={'property': 'og:description'})
            description = meta_desc.get('content', '') if meta_desc else ''

            # If no meta description, try to get first paragraph
            if not description:
                first_p = soup.find('p')
                if first_p:
                    description = first_p.get_text(strip=True)[:500]

            # Truncate description
            if len(description) > 500:
                description = description[:497] + "..."

            result = f"**{title}**\n\n{description}" if description else f"**{title}**"

            return {
                "success": True,
                "type": "text",
                "text": result,
                "description": f"URL preview: {url[:50]}"
            }

        except requests.Timeout:
            return {"success": False, "error": "Request timed out"}
        except Exception as e:
            return {"success": False, "error": f"Failed to fetch URL: {str(e)}"}

    async def _iracing_driver_stats(self, args: Dict[str, Any], user_id: Optional[int]) -> Dict[str, Any]:
        """Get iRacing driver statistics"""
        if not self.iracing_manager:
            return {"success": False, "error": "iRacing integration not configured"}

        driver_name = args.get("driver_name")
        category = args.get("category", "road")

        try:
            # If no driver name provided, try to get linked account
            if not driver_name and user_id:
                linked = await self.iracing_manager.get_linked_iracing_id(user_id)
                if linked:
                    cust_id = linked[0] if isinstance(linked, tuple) else linked
                    if cust_id:
                        stats = await self.iracing_manager.get_driver_profile(cust_id)
                        if stats:
                            return self._format_iracing_stats(stats, category)
                return {"success": False, "error": "No driver name provided and no linked iRacing account found. Use `/iracing_link` to link your account."}

            # Search for driver by name
            results = await self.iracing_manager.search_driver(driver_name)
            if not results:
                return {"success": False, "error": f"No iRacing driver found matching '{driver_name}'"}

            # Get first result's stats
            driver = results[0]
            stats = await self.iracing_manager.get_driver_profile(driver['cust_id'])
            if stats:
                return self._format_iracing_stats(stats, category)

            return {"success": False, "error": "Could not retrieve driver statistics"}

        except Exception as e:
            return {"success": False, "error": f"iRacing lookup failed: {str(e)}"}

    def _format_iracing_stats(self, stats: Dict[str, Any], category: str) -> Dict[str, Any]:
        """Format iRacing stats for display"""
        display_name = stats.get('display_name', 'Unknown')

        # Find the license for the requested category
        licenses = stats.get('licenses', [])
        category_map = {'road': 1, 'oval': 2, 'dirt_road': 3, 'dirt_oval': 4}
        cat_id = category_map.get(category, 1)

        license_info = None
        for lic in licenses:
            if lic.get('category_id') == cat_id:
                license_info = lic
                break

        if license_info:
            irating = license_info.get('irating', 'N/A')
            sr = license_info.get('safety_rating', 'N/A')
            license_level = license_info.get('license_level_letter', '?')
            license_class = license_info.get('group_name', 'Unknown')

            result = f"**{display_name}** - {category.replace('_', ' ').title()}\n\n"
            result += f"iRating: **{irating}**\n"
            result += f"Safety Rating: **{license_level} {sr}**\n"
            result += f"License: {license_class}"
        else:
            result = f"**{display_name}**\n\nNo {category.replace('_', ' ')} stats available."

        return {
            "success": True,
            "type": "text",
            "text": result,
            "description": f"iRacing stats for {display_name}"
        }

    async def _iracing_series_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get iRacing series information"""
        if not self.iracing_manager:
            return {"success": False, "error": "iRacing integration not configured"}

        series_name = args["series_name"]

        try:
            # Try to find series by name
            series = await self.iracing_manager.get_series_by_name(series_name)

            if not series:
                # Try getting all current series and searching
                all_series = await self.iracing_manager.get_current_series()
                if all_series:
                    series_name_lower = series_name.lower()
                    for s in all_series:
                        if series_name_lower in s.get('series_name', '').lower():
                            series = s
                            break

            if not series:
                return {"success": False, "error": f"No series found matching '{series_name}'"}

            result = f"**{series.get('series_name', 'Unknown')}**\n\n"

            if series.get('category'):
                result += f"Category: {series['category']}\n"
            if series.get('license_group_name'):
                result += f"License: {series['license_group_name']}\n"
            if series.get('min_license_level'):
                result += f"Min License: {series['min_license_level']}\n"
            if series.get('fixed_setup'):
                result += f"Setup: {'Fixed' if series['fixed_setup'] else 'Open'}\n"

            return {
                "success": True,
                "type": "text",
                "text": result,
                "description": f"iRacing series: {series_name}"
            }

        except Exception as e:
            return {"success": False, "error": f"Series lookup failed: {str(e)}"}

    async def _user_stats(self, args: Dict[str, Any], channel_id: Optional[int], user_id: Optional[int], guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Get Discord user activity stats for a specific server"""
        username = args.get("username")
        days = args.get("days", 30)

        try:
            # Get top message stats for the time period, filtered by guild and excluding bots
            stats = self.db.get_message_stats(days=days, limit=50, guild_id=guild_id, exclude_bots=True)

            if username:
                # Filter to find the specified user
                username_lower = username.lower()
                user_stats = None
                for i, stat in enumerate(stats):
                    if stat.get('username', '').lower() == username_lower:
                        user_stats = stat
                        user_stats['rank'] = i + 1
                        break

                if not user_stats:
                    return {"success": False, "error": f"User '{username}' not found in recent activity"}

                result = f"**{user_stats['username']}** - Last {days} days\n\n"
                result += f"Messages: **{user_stats['message_count']}**\n"
                result += f"Rank: #{user_stats['rank']}"

            elif user_id:
                # Try to find the requesting user in the stats
                user_stats = None
                for i, stat in enumerate(stats):
                    if stat.get('user_id') == user_id:
                        user_stats = stat
                        user_stats['rank'] = i + 1
                        break

                if user_stats:
                    result = f"**{user_stats['username']}** - Last {days} days\n\n"
                    result += f"Messages: **{user_stats['message_count']}**\n"
                    result += f"Rank: #{user_stats['rank']}"
                else:
                    result = "No activity found for you in the selected time period."
            else:
                # Show top 5 users
                result = f"**Top Users - Last {days} days**\n\n"
                for i, stat in enumerate(stats[:5], 1):
                    result += f"{i}. **{stat['username']}**: {stat['message_count']} messages\n"

            return {
                "success": True,
                "type": "text",
                "text": result,
                "description": f"User stats for last {days} days"
            }

        except Exception as e:
            return {"success": False, "error": f"Stats lookup failed: {str(e)}"}

    async def _create_reminder(self, args: Dict[str, Any], user_id: Optional[int], channel_id: Optional[int]) -> Dict[str, Any]:
        """Create a reminder for the user"""
        if not self.reminder_manager:
            return {"success": False, "error": "Reminder system not configured"}

        if not user_id:
            return {"success": False, "error": "Cannot create reminder without user context"}

        reminder_text = args["message"]
        time_str = args["time"]

        try:
            # Get username from bot if available
            username = "Unknown"
            if self.bot:
                try:
                    user = await self.bot.fetch_user(user_id)
                    if user:
                        username = user.name
                except Exception:
                    pass

            # Use ReminderSystem's create_reminder method
            # It handles time parsing internally
            result = await self.reminder_manager.create_reminder(
                user_id=user_id,
                username=username,
                channel_id=channel_id or 0,
                message_id=0,  # No message_id in tool context
                reminder_text=reminder_text,
                time_string=time_str
            )

            if result:
                reminder_id, remind_at = result
                time_formatted = remind_at.strftime("%I:%M %p on %B %d, %Y")
                return {
                    "success": True,
                    "type": "text",
                    "text": f"Reminder set! I'll remind you to '{reminder_text}' at {time_formatted}.",
                    "description": f"Reminder created for {time_str}"
                }
            else:
                return {"success": False, "error": "Could not parse the time. Try formats like 'in 30 minutes', 'tomorrow at 3pm', or 'next monday'."}

        except Exception as e:
            return {"success": False, "error": f"Failed to create reminder: {str(e)}"}

    async def _stock_price(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get stock or crypto price using Finnhub (stocks) and CoinGecko (crypto) (cached 5 min)"""
        import asyncio
        import os

        query = args["symbol"].upper()

        # Check cache first (5-min TTL — prices change but not second-by-second for Discord)
        cache_key = self._cache_key("stock", query)
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Stock cache hit: %s", query)
            return cached

        # Check if it's a crypto (centralised in constants.py)
        coingecko_id = CRYPTO_TICKERS.get(query)
        if coingecko_id:
            return await self._fetch_crypto_price_tool(coingecko_id, query)

        # It's a stock - use Finnhub (ticker mapping centralised in constants.py)
        symbol = STOCK_TICKERS.get(query, query)
        finnhub_key = os.getenv('FINNHUB_API_KEY')

        if not finnhub_key:
            return {"success": False, "error": "Stock lookup requires FINNHUB_API_KEY in .env (free at finnhub.io)"}

        try:
            def fetch_finnhub():
                url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={finnhub_key}"
                resp = self.session.get(url, timeout=10)
                return resp.json()

            data = await asyncio.to_thread(fetch_finnhub)

            if not data or data.get('c', 0) == 0:
                return {"success": False, "error": f"Could not find price for '{symbol}'"}

            price = data['c']
            change = data['d']
            change_pct = data['dp']

            # Get company name
            def fetch_profile():
                url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={finnhub_key}"
                resp = self.session.get(url, timeout=10)
                return resp.json()

            profile = await asyncio.to_thread(fetch_profile)
            name = profile.get('name', symbol) if profile else symbol

            change_str = f"+${change:.2f} (+{change_pct:.2f}%)" if change >= 0 else f"${change:.2f} ({change_pct:.2f}%)"

            text = f"**{name}** ({symbol})\n"
            text += f"Price: **${price:,.2f}** ({change_str})"

            result = {
                "success": True,
                "type": "text",
                "text": text,
                "description": f"Stock price: {symbol}"
            }
            self.cache.set(cache_key, result, ttl=300)  # 5 minutes
            return result

        except Exception as e:
            return {"success": False, "error": f"Stock lookup failed: {str(e)}"}

    async def _stock_history(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get historical stock price data using yfinance (no API key needed)"""
        import asyncio
        import yfinance as yf

        symbol = args["symbol"].upper()
        period = args.get("period", "1Y")
        chart_type = args.get("chart_type", "line")  # "line" or "candle"

        # Company name to ticker mapping (centralised in constants.py)
        symbol = STOCK_TICKERS.get(symbol, symbol)

        # Period mapping: internal -> (yfinance period, display name)
        period_map = {
            '1M': ('1mo', '1 Month'),
            '3M': ('3mo', '3 Months'),
            '6M': ('6mo', '6 Months'),
            '1Y': ('1y', '1 Year'),
            '2Y': ('2y', '2 Years'),
            '5Y': ('5y', '5 Years'),
            '10Y': ('10y', '10 Years'),
            'MAX': ('max', 'All Time'),
        }
        yf_period, period_display = period_map.get(period, ('1y', '1 Year'))

        try:
            def fetch_yfinance():
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=yf_period)
                info = ticker.info
                return hist, info

            hist, info = await asyncio.to_thread(fetch_yfinance)

            if hist.empty:
                return {"success": False, "error": f"No historical data found for '{symbol}'"}

            # Get company name
            company_name = info.get('shortName', info.get('longName', symbol))

            # Extract data
            closes = hist['Close'].tolist()
            dates_raw = hist.index.tolist()

            # Format dates based on period length
            if period in ['1M', '3M', '6M']:
                dates = [d.strftime('%m/%d') for d in dates_raw]
            elif period in ['1Y', '2Y']:
                dates = [d.strftime('%m/%y') for d in dates_raw]
            else:
                dates = [d.strftime('%Y') for d in dates_raw]

            # Sample data if there are too many points
            if len(closes) > 80:
                step = len(closes) // 80
                closes = closes[::step]
                dates = dates[::step]

            # Calculate price change
            start_price = closes[0]
            end_price = closes[-1]
            change = end_price - start_price
            change_pct = (change / start_price) * 100 if start_price else 0

            # Create chart using visualizer
            chart_data = {symbol: closes}
            image_buffer = self.viz.create_line_chart(
                data=chart_data,
                title=f"{company_name} ({symbol}) - {period_display}",
                xlabel="Date",
                ylabel="Price ($)",
                x_labels=dates
            )

            # Format summary with additional stats
            change_str = f"+${change:.2f} (+{change_pct:.1f}%)" if change >= 0 else f"-${abs(change):.2f} ({change_pct:.1f}%)"
            summary = f"**{company_name} ({symbol})** {period_display}\n"
            summary += f"${start_price:.2f} → ${end_price:.2f} ({change_str})\n"

            # Add extra info if available
            if info.get('fiftyTwoWeekHigh') and info.get('fiftyTwoWeekLow'):
                summary += f"52W Range: ${info['fiftyTwoWeekLow']:.2f} - ${info['fiftyTwoWeekHigh']:.2f}\n"
            if info.get('marketCap'):
                cap = info['marketCap']
                if cap >= 1e12:
                    cap_str = f"${cap/1e12:.2f}T"
                elif cap >= 1e9:
                    cap_str = f"${cap/1e9:.2f}B"
                else:
                    cap_str = f"${cap/1e6:.2f}M"
                summary += f"Market Cap: {cap_str}"

            return {
                "success": True,
                "type": "image",
                "image": image_buffer,
                "description": summary
            }

        except Exception as e:
            return {"success": False, "error": f"Stock history lookup failed: {str(e)}"}

    async def _fetch_crypto_price_tool(self, coingecko_id: str, display_symbol: str) -> Dict[str, Any]:
        """Fetch crypto price from CoinGecko for tool executor (cached 5 min)"""
        import asyncio

        # Check cache (shares the stock cache namespace with 5-min TTL)
        cache_key = self._cache_key("stock", display_symbol)
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Crypto cache hit: %s", display_symbol)
            return cached

        try:
            def fetch():
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true"
                resp = self.session.get(url, timeout=10)
                return resp.json()

            data = await asyncio.to_thread(fetch)

            if not data or coingecko_id not in data:
                return {"success": False, "error": f"Could not find crypto: '{display_symbol}'"}

            crypto_data = data[coingecko_id]
            price = crypto_data['usd']
            change_pct = crypto_data.get('usd_24h_change', 0) or 0

            name = coingecko_id.replace('-', ' ').title()
            change_str = f"+{change_pct:.2f}%" if change_pct >= 0 else f"{change_pct:.2f}%"

            if price >= 1:
                price_str = f"${price:,.2f}"
            else:
                price_str = f"${price:.6f}"

            text = f"**{name}** ({display_symbol})\n"
            text += f"Price: **{price_str}** (24h: {change_str})"

            result = {
                "success": True,
                "type": "text",
                "text": text,
                "description": f"Crypto price: {display_symbol}"
            }
            self.cache.set(cache_key, result, ttl=300)  # 5 minutes
            return result

        except Exception as e:
            return {"success": False, "error": f"Crypto lookup failed: {str(e)}"}

    async def _movie_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get movie/TV show info from OMDB (cached 24 hours)"""
        import asyncio
        import os

        title = args["title"]
        year = args.get("year")

        # Check cache (24-hour TTL — movie data is very stable)
        cache_key = self._cache_key("movie", title, year or "")
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Movie cache hit: %s", title)
            return cached

        omdb_key = os.getenv("OMDB_API_KEY")
        if not omdb_key:
            # Try web search as fallback
            return await self._web_search({"query": f"{title} movie {year or ''} imdb"})

        try:
            def do_fetch():
                params = {"apikey": omdb_key, "t": title, "plot": "short"}
                if year:
                    params["y"] = year
                resp = self.session.get("https://www.omdbapi.com/", params=params, timeout=10)
                return resp.json()

            data = await asyncio.to_thread(do_fetch)

            if data.get("Response") == "False":
                return {"success": False, "error": data.get("Error", "Movie not found")}

            text = f"**{data.get('Title', 'Unknown')}** ({data.get('Year', 'N/A')})\n\n"
            text += f"Rating: **{data.get('imdbRating', 'N/A')}/10** ({data.get('imdbVotes', 'N/A')} votes)\n"
            text += f"Runtime: {data.get('Runtime', 'N/A')}\n"
            text += f"Genre: {data.get('Genre', 'N/A')}\n"
            text += f"Director: {data.get('Director', 'N/A')}\n"
            text += f"Cast: {data.get('Actors', 'N/A')}\n\n"
            text += f"{data.get('Plot', '')}"

            result = {
                "success": True,
                "type": "text",
                "text": text,
                "description": f"Movie info: {title}"
            }
            self.cache.set(cache_key, result, ttl=86400)  # 24 hours
            return result

        except Exception as e:
            return {"success": False, "error": f"Movie lookup failed: {str(e)}"}

    async def _define_word(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get dictionary definition (cached 24 hours)"""
        import asyncio

        word = args["word"].lower().strip()

        # Check cache (24-hour TTL — definitions don't change)
        cache_key = self._cache_key("define", word)
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Definition cache hit: %s", word)
            return cached

        try:
            def do_fetch():
                from urllib.parse import quote
                # URL encode word to handle special characters safely
                url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(word, safe='')}"
                resp = self.session.get(url, timeout=10)
                return resp

            response = await asyncio.to_thread(do_fetch)

            if response.status_code == 404:
                return {"success": False, "error": f"No definition found for '{word}'"}

            data = response.json()
            if not data or not isinstance(data, list):
                return {"success": False, "error": f"No definition found for '{word}'"}

            entry = data[0]
            result = f"**{word}**"

            # Get phonetic
            phonetic = entry.get('phonetic', '')
            if phonetic:
                result += f" _{phonetic}_"
            result += "\n\n"

            # Get meanings (limit to first 3)
            meanings = entry.get('meanings', [])[:3]
            for meaning in meanings:
                part_of_speech = meaning.get('partOfSpeech', '')
                definitions = meaning.get('definitions', [])[:2]

                if part_of_speech:
                    result += f"**{part_of_speech}**\n"

                for i, defn in enumerate(definitions, 1):
                    definition = defn.get('definition', '')
                    example = defn.get('example', '')
                    result += f"{i}. {definition}\n"
                    if example:
                        result += f"   _Example: \"{example}\"_\n"

                result += "\n"

            response = {
                "success": True,
                "type": "text",
                "text": result.strip(),
                "description": f"Definition: {word}"
            }
            self.cache.set(cache_key, response, ttl=86400)  # 24 hours
            return response

        except Exception as e:
            return {"success": False, "error": f"Definition lookup failed: {str(e)}"}

    async def _currency_convert(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Convert between currencies using Frankfurter API (free, no key needed)"""
        import asyncio

        amount = args["amount"]
        from_curr = args["from_currency"].upper().strip()
        to_curr = args["to_currency"].upper().strip()

        # Common currency aliases
        currency_aliases = {
            'DOLLAR': 'USD', 'DOLLARS': 'USD', 'US': 'USD', 'BUCK': 'USD', 'BUCKS': 'USD',
            'EURO': 'EUR', 'EUROS': 'EUR',
            'POUND': 'GBP', 'POUNDS': 'GBP', 'BRITISH': 'GBP', 'STERLING': 'GBP',
            'YEN': 'JPY', 'JAPANESE': 'JPY',
            'YUAN': 'CNY', 'CHINESE': 'CNY', 'RMB': 'CNY',
            'FRANC': 'CHF', 'SWISS': 'CHF',
            'CANADIAN': 'CAD', 'CAD$': 'CAD',
            'AUSTRALIAN': 'AUD', 'AUD$': 'AUD', 'AUSSIE': 'AUD',
            'INDIAN': 'INR', 'RUPEE': 'INR', 'RUPEES': 'INR',
            'MEXICAN': 'MXN', 'PESO': 'MXN', 'PESOS': 'MXN',
            'KOREAN': 'KRW', 'WON': 'KRW',
            'BRAZILIAN': 'BRL', 'REAL': 'BRL',
            'RUSSIAN': 'RUB', 'RUBLE': 'RUB', 'RUBLES': 'RUB',
            'SWEDISH': 'SEK', 'KRONA': 'SEK',
            'NORWEGIAN': 'NOK', 'KRONE': 'NOK',
            'DANISH': 'DKK',
            'POLISH': 'PLN', 'ZLOTY': 'PLN',
            'TURKISH': 'TRY', 'LIRA': 'TRY',
            'SINGAPORE': 'SGD',
            'HONG KONG': 'HKD', 'HK': 'HKD',
            'NEW ZEALAND': 'NZD', 'KIWI': 'NZD',
            'SOUTH AFRICAN': 'ZAR', 'RAND': 'ZAR',
        }

        from_curr = currency_aliases.get(from_curr, from_curr)
        to_curr = currency_aliases.get(to_curr, to_curr)

        # Check cache first (30-min TTL)
        cache_key = self._cache_key("currency", from_curr, to_curr, str(amount))
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Currency cache hit: %s->%s", from_curr, to_curr)
            return cached

        try:
            def do_convert():
                # Frankfurter API - free, no key required
                url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_curr}&to={to_curr}"
                resp = self.session.get(url, timeout=10)
                return resp

            response = await asyncio.to_thread(do_convert)

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('message', f'API error (status {response.status_code})')
                return {"success": False, "error": error_msg}

            data = response.json()
            rates = data.get('rates', {})

            if to_curr not in rates:
                return {"success": False, "error": f"Could not convert {from_curr} to {to_curr}. Check currency codes."}

            converted = rates[to_curr]
            rate = converted / amount if amount != 0 else 0

            # Format with appropriate precision
            if converted >= 1000:
                converted_str = f"{converted:,.2f}"
            elif converted >= 1:
                converted_str = f"{converted:.2f}"
            else:
                converted_str = f"{converted:.4f}"

            text = f"**{amount:,.2f} {from_curr}** = **{converted_str} {to_curr}**\n"
            text += f"Rate: 1 {from_curr} = {rate:.4f} {to_curr}"

            result = {
                "success": True,
                "type": "text",
                "text": text,
                "description": f"Currency: {from_curr} to {to_curr}"
            }
            self.cache.set(cache_key, result, ttl=1800)  # 30 minutes
            return result

        except Exception as e:
            return {"success": False, "error": f"Currency conversion failed: {str(e)}"}

    async def _sports_scores(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get sports scores from ESPN API (no key needed, cached 5 min)"""
        import asyncio

        sport = args["sport"].lower()
        league = args.get("league", "")
        team_filter = args.get("team", "").lower()

        # Check cache (5-min TTL — scores change but not second-by-second)
        cache_key = self._cache_key("sports", sport, league, team_filter)
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Sports cache hit: %s %s", sport, team_filter)
            return cached

        # Map sport to ESPN API endpoint
        sport_endpoints = {
            "nfl": "football/nfl",
            "nba": "basketball/nba",
            "mlb": "baseball/mlb",
            "nhl": "hockey/nhl",
            "soccer": f"soccer/{league}" if league else "soccer/eng.1",  # Default to Premier League
            "f1": "racing/f1",
            "college-football": "football/college-football",
            "college-basketball": "basketball/mens-college-basketball",
        }

        endpoint = sport_endpoints.get(sport)
        if not endpoint:
            return {"success": False, "error": f"Unknown sport: {sport}"}

        try:
            def fetch_scores():
                url = f"https://site.api.espn.com/apis/site/v2/sports/{endpoint}/scoreboard"
                resp = self.session.get(url, timeout=15)
                return resp.json()

            data = await asyncio.to_thread(fetch_scores)

            events = data.get("events", [])
            if not events:
                return {"success": True, "type": "text", "text": f"No {sport.upper()} games found today.", "description": f"{sport.upper()} scores"}

            results = []
            for event in events[:10]:  # Limit to 10 games
                name = event.get("name", "Unknown")
                status_obj = event.get("status", {})
                status_type = status_obj.get("type", {})
                status = status_type.get("description", "Unknown")
                status_state = status_type.get("state", "")

                # Get competitors
                competitions = event.get("competitions", [{}])
                if competitions:
                    competitors = competitions[0].get("competitors", [])

                    # Filter by team if specified
                    if team_filter:
                        team_match = False
                        for comp in competitors:
                            team_name = comp.get("team", {}).get("displayName", "").lower()
                            team_abbrev = comp.get("team", {}).get("abbreviation", "").lower()
                            if team_filter in team_name or team_filter in team_abbrev:
                                team_match = True
                                break
                        if not team_match:
                            continue

                    # Format score
                    if len(competitors) >= 2:
                        away = competitors[0] if competitors[0].get("homeAway") == "away" else competitors[1]
                        home = competitors[1] if competitors[0].get("homeAway") == "away" else competitors[0]

                        away_name = away.get("team", {}).get("abbreviation", "???")
                        home_name = home.get("team", {}).get("abbreviation", "???")
                        away_score = away.get("score", "-")
                        home_score = home.get("score", "-")

                        # Winner indicator
                        away_win = ""
                        home_win = ""
                        if status_state == "post":
                            try:
                                if int(away_score) > int(home_score):
                                    away_win = " W"
                                elif int(home_score) > int(away_score):
                                    home_win = " W"
                            except (ValueError, TypeError):
                                pass

                        if status_state == "in":
                            # Live game
                            detail = status_obj.get("type", {}).get("detail", "")
                            results.append(f"**LIVE** {away_name} {away_score} @ {home_name} {home_score} ({detail})")
                        elif status_state == "post":
                            # Finished
                            results.append(f"{away_name} {away_score}{away_win} @ {home_name} {home_score}{home_win} (Final)")
                        else:
                            # Scheduled
                            date_str = event.get("date", "")
                            if date_str:
                                from datetime import datetime as dt
                                try:
                                    game_time = dt.fromisoformat(date_str.replace("Z", "+00:00"))
                                    time_str = game_time.strftime("%I:%M %p")
                                except (ValueError, TypeError):
                                    time_str = status
                            else:
                                time_str = status
                            results.append(f"{away_name} @ {home_name} ({time_str})")

            if not results:
                if team_filter:
                    return {"success": True, "type": "text", "text": f"No games found for '{team_filter}' in {sport.upper()} today.", "description": f"{sport.upper()} scores"}
                return {"success": True, "type": "text", "text": f"No {sport.upper()} games found.", "description": f"{sport.upper()} scores"}

            # Get league name for header
            league_info = data.get("leagues", [{}])[0]
            league_name = league_info.get("name", sport.upper())

            result_text = f"**{league_name} Scores**\n\n"
            result_text += "\n".join(results)

            result = {
                "success": True,
                "type": "text",
                "text": result_text,
                "description": f"{sport.upper()} scores"
            }
            self.cache.set(cache_key, result, ttl=300)  # 5 minutes
            return result

        except Exception as e:
            return {"success": False, "error": f"Sports scores lookup failed: {str(e)}"}
