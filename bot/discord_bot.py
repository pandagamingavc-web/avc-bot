from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import discord

from .config import Config

log = logging.getLogger(__name__)


class DiscordBot:
    def __init__(self, cfg: Config):
        self.cfg = cfg

        intents = discord.Intents.default()
        intents.message_content = True  # важно для чтения сообщений
        intents.guilds = True
        intents.messages = True

        self.client = discord.Client(intents=intents)

        self._bridge_channel: Optional[discord.TextChannel] = None
        self._tg_send_func = None  # будет задано из __main__.py

        @self.client.event
        async def on_ready():
            log.info("[Discord] Logged in as %s (id=%s)", self.client.user, self.client.user.id)
            await self._resolve_bridge_channel()

        @self.client.event
        async def on_message(message: discord.Message):
            if message.author.bot:
                return

            # если не настроен мост в TG — просто выходим
            if not self._tg_send_func:
                return

            # ждём пока канал будет найден
            if not self._bridge_channel:
                await self._resolve_bridge_channel()

            # только из нужного канала
            if self._bridge_channel and message.channel.id != self._bridge_channel.id:
                return

            text = message.content.strip()
            if not text:
                return

            author = message.author.display_name
            log.info("[Discord->TG] %s: %s", author, text)

            try:
                await self._tg_send_func(f"💬 Discord | {author}:\n{text}")
            except Exception:
                log.exception("Failed to send Discord message to Telegram")

    def set_telegram_sender(self, tg_send_func):
        """tg_send_func: async (text: str) -> None"""
        self._tg_send_func = tg_send_func

    async def _resolve_bridge_channel(self):
        chan_id = getattr(self.cfg, "bridge_discord_channel_id", None)
        if not chan_id:
            log.warning("BRIDGE_DISCORD_CHANNEL_ID is not set")
            return

        channel = self.client.get_channel(int(chan_id))
        if channel is None:
            # иногда нужно дождаться кеша
            await self.client.wait_until_ready()
            channel = self.client.get_channel(int(chan_id))

        if not isinstance(channel, discord.abc.Messageable):
            log.warning("Bridge channel not found or not messageable: %s", chan_id)
            return

        self._bridge_channel = channel  # type: ignore
        log.info("[Discord] Bridge channel resolved: %s", chan_id)

    async def send_to_bridge_channel(self, text: str):
        if not self._bridge_channel:
            await self._resolve_bridge_channel()
        if not self._bridge_channel:
            log.warning("[Bridge] Discord channel not available")
            return
        await self._bridge_channel.send(text[:1900])

    async def start(self):
        await self.client.start(self.cfg.discord_token)
