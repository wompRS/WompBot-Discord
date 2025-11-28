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

    def __init__(self, db, visualizer, data_retriever):
        """
        Args:
            db: Database instance
            visualizer: GeneralVisualizer instance
            data_retriever: DataRetriever instance
        """
        self.db = db
        self.viz = visualizer
        self.data = data_retriever

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
