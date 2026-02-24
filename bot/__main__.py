from __future__ import annotations

import asyncio
import logging
import os

from aiohttp import web

from .config import load_config
from .discord_bot import DiscordBot
from .telegram_bot import TelegramBridge  # <-- ВАЖНО: TelegramBridge, НЕ TelegramBot


def setup_logging():
    logging.basicConfig(
        level="INFO",
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def start_web_server():
    app = web.Application()

    async def health(_):
        return web.Response(text="OK")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    # держим веб-сервер живым
    await asyncio.Event().wait()


async def main():
    setup_logging()
    cfg = load_config()

    discord_bot: DiscordBot | None = None

    # TG -> Discord (мост)
    async def tg_to_discord(text: str, author: str):
        if not discord_bot:
            return
        if not cfg.bridge_discord_channel_id:
            return
        ch = discord_bot.get_channel(cfg.bridge_discord_channel_id)
        if ch:
            await ch.send(f"📩 TG {author}: {text}")

    tg = TelegramBridge(cfg, on_text_from_tg=tg_to_discord)

    # Discord -> TG (мост)
    async def discord_to_tg(text: str, author: str):
        target = cfg.bridge_telegram_chat_id or cfg.telegram_admin_chat_id
        if not target:
            return
        if not tg.app:
            return
        await tg.app.bot.send_message(
            chat_id=int(target),
            text=f"💬 Discord {author}: {text}",
        )

    # стартуем TG
    await tg.start()

    # стартуем Discord
    discord_bot = DiscordBot(cfg, tg_bridge_send=discord_to_tg)

    await asyncio.gather(
        start_web_server(),
        discord_bot.start(cfg.discord_token),
    )


if __name__ == "__main__":
    asyncio.run(main())
