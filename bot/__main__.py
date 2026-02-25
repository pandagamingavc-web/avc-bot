import asyncio
import logging

from .config import load_config
from .telegram_bot import TelegramBridge
from .discord_bot import DiscordBot

logging.basicConfig(level=logging.INFO)


async def main():
    cfg = load_config()

    tg_bridge: TelegramBridge | None = None
    dc_bot: DiscordBot | None = None

    async def on_text_from_tg(text: str, author: str):
        # TG -> Discord
        if not dc_bot:
            return
        await dc_bot.send_to_bridge_channel(f"[TG] {author}: {text}")

    tg_bridge = TelegramBridge(cfg, on_text_from_tg=on_text_from_tg)
    dc_bot = DiscordBot(cfg, tg_bridge=tg_bridge)

    await tg_bridge.start()
    await dc_bot.start()


if __name__ == "__main__":
    asyncio.run(main())
