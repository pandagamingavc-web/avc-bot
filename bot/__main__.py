from __future__ import annotations

import asyncio
import logging
import os

from .config import load_config
from .discord_bot import DiscordBridge
from .telegram_bot import TelegramBridge
from .stats import build_discord_stats
from .scheduler import Scheduler

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

log = logging.getLogger("bot")


async def main():
    cfg = load_config()

    # =========================
    # DISCORD
    # =========================
    discord = DiscordBridge(cfg)

    # =========================
    # TELEGRAM
    # =========================
    async def on_text_from_tg(text: str, author: str):
        await discord.send_to_bridge(f"📨 TG • {author}: {text}")

    tg = TelegramBridge(cfg, on_text_from_tg=on_text_from_tg)

    # =========================
    # Команда /stats в Telegram
    # =========================
    async def tg_stats(update, context):
        text = await build_discord_stats(discord.client, cfg.discord_guild_id)
        await update.effective_message.reply_text(text)

    tg.extra_command_handlers = [
        ("stats", tg_stats),
    ]

    # =========================
    # Команда !stats в Discord
    # =========================
    discord.enable_stats_command = True

    # =========================
    # Планировщик статистики
    # =========================
    stats_enabled = os.getenv("STATS_ENABLED", "1").lower() in ("1", "true", "yes")
    stats_every = int(os.getenv("STATS_EVERY_SECONDS", "3600"))

    scheduler = None
    if stats_enabled:

        async def build_stats():
            return await build_discord_stats(discord.client, cfg.discord_guild_id)

        scheduler = Scheduler(
            every_seconds=stats_every,
            send_to_discord=discord.send_to_bridge,
            send_to_telegram=tg.send_to_admin,
            build_stats_text=build_stats,
        )

    # =========================
    # Render health port (10000)
    # =========================
    from aiohttp import web

    async def health(_):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_head("/", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000")))
    await site.start()

    log.info("[HTTP] Health server started")

    # =========================
    # Запуск всего
    # =========================
    tasks = [
        discord.start(),
        tg.start(),
    ]

    if scheduler:
        tasks.append(scheduler.start())

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
