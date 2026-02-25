from __future__ import annotations

import asyncio
import logging
import os
from typing import Awaitable, Callable, Optional

from .stats import build_discord_stats

log = logging.getLogger(__name__)


def _int(name: str, default: int) -> int:
    v = os.getenv(name)
    if not v:
        return default
    try:
        return int(v)
    except Exception:
        return default


def _bool(name: str, default: bool = True) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


class Scheduler:
    """
    Простой планировщик: каждые N секунд делает пост.
    Работает внутри одного asyncio loop (Render OK).
    """

    def __init__(
        self,
        every_seconds: int,
        send_to_discord: Callable[[str], Awaitable[None]],
        send_to_telegram: Callable[[str], Awaitable[None]],
        build_stats_text: Callable[[], Awaitable[str]],
    ):
        self.every_seconds = max(30, int(every_seconds))  # защита от слишком частого спама
        self.send_to_discord = send_to_discord
        self.send_to_telegram = send_to_telegram
        self.build_stats_text = build_stats_text

        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    async def start(self):
        if self._task:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="scheduler")
        log.info("[Scheduler] Started (every %s sec)", self.every_seconds)

    async def stop(self):
        if not self._task:
            return
        self._stop.set()
        self._task.cancel()
        try:
            await self._task
        except Exception:
            pass
        self._task = None

    async def _run(self):
        # Сразу отправим один раз после запуска (можно выключить переменной)
        send_on_start = _bool("STATS_SEND_ON_START", True)

        if send_on_start:
            await self._safe_send()

        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.every_seconds)
                break
            except asyncio.TimeoutError:
                await self._safe_send()

    async def _safe_send(self):
        try:
            text = await self.build_stats_text()
            if not text:
                return

            # в TG + Discord
            await self.send_to_telegram(text)
            await self.send_to_discord(text)

            log.info("[Scheduler] Sent stats to TG + Discord")
        except Exception:
            log.exception("[Scheduler] Failed to send stats")
