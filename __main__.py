from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Optional

from .config import Config
from .telegram_bot import TelegramBridge
from .discord_bot import DiscordBot


def _setup_logging():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def main():
    _setup_logging()
    log = logging.getLogger("main")

    cfg = Config()

    # ---- Telegram bridge (TG -> Discord) ----
    discord_bot: Optional[DiscordBot] = None

    async def send_to_discord_from_tg(text: str, author: str):
        """
        Сюда приходят сообщения из Telegram.
        Если настроен DISCORD_BRIDGE_CHANNEL_ID — отправим туда.
        Иначе просто логируем.
        """
        nonlocal discord_bot
        channel_id = getattr(cfg, "discord_bridge_channel_id", None) or getattr(cfg, "DISCORD_BRIDGE_CHANNEL_ID", None)

        if not discord_bot or not discord_bot.is_ready():
            log.info("[TG->Discord] (bot not ready) %s: %s", author, text)
            return

        if not channel_id:
            log.info("[TG->Discord] (no channel configured) %s: %s", author, text)
            return

        try:
            ch = discord_bot.get_channel(int(channel_id))
            if ch is None:
                log.warning("[TG->Discord] channel %s not found", channel_id)
                return
            await ch.send(f"📩 **TG {author}:** {text}")
        except Exception:
            log.exception("Failed to forward TG -> Discord")

    tg = TelegramBridge(cfg, on_text_from_tg=send_to_discord_from_tg)

    # ---- Discord bridge (Discord -> TG) ----
    async def send_to_tg_from_discord(text: str, author: str):
        """
        Сюда DiscordBot будет слать текст (если у тебя где-то в discord_bot.py вызывается tg_bridge_send).
        Отправим в TG admin chat (TELEGRAM_ADMIN_CHAT_ID).
        """
        try:
            await tg.send_to_admin(f"💬 Discord {author}: {text}")
        except Exception:
            log.exception("Failed to forward Discord -> TG")

    # ---- Start Telegram (non-blocking polling) ----
    await tg.start()
    log.info("Telegram started")

    # ---- Start Discord ----
    discord_bot = DiscordBot(cfg, tg_bridge_send=send_to_tg_from_discord)

    stop_event = asyncio.Event()

    def _request_stop(*_):
        log.warning("Shutdown requested...")
        stop_event.set()

    # ловим SIGTERM/SIGINT (Render шлёт SIGTERM при остановке/перезапуске)
    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _request_stop)
            except NotImplementedError:
                # Windows / ограничения окружения
                signal.signal(sig, lambda *_: _request_stop())
    except Exception:
        pass

    # Discord запускаем как task
    discord_task = asyncio.create_task(discord_bot.start(cfg.discord_token), name="discord.start")

    # ждём остановки
    await stop_event.wait()

    # ---- Graceful shutdown ----
    log.info("Stopping services...")

    try:
        await tg.stop()
    except Exception:
        log.exception("Telegram stop failed")

    try:
        await discord_bot.close()
    except Exception:
        log.exception("Discord close failed")

    # дождаться задачи discord start (если ещё не упала/не завершилась)
    try:
        await asyncio.wait_for(discord_task, timeout=15)
    except asyncio.TimeoutError:
        discord_task.cancel()
    except Exception:
        pass

    log.info("Stopped. Bye!")


if __name__ == "__main__":
    asyncio.run(main())
