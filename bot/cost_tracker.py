"""
Cost tracking and alerting system for LLM API usage
"""
import logging
import os

import discord

logger = logging.getLogger(__name__)

# Model pricing per million tokens (input/output)
MODEL_PRICING = {
    'anthropic/claude-3.7-sonnet': {'input': 3.00, 'output': 15.00},
    'anthropic/claude-3.5-sonnet': {'input': 3.00, 'output': 15.00},
    'anthropic/claude-opus-4.1': {'input': 15.00, 'output': 75.00},
    'deepseek/deepseek-chat-v3.1': {'input': 0.20, 'output': 0.80},
    'deepseek/deepseek-r1-distill-qwen-32b': {'input': 0.27, 'output': 0.40},
    'google/gemini-2.5-flash': {'input': 0.10, 'output': 0.40},
    'google/gemini-2.0-flash-001': {'input': 0.125, 'output': 0.50},
    'nousresearch/hermes-3-llama-3.1-70b': {'input': 0.30, 'output': 0.30},
    # Default fallback for unknown models
    'default': {'input': 1.00, 'output': 2.00}
}

class CostTracker:
    def __init__(self, db, bot):
        self.db = db
        self.bot = bot
        self.wompie_username = 'wompie__'

    def calculate_cost(self, model, input_tokens, output_tokens):
        """Calculate cost for a model's token usage"""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING['default'])

        # Cost = (input_tokens / 1M * input_price) + (output_tokens / 1M * output_price)
        input_cost = (input_tokens / 1_000_000) * pricing['input']
        output_cost = (output_tokens / 1_000_000) * pricing['output']
        total_cost = input_cost + output_cost

        return total_cost

    def record_costs_sync(self, model, input_tokens, output_tokens, request_type, user_id=None, username=None):
        """Synchronous version of cost recording (without alerts) for use from worker threads"""
        # Calculate individual costs
        pricing = MODEL_PRICING.get(model, MODEL_PRICING['default'])
        input_cost = (input_tokens / 1_000_000) * pricing['input']
        output_cost = (output_tokens / 1_000_000) * pricing['output']
        total_cost = input_cost + output_cost

        # Record the cost
        self.db.record_api_cost(
            model, input_tokens, output_tokens, total_cost, request_type, user_id, username
        )

        # Get monthly total
        monthly_total = self.db.get_total_cost()

        # Log individual request cost with breakdown
        # Only log detailed costs if username is provided (text mentions only)
        if username:
            model_short = model.split('/')[-1] if '/' in model else model
            logger.info("Request Cost: $%.6f | In: $%.6f (%dtok) | Out: $%.6f (%dtok) | %s | %s | User: %s",
                        total_cost, input_cost, input_tokens, output_cost, output_tokens, model_short, request_type, username)
            logger.info("Monthly Total: $%.4f", monthly_total)

        # Return alert info for async handling
        alert_check = self.db.check_cost_alert_threshold(1.00)
        return alert_check

    async def record_and_check_costs(self, model, input_tokens, output_tokens, request_type, user_id=None, username=None):
        """Record API cost and check if we should send an alert"""
        # Use sync version for recording and logging
        alert_check = self.record_costs_sync(model, input_tokens, output_tokens, request_type, user_id, username)

        # Send alert if needed (async part)
        if alert_check['should_alert']:
            await self.send_cost_alert(
                alert_check['threshold'],
                alert_check['total_cost']
            )
            # Record that we sent the alert
            self.db.record_cost_alert(alert_check['threshold'], alert_check['total_cost'])

    async def send_cost_alert(self, threshold, total_cost):
        """Send DM to wompie__ about cost threshold"""
        try:
            # Find wompie__ in all guilds
            wompie_user = None
            for guild in self.bot.guilds:
                member = discord.utils.get(guild.members, name=self.wompie_username)
                if member:
                    wompie_user = member
                    break

            if not wompie_user:
                logger.warning("Could not find user %s to send cost alert", self.wompie_username)
                return

            # Get breakdown by model
            breakdown = self.get_cost_breakdown()

            embed = discord.Embed(
                title=f"💸 Cost Alert: ${threshold}.00 Threshold Crossed",
                description=f"**Total spending: ${total_cost:.2f}**\n\nYou've spent another $1.00 on LLM API calls.",
                color=discord.Color.red()
            )

            # Add breakdown
            if breakdown:
                breakdown_text = "\n".join([f"• {model}: ${cost:.2f}" for model, cost in breakdown.items()])
                embed.add_field(name="Cost by Model", value=breakdown_text, inline=False)

            # Add recommendations
            if total_cost > 10:
                embed.add_field(
                    name="💡 Cost Control",
                    value=(
                        "Consider:\n"
                        "• Reducing `HOURLY_TOKEN_LIMIT` in .env\n"
                        "• Switching to cheaper model (DeepSeek V3.1)\n"
                        "• Checking for abuse with `/api_stats`"
                    ),
                    inline=False
                )

            embed.set_footer(text="Cost tracking updates every $1")

            await wompie_user.send(embed=embed)
            logger.info("Sent cost alert to %s: $%.2f", self.wompie_username, total_cost)

        except discord.Forbidden:
            logger.error("Cannot send DM to %s (DMs closed)", self.wompie_username)
        except Exception as e:
            logger.error("Error sending cost alert: %s", e)

    def get_cost_breakdown(self):
        """Get cost breakdown by model"""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT model, SUM(cost_usd) as total_cost
                        FROM api_costs
                        GROUP BY model
                        ORDER BY total_cost DESC
                    """)
                    results = cur.fetchall()
                    return {row[0]: float(row[1]) for row in results}
        except Exception as e:
            logger.error("Error getting cost breakdown: %s", e)
            return {}
