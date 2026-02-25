from __future__ import annotations

import logging
from typing import Callable, Awaitable, Optional, List, Tuple

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

        # сюда __main__.py может положить доп. команды: [("stats", handler), ...]
        self.extra_command_handlers: List[Tuple[str, Callable]] = []

    def _allowed_chat(self, update: Update) -> bool:
        """
        Если задан TELEGRAM_ALLOWED_CHAT_ID — разрешаем только этот чат/группу.
        Если не задан — разрешаем везде.
        """
        allowed = getattr(self.cfg, "bridge_telegram_chat_id", None) or getattr(self.cfg, "telegram_allowed_chat_id", None)
        # В твоём Config есть bridge_telegram_chat_id и telegram_admin_chat_id.
        # Мы используем TELEGRAM_ALLOWED_CHAT_ID (если ты добавил), иначе пропускаем все.
        # Если у тебя переменная называется TELEGRAM_ALLOWED_CHAT_ID — она должна попадать в cfg как telegram_allowed_chat_id.
        # Если у тебя её нет в Config — просто убери проверку или добавь поле (я могу дать готовый config.py).
        try:
            allowed_env = getattr(self.cfg, "telegram_allowed_chat_id", None)
            allowed = allowed_env if allowed_env else allowed
        except Exception:
            pass

        if not allowed:
            return True

        try:
            chat_id = update.effective_chat.id if update.effective_chat else None
            return int(chat_id) == int(allowed)
        except Exception:
            return False

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._allowed_chat(update):
            return
        await update.effective_message.reply_text("✅ Бот жив. Напиши сообщение — отвечу.")

    async def _cmd_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /id — покажет chat_id и user_id (чтобы ты мог правильно поставить переменные в Render)
        """
        msg = update.effective_message
        if not msg:
            return
        chat = update.effective_chat
        user = update.effective_user

        chat_id = chat.id if chat else None
        user_id = user.id if user else None
        title = getattr(chat, "title", None)

        text = (
            f"🆔 chat_id: {chat_id}\n"
            f"👤 user_id: {user_id}\n"
            f'📌 chat_title: "{title}"'
        )
        await msg.reply_text(text)

    async def _on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._allowed_chat(update):
            return

        msg = update.effective_message
        if not msg or not msg.text:
            return

        text = msg.text
        user = update.effective_user
        author = (user.full_name if user else "unknown")

        # ЛОГ: чтобы видеть, что реально приходят апдейты
        log.info("[TG] got message from %s: %s", author, text)

        # тестовый ответ в телеге (чтобы сразу понять, что хендлер работает)
        await msg.reply_text("👍 Принял: " + text[:200])

        # если у тебя есть мост в Discord — отправим туда
        try:
            await self.on_text_from_tg(text, author)
        except Exception:
            log.exception("TG -> Discord bridge failed")

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        log.exception("Telegram error: %s", context.error)

    async def start(self):
        """
        Запускаем polling НЕ блокируя loop.
        """
        if self._started:
            return
        self._started = True

        if not self.cfg.telegram_token:
            raise RuntimeError("TELEGRAM_TOKEN is empty")

        # build() без run_polling()
        self.app = Application.builder().token(self.cfg.telegram_token).build()

        # базовые команды
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("id", self._cmd_id))

        # ✅ ДОП КОМАНДЫ из __main__.py
        extra = getattr(self, "extra_command_handlers", [])
        for cmd, fn in extra:
            self.app.add_handler(CommandHandler(cmd, fn))

        # текстовые сообщения
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text))
        self.app.add_error_handler(self._on_error)

        # правильный неблокирующий старт
        await self.app.initialize()
        await self.app.start()

        if not self.app.updater:
            raise RuntimeError("Telegram Updater is not available (check python-telegram-bot version)")

        await self.app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )

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
        """
        Отправка в TG-админ чат/группу.
        TELEGRAM_ADMIN_CHAT_ID должен быть -100...
        """
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
