from __future__ import annotations

import logging
from typing import Optional

import discord

from .config import Config

log = logging.getLogger(__name__)


class DiscordBot:
    def __init__(self, cfg: Config, tg_bridge=None):
        self.cfg = cfg
        self.tg_bridge = tg_bridge  # TelegramBridge (может быть None)

        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True  # нужен включенный intent в Dev Portal

        self.client = discord.Client(intents=intents)

        @self.client.event
        async def on_ready():
            log.info("[Discord] Logged in as %s (id=%s)", self.client.user, self.client.user.id)

        @self.client.event
        async def on_message(message: discord.Message):
            try:
                # игнорим свои сообщения
                if message.author.bot:
                    return

                # если задан мост-канал, слушаем только его
                bridge_ch = self.cfg.bridge_discord_channel_id
                if bridge_ch and message.channel.id != int(bridge_ch):
                    return

                # пустые / без текста
                if not message.content:
                    return

                text = message.content.strip()

                # команды не зеркалим
                if text.startswith("/"):
                    return

                # анти-зацикливание: если это уже от TG — не шлем обратно
                if text.startswith("[TG]"):
                    return

                author = message.author.display_name
                log.info("[DC] %s: %s", author, text)

                # отправляем в TG (в мост-чат)
                if self.tg_bridge and self.cfg.bridge_telegram_chat_id:
                    await self.tg_bridge.send_to_chat(int(self.cfg.bridge_telegram_chat_id), f"[DC] {author}: {text}")

            except Exception:
                log.exception("on_message failed")

    async def send_to_bridge_channel(self, text: str):
        ch_id = self.cfg.bridge_discord_channel_id
        if not ch_id:
            return
        channel = self.client.get_channel(int(ch_id))
        if channel is None:
            try:
                channel = await self.client.fetch_channel(int(ch_id))
            except Exception:
                log.exception("Failed to fetch Discord bridge channel")
                return
        try:
            await channel.send(text[:1900])
        except Exception:
            log.exception("Failed to send message to Discord channel")

    async def start(self):
        await self.client.start(self.cfg.discord_token)
