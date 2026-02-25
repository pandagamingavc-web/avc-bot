from __future__ import annotations

import asyncio
import logging
import os

from aiohttp import web

from .config import load_config
from .discord_bot import DiscordBot
from .telegram_bot import TelegramBridge


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

log = logging.getLogger("bot")


# Render Free Web Service требует открытый порт
async def _health_server():
    port = int(os.getenv("PORT", "10000"))

    async def handle(_):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()

    log.info("[HTTP] Health server started on port %s", port)

    while True:
        await asyncio.sleep(3600)


async def main():
    cfg = load_config()

    discord_bot = DiscordBot(cfg)

    # Telegram -> Discord
    async def tg_to_discord(text: str, author: str):
        await discord_bot.send_to_bridge_channel(f"📩 TG | **{author}:** {text}")

    tg_bot = TelegramBridge(cfg, on_text_from_tg=tg_to_discord)

    # Discord -> Telegram (куда слать)
    async def discord_to_tg(text: str):
        await tg_bot.send_to_admin(text)

    discord_bot.set_telegram_sender(discord_to_tg)

    await asyncio.gather(
        _health_server(),
        discord_bot.start(),
        tg_bot.start(),
    )


if __name__ == "__main__":
    asyncio.run(main())
