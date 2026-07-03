"""
Lightweight HTTP health endpoint for container / uptime monitoring.

Exposes GET /health which returns 200 only when the bot is fully READY and the
database answers `SELECT 1`, and 503 otherwise. Wire it into the compose bot
service `healthcheck:` (and optionally point an external uptime monitor at it once
the port is published) so a wedged bot or a dead DB connection is visible instead
of silent.
"""
import asyncio
import logging

from aiohttp import web

logger = logging.getLogger(__name__)


def _db_ping(db):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()


def make_health_starter(bot, db, port: int = 8080):
    """Return an async `start()` that launches the /health server on the bot's loop."""

    async def health(_request):
        if not bot.is_ready():
            return web.json_response({"status": "starting"}, status=503)
        try:
            await asyncio.to_thread(_db_ping, db)
        except Exception as e:
            logger.warning("Health check DB ping failed: %s", e)
            return web.json_response({"status": "unhealthy", "db": "down"}, status=503)
        return web.json_response({"status": "ok", "guilds": len(bot.guilds)})

    async def start():
        app = web.Application()
        app.router.add_get("/health", health)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info("Health server listening on :%d/health", port)

    return start
