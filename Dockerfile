FROM python:3.11-slim

WORKDIR /app

# системные зависимости (минимум)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# копируем зависимости отдельно для кэша
COPY requirements.txt /app/requirements.txt

# обновляем pip, удаляем "левый" discord, ставим нужное
RUN pip install --no-cache-dir -U pip setuptools wheel \
 && pip uninstall -y discord discord.py || true \
 && pip install --no-cache-dir -r /app/requirements.txt \
 && python -c "import discord; from discord import app_commands; print('OK:', discord.__version__)"

# копируем код
COPY . /app

# запуск
CMD ["python", "-m", "bot"]
