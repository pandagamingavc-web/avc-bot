from __future__ import annotations

import asyncio
import logging
from datetime import datetime

log = logging.getLogger(__name__)


class Scheduler:
    """
    Простой планировщик: раз в N секунд отправляет сообщение в TG и Discord.
    Потом сюда подключим YouTube/Twitch/новости.
    """

    def __init__(self, every_seconds: int, send_to_tg, send_to_discord):
        self.every_seconds = every_seconds
        self.send_to_tg = send_to_tg            # async (text: str) -> None
        self.send_to_discord = send_to_discord  # async (text: str) -> None

    async def start(self):
        log.info("[Scheduler] Started (every %s sec)", self.every_seconds)
        while True:
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                text = f"🕒 Авто-пост (тест) — {now}\nЕсли видишь это и в TG и в Discord — всё ок ✅"

                # шлем сразу в оба
                await self.send_to_tg(text)
                await self.send_to_discord(text)

                log.info("[Scheduler] Sent hourly post to TG + Discord")
            except Exception:
                log.exception("[Scheduler] Failed to send post")

            await asyncio.sleep(self.every_seconds)
