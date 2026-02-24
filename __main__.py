from __future__ import annotations

import asyncio
import logging
import os
from aiohttp import web

from .config import load_config
from .discord_bot import DiscordBot
from .telegram_bot import TelegramBridge


def setup_logging():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def start_web_server() -> None:
    """
    Нужен для Render Web Service (чтобы был открыт порт).
    """
    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.Response(text="OK")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logging.getLogger("web").info("Health server listening on %s", port)

    # держим сервер всегда
    await asyncio.Event().wait()


async def main():
    setup_logging()
    log = logging.getLogger("main")

    cfg = load_config()

    # Создадим Discord позже, но подготовим функции мостов заранее
    discord_bot: DiscordBot | None = None

    # --- TG -> Discord ---
    async def send_to_discord_from_tg(text: str, author: str):
        nonlocal discord_bot
        if not cfg.bridge_discord_channel_id:
            return
        if not discord_bot or not discord_bot.is_ready():
            return
        ch = discord_bot.get_channel(cfg.bridge_discord_channel_id)
        if ch:
            await ch.send(f"📩 **TG {author}:** {text}")

    tg = TelegramBridge(cfg, on_text_from_tg=send_to_discord_from_tg)

    # --- Discord -> TG (в админ-чат или в bridge чат) ---
    async def send_to_tg_from_discord(text: str, author: str):
        # если указан BRIDGE_TELEGRAM_CHAT_ID — шлём туда, иначе в TELEGRAM_ADMIN_CHAT_ID
        target = cfg.bridge_telegram_chat_id or cfg.telegram_admin_chat_id
        if not target:
            return
        if not tg.app:
            return
        await tg.app.bot.send_message(chat_id=int(target), text=f"💬 Discord {author}: {text}")

    # Стартуем TG polling (не блокирует)
    await tg.start()
    log.info("Telegram started")

    # Стартуем Discord
    discord_bot = DiscordBot(cfg, tg_bridge_send=send_to_tg_from_discord)

    await asyncio.gather(
        start_web_server(),                 # порт для Render
        discord_bot.start(cfg.discord_token) # discord
    )


if __name__ == "__main__":
    asyncio.run(main())
