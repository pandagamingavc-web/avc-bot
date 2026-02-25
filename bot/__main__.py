import asyncio
import logging

from .config import load_config
from .discord_bot import DiscordBot
from .telegram_bot import TelegramBridge
from .web import start_web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bot")


async def main():
    cfg = load_config()

    tg_bridge: TelegramBridge | None = None

    async def on_text_from_tg(text: str, author: str):
        log.info("[Bridge] TG -> Discord: %s: %s", author, text)

    async def on_text_from_discord(text: str, author: str):
        if tg_bridge:
            await tg_bridge.send_to_admin(f"[Discord] {author}: {text}")

    discord_bot = DiscordBot(cfg, on_text_from_discord)
    tg_bridge = TelegramBridge(cfg, on_text_from_tg)

    await asyncio.gather(
        start_web_server(),     # <-- открываем порт для Render
        discord_bot.start(),
        tg_bridge.start(),
    )

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
