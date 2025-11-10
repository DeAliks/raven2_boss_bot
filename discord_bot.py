# discord_bot.py
import discord
from discord.ext import tasks
import asyncio
from datetime import datetime
import pytz
from config import DISCORD_TOKEN, TIMEZONE, GROUP_GUILD
from google_sheets_manager import sheets_manager
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

# Настройки Discord
DISCORD_CHANNEL_NAME = "👻︱боссы"  # Название канала для уведомлений
DISCORD_ROLE_MENTION = "@Raven2"  # Роль для упоминания


class DiscordBot:
    def __init__(self):
        self.bot = discord.Client(intents=discord.Intents.default())
        self.channel = None
        self.setup_handlers()

    def setup_handlers(self):
        @self.bot.event
        async def on_ready():
            logger.info(f'✅ Discord бот вошел как {self.bot.user}')
            # Находим нужный канал
            for guild in self.bot.guilds:
                for channel in guild.channels:
                    if channel.name == DISCORD_CHANNEL_NAME and isinstance(channel, discord.TextChannel):
                        self.channel = channel
                        logger.info(f'✅ Найден канал для уведомлений: {channel.name}')
                        break
                if self.channel:
                    break

            if not self.channel:
                logger.error(f'❌ Канал "{DISCORD_CHANNEL_NAME}" не найден!')

            # Запускаем фоновые задачи
            self.check_bosses.start()

        @self.bot.event
        async def on_error(event, *args, **kwargs):
            logger.error(f'Ошибка в Discord боте: {event}')

    async def send_boss_notification(self, time_key: str, target_tiers: list, is_free_farm: bool, schedule_key: str):
        """Отправляет уведомление о боссах в Discord"""
        if not self.channel:
            logger.error("Канал Discord не найден")
            return

        try:
            if is_free_farm:
                message = f"🎯 **FREE FARM через 10 минут ({time_key})!**\n\n"

                if time_key == '03:30':
                    message += "🟢 **1 тир**\n\n"
                    message += "⚔️ Можно бить **ВСЕХ** боссов 1 тира!\n"
                    message += "Независимо от вашей гильдии!"
                elif time_key == '07:30':
                    message += "🟢 **1 тир** + 🟡 **2 тир**\n\n"
                    message += "⚔️ Можно бить **ВСЕХ** боссов 1 и 2 тира!\n"
                    message += "Независимо от вашей гильдии!"

                message += "\n🎉 **Удачи в охоте!**"

            else:
                # Получаем данные из Google Таблицы
                bosses_data = sheets_manager.get_today_bosses()

                # Фильтруем только нужные тиры для гильдии
                bosses_to_show = {}
                for tier in target_tiers:
                    if tier in bosses_data:
                        # Фильтруем боссов только для гильдии
                        guild_bosses = [boss for guild_name, boss in bosses_data[tier] if guild_name == GROUP_GUILD]
                        if guild_bosses:
                            bosses_to_show[tier] = guild_bosses

                if not bosses_to_show:
                    return

                # Формируем сообщение с боссами гильдии
                message = f"⏰ **Через 10 минут ({time_key}) появятся боссы:**\n"
                message += f"**Гильдия:** {GROUP_GUILD}\n"
                message += f"**Слот:** {schedule_key}\n\n"

                # Добавляем боссов по тирам
                for tier, bosses in bosses_to_show.items():
                    if tier == "tier1":
                        emoji = "🟢"
                        tier_name = "1 тир"
                    elif tier == "tier2":
                        emoji = "🟡"
                        tier_name = "2 тир"
                    elif tier == "tier3":
                        emoji = "🔴"
                        tier_name = "3 тир"
                    elif tier == "tier4":
                        emoji = "🔵"
                        tier_name = "4 тир"
                    elif tier == "tier5":
                        emoji = "🟣"
                        tier_name = "5 тир"
                    else:
                        emoji = "⚪"
                        tier_name = tier

                    message += f"{emoji} **{tier_name}:**\n"
                    for boss in bosses:
                        message += f"• {boss}\n"
                    message += "\n"

                message += "💀 **Удачи в бою!**"

            # Отправляем сообщение с упоминанием роли
            full_message = f"{DISCORD_ROLE_MENTION}\n{message}"
            await self.channel.send(full_message)
            logger.info(f"✅ Уведомление отправлено в Discord: {time_key}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки в Discord: {e}")

    async def send_rift_notification(self):
        """Отправляет уведомление о разломах в Discord"""
        if not self.channel:
            return

        try:
            message = (
                "🌀 **РАЗЛОМЫ СКОРО ПОЯВЯТСЯ!** 🌀\n\n"
                "⏰ Через 10 минут откроются разломы\n"
                "⚔️ Готовьтесь к битве!\n\n"
                "💎 Не пропустите возможность получить ценные награды!"
            )

            full_message = f"{DISCORD_ROLE_MENTION}\n{message}"
            await self.channel.send(full_message)
            logger.info("✅ Уведомление о разломах отправлено в Discord")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о разломах в Discord: {e}")

    async def send_tier4_notification(self, alliance_bosses: list):
        """Отправляет уведомление о боссах 4 тира в Discord"""
        if not self.channel:
            return

        try:
            if alliance_bosses:
                boss_list = "\n".join([f"• {boss} (**гильдия {guild}**)" for guild, boss in alliance_bosses])

                message = (
                    "🔔 **ВНИМАНИЕ АЛЬЯНС!** 🔔\n\n"
                    f"Обратите внимание! Сегодня есть боссы **Тира 4**:\n\n"
                    f"{boss_list}\n\n"
                    f"⚔️ **Не пропустите возможность помочь нашим гильдиям!** ⚔️"
                )

                full_message = f"{DISCORD_ROLE_MENTION}\n{message}"
                await self.channel.send(full_message)
                logger.info(f"✅ Уведомление о {len(alliance_bosses)} боссах 4 тира отправлено в Discord")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о Tier 4 в Discord: {e}")

    @tasks.loop(minutes=1)
    async def check_bosses(self):
        """Проверяет время и отправляет уведомления"""
        try:
            tz = pytz.timezone(TIMEZONE)
            now = datetime.now(tz)
            current_time = now.strftime('%H:%M')

            # Время за 10 минут до появления боссов
            notification_times = ['03:20', '07:20', '11:20', '15:20', '19:20', '23:20']

            if current_time in notification_times:
                time_key = current_time.replace('20', '30')  # Время появления боссов

                # Определяем какие тиры появляются в это время
                tiers_info = {
                    '03:30': {'tiers': ['tier1'], 'free_farm': True},
                    '07:30': {'tiers': ['tier1', 'tier2'], 'free_farm': True},
                    '11:30': {'tiers': ['tier1'], 'free_farm': False},
                    '15:30': {'tiers': ['tier1', 'tier2'], 'free_farm': False},
                    '19:30': {'tiers': ['tier1'], 'free_farm': False},
                    '23:30': {'tiers': ['tier1', 'tier2', 'tier3', 'tier4', 'tier5'], 'free_farm': False}
                }

                if time_key in tiers_info:
                    target_tiers = tiers_info[time_key]['tiers']
                    is_free_farm = tiers_info[time_key]['free_farm']
                    schedule_key = now.strftime('%d.%m')

                    await self.send_boss_notification(time_key, target_tiers, is_free_farm, schedule_key)

            # Проверяем разломы
            rift_times = ['14:20', '22:20']
            if current_time in rift_times:
                await self.send_rift_notification()

        except Exception as e:
            logger.error(f"❌ Ошибка в check_bosses: {e}")

    @check_bosses.before_loop
    async def before_check_bosses(self):
        await self.bot.wait_until_ready()

    def run(self):
        """Запускает Discord бота"""
        try:
            self.bot.run(DISCORD_TOKEN)
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Discord бота: {e}")

discord_bot = DiscordBot()