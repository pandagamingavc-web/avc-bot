from __future__ import annotations

import logging
from typing import Callable, Awaitable, Optional

from telegram import Update
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
    Неблокирующий Telegram polling для совместной работы с Discord в одном asyncio-loop.
    """

    def __init__(self, cfg: Config, on_text_from_tg: Callable[[str, str], Awaitable[None]]):
        self.cfg = cfg
        self.on_text_from_tg = on_text_from_tg  # async (text, author)
        self.app: Optional[Application] = None
        self._started = False

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.effective_message
        if not msg:
            return
        await msg.reply_text("✅ Бот жив. Напиши любое сообщение — отвечу.")

    async def _on_any_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.effective_message
        if not msg or not msg.text:
            return

        text = msg.text
        user = update.effective_user
        author = (user.full_name if user else "unknown")

        log.info("[TG] got message from %s: %s", author, text)

        # Ответ в телеге — чтобы 100% видеть что хендлер работает
        await msg.reply_text("👍 Принял: " + text[:200])

        # Мост в Discord (если подключён)
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

        self.app = Application.builder().token(self.cfg.telegram_token).build()

        # /start
        self.app.add_handler(CommandHandler("start", self._cmd_start))

        # любые текстовые сообщения (включая команды — для теста!)
        self.app.add_handler(MessageHandler(filters.TEXT, self._on_any_text))

        self.app.add_error_handler(self._on_error)

        await self.app.initialize()
        await self.app.start()

        if not self.app.updater:
            raise RuntimeError("Telegram Updater is not available (check python-telegram-bot version)")

        # ВАЖНО: без drop_pending_updates и без allowed_updates
        await self.app.updater.start_polling()

        log.info("[Telegram] Started polling (non-blocking)")

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

    async def send_to_admin(self, text: str):
        if not self.app:
            return
        chat_id = getattr(self.cfg, "telegram_admin_chat_id", None)
        if not chat_id:
            log.warning("TELEGRAM_ADMIN_CHAT_ID is not set, cannot send message")
            return
        try:
            await self.app.bot.send_message(chat_id=int(chat_id), text=text[:4000])
        except Exception:
            log.exception("Failed to send message to admin chat")
