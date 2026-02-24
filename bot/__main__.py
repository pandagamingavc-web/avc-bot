import os
import asyncio
from aiohttp import web

from .config import load_config
from .discord_bot import DiscordBot
from .telegram_bot import TelegramBot


async def start_web_server() -> None:
    """
    Нужен для Render Web Service (чтобы был открыт порт).
    Render ждёт, что процесс слушает PORT.
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

    # держим сервер запущенным всегда
    await asyncio.Event().wait()


async def main():
    cfg = load_config()

    async def noop(**kwargs):
        return None

    discord = DiscordBot(cfg, tg_bridge_send=noop)
    telegram = TelegramBot(cfg, discord_bridge_send=noop)

    async def tg_send(text: str, author: str = ""):
        if cfg.bridge_telegram_chat_id:
            await telegram.app.bot.send_message(
                chat_id=cfg.bridge_telegram_chat_id,
                text=f"{author}: {text}",
            )

    async def dc_send(text: str, author: str = ""):
        if cfg.bridge_discord_channel_id:
            ch = discord.get_channel(cfg.bridge_discord_channel_id)
            if ch:
                await ch.send(f"{author}: {text}")

    discord.tg_bridge_send = tg_send
    telegram.discord_bridge_send = dc_send

    await asyncio.gather(
        start_web_server(),                 # <-- ВАЖНО для Render Web Service
        telegram.start(),
        discord.start(cfg.discord_token),
    )


if __name__ == "__main__":
    asyncio.run(main())
