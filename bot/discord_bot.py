from __future__ import annotations

import discord
from discord.ext import commands

from .config import Config
from .shared import SpamGate
from .keywords import KEYWORD_REPLIES


def _low(s: str) -> str:
    return (s or "").lower()


class RolePanelView(discord.ui.View):
    def __init__(self, role_ids: list[int]):
        super().__init__(timeout=None)
        for rid in role_ids:
            self.add_item(RoleButton(rid))


class RoleButton(discord.ui.Button):
    def __init__(self, role_id: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=f"Role {role_id}",
            custom_id=f"rolebtn:{role_id}",
        )
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Только на сервере.", ephemeral=True)

        role = interaction.guild.get_role(self.role_id)
        if role is None:
            return await interaction.response.send_message("Роль не найдена.", ephemeral=True)

        member: discord.Member = interaction.user
        if role in member.roles:
            await member.remove_roles(role, reason="Role toggle")
            await interaction.response.send_message(f"Роль снята: {role.name}", ephemeral=True)
        else:
            await member.add_roles(role, reason="Role toggle")
            await interaction.response.send_message(f"Роль выдана: {role.name}", ephemeral=True)


class DiscordBot(commands.Bot):
    def __init__(self, cfg: Config, tg_bridge_send):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True  # нужно включить Message Content Intent в Dev Portal, если используешь сообщения
        super().__init__(command_prefix="!", intents=intents)

        self.cfg = cfg
        self.spam = SpamGate(cfg.spam_max_msgs, cfg.spam_window_sec)
        self.tg_bridge_send = tg_bridge_send  # async (text, author)

    async def setup_hook(self):
        # ВАЖНО: /команды будут зарегистрированы только в этом guild (быстро обновляются)
        guild = discord.Object(id=self.cfg.discord_guild_id)

        @self.tree.command(guild=guild, name="donate", description="Ссылка на донат")
        async def donate(interaction: discord.Interaction):
            await interaction.response.send_message(self.cfg.link_donate or "Ссылка не настроена.")

        @self.tree.command(guild=guild, name="discord", description="Ссылка на Discord")
        async def discord_link(interaction: discord.Interaction):
            await interaction.response.send_message(self.cfg.link_discord or "Ссылка не настроена.")

        @self.tree.command(guild=guild, name="steam", description="Ссылка на Steam")
        async def steam(interaction: discord.Interaction):
            await interaction.response.send_message(self.cfg.link_steam or "Ссылка не настроена.")

        # Синхронизация слэш-команд в конкретный сервер
        await self.tree.sync(guild=guild)

    async def on_ready(self):
        print(f"[Discord] Logged in as {self.user} (id={self.user.id})")

    async def on_message(self, message: discord.Message):
        # игнор ботов и личек
        if message.author.bot or message.guild is None:
            return

        # антиспам
        if self.spam.hit(str(message.author.id)):
            return

        text = message.content or ""
        low = _low(text)

        # авто-ответы по ключевым словам
        for key, reply in KEYWORD_REPLIES.items():
            if key in low:
                try:
                    await message.channel.send(reply)
                except Exception:
                    pass
                break

        # обязательно, чтобы работали префикс-команды (если есть)
        await self.process_commands(message)
