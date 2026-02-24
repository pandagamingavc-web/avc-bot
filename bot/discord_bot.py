from __future__ import annotations
import discord
from discord import app_commands
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
        super().__init__(style=discord.ButtonStyle.secondary, label=f"Role {role_id}", custom_id=f"rolebtn:{role_id}")
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
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.cfg = cfg
        self.spam = SpamGate(cfg.spam_max_msgs, cfg.spam_window_sec)
        self.tg_bridge_send = tg_bridge_send  # async (text, author)

    async def setup_hook(self):
        guild = discord.Object(id=self.cfg.discord_guild_id)

        @self.tree.command(name="donate", description="Ссылка на донат", guild=guild)
        async def donate(interaction: discord.Interaction):
            await interaction.response.send_message(self.cfg.link_donate or "Ссылка не настроена.")

        @self.tree.command(name="discord", description="Ссылка на Discord", guild=guild)
        async def discord_link(interaction: discord.Interaction):
            await interaction.response.send_message(self.cfg.link_discord or "Ссылка не настроена.")

        @self.tree.command(name="steam", description="Ссылка на Steam", guild=guild)
        async def steam(interaction: discord.Interaction):
            await interaction.response.send_message(self.cfg.link_steam or "Ссылка не настроена.")

        @self.tree.command(name="goals", description="Ссылка на цели", guild=guild)
        async def goals(interaction: discord.Interaction):
            await interaction.response.send_message(self.cfg.link_goals or "Ссылка не настроена.")

        @self.tree.command(name="ticket", description="Создать тикет/заявку", guild=guild)
        @app_commands.describe(text="Опиши проблему/заявку")
        async def ticket(interaction: discord.Interaction, text: str):
            if not interaction.guild:
                return await interaction.response.send_message("Только на сервере.", ephemeral=True)

            created = None
            if self.cfg.discord_ticket_category_id:
                category = interaction.guild.get_channel(self.cfg.discord_ticket_category_id)
                if isinstance(category, discord.CategoryChannel):
                    created = await interaction.guild.create_text_channel(
                        name=f"ticket-{interaction.user.name}".lower()[:90],
                        category=category,
                        overwrites={
                            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                        },
                    )
            if created is None and self.cfg.discord_ticket_channel_id:
                parent = interaction.guild.get_channel(self.cfg.discord_ticket_channel_id)
                if isinstance(parent, discord.TextChannel):
                    created = await parent.create_thread(name=f"ticket-{interaction.user.name}".lower()[:90], auto_archive_duration=1440)

            if created is None:
                return await interaction.response.send_message(
                    "Тикеты не настроены: укажи DISCORD_TICKET_CATEGORY_ID или DISCORD_TICKET_CHANNEL_ID",
                    ephemeral=True
                )

            await interaction.response.send_message(f"Тикет создан: {created.mention}", ephemeral=True)
            await created.send(f"🎫 Тикет от {interaction.user.mention}\n**Текст:** {text}")

        @self.tree.command(name="ban", description="Бан пользователя", guild=guild)
        @app_commands.checks.has_permissions(ban_members=True)
        async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            await member.ban(reason=reason)
            await interaction.response.send_message(f"✅ Забанен {member.mention}. Причина: {reason}")

        @self.tree.command(name="timeout", description="Таймаут (сек)", guild=guild)
        @app_commands.checks.has_permissions(moderate_members=True)
        async def timeout(interaction: discord.Interaction, member: discord.Member, seconds: int, reason: str = "No reason"):
            until = discord.utils.utcnow() + discord.timedelta(seconds=seconds)
            await member.timeout(until, reason=reason)
            await interaction.response.send_message(f"✅ Таймаут {member.mention} на {seconds}s. Причина: {reason}")

        @self.tree.command(name="purge", description="Удалить N сообщений", guild=guild)
        @app_commands.checks.has_permissions(manage_messages=True)
        async def purge(interaction: discord.Interaction, count: int):
            if not isinstance(interaction.channel, discord.TextChannel):
                return await interaction.response.send_message("Только текстовый канал.", ephemeral=True)
            deleted = await interaction.channel.purge(limit=max(1, min(count, 200)))
            await interaction.response.send_message(f"🧹 Удалено: {len(deleted)}", ephemeral=True)

        @self.tree.command(name="rolepanel", description="Панель ролей по кнопкам", guild=guild)
        @app_commands.checks.has_permissions(manage_roles=True)
        async def rolepanel(interaction: discord.Interaction):
            # TODO: Впиши сюда ID ролей, которые можно выдавать кнопками
            role_ids: list[int] = []
            if not role_ids:
                return await interaction.response.send_message("Не настроено: впиши role_ids в bot/discord_bot.py", ephemeral=True)
            await interaction.response.send_message("Выбери роли:", view=RolePanelView(role_ids))

        await self.tree.sync(guild=guild)

    async def on_ready(self):
        print(f"[Discord] Logged in as {self.user}")

    async def on_member_join(self, member: discord.Member):
        ch = member.guild.system_channel
        if ch:
            await ch.send(f"👋 Добро пожаловать, {member.mention}!")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.spam.hit(message.author.id):
            if isinstance(message.author, discord.Member):
                try:
                    until = discord.utils.utcnow() + discord.timedelta(seconds=self.cfg.spam_timeout_sec)
                    await message.author.timeout(until, reason="Spam detected")
                    await message.channel.send(f"⛔ {message.author.mention} таймаут за спам ({self.cfg.spam_timeout_sec}s).")
                except Exception:
                    pass

        content = _low(message.content)
        for k, v in KEYWORD_REPLIES.items():
            if k in content:
                await message.reply(v, mention_author=False)
                break

        if self.cfg.bridge_discord_channel_id and message.channel.id == self.cfg.bridge_discord_channel_id:
            if self.tg_bridge_send:
                await self.tg_bridge_send(text=message.content, author=str(message.author))

        await self.process_commands(message)
