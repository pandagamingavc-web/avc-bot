import asyncio
import logging
from aiohttp import web

from .config import load_config
from .discord_bot import DiscordBridge
from .telegram_bot import TelegramBridge

# Если scheduler.py у тебя есть — оставь. Если нет, просто удали 2 строки ниже (import + создание scheduler)
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
    app.router.add_get("/", health)  # ВАЖНО: только GET (HEAD не добавляем вручную)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(10000)  # Render обычно ок на 10000
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    log.info("[HTTP] Health server started on port %s", port)


# =========================
# Main
# =========================
async def main():
    cfg = load_config()

    discord = None
    telegram = None

    # Telegram -> Discord
    async def on_text_from_tg(text: str, author: str):
        if not discord:
            return
        try:
            # если у DiscordBridge есть send_to_bridge(text)
            if hasattr(discord, "send_to_bridge"):
                await discord.send_to_bridge(f"📨 TG | {author}: {text}")
            # если у DiscordBridge другой метод — не упадём, просто залогируем
            else:
                log.warning("Discord bridge has no send_to_bridge()")
        except Exception:
            log.exception("TG -> Discord failed")

    # Discord -> Telegram
    async def on_text_from_discord(text: str, author: str):
        if not telegram:
            return
        try:
            # если у TelegramBridge есть send_to_bridge(text) — используем его
            if hasattr(telegram, "send_to_bridge"):
                await telegram.send_to_bridge(f"💬 Discord | {author}: {text}")
            # иначе fallback на send_to_admin (как в твоём классе выше)
            elif hasattr(telegram, "send_to_admin"):
                await telegram.send_to_admin(f"💬 Discord | {author}: {text}")
            else:
                log.warning("Telegram bridge has no send_to_bridge() / send_to_admin()")
        except Exception:
            log.exception("Discord -> TG failed")

    # ВАЖНО: создаём мосты с коллбеками
    telegram = TelegramBridge(cfg, on_text_from_tg)
    discord = DiscordBridge(cfg, on_text_from_discord)

    # Scheduler (если есть)
    scheduler = Scheduler(cfg, telegram, discord)

    # Стартуем всё
    await start_health_server()

    await asyncio.gather(
        discord.start(),
        telegram.start(),
        scheduler.start(),
    )


if __name__ == "__main__":
    asyncio.run(main())
