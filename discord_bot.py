# discord_bot.py (универсальная версия с новой гильдией)
import discord
from discord.ext import tasks, commands
import asyncio
from datetime import datetime
import pytz
import random
from config import DISCORD_BOT_TOKEN, TIMEZONE
from google_sheets_manager import sheets_manager
import logging
import db

# Настройка логирования
logger = logging.getLogger(__name__)

# ID администратора (ваш ID)
ADMIN_USER_ID = 7774897924

# Поддерживаемые гильдии (теперь с RussianTeam)
SUPPORTED_GUILDS = ["All", "DarkSyndicate", "Mercia", "HryKings", "RussianTeam"]


class DiscordBot:
    def __init__(self):
        # Настройка правильных интентов
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        # Используем префикс '!' для текстовых команд
        self.bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
        self.setup_handlers()

    def setup_handlers(self):
        @self.bot.event
        async def on_ready():
            logger.info(f'✅ Discord бот вошел как {self.bot.user}')
            logger.info(f'✅ ID бота: {self.bot.user.id}')

            # Запускаем фоновые задачи
            self.check_bosses.start()

            # Выводим список зарегистрированных команд
            logger.info('📋 Зарегистрированные команды:')
            for command in self.bot.commands:
                logger.info(f'  - !{command.name}')

        # Команда активации уведомлений
        @self.bot.command(name="start_boss_alert")
        async def start_boss_alert(ctx, guild_name: str = None):
            """Активирует уведомления о боссах в текущем канале"""
            try:
                # Если гильдия не указана, показываем варианты
                if not guild_name:
                    embed = discord.Embed(
                        title="🎯 Настройка уведомлений о боссах",
                        description="Пожалуйста, выберите гильдию для уведомлений:",
                        color=0x00ff00
                    )

                    embed.add_field(
                        name="Доступные гильдии:",
                        value="\n".join([f"• **{g}**" for g in SUPPORTED_GUILDS]),
                        inline=False
                    )

                    embed.add_field(
                        name="Пример использования:",
                        value="`!start_boss_alert All` - для всех гильдий\n"
                              "`!start_boss_alert DarkSyndicate` - только для DarkSyndicate\n"
                              "`!start_boss_alert RussianTeam` - только для RussianTeam",
                        inline=False
                    )

                    await ctx.send(embed=embed)
                    return

                # Проверяем корректность названия гильдии
                if guild_name not in SUPPORTED_GUILDS:
                    available = ", ".join(SUPPORTED_GUILDS)
                    await ctx.send(f"❌ Неверное название гильдии. Доступные варианты: {available}")
                    return

                # Сохраняем настройки в базу данных
                guild_id = str(ctx.guild.id)
                channel_id = str(ctx.channel.id)

                db.set_discord_guild(guild_id, channel_id, guild_name)

                embed = discord.Embed(
                    title="✅ Уведомления активированы!",
                    description=f"Канал: {ctx.channel.mention}\nГильдия: **{guild_name}**",
                    color=0x00ff00
                )

                embed.add_field(
                    name="📋 Что будет приходить:",
                    value="• Уведомления о боссах за 10 минут до появления\n"
                          "• Уведомления о разломах (Rifts)\n"
                          "• Уведомления о боссах 4 тира",
                    inline=False
                )

                if guild_name == "All":
                    embed.add_field(
                        name="ℹ️ Режим 'All':",
                        value="Вы будете получать уведомления для ВСЕХ гильдий",
                        inline=False
                    )

                embed.set_footer(text="Для отключения используйте !stop_boss_alert")

                await ctx.send(embed=embed)

            except Exception as e:
                logger.error(f"❌ Ошибка в команде start_boss_alert: {e}")
                await ctx.send("❌ Произошла ошибка при настройке уведомлений")

        @self.bot.command(name="stop_boss_alert")
        async def stop_boss_alert(ctx):
            """Отключает уведомления о боссах"""
            try:
                guild_id = str(ctx.guild.id)
                db.deactivate_discord_server(guild_id)

                embed = discord.Embed(
                    title="🔕 Уведомления отключены",
                    description="Уведомления о боссах больше не будут приходить в этот канал.",
                    color=0xff9900
                )

                embed.add_field(
                    name="Для повторной активации:",
                    value="Используйте команду `!start_boss_alert <гильдия>`",
                    inline=False
                )

                await ctx.send(embed=embed)

            except Exception as e:
                logger.error(f"❌ Ошибка в команде stop_boss_alert: {e}")
                await ctx.send("❌ Произошла ошибка при отключении уведомлений")

        @self.bot.command(name="boss_status")
        async def boss_status(ctx):
            """Показывает текущий статус уведомлений"""
            try:
                guild_id = str(ctx.guild.id)
                settings = db.get_discord_guild(guild_id)

                embed = discord.Embed(
                    title="📊 Статус уведомлений",
                    color=0x0099ff
                )

                if settings:
                    channel = ctx.guild.get_channel(int(settings['channel_id']))
                    channel_mention = channel.mention if channel else f"ID: {settings['channel_id']}"

                    embed.add_field(name="✅ Статус", value="АКТИВНЫ", inline=True)
                    embed.add_field(name="📁 Гильдия", value=settings['selected_guild'], inline=True)
                    embed.add_field(name="📢 Канал", value=channel_mention, inline=False)

                    # Показываем сегодняшних боссов для выбранной гильдии
                    today_bosses = await self.get_today_bosses_for_guild(settings['selected_guild'])
                    if today_bosses and len(today_bosses) < 1000:
                        embed.add_field(
                            name="📅 Боссы на сегодня:",
                            value=today_bosses,
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="❌ Статус",
                        value="НЕ АКТИВНЫ",
                        inline=False
                    )

                    embed.add_field(
                        name="Для активации:",
                        value="Используйте `!start_boss_alert <гильдия>`\n"
                              f"Доступные гильдии: {', '.join(SUPPORTED_GUILDS)}",
                        inline=False
                    )

                await ctx.send(embed=embed)

            except Exception as e:
                logger.error(f"❌ Ошибка в команде boss_status: {e}")
                await ctx.send("❌ Произошла ошибка при получении статуса")

        @self.bot.command(name="today_bosses")
        async def today_bosses(ctx, guild_name: str = None):
            """Показывает боссов на сегодня для указанной гильдии"""
            try:
                # Если гильдия не указана, берем из настроек сервера
                if not guild_name:
                    settings = db.get_discord_guild(str(ctx.guild.id))
                    if settings:
                        guild_name = settings['selected_guild']
                    else:
                        await ctx.send(
                            "❌ Гильдия не указана и уведомления не настроены. Используйте: `!today_bosses <гильдия>`")
                        return

                # Проверяем, поддерживается ли гильдия
                if guild_name not in SUPPORTED_GUILDS and guild_name != "All":
                    available = ", ".join(SUPPORTED_GUILDS)
                    await ctx.send(f"❌ Гильдия '{guild_name}' не поддерживается. Доступные: {available}")
                    return

                # Получаем боссов на сегодня
                bosses_text = await self.get_today_bosses_for_guild(guild_name)

                if not bosses_text:
                    await ctx.send(f"❌ На сегодня для гильдии **{guild_name}** боссов не найдено.")
                    return

                # Разбиваем на части если сообщение слишком длинное
                if len(bosses_text) > 2000:
                    chunks = [bosses_text[i:i + 2000] for i in range(0, len(bosses_text), 2000)]
                    for chunk in chunks:
                        embed = discord.Embed(
                            title=f"📅 Боссы на сегодня - {guild_name}",
                            description=chunk,
                            color=0xff9900
                        )
                        await ctx.send(embed=embed)
                else:
                    embed = discord.Embed(
                        title=f"📅 Боссы на сегодня - {guild_name}",
                        description=bosses_text,
                        color=0xff9900
                    )
                    await ctx.send(embed=embed)

            except Exception as e:
                logger.error(f"❌ Ошибка в команде today_bosses: {e}")
                await ctx.send("❌ Произошла ошибка при получении списка боссов")

        @self.bot.event
        async def on_command_error(ctx, error):
            if isinstance(error, commands.CommandNotFound):
                # Игнорируем ошибку "команда не найдена"
                return
            elif isinstance(error, commands.CheckFailure):
                await ctx.send("❌ У вас нет прав для выполнения этой команды.")
            else:
                logger.error(f'Ошибка в команде: {error}')
                await ctx.send("❌ Произошла ошибка при выполнении команды.")

        def is_admin():
            """Проверка прав администратора"""

            async def predicate(ctx):
                # Проверяем по ID пользователя
                if ctx.author.id == ADMIN_USER_ID:
                    return True

                # Проверяем по роли администратора
                if ctx.guild and ctx.author.guild_permissions.administrator:
                    return True

                # Проверяем по наличию роли с названием "Admin"
                if ctx.guild:
                    admin_role = discord.utils.get(ctx.author.roles, name="Admin")
                    if admin_role:
                        return True

                return False

            return commands.check(predicate)

        # Глобальная проверка перед выполнением любой команды
        @self.bot.check
        async def global_check(ctx):
            """Глобальная проверка перед выполнением любой команды"""
            # Сохраняем информацию о пользователе
            user_id = str(ctx.author.id)
            username = f"{ctx.author.name}#{ctx.author.discriminator}"

            # Добавляем/обновляем пользователя в базе
            db.add_or_update_user(user_id, username)

            # Проверяем бан пользователя
            user_info = db.get_user(user_id)
            if user_info and user_info['is_banned']:
                await ctx.send(f"❌ Вы забанены. Причина: {user_info['ban_reason']}")
                return False

            # Проверяем бан гильдии (если пользователь выбрал гильдию)
            user_guild = user_info['guild'] if user_info else None
            if user_guild and db.is_guild_banned(user_guild):
                await ctx.send(f"❌ Ваша гильдия '{user_guild}' забанена.")
                return False

            return True

        # Добавляем команду random как текстовую команду
        @self.bot.command(name="random")
        async def random_command(ctx, *, input_data: str):
            """Обрабатывает команду !random для случайного выбора"""
            try:
                logger.info(f"🎲 Получена команда random от {ctx.author.id}: {input_data}")
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

        # Команды администратора
        @self.bot.command(name="ban")
        @is_admin()
        async def ban_user_cmd(ctx, user_id: str, *, reason: str = "Не указана"):
            """Банит пользователя по ID"""
            try:
                # Проверяем, существует ли пользователь
                user_info = db.get_user(user_id)
                if not user_info:
                    await ctx.send(f"❌ Пользователь с ID {user_id} не найден в базе данных.")
                    return

                if user_info['is_banned']:
                    await ctx.send(f"❌ Пользователь {user_id} уже забанен.")
                    return

                db.ban_user(user_id, reason, f"Discord: {ctx.author.id}")
                await ctx.send(f"✅ Пользователь {user_id} забанен. Причина: {reason}")

            except Exception as e:
                logger.error(f"❌ Ошибка при бане пользователя: {e}")
                await ctx.send("❌ Произошла ошибка при бане пользователя")

        @self.bot.command(name="unban")
        @is_admin()
        async def unban_user_cmd(ctx, user_id: str):
            """Разбанивает пользователя по ID"""
            try:
                user_info = db.get_user(user_id)
                if not user_info:
                    await ctx.send(f"❌ Пользователь с ID {user_id} не найден в базе данных.")
                    return

                if not user_info['is_banned']:
                    await ctx.send(f"❌ Пользователь {user_id} не забанен.")
                    return

                db.unban_user(user_id)
                await ctx.send(f"✅ Пользователь {user_id} разбанен.")

            except Exception as e:
                logger.error(f"❌ Ошибка при разбане пользователя: {e}")
                await ctx.send("❌ Произошла ошибка при разбане пользователя")

        @self.bot.command(name="banguild")
        @is_admin()
        async def ban_guild_cmd(ctx, guild_name: str, *, reason: str = "Не указана"):
            """Банит гильдию"""
            try:
                if db.is_guild_banned(guild_name):
                    await ctx.send(f"❌ Гильдия '{guild_name}' уже забанена.")
                    return

                db.ban_guild(guild_name, reason, f"Discord: {ctx.author.id}")
                await ctx.send(f"✅ Гильдия '{guild_name}' забанена. Причина: {reason}")

            except Exception as e:
                logger.error(f"❌ Ошибка при бане гильдии: {e}")
                await ctx.send("❌ Произошла ошибка при бане гильдии")

        @self.bot.command(name="unbanguild")
        @is_admin()
        async def unban_guild_cmd(ctx, guild_name: str):
            """Разбанивает гильдию"""
            try:
                if not db.is_guild_banned(guild_name):
                    await ctx.send(f"❌ Гильдия '{guild_name}' не забанена.")
                    return

                db.unban_guild(guild_name)
                await ctx.send(f"✅ Гильдия '{guild_name}' разбанена.")

            except Exception as e:
                logger.error(f"❌ Ошибка при разбане гильдии: {e}")
                await ctx.send("❌ Произошла ошибка при разбане гильдии")

        @self.bot.command(name="userinfo")
        @is_admin()
        async def user_info_cmd(ctx, user_id: str = None):
            """Показывает информацию о пользователе"""
            try:
                if user_id is None:
                    user_id = str(ctx.author.id)

                user_info = db.get_user(user_id)
                if not user_info:
                    await ctx.send(f"❌ Пользователь с ID {user_id} не найден.")
                    return

                embed = discord.Embed(title=f"Информация о пользователе {user_id}", color=0x00ff00)
                embed.add_field(name="👤 Имя", value=user_info['username'] or "Не указано", inline=True)
                embed.add_field(name="🏷 Гильдия", value=user_info['guild'] or "Не выбрана", inline=True)
                embed.add_field(name="📅 Дата регистрации", value=user_info['created_at'], inline=True)
                embed.add_field(name="🚫 Забанен", value="✅ Да" if user_info['is_banned'] else "❌ Нет", inline=True)

                if user_info['is_banned']:
                    embed.add_field(name="📝 Причина бана", value=user_info['ban_reason'] or "Не указана", inline=True)
                    embed.add_field(name="⏰ Дата бана", value=user_info['banned_at'] or "Неизвестно", inline=True)
                    embed.add_field(name="🛡 Забанен кем", value=user_info['banned_by'] or "Неизвестно", inline=True)

                await ctx.send(embed=embed)

            except Exception as e:
                logger.error(f"❌ Ошибка при получении информации о пользователе: {e}")
                await ctx.send("❌ Произошла ошибка при получении информации о пользователе")

        @self.bot.command(name="userstats")
        @is_admin()
        async def user_stats_cmd(ctx):
            """Показывает статистику пользователей"""
            try:
                stats = db.get_user_stats()
                banned_guilds = db.get_banned_guilds()

                embed = discord.Embed(title="📊 Статистика пользователей", color=0x0099ff)

                embed.add_field(name="👥 Всего пользователей", value=stats['total_users'], inline=True)
                embed.add_field(name="✅ Активных", value=stats['active_users'], inline=True)
                embed.add_field(name="🚫 Забаненных", value=stats['banned_users'], inline=True)

                # Распределение по гильдиям
                guild_distribution = "\n".join(
                    [f"• {guild}: {count}" for guild, count in stats['guild_distribution'].items()])
                if guild_distribution:
                    embed.add_field(name="🏷 Распределение по гильдиям", value=guild_distribution, inline=False)

                # Забаненные гильдии
                if banned_guilds:
                    banned_guilds_text = "\n".join(
                        [f"• {guild['guild_name']}: {guild['ban_reason']}" for guild in banned_guilds])
                    embed.add_field(name="🚫 Забаненные гильдии", value=banned_guilds_text, inline=False)

                await ctx.send(embed=embed)

            except Exception as e:
                logger.error(f"❌ Ошибка при получении статистики: {e}")
                await ctx.send("❌ Произошла ошибка при получении статистики")

        @self.bot.command(name="userlist")
        @is_admin()
        async def user_list_cmd(ctx, page: int = 1):
            """Показывает список пользователей"""
            try:
                users = db.get_all_users()
                if not users:
                    await ctx.send("❌ В базе данных нет пользователей.")
                    return

                # Пагинация
                items_per_page = 10
                total_pages = (len(users) + items_per_page - 1) // items_per_page
                page = max(1, min(page, total_pages))

                start_idx = (page - 1) * items_per_page
                end_idx = start_idx + items_per_page
                page_users = users[start_idx:end_idx]

                embed = discord.Embed(title=f"📋 Список пользователей (стр. {page}/{total_pages})", color=0xff9900)

                for user in page_users:
                    status = "🚫" if user['is_banned'] else "✅"
                    guild = user['guild'] or "Не выбрана"
                    embed.add_field(
                        name=f"{status} {user['user_id']}",
                        value=f"👤 {user['username']}\n🏷 {guild}\n📅 {user['created_at']}",
                        inline=False
                    )

                await ctx.send(embed=embed)

            except Exception as e:
                logger.error(f"❌ Ошибка при получении списка пользователей: {e}")
                await ctx.send("❌ Произошла ошибка при получении списка пользователей")

        @self.bot.command(name="admincheck")
        @is_admin()
        async def admin_check_cmd(ctx):
            """Проверка прав администратора"""
            await ctx.send("✅ У вас есть права администратора!")

        # Добавляем команду справки
        @self.bot.command(name="commands")
        async def commands_help(ctx):
            """Показывает справку по командам"""
            help_text = f"""
**📋 Основные команды уведомлений:**

`!start_boss_alert <гильдия>` - активировать уведомления
• `!start_boss_alert All` - для всех гильдий
• `!start_boss_alert DarkSyndicate` - только для DarkSyndicate
• `!start_boss_alert Mercia` - только для Mercia
• `!start_boss_alert HryKings` - только для HryKings
• `!start_boss_alert RussianTeam` - только для RussianTeam

`!stop_boss_alert` - отключить уведомления
`!boss_status` - статус уведомлений
`!today_bosses [гильдия]` - боссы на сегодня

**🎲 Случайный выбор:**

`!random <данные>` - случайный выбор
• `!random 1-10` - случайное число от 1 до 10
• `!random 7` - случайное число от 1 до 7
• Многострочный ввод для списка:!random Ника

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

    async def get_today_bosses_for_guild(self, guild_name: str):
        """Получает боссов на сегодня для указанной гильдии"""
        try:
            tz = pytz.timezone(TIMEZONE)
            now = datetime.now(tz)
            schedule_key = now.strftime('%d.%m')

            # Получаем данные из Google Таблицы
            bosses_data = sheets_manager.get_today_bosses()

            result = []

            # Если выбрана гильдия "All", показываем всех боссов
            if guild_name == "All":
                # Группируем по гильдиям
                guilds_dict = {}
                for tier in ['tier1', 'tier2', 'tier3', 'tier4', 'tier5']:
                    tier_bosses = bosses_data.get(tier, [])
                    for guild, boss in tier_bosses:
                        if guild not in guilds_dict:
                            guilds_dict[guild] = []
                        guilds_dict[guild].append((tier, boss))

                # Формируем текст
                for guild, bosses in guilds_dict.items():
                    if bosses:  # Показываем только гильдии с боссами
                        result.append(f"**🏷 {guild}:**")
                        for tier, boss in bosses:
                            tier_emoji = self.get_tier_emoji(tier)
                            result.append(f"  {tier_emoji} {boss}")
                        result.append("")
            else:
                # Для конкретной гильдии
                result.append(f"**🏷 {guild_name}:**")
                bosses_found = False

                for tier in ['tier1', 'tier2', 'tier3', 'tier4', 'tier5']:
                    tier_bosses = bosses_data.get(tier, [])
                    guild_bosses = [boss for g, boss in tier_bosses if g == guild_name]

                    if guild_bosses:
                        bosses_found = True
                        tier_emoji = self.get_tier_emoji(tier)
                        result.append(f"\n{tier_emoji} **{self.get_tier_name(tier)}:**")
                        for boss in guild_bosses:
                            result.append(f"  • {boss}")

                if not bosses_found:
                    return f"Для гильдии **{guild_name}** на сегодня боссов не найдено."

            return "\n".join(result) if result else None

        except Exception as e:
            logger.error(f"❌ Ошибка при получении боссов для гильдии {guild_name}: {e}")
            return None

    def get_tier_emoji(self, tier: str):
        """Возвращает эмодзи для тира"""
        emoji_map = {
            'tier1': '🟢',
            'tier2': '🟡',
            'tier3': '🔴',
            'tier4': '🔵',
            'tier5': '🟣'
        }
        return emoji_map.get(tier, '⚪')

    def get_tier_name(self, tier: str):
        """Возвращает название тира"""
        name_map = {
            'tier1': 'Тир 1',
            'tier2': 'Тир 2',
            'tier3': 'Тир 3',
            'tier4': 'Тир 4',
            'tier5': 'Тир 5'
        }
        return name_map.get(tier, tier)

    async def send_boss_notification(self, time_key: str, target_tiers: list, is_free_farm: bool, schedule_key: str):
        """Отправляет уведомление о боссах во все активные Discord серверы"""
        try:
            # Получаем все активные серверы
            active_servers = db.get_all_active_discord_servers()

            if not active_servers:
                return

            # Получаем данные о боссах
            bosses_data = sheets_manager.get_today_bosses()

            for server in active_servers:
                guild_id = server['guild_id']
                channel_id = server['channel_id']
                selected_guild = server['selected_guild']

                try:
                    # Получаем канал
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue

                    channel = guild.get_channel(int(channel_id))
                    if not channel:
                        continue

                    # Формируем сообщение в зависимости от выбранной гильдии
                    message = ""

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
                        # Фильтруем боссов для выбранной гильдии
                        bosses_to_show = {}

                        if selected_guild == "All":
                            # Для режима All показываем всех боссов, сгруппированных по гильдиям
                            for tier in target_tiers:
                                if tier in bosses_data:
                                    all_bosses = bosses_data[tier]
                                    if all_bosses:
                                        bosses_to_show[tier] = all_bosses
                        else:
                            # Для конкретной гильдии
                            for tier in target_tiers:
                                if tier in bosses_data:
                                    guild_bosses = [boss for guild_name, boss in bosses_data[tier] if
                                                    guild_name == selected_guild]
                                    if guild_bosses:
                                        bosses_to_show[tier] = guild_bosses

                        if not bosses_to_show:
                            continue

                        # Формируем сообщение
                        message = f"@everyone\n"
                        message += f"⏰ **Через 10 минут ({time_key}) появятся боссы:**\n"
                        message += f"**Гильдия:** {selected_guild}\n"
                        message += f"**Слот:** {schedule_key}\n\n"

                        if selected_guild == "All":
                            # Для All группируем по гильдиям
                            guilds_dict = {}
                            for tier, bosses in bosses_to_show.items():
                                tier_emoji = self.get_tier_emoji(tier)
                                tier_name = self.get_tier_name(tier)

                                for guild_name, boss_name in bosses:
                                    if guild_name not in guilds_dict:
                                        guilds_dict[guild_name] = []
                                    guilds_dict[guild_name].append(f"{tier_emoji} {boss_name}")

                            for guild_name, boss_list in guilds_dict.items():
                                message += f"**🏷 {guild_name}:**\n"
                                for boss_item in boss_list:
                                    message += f"{boss_item}\n"
                                message += "\n"
                        else:
                            # Для конкретной гильдии
                            for tier, bosses in bosses_to_show.items():
                                tier_emoji = self.get_tier_emoji(tier)
                                tier_name = self.get_tier_name(tier)

                                message += f"{tier_emoji} **{tier_name}:**\n"
                                for boss in bosses:
                                    message += f"• {boss}\n"
                                message += "\n"

                        message += "💀 **Удачи в бою!**"

                    # Отправляем сообщение
                    await channel.send(message)
                    logger.info(f"✅ Уведомление отправлено в Discord сервер {guild.name}, канал {channel.name}")

                except Exception as e:
                    logger.error(f"❌ Ошибка отправки уведомления на сервер {guild_id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Общая ошибка в send_boss_notification: {e}")

    async def send_rift_notification(self):
        """Отправляет уведомление о разломах во все активные Discord серверы"""
        try:
            active_servers = db.get_all_active_discord_servers()

            if not active_servers:
                return

            message = (
                "🌀 **РАЗЛОМЫ СКОРО ПОЯВЯТСЯ!** 🌀\n\n"
                f"@everyone\n"
                "⏰ Через 10 минут откроются разломы\n"
                "⚔️ Готовьтесь к битве!\n\n"
                "💎 Не пропустите возможность получить ценные награды!"
            )

            for server in active_servers:
                guild_id = server['guild_id']
                channel_id = server['channel_id']

                try:
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue

                    channel = guild.get_channel(int(channel_id))
                    if not channel:
                        continue

                    await channel.send(message)
                    logger.info(f"✅ Уведомление о разломах отправлено в Discord сервер {guild.name}")

                except Exception as e:
                    logger.error(f"❌ Ошибка отправки уведомления о разломах на сервер {guild_id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Общая ошибка в send_rift_notification: {e}")

    async def send_tier4_notification(self):
        """Отправляет уведомление о боссах 4 тира во все активные Discord серверы"""
        try:
            # Получаем данные о боссах 4 тира
            bosses_data = sheets_manager.get_today_bosses()
            tier4_bosses = bosses_data.get('tier4', [])

            if not tier4_bosses:
                return

            active_servers = db.get_all_active_discord_servers()

            if not active_servers:
                return

            for server in active_servers:
                guild_id = server['guild_id']
                channel_id = server['channel_id']
                selected_guild = server['selected_guild']

                try:
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue

                    channel = guild.get_channel(int(channel_id))
                    if not channel:
                        continue

                    # Фильтруем боссов в зависимости от выбранной гильдии
                    bosses_to_show = []

                    if selected_guild == "All":
                        bosses_to_show = tier4_bosses
                    else:
                        bosses_to_show = [(g, b) for g, b in tier4_bosses if g == selected_guild]

                    if not bosses_to_show:
                        continue

                    # Формируем сообщение
                    boss_list = "\n".join([f"• {boss} (**гильдия {guild}**)" for guild, boss in bosses_to_show])

                    message = (
                        "🔔 **ВНИМАНИЕ АЛЬЯНС!** 🔔\n\n"
                        f"Обратите внимание! Сегодня есть боссы **Тира 4**:\n\n"
                        f"{boss_list}\n\n"
                        f"⚔️ **Не пропустите возможность помочь нашим гильдиям!** ⚔️"
                    )

                    await channel.send(message)
                    logger.info(f"✅ Уведомление о Tier 4 отправлено в Discord сервер {guild.name}")

                except Exception as e:
                    logger.error(f"❌ Ошибка отправки уведомления о Tier 4 на сервер {guild_id}: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Общая ошибка в send_tier4_notification: {e}")

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
            test_bosses = [("Mercia", "Двуликий Моргон"), ("DarkSyndicate", "Марионетка Нидрок"),
                           ("RussianTeam", "Древний дракон Истерия")]

            # Отправляем в активные серверы
            active_servers = db.get_all_active_discord_servers()
            for server in active_servers:
                guild_id = server['guild_id']
                channel_id = server['channel_id']

                try:
                    guild = self.bot.get_guild(int(guild_id))
                    if not guild:
                        continue

                    channel = guild.get_channel(int(channel_id))
                    if not channel:
                        continue

                    boss_list = "\n".join([f"• {boss} (**гильдия {guild}**)" for guild, boss in test_bosses])
                    message = (
                        "🔔 **ТЕСТ: ВНИМАНИЕ АЛЬЯНС!** 🔔\n\n"
                        f"Тестовое уведомление о боссах **Тира 4**:\n\n"
                        f"{boss_list}\n\n"
                        f"⚔️ **Тестовое уведомление!** ⚔️"
                    )

                    await channel.send(message)

                except Exception as e:
                    logger.error(f"❌ Ошибка отправки тестового уведомления о Tier 4: {e}")
                    continue

            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отправки тестового уведомления о Tier 4: {e}")
            return False

    @tasks.loop(minutes=1)
    async def check_bosses(self):
        """Проверяет время и отправляет уведомления во все активные серверы"""
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

            # Проверяем боссов 4 тира в 19:20
            if current_time == '19:20':
                await self.send_tier4_notification()

        except Exception as e:
            logger.error(f"❌ Ошибка в check_bosses: {e}")

    @check_bosses.before_loop
    async def before_check_bosses(self):
        await self.bot.wait_until_ready()

    def run(self):
        """Запускает Discord бота"""
        try:
            self.bot.run(DISCORD_BOT_TOKEN)
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Discord бота: {e}")


# Создаем глобальный экземпляр бота
discord_bot = DiscordBot()