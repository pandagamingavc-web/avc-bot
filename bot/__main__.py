from __future__ import annotations

import asyncio
import logging

from .config import load_config
from .telegram_bot import TelegramBridge
from .discord_bot import DiscordBridge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

log = logging.getLogger("bot")


async def main():
    cfg = load_config()

    telegram: TelegramBridge | None = None
    discord: DiscordBridge | None = None

    # ---------- TG -> Discord ----------
    async def on_text_from_tg(text: str, author: str):
        if not discord:
            return
        msg = f"📨 TG | {author}: {text}"
        ok = await discord.send_to_bridge_channel(msg)
        if not ok:
            log.warning("[Bridge] TG -> Discord failed (check channel id / permissions)")

    # ---------- Discord -> TG ----------
    async def on_text_from_discord(text: str, author: str):
        if not telegram:
            return

        # куда отправлять в телеге:
        # 1) BRIDGE_TELEGRAM_CHAT_ID (если задан)
        # 2) иначе TELEGRAM_ADMIN_CHAT_ID
        target_chat_id = cfg.bridge_telegram_chat_id or cfg.telegram_admin_chat_id
        if not target_chat_id:
            log.warning("[Bridge] No BRIDGE_TELEGRAM_CHAT_ID or TELEGRAM_ADMIN_CHAT_ID set")
            return

        msg = f"💬 Discord | {author}: {text}"

        try:
            # если у тебя есть метод send_to_admin — он шлёт в TELEGRAM_ADMIN_CHAT_ID
            # но нам нужно иногда слать и в BRIDGE_TELEGRAM_CHAT_ID, поэтому отправляем напрямую
            if telegram.app is None:
                log.warning("[Bridge] Telegram app not started yet")
                return

            await telegram.app.bot.send_message(chat_id=int(target_chat_id), text=msg[:4000])
            log.info("[Bridge] Sent Discord -> TG OK (chat_id=%s)", target_chat_id)
        except Exception:
            log.exception("[Bridge] Failed to send Discord -> TG")

    # создаём мосты
    telegram = TelegramBridge(cfg, on_text_from_tg=on_text_from_tg)
    discord = DiscordBridge(cfg, on_text_from_discord=on_text_from_discord)

    # стартуем оба в одном loop
    await asyncio.gather(
        telegram.start(),
        discord.start(),
    )


if __name__ == "__main__":
    asyncio.run(main())
