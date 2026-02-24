FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -U pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt \
 && pip uninstall -y discord discord.py || true \
 && pip install --no-cache-dir py-cord==2.4.1

COPY . .

CMD ["python", "-m", "bot"]
