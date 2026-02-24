# AVC Bot (Discord + Telegram) — Render Worker

## Как запустить на Render (без карты)
1) Залей эти файлы в GitHub репозиторий (в корень).
2) В Render нажми **New + → Blueprint** и выбери репозиторий.
   Render сам создаст **Worker** по файлу `render.yaml`.
3) В Render → Service → Environment добавь переменные:
   - DISCORD_TOKEN
   - TELEGRAM_TOKEN
   - DISCORD_GUILD_ID (ID сервера)
   - TELEGRAM_ADMIN_CHAT_ID (ID админ-чата)
   - Остальное по желанию (тикеты/bridge/ссылки)
4) Нажми Deploy.

## Команды
Discord: /ticket /donate /discord /steam /goals + /ban /timeout /purge
Telegram: /ticket /donate /discord /steam /goals

## Роли по кнопкам (Discord)
Открой `bot/discord_bot.py` и впиши `role_ids` в команде `/rolepanel`.
