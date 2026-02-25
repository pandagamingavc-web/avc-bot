from __future__ import annotations

import logging
from typing import Callable, Awaitable, Optional

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from .config import Config

log = logging.getLogger(__name__)


class TelegramBridge:
    """
    Telegram polling (non-blocking) + фильтр чата + команды.
    """

    def __init__(self, cfg: Config, on_text_from_tg: Callable[[str, str], Awaitable[None]]):
        self.cfg = cfg
        self.on_text_from_tg = on_text_from_tg  # async (text, author)
        self.app: Optional[Application] = None
        self._started = False

    def _chat_allowed(self, update: Update) -> bool:
        allowed = self.cfg.telegram_allowed_chat_id
        if not allowed:
            return True
        chat = update.effective_chat
        if not chat:
            return False
        return int(chat.id) == int(allowed)

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._chat_allowed(update):
            return
        await update.effective_message.reply_text("✅ Бот жив. Команды: /ping /id")

    async def _cmd_ping(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._chat_allowed(update):
            return
        await update.effective_message.reply_text("🏓 Pong")

    async def _cmd_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        user = update.effective_user
        if not chat:
            return
        await update.effective_message.reply_text(
            f"🆔 chat_id: {chat.id}\n"
            f"👤 user_id: {user.id if user else 'unknown'}\n"
            f"📌 chat_title: {chat.title if getattr(chat, 'title', None) else 'private'}"
        )

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._chat_allowed(update):
            return

        msg = update.effective_message
        if not msg or not msg.text:
            return

        text = msg.text.strip()
        user = update.effective_user
        author = (user.full_name if user else "unknown")

        # команды не зеркалим
        if text.startswith("/"):
            return

        # анти-зацикливание: если это уже от Discord — не шлем обратно
        if text.startswith("[DC]"):
            return

        log.info("[TG] %s: %s", author, text)

        try:
            await self.on_text_from_tg(text, author)
        except Exception:
            log.exception("TG -> Discord bridge failed")

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        log.exception("Telegram error: %s", context.error)

    async def start(self):
        if self._started:
            return
        self._started = True

        if not self.cfg.telegram_token:
            raise RuntimeError("TELEGRAM_TOKEN is empty")

        # сбрасываем webhook (чтобы не было Conflict getUpdates)
        try:
            await Bot(self.cfg.telegram_token).delete_webhook(drop_pending_updates=True)
            log.info("[Telegram] deleteWebhook OK")
        except Exception:
            log.exception("[Telegram] deleteWebhook failed")

        self.app = Application.builder().token(self.cfg.telegram_token).build()

        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("ping", self._cmd_ping))
        self.app.add_handler(CommandHandler("id", self._cmd_id))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))
        self.app.add_error_handler(self._on_error)

        await self.app.initialize()
        await self.app.start()

        if not self.app.updater:
            raise RuntimeError("Telegram Updater is not available (check python-telegram-bot version)")

        await self.app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )

        log.info("[Telegram] Started polling (non-blocking)")

    async def send_to_chat(self, chat_id: int, text: str):
        if not self.app:
            return
        try:
            await self.app.bot.send_message(chat_id=int(chat_id), text=text[:4000])
        except Exception:
            log.exception("Failed to send message to chat")

    async def send_to_admin(self, text: str):
        if not self.app:
            return
        chat_id = getattr(self.cfg, "telegram_admin_chat_id", None)
        if not chat_id:
            log.warning("TELEGRAM_ADMIN_CHAT_ID is not set, cannot send message")
            return
        await self.send_to_chat(int(chat_id), text)

    async def stop(self):
        if not self.app:
            return
        try:
            if self.app.updater:
                await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        finally:
            self.app = None
            self._started = False
