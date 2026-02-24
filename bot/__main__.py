import asyncio
from .config import load_config
from .discord_bot import DiscordBot
from .telegram_bot import TelegramBot

async def main():
    cfg = load_config()

    async def noop(**kwargs):
        return None

    discord = DiscordBot(cfg, tg_bridge_send=noop)
    telegram = TelegramBot(cfg, discord_bridge_send=noop)

    async def tg_send(text: str, author: str = ""):
        if cfg.bridge_telegram_chat_id:
            await telegram.app.bot.send_message(chat_id=cfg.bridge_telegram_chat_id, text=f"{author}: {text}")

    async def dc_send(text: str, author: str = ""):
        if cfg.bridge_discord_channel_id:
            ch = discord.get_channel(cfg.bridge_discord_channel_id)
            if ch:
                await ch.send(f"{author}: {text}")

    discord.tg_bridge_send = tg_send
    telegram.discord_bridge_send = dc_send

    await asyncio.gather(
        telegram.start(),
        discord.start(cfg.discord_token),
    )

if __name__ == "__main__":
    asyncio.run(main())
