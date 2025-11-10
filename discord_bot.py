# discord_bot.py
import discord
from discord.ext import tasks, commands
import asyncio
from datetime import datetime
import pytz
import random
from config import DISCORD_TOKEN, TIMEZONE, GROUP_GUILD, DISCORD_ROLE_ID
from google_sheets_manager import sheets_manager
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

# Настройки Discord
DISCORD_CHANNEL_NAME = "👻︱боссы"  # Название канала для уведомлений


class DiscordBot:
    def __init__(self):
        # Настройка правильных интентов
        intents = discord.Intents.default()
        intents.message_content = True

        # Используем префикс '!' для текстовых команд
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        self.channel = None
        self.setup_handlers()

    def setup_handlers(self):
        @self.bot.event
        async def on_ready():
            logger.info(f'✅ Discord бот вошел как {self.bot.user}')
            logger.info(f'✅ ID бота: {self.bot.user.id}')

            # Находим нужный канал
            for guild in self.bot.guilds:
                logger.info(f'🔍 Поиск канала в гильдии: {guild.name}')
                for channel in guild.channels:
                    if channel.name == DISCORD_CHANNEL_NAME and isinstance(channel, discord.TextChannel):
                        self.channel = channel
                        logger.info(f'✅ Найден канал для уведомлений: {channel.name} (ID: {channel.id})')
                        break
                if self.channel:
                    break

            if not self.channel:
                logger.error(f'❌ Канал "{DISCORD_CHANNEL_NAME}" не найден!')
                # Покажем доступные каналы для отладки
                for guild in self.bot.guilds:
                    logger.info(f'📋 Доступные каналы в {guild.name}:')
                    for channel in guild.channels:
                        if isinstance(channel, discord.TextChannel):
                            logger.info(f'  - {channel.name} (ID: {channel.id})')

            # Выводим список зарегистрированных команд
            logger.info('📋 Зарегистрированные команды:')
            for command in self.bot.commands:
                logger.info(f'  - !{command.name}')

            # Запускаем фоновые задачи
            self.check_bosses.start()

        @self.bot.event
        async def on_command_error(ctx, error):
            if isinstance(error, commands.CommandNotFound):
                await ctx.send(f"❌ Команда не найдена. Используйте `!help` для списка команд.")
            else:
                logger.error(f'Ошибка в команде: {error}')
                await ctx.send("❌ Произошла ошибка при выполнении команды.")

        # Добавляем команду random как текстовую команду
        @self.bot.command(name="random")
        async def random_command(ctx, *, input_data: str):
            """Обрабатывает команду !random для случайного выбора"""
            try:
                logger.info(f"🎲 Получена команда random: {input_data}")
                result = self.process_random_input(input_data)
                if result:
                    response = f"🎲 Случайный выбор: **{result}**"
                    await ctx.send(response)
                    logger.info(f"✅ Отправлен ответ: {result}")
                else:
                    response = (
                        "❌ Неверный формат. Используйте:\n"
                        "• `!random 1-10` - диапазон чисел\n"
                        "• `!random 7` - число от 1 до 7\n"
                        "• Многострочный ввод для списка ников:\n"
                        "```\n"
                        "!random Ника\n"
                        "Леся\n"
                        "Лось\n"
                        "```"
                    )
                    await ctx.send(response)
            except Exception as e:
                logger.error(f"❌ Ошибка в команде random: {e}")
                await ctx.send("❌ Произошла ошибка при обработке команды")

        # Добавляем команду help
        @self.bot.command(name="help")
        async def help_command(ctx):
            """Показывает справку по командам"""
            help_text = """
**📋 Доступные команды:**

`!random <данные>` - случайный выбор
  • `!random 1-10` - случайное число от 1 до 10
  • `!random 7` - случайное число от 1 до 7
  • `!random` с многострочным вводом для списка:
    ```
    !random Ника
    Леся
    Лось
    ```

`!help` - показывает эту справку

**🤖 Автоматические уведомления:**
Бот автоматически отправляет уведомления о боссах и разломах за 10 минут до их появления.
            """
            await ctx.send(help_text)

    def process_random_input(self, input_data: str) -> str:
        """Обрабатывает входные данные для команды random"""
        input_data = input_data.strip()
        logger.info(f"🔧 Обработка входных данных: '{input_data}'")

        # Проверяем, является ли ввод диапазоном чисел (например: "1-10")
        if '-' in input_data:
            parts = input_data.split('-')
            if len(parts) == 2:
                try:
                    start = int(parts[0].strip())
                    end = int(parts[1].strip())
                    if start <= end:
                        result = str(random.randint(start, end))
                        logger.info(f"🔢 Диапазон {start}-{end} -> {result}")
                        return result
                    else:
                        result = str(random.randint(end, start))
                        logger.info(f"🔢 Диапазон {end}-{start} -> {result}")
                        return result
                except ValueError:
                    logger.info("❌ Неверный формат диапазона")
                    pass  # Не числа, значит не диапазон

        # Проверяем, является ли ввод одним числом (например: "7")
        try:
            num = int(input_data)
            result = str(random.randint(1, num))
            logger.info(f"🔢 Число от 1 до {num} -> {result}")
            return result
        except ValueError:
            logger.info("❌ Не число, проверяем как список")

        # Если не числа, то обрабатываем как список ников
        lines = [line.strip() for line in input_data.split('\n') if line.strip()]
        logger.info(f"📝 Найдено строк: {len(lines)}")
        if len(lines) >= 2:
            result = random.choice(lines)
            logger.info(f"📝 Выбран ник: {result}")
            return result

        logger.info("❌ Не удалось обработать входные данные")
        return None

    def get_role_mention(self):
        """Возвращает правильное упоминание роли"""
        if DISCORD_ROLE_ID:
            return f"<@&{DISCORD_ROLE_ID}>"
        else:
            logger.warning("❌ DISCORD_ROLE_ID не настроен, упоминания роли не будут работать")
            return "@Raven2"

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

            # Отправляем сообщение с правильным упоминанием роли
            role_mention = self.get_role_mention()
            full_message = f"{role_mention}\n{message}"

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

            role_mention = self.get_role_mention()
            full_message = f"{role_mention}\n{message}"

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

                role_mention = self.get_role_mention()
                full_message = f"{role_mention}\n{message}"

                await self.channel.send(full_message)
                logger.info(f"✅ Уведомление о {len(alliance_bosses)} боссах 4 тира отправлено в Discord")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о Tier 4 в Discord: {e}")

    async def send_test_boss_notification(self):
        """Отправляет тестовое уведомление о боссах в Discord"""
        try:
            # Получаем текущие данные
            tz = pytz.timezone(TIMEZONE)
            now = datetime.now(tz)
            schedule_key = now.strftime('%d.%m')

            # Используем ближайшее время для теста
            time_key = "15:30"
            target_tiers = ['tier1', 'tier2']
            is_free_farm = False

            await self.send_boss_notification(time_key, target_tiers, is_free_farm, schedule_key)
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка отправки тестового уведомления о боссах: {e}")
            return False

    async def send_test_rift_notification(self):
        """Отправляет тестовое уведомление о разломах в Discord"""
        try:
            await self.send_rift_notification()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отправки тестового уведомления о разломах: {e}")
            return False

    async def send_test_tier4_notification(self):
        """Отправляет тестовое уведомление о боссах 4 тира в Discord"""
        try:
            # Тестовые данные для боссов 4 тира
            test_bosses = [("Mercia", "Двуликий Моргон"), ("DarkSyndicate", "Марионетка Нидрок")]
            await self.send_tier4_notification(test_bosses)
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отправки тестового уведомления о Tier 4: {e}")
            return False

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


# Создаем глобальный экземпляр бота
discord_bot = DiscordBot()