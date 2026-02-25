from __future__ import annotations

import asyncio
import logging
import os

from .config import load_config
from .discord_bot import DiscordBridge
from .telegram_bot import TelegramBridge
from .scheduler import Scheduler
from .stats import build_discord_stats
from .web_health import start_health_server  # если у тебя файл иначе называется — скажи, поправлю


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

log = logging.getLogger("bot")


async def main():
    cfg = load_config()

    # 1) Discord
    discord = DiscordBridge(cfg)

    # 2) Telegram (мост TG -> Discord)
    async def on_text_from_tg(text: str, author: str):
        # отправляем в Discord канал-мост
        await discord.send_to_bridge(f"📨 **TG** ({author}): {text}")

    tg = TelegramBridge(cfg, on_text_from_tg=on_text_from_tg)

    # 3) Мост Discord -> TG
    async def on_text_from_discord(text: str, author: str):
        # в Telegram админ-чат/группу
        await tg.send_to_admin(f"💬 Discord ({author}): {text}")

    discord.on_text_from_discord = on_text_from_discord

    # 4) Команды /stats и !stats
    # Telegram /stats
    async def tg_stats_handler(update, context):
        text = await build_discord_stats(discord.client, cfg.discord_guild_id)
        await update.effective_message.reply_text(text)

    tg.extra_command_handlers = [("stats", tg_stats_handler)]  # добавим хендлер в tg.start()

    # Discord !stats (в твоём discord_bot.py должно быть место для команд — если нет, я дам обновление)
    discord.enable_stats_command = True  # флаг

    # 5) Планировщик статистики
    stats_every = int(os.getenv("STATS_EVERY_SECONDS", "3600"))  # 1 час
    stats_enabled = os.getenv("STATS_ENABLED", "1").strip().lower() in ("1", "true", "yes", "y", "on")

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

    # 6) Health server для Render (чтобы не ругался на порт)
    # Render обычно ждёт порт 10000
    await start_health_server(port=int(os.getenv("PORT", "10000")))

    # 7) Запуск всего вместе
    tasks = [
        discord.start(),
        tg.start(),
    ]
    if scheduler:
        tasks.append(scheduler.start())

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
