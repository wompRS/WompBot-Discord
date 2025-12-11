"""
Tool Execution Handler
Executes tools requested by the LLM and returns results
"""

import json
from typing import Dict, Any, Optional
from io import BytesIO
import discord

class ToolExecutor:
    """Execute tools requested by LLM"""

    def __init__(self, db, visualizer, data_retriever, wolfram=None, weather=None, search=None):
        """
        Args:
            db: Database instance
            visualizer: GeneralVisualizer instance
            data_retriever: DataRetriever instance
            wolfram: WolframAlpha instance (optional)
            weather: Weather instance (optional)
            search: SearchClient instance (optional)
        """
        self.db = db
        self.viz = visualizer
        self.data = data_retriever
        self.wolfram = wolfram
        self.weather = weather
        self.search = search

    async def execute_tool(
        self,
        tool_call: Dict[str, Any],
        channel_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute a single tool call

        Args:
            tool_call: Tool call from LLM
            channel_id: Discord channel ID for context

        Returns:
            Dictionary with execution result
        """
        function_name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"])

        print(f"🛠️  Executing tool: {function_name}")
        print(f"   Arguments: {arguments}")

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
                return await self._get_weather(arguments)
            elif function_name == "get_weather_forecast":
                return await self._get_weather_forecast(arguments)
            elif function_name == "web_search":
                return await self._web_search(arguments)
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

    async def _get_weather(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get current weather as a visual card"""
        if not self.weather:
            return {"success": False, "error": "Weather API not configured"}

        location = args["location"]
        units = args.get("units", "metric")

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

            # Create weather card visualization with icon
            image_buffer = self.viz.create_weather_card(
                location=result["location"],
                country=result["country"],
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

    async def _get_weather_forecast(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get weather forecast"""
        if not self.weather:
            return {"success": False, "error": "Weather API not configured"}

        location = args["location"]
        days = args.get("days", 3)
        units = args.get("units", "metric")

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
