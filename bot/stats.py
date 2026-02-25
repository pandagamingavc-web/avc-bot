from __future__ import annotations

import datetime as dt
from typing import Optional

import discord


def _fmt_dt(d: Optional[dt.datetime]) -> str:
    if not d:
        return "—"
    # делаем красиво и одинаково
    return d.strftime("%Y-%m-%d %H:%M")


async def build_discord_stats(client: discord.Client, guild_id: int) -> str:
    """
    Собирает безопасную статистику сервера без privileged intents.
    (Если у тебя включены Presence/Members intents — покажем больше.)
    """
    guild = client.get_guild(guild_id)
    if not guild:
        # пробуем догрузить
        try:
            guild = await client.fetch_guild(guild_id)
        except Exception:
            return "⚠️ Не могу найти Discord сервер по DISCORD_GUILD_ID. Проверь ID и доступ бота."

    # Некоторые поля доступны только если есть members intent / cache
    members_total = guild.member_count or 0

    # Если members закешированы (интенты включены) — посчитаем людей/ботов
    humans = None
    bots = None
    online = None

    try:
        if guild.members:
            humans = sum(1 for m in guild.members if not m.bot)
            bots = sum(1 for m in guild.members if m.bot)

            # online будет только если включен Presence intent
            try:
                online = sum(
                    1 for m in guild.members
                    if getattr(m, "status", None) in (discord.Status.online, discord.Status.idle, discord.Status.dnd)
                )
            except Exception:
                online = None
    except Exception:
        pass

    text = []
    text.append("📊 **Статистика сервера**")
    text.append(f"🏰 Сервер: **{guild.name}**")
    text.append(f"🆔 Guild ID: `{guild.id}`")
    text.append("")

    # участники
    if humans is not None and bots is not None:
        text.append(f"👥 Участники: **{members_total}** (людей: **{humans}**, ботов: **{bots}**)")
    else:
        text.append(f"👥 Участники: **{members_total}**")

    # online если доступно
    if online is not None:
        text.append(f"🟢 Онлайн (примерно): **{online}**")

    # каналы
    try:
        text.append(f"💬 Текстовых каналов: **{len(getattr(guild, 'text_channels', []))}**")
        text.append(f"🔊 Голосовых каналов: **{len(getattr(guild, 'voice_channels', []))}**")
        text.append(f"🧵 Форумов: **{len(getattr(guild, 'forum_channels', []))}**")
    except Exception:
        pass

    # роли
    try:
        text.append(f"🎭 Ролей: **{len(guild.roles)}**")
    except Exception:
        pass

    # бусты
    try:
        level = getattr(guild, "premium_tier", None)
        boosts = getattr(guild, "premium_subscription_count", None)
        if level is not None:
            text.append(f"🚀 Boost level: **{int(level)}**")
        if boosts is not None:
            text.append(f"✨ Boosts: **{int(boosts)}**")
    except Exception:
        pass

    # дата создания
    try:
        created = guild.created_at
        text.append(f"📅 Создан: **{_fmt_dt(created)}**")
    except Exception:
        pass

    return "\n".join(text)
