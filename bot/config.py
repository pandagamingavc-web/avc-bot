import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _int(name: str, default=None):
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return int(v)

def _str(name: str, default=""):
    return os.getenv(name, default)

@dataclass(frozen=True)
class Config:
    discord_token: str
    telegram_token: str
    discord_guild_id: int
    discord_ticket_category_id: int | None
    discord_ticket_channel_id: int | None
    discord_log_channel_id: int | None
    telegram_admin_chat_id: int
    bridge_discord_channel_id: int | None
    bridge_telegram_chat_id: int | None
    spam_max_msgs: int
    spam_window_sec: int
    spam_timeout_sec: int
    link_donate: str
    link_discord: str
    link_steam: str
    link_goals: str

def load_config() -> Config:
    discord_token = _str("DISCORD_TOKEN")
    telegram_token = _str("TELEGRAM_TOKEN")
    if not discord_token:
        raise RuntimeError("DISCORD_TOKEN missing")
    if not telegram_token:
        raise RuntimeError("TELEGRAM_TOKEN missing")

    guild_id = _int("DISCORD_GUILD_ID")
    if not guild_id:
        raise RuntimeError("DISCORD_GUILD_ID missing")

    return Config(
        discord_token=discord_token,
        telegram_token=telegram_token,
        discord_guild_id=guild_id,
        discord_ticket_category_id=_int("DISCORD_TICKET_CATEGORY_ID"),
        discord_ticket_channel_id=_int("DISCORD_TICKET_CHANNEL_ID"),
        discord_log_channel_id=_int("DISCORD_LOG_CHANNEL_ID"),
        telegram_admin_chat_id=_int("TELEGRAM_ADMIN_CHAT_ID") or 0,
        bridge_discord_channel_id=_int("BRIDGE_DISCORD_CHANNEL_ID"),
        bridge_telegram_chat_id=_int("BRIDGE_TELEGRAM_CHAT_ID"),
        spam_max_msgs=int(_str("SPAM_MAX_MSGS", "5")),
        spam_window_sec=int(_str("SPAM_WINDOW_SEC", "8")),
        spam_timeout_sec=int(_str("SPAM_TIMEOUT_SEC", "300")),
        link_donate=_str("LINK_DONATE"),
        link_discord=_str("LINK_DISCORD"),
        link_steam=_str("LINK_STEAM"),
        link_goals=_str("LINK_GOALS"),
    )
