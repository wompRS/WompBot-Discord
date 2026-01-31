"""
Tool Execution Handler
Executes tools requested by the LLM and returns results
"""

import json
import random
import re
from typing import Dict, Any, Optional
from io import BytesIO
from datetime import datetime, timedelta
import discord
import pytz
import requests
from bs4 import BeautifulSoup

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

        # Common timezone aliases
        self.timezone_aliases = {
            'est': 'America/New_York', 'edt': 'America/New_York',
            'cst': 'America/Chicago', 'cdt': 'America/Chicago',
            'mst': 'America/Denver', 'mdt': 'America/Denver',
            'pst': 'America/Los_Angeles', 'pdt': 'America/Los_Angeles',
            'gmt': 'Europe/London', 'bst': 'Europe/London',
            'utc': 'UTC',
            'tokyo': 'Asia/Tokyo', 'japan': 'Asia/Tokyo',
            'london': 'Europe/London', 'uk': 'Europe/London',
            'paris': 'Europe/Paris', 'france': 'Europe/Paris',
            'berlin': 'Europe/Berlin', 'germany': 'Europe/Berlin',
            'sydney': 'Australia/Sydney', 'australia': 'Australia/Sydney',
            'new york': 'America/New_York', 'nyc': 'America/New_York',
            'los angeles': 'America/Los_Angeles', 'la': 'America/Los_Angeles',
            'chicago': 'America/Chicago',
            'denver': 'America/Denver',
            'phoenix': 'America/Phoenix',
            'seattle': 'America/Los_Angeles',
            'miami': 'America/New_York',
            'dallas': 'America/Chicago',
            'houston': 'America/Chicago',
            'toronto': 'America/Toronto', 'canada': 'America/Toronto',
            'vancouver': 'America/Vancouver',
            'moscow': 'Europe/Moscow', 'russia': 'Europe/Moscow',
            'beijing': 'Asia/Shanghai', 'china': 'Asia/Shanghai', 'shanghai': 'Asia/Shanghai',
            'hong kong': 'Asia/Hong_Kong',
            'singapore': 'Asia/Singapore',
            'dubai': 'Asia/Dubai',
            'india': 'Asia/Kolkata', 'mumbai': 'Asia/Kolkata', 'delhi': 'Asia/Kolkata',
            'seoul': 'Asia/Seoul', 'korea': 'Asia/Seoul',
        }

    async def execute_tool(
        self,
        tool_call: Dict[str, Any],
        channel_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute a single tool call

        Args:
            tool_call: Tool call from LLM
            channel_id: Discord channel ID for context
            user_id: Discord user ID for user-specific preferences

        Returns:
            Dictionary with execution result
        """
        try:
            function_name = tool_call["function"]["name"]
            arguments_str = tool_call["function"].get("arguments", "{}")
            arguments = json.loads(arguments_str) if arguments_str else {}

            print(f"🛠️  Executing tool: {function_name}")
            print(f"   Arguments: {arguments}")

        except (KeyError, json.JSONDecodeError) as e:
            return {
                "success": False,
                "error": "Invalid tool call format. Please try your request again."
            }

        try:
            if function_name == "create_bar_chart":
                return await self._create_bar_chart(arguments, channel_id)
            elif function_name == "create_line_chart":
                return await self._create_line_chart(arguments, channel_id)
            elif function_name == "create_pie_chart":
                return await self._create_pie_chart(arguments, channel_id)
            elif function_name == "create_table":
                return await self._create_table(arguments, channel_id)
            elif function_name == "create_comparison_chart":
                return await self._create_comparison_chart(arguments, channel_id)

            # Computational tools
            elif function_name == "wolfram_query":
                return await self._wolfram_query(arguments)
            elif function_name == "get_weather":
                return await self._get_weather(arguments, user_id)
            elif function_name == "get_weather_forecast":
                return await self._get_weather_forecast(arguments, user_id)
            elif function_name == "web_search":
                return await self._web_search(arguments)

            # New utility tools
            elif function_name == "get_time":
                return await self._get_time(arguments)
            elif function_name == "translate":
                return await self._translate(arguments)
            elif function_name == "wikipedia":
                return await self._wikipedia(arguments)
            elif function_name == "youtube_search":
                return await self._youtube_search(arguments)
            elif function_name == "random_choice":
                return await self._random_choice(arguments)
            elif function_name == "url_preview":
                return await self._url_preview(arguments)
            elif function_name == "iracing_driver_stats":
                return await self._iracing_driver_stats(arguments, user_id)
            elif function_name == "iracing_series_info":
                return await self._iracing_series_info(arguments)
            elif function_name == "user_stats":
                return await self._user_stats(arguments, channel_id, user_id)
            elif function_name == "create_reminder":
                return await self._create_reminder(arguments, user_id, channel_id)
            elif function_name == "stock_price":
                return await self._stock_price(arguments)
            elif function_name == "movie_info":
                return await self._movie_info(arguments)
            elif function_name == "define_word":
                return await self._define_word(arguments)
            elif function_name == "currency_convert":
                return await self._currency_convert(arguments)
            else:
                return {
                    "success": False,
                    "error": f"Unknown tool: {function_name}"
                }
        except Exception as e:
            print(f"❌ Tool execution error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    async def _create_bar_chart(self, args: Dict[str, Any], channel_id: Optional[int]) -> Dict[str, Any]:
        """Create bar chart"""
        # Retrieve data based on query
        data_result = self.data.retrieve_data(args["data_query"], channel_id)

        # Create visualization
        image_buffer = self.viz.create_bar_chart(
            data=data_result["data"],
            title=args["title"],
            xlabel=args.get("xlabel", ""),
            ylabel=args.get("ylabel", "Value"),
            horizontal=args.get("horizontal", False)
        )

        return {
            "success": True,
            "type": "image",
            "image": image_buffer,
            "description": f"Created bar chart: {args['title']}"
        }

    async def _create_line_chart(self, args: Dict[str, Any], channel_id: Optional[int]) -> Dict[str, Any]:
        """Create line chart"""
        data_result = self.data.retrieve_data(args["data_query"], channel_id)

        image_buffer = self.viz.create_line_chart(
            data=data_result["data"],
            title=args["title"],
            xlabel=args.get("xlabel", ""),
            ylabel=args.get("ylabel", "Value"),
            x_labels=data_result.get("x_labels")
        )

        return {
            "success": True,
            "type": "image",
            "image": image_buffer,
            "description": f"Created line chart: {args['title']}"
        }

    async def _create_pie_chart(self, args: Dict[str, Any], channel_id: Optional[int]) -> Dict[str, Any]:
        """Create pie chart"""
        data_result = self.data.retrieve_data(args["data_query"], channel_id)

        image_buffer = self.viz.create_pie_chart(
            data=data_result["data"],
            title=args["title"],
            show_percentages=args.get("show_percentages", True)
        )

        return {
            "success": True,
            "type": "image",
            "image": image_buffer,
            "description": f"Created pie chart: {args['title']}"
        }

    async def _create_table(self, args: Dict[str, Any], channel_id: Optional[int]) -> Dict[str, Any]:
        """Create table"""
        data_result = self.data.retrieve_data(args["data_query"], channel_id)

        # For tables, data should be list of dicts
        if isinstance(data_result["data"], dict):
            # Convert dict to list of dicts
            table_data = [{"name": k, "value": v} for k, v in data_result["data"].items()]
            columns = ["name", "value"]
        else:
            table_data = data_result["data"]
            columns = list(table_data[0].keys()) if table_data else []

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

    async def _create_comparison_chart(self, args: Dict[str, Any], channel_id: Optional[int]) -> Dict[str, Any]:
        """Create comparison chart"""
        data_result = self.data.retrieve_data(args["data_query"], channel_id)

        # Extract categories and datasets from result
        # This depends on how the data retriever structures comparison data
        if "categories" in data_result and "datasets" in data_result:
            categories = data_result["categories"]
            datasets = data_result["datasets"]
        else:
            # Fallback: use data as-is
            categories = list(data_result["data"].keys())
            datasets = {"Values": list(data_result["data"].values())}

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
        """Execute Wolfram Alpha query with both metric and imperial units"""
        if not self.wolfram:
            return {"success": False, "error": "Wolfram Alpha not configured"}

        query = args["query"]

        # Query with both metric and imperial units
        metric_result = self.wolfram.query(query, units="metric")
        imperial_result = self.wolfram.query(query, units="imperial")

        # If metric query failed, just return the error
        if not metric_result["success"]:
            return {"success": False, "error": metric_result.get("error", "Query failed")}

        # If both succeeded and answers are different, show both
        if imperial_result["success"] and metric_result["answer"] != imperial_result["answer"]:
            # Answers differ, likely unit-dependent - show both
            combined_answer = f"**Metric:** {metric_result['answer']}\n**Imperial:** {imperial_result['answer']}"
            return {"success": True, "type": "text", "text": combined_answer, "description": f"Wolfram Alpha: {query}"}
        else:
            # Answers are the same or imperial failed - just show metric
            return {"success": True, "type": "text", "text": metric_result["answer"], "description": f"Wolfram Alpha: {query}"}

    async def _get_weather(self, args: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
        """Get current weather as a visual card"""
        if not self.weather:
            return {"success": False, "error": "Weather API not configured"}

        # Check if location was provided, otherwise use saved preference
        location = args.get("location")
        units = args.get("units", "metric")

        if not location and user_id:
            # Try to get saved preference
            pref = self.db.get_weather_preference(user_id)
            if pref:
                location = pref['location']
                units = pref['units']  # Use saved unit preference
            else:
                return {
                    "success": False,
                    "error": "No location provided. Please specify a location (e.g., 'weather in Tokyo') or set a default location using `/weather_set`."
                }
        elif not location:
            return {
                "success": False,
                "error": "No location provided. Please specify a location (e.g., 'weather in Tokyo')."
            }

        result = self.weather.get_current_weather(location, units=units)

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
        units = args.get("units", "metric")

        if not location and user_id:
            # Try to get saved preference
            pref = self.db.get_weather_preference(user_id)
            if pref:
                location = pref['location']
                units = pref['units']  # Use saved unit preference
            else:
                return {
                    "success": False,
                    "error": "No location provided. Please specify a location (e.g., 'weather in Tokyo') or set a default location using `/weather_set`."
                }
        elif not location:
            return {
                "success": False,
                "error": "No location provided. Please specify a location (e.g., 'weather in Tokyo')."
            }

        result = self.weather.get_forecast(location, units=units, days=days)

        if result["success"]:
            return {"success": True, "type": "text", "text": result["summary"], "description": f"{days}-day forecast for {location}"}
        else:
            return {"success": False, "error": result.get("error", "Forecast query failed")}

    async def _web_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform web search and return formatted results"""
        import asyncio

        if not self.search:
            return {"success": False, "error": "Web search not configured"}

        query = args["query"]

        try:
            # Run search in thread pool (search.search() is blocking)
            search_results_raw = await asyncio.to_thread(self.search.search, query)

            if not search_results_raw:
                return {"success": False, "error": "No search results found"}

            # Format results for display
            search_results = self.search.format_results_for_llm(search_results_raw)

            return {
                "success": True,
                "type": "text",
                "text": search_results,
                "description": f"Web search: {query}"
            }
        except Exception as e:
            return {"success": False, "error": f"Search failed: {str(e)}"}

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
        """Translate text using LibreTranslate (free) or Google Translate"""
        import asyncio

        text = args["text"]
        target = args["target_language"].lower()
        source = args.get("source_language", "auto")

        # Language code mapping for common names
        lang_codes = {
            'spanish': 'es', 'french': 'fr', 'german': 'de', 'italian': 'it',
            'portuguese': 'pt', 'russian': 'ru', 'japanese': 'ja', 'chinese': 'zh',
            'korean': 'ko', 'arabic': 'ar', 'hindi': 'hi', 'dutch': 'nl',
            'swedish': 'sv', 'norwegian': 'no', 'danish': 'da', 'finnish': 'fi',
            'polish': 'pl', 'turkish': 'tr', 'greek': 'el', 'hebrew': 'he',
            'thai': 'th', 'vietnamese': 'vi', 'indonesian': 'id', 'malay': 'ms',
            'english': 'en'
        }
        target = lang_codes.get(target, target)
        if source != "auto":
            source = lang_codes.get(source, source)

        # Try LibreTranslate (free, public instances)
        libre_instances = [
            "https://libretranslate.com",
            "https://translate.argosopentech.com",
            "https://translate.terraprint.co"
        ]

        for instance in libre_instances:
            try:
                def do_translate():
                    resp = requests.post(
                        f"{instance}/translate",
                        json={
                            "q": text,
                            "source": source if source != "auto" else "auto",
                            "target": target
                        },
                        timeout=10
                    )
                    return resp

                response = await asyncio.to_thread(do_translate)
                if response.status_code == 200:
                    result = response.json()
                    translated = result.get("translatedText", "")
                    if translated:
                        return {
                            "success": True,
                            "type": "text",
                            "text": f"**Translation ({target}):** {translated}",
                            "description": f"Translated to {target}"
                        }
            except Exception:
                continue

        return {"success": False, "error": "Translation service unavailable. Try again later."}

    async def _wikipedia(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Look up information on Wikipedia"""
        import asyncio

        query = args["query"]

        try:
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
                resp = requests.get(search_url, params=search_params, timeout=10)
                return resp

            search_response = await asyncio.to_thread(do_search)
            search_data = search_response.json()

            if not search_data.get("query", {}).get("search"):
                return {"success": False, "error": f"No Wikipedia article found for '{query}'"}

            title = search_data["query"]["search"][0]["title"]

            # Get the summary
            def do_summary():
                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"
                resp = requests.get(summary_url, timeout=10)
                return resp

            summary_response = await asyncio.to_thread(do_summary)
            summary_data = summary_response.json()

            extract = summary_data.get("extract", "No summary available.")
            page_url = summary_data.get("content_urls", {}).get("desktop", {}).get("page", "")

            # Truncate if too long
            if len(extract) > 1000:
                extract = extract[:997] + "..."

            result = f"**{title}**\n\n{extract}"
            if page_url:
                result += f"\n\n[Read more on Wikipedia]({page_url})"

            return {
                "success": True,
                "type": "text",
                "text": result,
                "description": f"Wikipedia: {title}"
            }

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
                resp = requests.get(search_url, headers=headers, timeout=10)
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

    async def _url_preview(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch and summarize a URL"""
        import asyncio

        url = args["url"]

        # Validate URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            def do_fetch():
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                resp = requests.get(url, headers=headers, timeout=15)
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

    async def _user_stats(self, args: Dict[str, Any], channel_id: Optional[int], user_id: Optional[int]) -> Dict[str, Any]:
        """Get Discord user activity stats"""
        username = args.get("username")
        days = args.get("days", 30)

        try:
            # Get top message stats for the time period
            stats = self.db.get_message_stats(days=days, limit=50)

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
        """Get stock or crypto price using yfinance"""
        import asyncio

        query = args["symbol"].upper()

        # Common company/crypto name to ticker mappings
        name_to_ticker = {
            # Tech giants
            'MICROSOFT': 'MSFT', 'APPLE': 'AAPL', 'GOOGLE': 'GOOGL', 'ALPHABET': 'GOOGL',
            'AMAZON': 'AMZN', 'META': 'META', 'FACEBOOK': 'META', 'NETFLIX': 'NFLX',
            'NVIDIA': 'NVDA', 'TESLA': 'TSLA', 'AMD': 'AMD', 'INTEL': 'INTC',
            'IBM': 'IBM', 'ORACLE': 'ORCL', 'CISCO': 'CSCO', 'ADOBE': 'ADBE',
            'SALESFORCE': 'CRM', 'PAYPAL': 'PYPL', 'SQUARE': 'SQ', 'BLOCK': 'SQ',
            'SHOPIFY': 'SHOP', 'SPOTIFY': 'SPOT', 'UBER': 'UBER', 'LYFT': 'LYFT',
            'AIRBNB': 'ABNB', 'TWITTER': 'X', 'SNAP': 'SNAP', 'SNAPCHAT': 'SNAP',
            'PINTEREST': 'PINS', 'ZOOM': 'ZM', 'SLACK': 'WORK', 'DROPBOX': 'DBX',
            'PALANTIR': 'PLTR', 'SNOWFLAKE': 'SNOW', 'DATADOG': 'DDOG',
            'CROWDSTRIKE': 'CRWD', 'CLOUDFLARE': 'NET', 'TWILIO': 'TWLO',
            # Finance
            'JPMORGAN': 'JPM', 'JP MORGAN': 'JPM', 'CHASE': 'JPM',
            'BANK OF AMERICA': 'BAC', 'BOFA': 'BAC', 'WELLS FARGO': 'WFC',
            'GOLDMAN': 'GS', 'GOLDMAN SACHS': 'GS', 'MORGAN STANLEY': 'MS',
            'VISA': 'V', 'MASTERCARD': 'MA', 'AMEX': 'AXP', 'AMERICAN EXPRESS': 'AXP',
            'BERKSHIRE': 'BRK-B', 'BERKSHIRE HATHAWAY': 'BRK-B',
            # Retail
            'WALMART': 'WMT', 'TARGET': 'TGT', 'COSTCO': 'COST', 'HOME DEPOT': 'HD',
            'LOWES': 'LOW', "LOWE'S": 'LOW', 'NIKE': 'NKE', 'STARBUCKS': 'SBUX',
            'MCDONALDS': 'MCD', "MCDONALD'S": 'MCD', 'CHIPOTLE': 'CMG',
            # Healthcare
            'JOHNSON': 'JNJ', 'JOHNSON AND JOHNSON': 'JNJ', 'J&J': 'JNJ',
            'PFIZER': 'PFE', 'MODERNA': 'MRNA', 'MERCK': 'MRK',
            'UNITEDHEALTH': 'UNH', 'CVS': 'CVS', 'WALGREENS': 'WBA',
            # Energy
            'EXXON': 'XOM', 'EXXONMOBIL': 'XOM', 'CHEVRON': 'CVX', 'SHELL': 'SHEL',
            # Crypto (yfinance uses -USD suffix)
            'BITCOIN': 'BTC-USD', 'BTC': 'BTC-USD',
            'ETHEREUM': 'ETH-USD', 'ETH': 'ETH-USD', 'ETHER': 'ETH-USD',
            'DOGECOIN': 'DOGE-USD', 'DOGE': 'DOGE-USD',
            'SOLANA': 'SOL-USD', 'SOL': 'SOL-USD',
            'CARDANO': 'ADA-USD', 'ADA': 'ADA-USD',
            'RIPPLE': 'XRP-USD', 'XRP': 'XRP-USD',
            'LITECOIN': 'LTC-USD', 'LTC': 'LTC-USD',
            'POLKADOT': 'DOT-USD', 'DOT': 'DOT-USD',
            'CHAINLINK': 'LINK-USD', 'LINK': 'LINK-USD',
            'AVALANCHE': 'AVAX-USD', 'AVAX': 'AVAX-USD',
            'SHIBA': 'SHIB-USD', 'SHIB': 'SHIB-USD', 'SHIBA INU': 'SHIB-USD',
            # Indices
            'S&P': '^GSPC', 'S&P 500': '^GSPC', 'SP500': '^GSPC', 'SPX': '^GSPC',
            'DOW': '^DJI', 'DOW JONES': '^DJI', 'DJIA': '^DJI',
            'NASDAQ': '^IXIC', 'NASDAQ COMPOSITE': '^IXIC',
            'RUSSELL': '^RUT', 'RUSSELL 2000': '^RUT',
        }

        symbol = name_to_ticker.get(query, query)

        try:
            def do_fetch():
                # Use Yahoo Finance
                import yfinance as yf
                ticker = yf.Ticker(symbol)
                info = ticker.info
                return info

            info = await asyncio.to_thread(do_fetch)

            if not info or 'currentPrice' not in info and 'regularMarketPrice' not in info:
                return {"success": False, "error": f"Could not find price for '{symbol}'"}

            price = info.get('currentPrice') or info.get('regularMarketPrice')
            prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose')
            name = info.get('shortName') or info.get('longName') or symbol

            if prev_close and price:
                change = price - prev_close
                change_pct = (change / prev_close) * 100
                change_str = f"+${change:.2f} (+{change_pct:.2f}%)" if change >= 0 else f"-${abs(change):.2f} ({change_pct:.2f}%)"
            else:
                change_str = ""

            result = f"**{name}** ({symbol})\n"
            result += f"Price: **${price:,.2f}**"
            if change_str:
                result += f" ({change_str})"

            return {
                "success": True,
                "type": "text",
                "text": result,
                "description": f"Stock price: {symbol}"
            }

        except ImportError:
            return {"success": False, "error": "Stock price lookup not available (yfinance not installed)"}
        except Exception as e:
            return {"success": False, "error": f"Stock lookup failed: {str(e)}"}

    async def _movie_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get movie/TV show info from OMDB"""
        import asyncio
        import os

        title = args["title"]
        year = args.get("year")

        omdb_key = os.getenv("OMDB_API_KEY")
        if not omdb_key:
            # Try web search as fallback
            return await self._web_search({"query": f"{title} movie {year or ''} imdb"})

        try:
            def do_fetch():
                params = {"apikey": omdb_key, "t": title, "plot": "short"}
                if year:
                    params["y"] = year
                resp = requests.get("http://www.omdbapi.com/", params=params, timeout=10)
                return resp.json()

            data = await asyncio.to_thread(do_fetch)

            if data.get("Response") == "False":
                return {"success": False, "error": data.get("Error", "Movie not found")}

            result = f"**{data.get('Title', 'Unknown')}** ({data.get('Year', 'N/A')})\n\n"
            result += f"Rating: **{data.get('imdbRating', 'N/A')}/10** ({data.get('imdbVotes', 'N/A')} votes)\n"
            result += f"Runtime: {data.get('Runtime', 'N/A')}\n"
            result += f"Genre: {data.get('Genre', 'N/A')}\n"
            result += f"Director: {data.get('Director', 'N/A')}\n"
            result += f"Cast: {data.get('Actors', 'N/A')}\n\n"
            result += f"{data.get('Plot', '')}"

            return {
                "success": True,
                "type": "text",
                "text": result,
                "description": f"Movie info: {title}"
            }

        except Exception as e:
            return {"success": False, "error": f"Movie lookup failed: {str(e)}"}

    async def _define_word(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get dictionary definition"""
        import asyncio

        word = args["word"].lower().strip()

        try:
            def do_fetch():
                url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
                resp = requests.get(url, timeout=10)
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

            return {
                "success": True,
                "type": "text",
                "text": result.strip(),
                "description": f"Definition: {word}"
            }

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

        try:
            def do_convert():
                # Frankfurter API - free, no key required
                url = f"https://api.frankfurter.app/latest?amount={amount}&from={from_curr}&to={to_curr}"
                resp = requests.get(url, timeout=10)
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

            result = f"**{amount:,.2f} {from_curr}** = **{converted_str} {to_curr}**\n"
            result += f"Rate: 1 {from_curr} = {rate:.4f} {to_curr}"

            return {
                "success": True,
                "type": "text",
                "text": result,
                "description": f"Currency: {from_curr} to {to_curr}"
            }

        except Exception as e:
            return {"success": False, "error": f"Currency conversion failed: {str(e)}"}
