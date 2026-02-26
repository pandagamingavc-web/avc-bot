import asyncio
import logging
from aiohttp import web

from .config import load_config
from .discord_bot import DiscordBridge
from .telegram_bot import TelegramBridge
from .scheduler import Scheduler

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")


# =========================
# Health server (для Render)
# =========================

async def health(request):
    return web.Response(text="OK")


async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health)   # <-- ТОЛЬКО GET

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

    log.info("[HTTP] Health server started on port 10000")


# =========================
# Main
# =========================

async def main():
    cfg = load_config()

    discord = DiscordBridge(cfg)
    telegram = TelegramBridge(cfg)

    # мосты
    discord.set_telegram_sender(telegram.send_to_bridge)
    telegram.set_discord_sender(discord.send_to_bridge)

    # планировщик
    scheduler = Scheduler(cfg, telegram, discord)

    # запускаем всё
    await start_health_server()

    await asyncio.gather(
        discord.start(),
        telegram.start(),
        scheduler.start()
    )


if __name__ == "__main__":
    asyncio.run(main())
