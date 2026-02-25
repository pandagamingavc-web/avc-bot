from __future__ import annotations

import asyncio
import logging
import os

import aiohttp
from aiohttp import web

from .config import load_config
from .discord_bot import DiscordBot
from .telegram_bot import TelegramBridge

from .dedupe import DedupeTTL
from .youtube_watch import YouTubeWatcher
from .twitch_watch import TwitchWatcher
from .news_watch import NewsWatcher

# бесплатное "AI-похожее" форматирование
from .ai_format import FreeAIFormatter


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bot")


async def _health_server():
    """
    Render FREE Web Service требует открытый порт.
    Делаем простой HTTP / => 200 OK.
    """
    port = int(os.getenv("PORT", "10000"))

    async def handle(_request: web.Request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", handle)
    app.router.add_head("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()

    log.info("[HTTP] Health server started on port %s", port)

    # держим процесс
    while True:
        await asyncio.sleep(3600)


async def main():
    cfg = load_config()

    # анти-дубль (в памяти)
    dedupe = DedupeTTL(ttl_sec=6 * 3600)

    # форматирование "как AI" (бесплатно)
    fmt = FreeAIFormatter()

    # watchers
    yt = YouTubeWatcher()
    tw = TwitchWatcher()
    nw = NewsWatcher()

    interval = int(os.getenv("POST_INTERVAL_SEC", "3600"))  # раз в час по умолчанию

    # Discord
    discord_bot = DiscordBot(cfg)

    # TG -> Discord
    async def tg_to_discord(text: str, author: str):
        await discord_bot.send_to_bridge_channel(f"📨 TG • {author}: {text}")

    # Telegram
    tg_bot = TelegramBridge(cfg, on_text_from_tg=tg_to_discord)

    # отправка в обе платформы
    async def post_to_both(message: str):
        # Telegram (у тебя настроено на канал/чат через переменные)
        await tg_bot.send_to_admin(message)
        # Discord
        await discord_bot.send_to_bridge_channel(message)

    async def scheduler_loop():
        log.info("[Scheduler] Started (every %s sec)", interval)

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    # YouTube
                    if yt.enabled():
                        post = await yt.poll(session)
                        if post:
                            key = f"yt:{post.video_id}"
                            if not dedupe.seen(key):
                                text = fmt.format_post("youtube", post.title, post.url)
                                await post_to_both(text)

                    # Twitch
                    if tw.enabled():
                        post = await tw.poll(session)
                        if post:
                            key = f"tw:{post.user_login}:{post.url}"
                            if not dedupe.seen(key):
                                title = f"{post.user_login} — {post.title}"
                                text = fmt.format_post("twitch", title, post.url)
                                await post_to_both(text)

                    # News
                    if nw.enabled():
                        post = await nw.poll(session)
                        if post:
                            key = f"news:{post.url}"
                            if not dedupe.seen(key):
                                text = fmt.format_post("news", post.title, post.url)
                                await post_to_both(text)

                    log.info("[Scheduler] tick ok")
                except Exception:
                    log.exception("[Scheduler] tick failed")

                await asyncio.sleep(interval)

    await asyncio.gather(
        _health_server(),
        discord_bot.start(),
        tg_bot.start(),
        scheduler_loop(),
    )


if __name__ == "__main__":
    asyncio.run(main())
