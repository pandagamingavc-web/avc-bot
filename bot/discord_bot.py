from __future__ import annotations

import logging
from typing import Callable, Awaitable, Optional

import discord

from .config import Config

log = logging.getLogger(__name__)


class DiscordBridge:
    def __init__(self, cfg: Config, on_text_from_discord: Callable[[str, str], Awaitable[None]]):
        self.cfg = cfg
        self.on_text_from_discord = on_text_from_discord  # async(text, author)
        intents = discord.Intents.default()
        intents.message_content = True  # нужно чтобы читать текст сообщений
        intents.guilds = True
        intents.messages = True

        self.client = discord.Client(intents=intents)
        self._started = False

        @self.client.event
        async def on_ready():
            log.info("[Discord] Logged in as %s (id=%s)", self.client.user, self.client.user.id)

        @self.client.event
        async def on_message(message: discord.Message):
            # игнорим ботов (и себя)
            if message.author.bot:
                return

            # если указан мост-канал — слушаем только его
            if self.cfg.bridge_discord_channel_id:
                if message.channel.id != int(self.cfg.bridge_discord_channel_id):
                    return

            text = message.content or ""
            if not text.strip():
                return

            author = message.author.display_name
            log.info("[DC] got message from %s: %s", author, text)

            try:
                await self.on_text_from_discord(text, author)
            except Exception:
                log.exception("Discord -> TG bridge failed")

    async def start(self):
        if self._started:
            return
        self._started = True

        if not self.cfg.discord_token:
            raise RuntimeError("DISCORD_TOKEN missing")

        await self.client.start(self.cfg.discord_token)

    async def stop(self):
        try:
            await self.client.close()
        finally:
            self._started = False

    async def send_to_bridge_channel(self, text: str) -> bool:
        """
        Отправляет сообщение в Discord канал BRIDGE_DISCORD_CHANNEL_ID
        Возвращает True если отправили, иначе False.
        """
        ch_id = self.cfg.bridge_discord_channel_id
        if not ch_id:
            log.warning("[Bridge] BRIDGE_DISCORD_CHANNEL_ID is not set")
            return False

        ch_id = int(ch_id)

        # 1) пробуем из кэша
        channel = self.client.get_channel(ch_id)

        # 2) если не нашли — fetch (самое важное!)
        if channel is None:
            try:
                channel = await self.client.fetch_channel(ch_id)
            except Exception:
                log.exception("[Bridge] Cannot fetch Discord channel id=%s", ch_id)
                return False

        # 3) отправляем
        try:
            await channel.send(text[:1900])
            log.info("[Bridge] Sent to Discord channel %s OK", ch_id)
            return True
        except Exception:
            log.exception("[Bridge] Failed to send message to Discord channel %s", ch_id)
            return False
