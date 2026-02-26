from __future__ import annotations

import logging
from typing import Optional

import discord

from .config import Config
from .stats import build_discord_stats

log = logging.getLogger(__name__)


class DiscordBridge:
    """
    Discord бот + мост:
    - Discord -> TG: сообщения из bridge канала пересылаем в TG (через callback set_telegram_sender)
    - TG -> Discord: send_to_bridge()
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg

        intents = discord.Intents.default()
        intents.message_content = True  # важно для чтения сообщений
        intents.guilds = True
        intents.members = True  # нужно для статистики участников

        self.client = discord.Client(intents=intents)

        self.bridge_channel: Optional[discord.abc.Messageable] = None
        self._tg_send = None  # async func(text:str)

        # флаг из __main__.py
        self.enable_stats_command: bool = False

        # events
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

    # ---------- wiring ----------

    def set_telegram_sender(self, tg_send_callable):
        """
        tg_send_callable: async (text:str) -> None
        """
        self._tg_send = tg_send_callable

    # ---------- lifecycle ----------

    async def start(self):
        if not self.cfg.discord_token:
            raise RuntimeError("DISCORD_TOKEN is empty")
        await self.client.start(self.cfg.discord_token)

    # ---------- helpers ----------

    async def _resolve_bridge_channel(self):
        """
        Ищем канал по BRIDGE_DISCORD_CHANNEL_ID.
        """
        ch_id = getattr(self.cfg, "bridge_discord_channel_id", None)
        if not ch_id:
            log.warning("[Discord] BRIDGE_DISCORD_CHANNEL_ID is not set")
            self.bridge_channel = None
            return

        # 1) пробуем get_channel (кэш)
        ch = self.client.get_channel(int(ch_id))

        # 2) если нет — fetch_channel
        if ch is None:
            try:
                ch = await self.client.fetch_channel(int(ch_id))
            except Exception:
                log.exception("[Discord] Failed to fetch channel id=%s", ch_id)
                ch = None

        self.bridge_channel = ch
        if ch:
            log.info("[Discord] Bridge channel resolved: %s", ch_id)
        else:
            log.warning("[Discord] Bridge channel NOT found: %s", ch_id)

    async def send_to_bridge(self, text: str):
        """
        Отправка текста в Discord bridge-канал.
        """
        if not self.bridge_channel:
            await self._resolve_bridge_channel()
        if not self.bridge_channel:
            log.warning("[Discord] Can't send: bridge channel is None")
            return

        try:
            await self.bridge_channel.send(text[:2000])
            log.info("[Discord] Sent to bridge channel: %s", text[:120])
        except Exception:
            log.exception("[Discord] Failed to send message to bridge channel")

    # ---------- events ----------

    async def on_ready(self):
        await self._resolve_bridge_channel()
        log.info("[Discord] Logged in as %s (id=%s)", self.client.user, self.client.user.id)

    async def on_message(self, message: discord.Message):
        # игнорим свои сообщения
        if message.author == self.client.user:
            return

        content = (message.content or "").strip()

        # ---- команда !stats ----
        if self.enable_stats_command and content.lower().startswith("!stats"):
            try:
                text = await build_discord_stats(self.client, int(self.cfg.discord_guild_id))
                await message.channel.send(text[:2000])
            except Exception:
                log.exception("[Discord] !stats failed")
                await message.channel.send("❌ Не смог собрать статистику.")
            return

        # ---- обычный мост Discord -> TG ----
        bridge_id = getattr(self.cfg, "bridge_discord_channel_id", None)
        if not bridge_id:
            return

        # только из нужного канала
        if message.channel.id != int(bridge_id):
            return

        if not self._tg_send:
            log.warning("[Discord] Telegram sender is not set. Can't forward to TG.")
            return

        # формируем текст в TG
        author = getattr(message.author, "display_name", "unknown")
        text = f"💬 Discord • {author}: {content}" if content else f"💬 Discord • {author}: (без текста)"

        try:
            await self._tg_send(text[:4000])
            log.info("[Bridge] Discord -> TG: %s", text[:120])
        except Exception:
            log.exception("[Bridge] Discord -> TG failed")
