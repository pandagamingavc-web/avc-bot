# AVC Bot (Discord + Telegram)

Функции:
- тикеты/заявки (Discord + Telegram)
- модерация (Discord: ban/timeout/purge + антиспам)
- приветствие новичков (Discord + Telegram)
- автоответы по ключевым словам (оба)
- команды ссылок: /donate /discord /steam /goals (оба)
- роли по кнопкам (Discord)
- мост сообщений (Discord канал <-> Telegram чат)

## Запуск
```bash
python -m venv .venv
# Win: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt

copy .env.example .env  # Windows
cp .env.example .env    # Mac/Linux
python -m bot
```

## Важно
1) В `.env` укажи токены и ID.
2) Для ролей-кнопок открой `bot/discord_bot.py` и заполни `role_ids` в команде `/rolepanel`.
