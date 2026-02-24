from __future__ import annotations
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from .config import Config
from .keywords import KEYWORD_REPLIES
import uuid

def _low(s: str) -> str:
    return (s or "").lower()

def make_ticket_id() -> str:
    return uuid.uuid4().hex[:8]

class TelegramBot:
    def __init__(self, cfg: Config, discord_bridge_send):
        self.cfg = cfg
        self.discord_bridge_send = discord_bridge_send
        self.app = Application.builder().token(cfg.telegram_token).build()

        self.app.add_handler(CommandHandler("donate", self._link("donate")))
        self.app.add_handler(CommandHandler("discord", self._link("discord")))
        self.app.add_handler(CommandHandler("steam", self._link("steam")))
        self.app.add_handler(CommandHandler("goals", self._link("goals")))
        self.app.add_handler(CommandHandler("ticket", self.ticket))

        self.app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, self.welcome))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_text))

        self.ticket_map = {}  # admin_msg_id -> user_chat_id

    def _link(self, which: str):
        async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            link = getattr(self.cfg, f"link_{which}", "") or "Ссылка не настроена."
            await update.message.reply_text(link)
        return handler

    async def welcome(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        for m in update.message.new_chat_members or []:
            await update.message.reply_text(f"👋 Добро пожаловать, {m.full_name}!")

    async def ticket(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return
        text = " ".join(context.args).strip()
        if not text:
            return await update.message.reply_text("Напиши: /ticket твоя заявка")

        if not self.cfg.telegram_admin_chat_id:
            return await update.message.reply_text("Не настроен TELEGRAM_ADMIN_CHAT_ID.")

        tid = make_ticket_id()
        user = update.effective_user
        user_chat_id = update.effective_chat.id

        admin_text = (
            f"🎫 TICKET {tid}\n"
            f"From: {user.id} {user.full_name}\n"
            f"Chat: {user_chat_id}\n"
            f"Text: {text}"
        )
        msg = await context.bot.send_message(chat_id=self.cfg.telegram_admin_chat_id, text=admin_text)
        self.ticket_map[msg.message_id] = user_chat_id
        await update.message.reply_text(f"✅ Тикет создан: {tid}.")

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message:
            return

        # Admin reply-to-ticket -> forward to user
        if self.cfg.telegram_admin_chat_id and update.effective_chat.id == self.cfg.telegram_admin_chat_id:
            rt = update.message.reply_to_message
            if rt and rt.message_id in self.ticket_map:
                user_chat_id = self.ticket_map[rt.message_id]
                await context.bot.send_message(chat_id=user_chat_id, text=f"💬 Ответ админа: {update.message.text}")
                return

        content = _low(update.message.text)
        for k, v in KEYWORD_REPLIES.items():
            if k in content:
                await update.message.reply_text(v)
                break

        if self.cfg.bridge_telegram_chat_id and update.effective_chat.id == self.cfg.bridge_telegram_chat_id:
            if self.discord_bridge_send:
                await self.discord_bridge_send(text=update.message.text, author=update.effective_user.full_name)

    async def start(self):
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        print("[Telegram] Started polling")
