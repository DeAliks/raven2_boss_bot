# main.py (updated with better date handling)
import asyncio
from datetime import datetime
import pytz
import logging
import threading
from discord_bot import discord_bot
from config import DISCORD_BOT_TOKEN

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from google_sheets_manager import sheets_manager

    GOOGLE_SHEETS_AVAILABLE = True
except Exception as e:
    logger.error(f"❌ Ошибка импорта Google Sheets manager: {e}")
    GOOGLE_SHEETS_AVAILABLE = False


    class DummySheetsManager:
        def get_today_bosses(self):
            return {'tier1': [], 'tier2': [], 'tier3': [], 'tier4': [], 'tier5': []}

        def clear_cache(self):
            pass

        @property
        def connected(self):
            return False


    sheets_manager = DummySheetsManager()

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from config import BOT_TOKEN, TIMEZONE
from db import (
    init_db,
    set_guild,
    get_guild,
    get_all_users,
)
from scheduler import setup_scheduler, send_notification, send_rift_notification

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# -------------------- Keyboards --------------------
def main_menu_keyboard():
    buttons = [
        [types.KeyboardButton(text="Моя гильдия"), types.KeyboardButton(text="Сменить гильдию")],
        [types.KeyboardButton(text="Сегодняшние боссы"), types.KeyboardButton(text="Обновить данные")],
        [types.KeyboardButton(text="Диагностика"), types.KeyboardButton(text="Скрыть клавиатуру")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def guild_selection_keyboard():
    buttons = [
        [types.KeyboardButton(text="Mercia"), types.KeyboardButton(text="DarkSyndicate")],
        [types.KeyboardButton(text="RussianTeam"), types.KeyboardButton(text="HryKings")],
        [types.KeyboardButton(text="Назад в меню")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# -------------------- Schedule helpers --------------------
def get_schedule_key_for_date(dt: datetime) -> str:
    return dt.strftime("%d.%m")


def normalize_guild_name(guild_name):
    """Нормализует названия гильдий для соответствия с таблицей"""
    guild_map = {
        'dark syndicate': 'DarkSyndicate',
        'darksyndicate': 'DarkSyndicate',
        'dark_syndicate': 'DarkSyndicate',
        'mercia': 'Mercia',
        'hrykings': 'HryKings',
        'hry kings': 'HryKings',
        'russianteam': 'RussianTeam',
        'russian team': 'RussianTeam',
        'russian': 'RussianTeam'
    }

    normalized = guild_name.strip()
    lower_name = normalized.lower()

    return guild_map.get(lower_name, normalized)


def get_bosses_from_sheets(guild: str, schedule_key: str):
    """Получает боссов для гильдии на указанную дату из Google Таблицы."""
    if not GOOGLE_SHEETS_AVAILABLE:
        logger.error("Google Sheets недоступен")
        return []

    today = datetime.now(pytz.timezone(TIMEZONE)).strftime('%d.%m')

    # Проверяем, что запрашиваемая дата совпадает с сегодняшней
    if schedule_key != today:
        logger.warning(f"⚠️ Запрошенная дата {schedule_key} не совпадает с сегодняшней {today}")
        return []

    normalized_guild = normalize_guild_name(guild)

    logger.info(f"🔍 Поиск боссов для гильдии '{guild}' (нормализовано: '{normalized_guild}') на дату '{schedule_key}'")

    # Получаем все данные на сегодня
    bosses_data = sheets_manager.get_today_bosses()
    result = []

    # Проверяем все тиры: 1, 2, 3, 4, 5
    for tier in ['tier1', 'tier2', 'tier3', 'tier4', 'tier5']:
        tier_bosses = bosses_data.get(tier, [])
        logger.info(f"🔍 Проверка {tier}: {len(tier_bosses)} боссов")

        for guild_name, boss_name in tier_bosses:
            if guild_name == normalized_guild:
                result.append((tier, boss_name))
                logger.info(f"✅ Найден босс для {normalized_guild}: {boss_name} ({tier})")

    logger.info(f"📊 Итого найдено {len(result)} боссов для гильдии {normalized_guild}")
    return result


def format_bosses_grouped_rows(rows):
    tiers_order = ["tier1", "tier2", "tier3", "tier4", "tier5"]
    grouped = {t: [] for t in tiers_order}
    for tier, name in rows:
        grouped.setdefault(tier, []).append(name)

    text = ""
    for t in tiers_order:
        if grouped.get(t):
            # Добавляем эмодзи для каждого тира
            if t == "tier1":
                emoji = "🟢"
                tier_name = "1 тир"
            elif t == "tier2":
                emoji = "🟡"
                tier_name = "2 тир"
            elif t == "tier3":
                emoji = "🔴"
                tier_name = "3 тир"
            elif t == "tier4":
                emoji = "🔵"
                tier_name = "4 тир"
            elif t == "tier5":
                emoji = "🟣"
                tier_name = "5 тир"
            else:
                emoji = "⚪"
                tier_name = t

            text += f"{emoji} <b>{tier_name}</b>:\n"
            for n in grouped[t]:
                text += f"• {n}\n"
            text += "\n"
    return text

async def send_text_chunks(message_obj, text: str, parse_mode: str = None):
    chunk_size = 3800
    for i in range(0, len(text), chunk_size):
        part = text[i:i + chunk_size]
        if parse_mode:
            await message_obj.answer(part, parse_mode=parse_mode)
        else:
            await message_obj.answer(part)


# -------------------- Handlers --------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    guild = get_guild(message.from_user.id)
    if guild:
        # Нормализуем название гильдии для отображения
        normalized_guild = normalize_guild_name(guild)
        status_msg = "✅ Google Sheets подключен" if GOOGLE_SHEETS_AVAILABLE else "⚠️ Google Sheets недоступен"
        text = (
            f"✅ Вы уже выбрали гильдию: <b>{normalized_guild}</b>\n"
            f"{status_msg}\n\n"
            "Выберите действие кнопкой ниже."
        )
        await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    else:
        status_msg = "✅ Google Sheets подключен" if GOOGLE_SHEETS_AVAILABLE else "⚠️ Google Sheets недоступен"
        await message.answer(f"Привет! {status_msg}\n\nВыберите вашу гильдию:", reply_markup=guild_selection_keyboard())


@dp.message(lambda msg: msg.text in ["Mercia", "DarkSyndicate", "HryKings", "RussianTeam"])
async def handle_choose_guild(message: types.Message):
    # Сохраняем выбранную гильдию как есть (уже нормализована в клавиатуре)
    set_guild(message.from_user.id, message.text)
    status_msg = "✅ Google Sheets подключен" if GOOGLE_SHEETS_AVAILABLE else "⚠️ Google Sheets недоступен"
    await message.answer(f"✅ Ваша гильдия установлена: <b>{message.text}</b>\n{status_msg}", parse_mode="HTML")
    await message.answer("Выберите действие:", reply_markup=main_menu_keyboard())


@dp.message(lambda msg: msg.text == "Сменить гильдию")
async def handle_change_guild(message: types.Message):
    await message.answer("Выберите новую гильдию:", reply_markup=guild_selection_keyboard())


@dp.message(lambda msg: msg.text == "Назад в меню")
async def handle_back_to_menu(message: types.Message):
    await message.answer("Вернулись в главное меню:", reply_markup=main_menu_keyboard())


@dp.message(lambda msg: msg.text == "Моя гильдия")
async def handle_my_guild(message: types.Message):
    guild = get_guild(message.from_user.id)
    if not guild:
        await message.answer("⚠️ Гильдия не выбрана. Пожалуйста, выберите гильдию:",
                             reply_markup=guild_selection_keyboard())
        return

    # Нормализуем название для отображения
    normalized_guild = normalize_guild_name(guild)
    status_msg = "✅ Google Sheets подключен" if GOOGLE_SHEETS_AVAILABLE else "⚠️ Google Sheets недоступen"
    await message.answer(f"🏷 Ваша гильдия: <b>{normalized_guild}</b>\n{status_msg}\n\nВыберите действие кнопкой.",
                         parse_mode="HTML",
                         reply_markup=main_menu_keyboard())


@dp.message(lambda msg: msg.text == "Скрыть клавиатуру")
async def handle_hide_kb(message: types.Message):
    await message.answer("Клавиатура скрыта. Чтобы открыть меню снова, отправьте /start.",
                         reply_markup=types.ReplyKeyboardRemove())


@dp.message(lambda msg: msg.text == "Сегодняшние боссы")
async def handle_today_bosses(message: types.Message):
    guild = get_guild(message.from_user.id)
    if not guild:
        await message.answer("⚠️ Сначала выберите гильдию:", reply_markup=guild_selection_keyboard())
        return

    if not GOOGLE_SHEETS_AVAILABLE:
        await message.answer("❌ Google Sheets недоступен. Данные о боссах не могут быть загружены.")
        return

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    schedule_key = get_schedule_key_for_date(now)

    rows = get_bosses_from_sheets(guild, schedule_key)
    if not rows:
        normalized_guild = normalize_guild_name(guild)
        await message.answer(
            f"На сегодня (слот {schedule_key}) для гильдии <b>{normalized_guild}</b> данных нет.\n\n"
            "Возможные причины:\n"
            "• Данные еще не добавлены в таблицу\n"
            "• Неправильное название гильдии в таблице\n"
            "• Проблемы с форматом даты\n\n"
            "Используйте кнопку 'Диагностика' для получения подробной информации.",
            parse_mode="HTML"
        )
        return

    normalized_guild = normalize_guild_name(guild)
    header = f"📅 Боссы для гильдии <b>{normalized_guild}</b> (слот {schedule_key}):\n\n"
    body = format_bosses_grouped_rows(rows)
    text = header + body
    await message.answer(text, parse_mode="HTML")


@dp.message(lambda msg: msg.text == "Обновить данные")
async def handle_refresh_data(message: types.Message):
    """Принудительно обновляет данные из Google Таблицы"""
    if not GOOGLE_SHEETS_AVAILABLE:
        await message.answer("❌ Google Sheets недоступен. Невозможно обновить данные.")
        return

    try:
        sheets_manager.clear_cache()
        # Тестируем подключение
        test_data = sheets_manager.get_today_bosses()
        boss_count = sum(len(test_data.get(tier, [])) for tier in ['tier1', 'tier2', 'tier3', 'tier4', 'tier5'])
        await message.answer(f"✅ Данные успешно обновлены! Загружено {boss_count} боссов.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при обновлении данных: {e}")


@dp.message(lambda msg: msg.text == "Диагностика")
async def handle_diagnostics(message: types.Message):
    """Показывает диагностическую информацию"""
    guild = get_guild(message.from_user.id)

    text = f"🔧 <b>Диагностическая информация</b>\n\n"
    text += f"• Google Sheets доступен: {'✅' if GOOGLE_SHEETS_AVAILABLE else '❌'}\n"
    text += f"• Подключение к таблице: {'✅' if sheets_manager.connected else '❌'}\n"

    if GOOGLE_SHEETS_AVAILABLE and sheets_manager.connected:
        try:
            text += f"• Название таблицы: {sheets_manager.spreadsheet.title}\n"
            text += f"• ID таблицы: {sheets_manager.spreadsheet.id}\n"
        except:
            text += "• Информация о таблице: недоступна\n"

    if guild:
        normalized_guild = normalize_guild_name(guild)
        text += f"• Ваша гильдия в базе: <b>{guild}</b>\n"
        text += f"• Нормализованное название: <b>{normalized_guild}</b>\n"

        # Получаем текущие данные
        today = datetime.now(pytz.timezone(TIMEZONE)).strftime('%d.%m')
        bosses_data = sheets_manager.get_today_bosses()

        text += f"• Текущая дата: {today}\n\n"
        text += f"<b>Загруженные данные:</b>\n"

        for tier in ['tier1', 'tier2', 'tier3', 'tier4', 'tier5']:
            tier_bosses = bosses_data.get(tier, [])
            text += f"• {tier}: {len(tier_bosses)} боссов\n"

        # Проверяем конкретно для гильдии пользователя
        user_bosses = []
        for tier in ['tier1', 'tier2', 'tier3', 'tier4', 'tier5']:
            for g, boss in bosses_data.get(tier, []):
                if g == normalized_guild:
                    user_bosses.append((tier, boss))

        if user_bosses:
            text += f"\n✅ <b>Найдены боссы для {normalized_guild}:</b>\n"
            for tier, boss in user_bosses:
                text += f"• {tier}: {boss}\n"
        else:
            text += f"\n❌ <b>Боссы для {normalized_guild} не найдены</b>\n"
            text += "Проверьте правильность написания гильдии в таблице."

    else:
        text += "• Гильдия не выбрана\n"

    await message.answer(text, parse_mode="HTML")


# -------------------- Test Notification --------------------
@dp.message(Command("test_notification"))
async def cmd_test_notification(message: types.Message):
    """Тестовая команда для проверки уведомлений"""
    guild = get_guild(message.from_user.id)
    if not guild:
        await message.answer("⚠️ Сначала выберите гильдию:", reply_markup=guild_selection_keyboard())
        return

    await message.answer("🔔 Тестовые уведомления:")

    test_times = ['03:30', '07:30', '11:30', '15:30', '19:30', '23:30']

    for time_key in test_times:
        await message.answer(f"--- Тест для {time_key} ---")
        await send_notification(bot, time_key)
        await asyncio.sleep(1)


# -------------------- Test Rift Notification --------------------
@dp.message(Command("test_rift"))
async def cmd_test_rift(message: types.Message):
    """Тестовая команда для проверки уведомлений о разломах"""
    await message.answer("🌀 Тестовое уведомление о разломах:")
    await send_rift_notification(bot)

@dp.message(Command("group_info"))
async def cmd_group_info(message: types.Message):
    """Показывает информацию о настройках групповых уведомлений"""
    from scheduler import GROUP_CHAT_ID, GROUP_TOPIC_ID, GROUP_GUILD

    text = "📢 <b>Настройки групповых уведомлений</b>\n\n"
    text += f"<b>Чат/канал:</b> {GROUP_CHAT_ID or 'Не настроен'}\n"
    text += f"<b>ID темы:</b> {GROUP_TOPIC_ID or 'Не настроено'}\n"
    text += f"<b>Гильдия:</b> {GROUP_GUILD or 'Не настроена'}\n\n"

    if GROUP_CHAT_ID:
        text += "✅ Групповые уведомления активны\n"
        text += f"📝 Бот будет отправлять уведомления для гильдии <b>{GROUP_GUILD}</b>"
    else:
        text += "❌ Групповые уведомления не настроены"

    await message.answer(text, parse_mode="HTML")


@dp.message(Command("test_group_notification"))
async def cmd_test_group_notification(message: types.Message):
    """Тестовая команда для проверки групповых уведомлений"""
    from scheduler import send_group_notification, send_rift_notification

    try:
        await message.answer("🔔 Тестируем групповые уведомления...")

        # Тест уведомления о боссах
        await send_group_notification(bot, "11:30", ["tier1", "tier2"], False, "03.11")
        await asyncio.sleep(1)

        # Тест уведомления о разломах
        await send_rift_notification(bot)

        await message.answer("✅ Тестовые уведомления отправлены в группу/канал")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("test_discord_bosses"))
async def cmd_test_discord_bosses(message: types.Message):
    """Тестовая команда для отправки уведомления о боссах в Discord"""
    try:
        await message.answer("🔄 Отправляю тестовое уведомление о боссах в Discord...")

        # Используем asyncio для запуска корутины в правильном event loop
        success = await discord_bot.send_test_boss_notification()

        if success:
            await message.answer("✅ Тестовое уведомление о боссах отправлено в Discord!")
        else:
            await message.answer("❌ Не удалось отправить тестовое уведомление в Discord")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("test_discord_rift"))
async def cmd_test_discord_rift(message: types.Message):
    """Тестовая команда для отправки уведомления о разломах в Discord"""
    try:
        await message.answer("🔄 Отправляю тестовое уведомление о разломах в Discord...")

        success = await discord_bot.send_test_rift_notification()

        if success:
            await message.answer("✅ Тестовое уведомление о разломах отправлено в Discord!")
        else:
            await message.answer("❌ Не удалось отправить тестовое уведомление в Discord")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("test_discord_tier4"))
async def cmd_test_discord_tier4(message: types.Message):
    """Тестовая команда для отправки уведомления о боссах 4 тира в Discord"""
    try:
        await message.answer("🔄 Отправляю тестовое уведомление о боссах 4 тира в Discord...")

        success = await discord_bot.send_test_tier4_notification()

        if success:
            await message.answer("✅ Тестовое уведомление о боссах 4 тира отправлено в Discord!")
        else:
            await message.answer("❌ Не удалось отправить тестовое уведомление в Discord")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("test_discord_all"))
async def cmd_test_discord_all(message: types.Message):
    """Тестовая команда для отправки всех уведомлений в Discord"""
    try:
        await message.answer("🔄 Отправляю все тестовые уведомления в Discord...")

        results = []

        # Тест уведомления о боссах
        await asyncio.sleep(1)
        boss_success = await discord_bot.send_test_boss_notification()
        results.append(f"Боссы: {'✅' if boss_success else '❌'}")

        # Тест уведомления о разломах
        await asyncio.sleep(1)
        rift_success = await discord_bot.send_test_rift_notification()
        results.append(f"Разломы: {'✅' if rift_success else '❌'}")

        # Тест уведомления о Tier 4
        await asyncio.sleep(1)
        tier4_success = await discord_bot.send_test_tier4_notification()
        results.append(f"Tier 4: {'✅' if tier4_success else '❌'}")

        report = "📊 **Отчет по тестированию Discord:**\n\n" + "\n".join(results)
        await message.answer(report)

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("discord_status"))
async def cmd_discord_status(message: types.Message):
    """Показывает статус Discord бота"""
    try:
        status_info = "🤖 **Статус Discord бота:**\n\n"

        if discord_bot.bot.is_ready():
            status_info += "✅ **Бот подключен и готов**\n"

            if discord_bot.channel:
                status_info += f"✅ **Канал найден:** {discord_bot.channel.name}\n"
            else:
                status_info += "❌ **Канал не найден**\n"

            status_info += f"👥 **Серверы:** {len(discord_bot.bot.guilds)}\n"

            # Информация о серверах
            for guild in discord_bot.bot.guilds:
                status_info += f"  • {guild.name} (участников: {guild.member_count})\n"

        else:
            status_info += "❌ **Бот не подключен**\n"

        await message.answer(status_info)

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# -------------------- Debug / Admin utilities --------------------
@dp.message(Command("debug_guild"))
async def cmd_debug_guild(message: types.Message):
    user_id = message.from_user.id
    guild = get_guild(user_id)
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    schedule_key = get_schedule_key_for_date(now)

    text = f"🛠 DEBUG\nUser id: {user_id}\nSaved guild: {guild}\nSlot (schedule_key): {schedule_key}\n"
    text += f"Google Sheets доступен: {GOOGLE_SHEETS_AVAILABLE}\n\n"

    if not guild:
        text += "Гильдия не сохранена.\n"
        await message.answer(text)
        return

    rows = get_bosses_from_sheets(guild, schedule_key)
    text += f"Rows from Google Sheets (tier, name): {rows}\n"

    await message.answer(text)


@dp.message(Command("everyone"))
async def cmd_everyone(message: types.Message):
    """Отправляет сообщение всем пользователям бота"""
    # Проверяем, что команда используется в личном чате или есть права
    if message.chat.type not in ['private', 'group', 'supergroup']:
        await message.answer("❌ Эта команда доступна только в личных чатах или группах")
        return

    # Получаем текст сообщения (всё после команды /everyone)
    command_text = message.text
    if not command_text or len(command_text.split()) < 2:
        await message.answer("❌ Использование: /everyone <текст сообщения>")
        return

    # Извлекаем текст объявления
    announcement_text = command_text.split(maxsplit=1)[1]

    # Получаем всех пользователей из базы данных
    users = get_all_users()

    if not users:
        await message.answer("❌ В базе данных нет пользователей")
        return

    # Отправляем сообщение всем пользователям
    success_count = 0
    fail_count = 0

    announcement_message = (
        f"📢 <b>ВАЖНОЕ ОБЪЯВЛЕНИЕ ОТ АЛЬЯНСА</b> 📢\n\n"
        f"{announcement_text}\n\n"
        f"<i>С уважением, команда альянса</i>"
    )

    # Проверяем, есть ли изображение в сообщении
    has_photo = message.photo is not None
    photo_file_id = None
    if has_photo:
        # Берем самое большое фото
        photo_file_id = message.photo[-1].file_id

    for user in users:
        user_id = user['user_id']  # Теперь user - это словарь
        try:
            if has_photo and photo_file_id:
                # Отправляем фото с текстом
                await bot.send_photo(
                    user_id,
                    photo=photo_file_id,
                    caption=announcement_message,
                    parse_mode="HTML"
                )
            else:
                # Отправляем только текст
                await bot.send_message(
                    user_id,
                    announcement_message,
                    parse_mode="HTML"
                )
            success_count += 1
            # Небольшая задержка чтобы не превысить лимиты Telegram
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            fail_count += 1

    # Отправляем отчет
    report_message = (
        f"📊 <b>Отчет по рассылке:</b>\n\n"
        f"✅ Успешно отправлено: {success_count} пользователям\n"
        f"❌ Не удалось отправить: {fail_count} пользователям\n"
        f"📝 Всего в базе: {len(users)} пользователей"
    )

    if has_photo:
        report_message += f"\n🖼 С фото: Да"
    else:
        report_message += f"\n🖼 С фото: Нет"

    await message.answer(report_message, parse_mode="HTML")

    # Также отправляем в группу/канал, если настроено
    from scheduler import GROUP_CHAT_ID, GROUP_TOPIC_ID
    if GROUP_CHAT_ID:
        try:
            group_announcement = (
                f"📢 <b>ОБЪЯВЛЕНИЕ ДЛЯ ВСЕХ УЧАСТНИКОВ АЛЬЯНСА</b> 📢\n\n"
                f"{announcement_text}\n\n"
                f"<i>Сообщение также отправлено в личные сообщения {success_count} участникам бота</i>"
            )

            if has_photo and photo_file_id:
                # Отправляем фото в группу
                send_params = {
                    'chat_id': GROUP_CHAT_ID,
                    'photo': photo_file_id,
                    'caption': group_announcement,
                    'parse_mode': 'HTML'
                }
                if GROUP_TOPIC_ID:
                    send_params['message_thread_id'] = GROUP_TOPIC_ID

                await bot.send_photo(**send_params)
            else:
                # Отправляем текст в группу
                send_params = {
                    'chat_id': GROUP_CHAT_ID,
                    'text': group_announcement,
                    'parse_mode': 'HTML'
                }
                if GROUP_TOPIC_ID:
                    send_params['message_thread_id'] = GROUP_TOPIC_ID

                await bot.send_message(**send_params)
        except Exception as e:
            logger.error(f"Не удалось отправить объявление в группу: {e}")

    await message.answer(report_message, parse_mode="HTML")

    # Также отправляем в группу/канал, если настроено
    from scheduler import GROUP_CHAT_ID, GROUP_TOPIC_ID
    if GROUP_CHAT_ID:
        try:
            group_announcement = (
                f"📢 <b>ОБЪЯВЛЕНИЕ ДЛЯ ВСЕХ УЧАСТНИКОВ АЛЬЯНСА</b> 📢\n\n"
                f"{announcement_text}\n\n"
                f"<i>Сообщение также отправлено в личные сообщения {success_count} участникам бota</i>"
            )

            send_params = {
                'chat_id': GROUP_CHAT_ID,
                'text': group_announcement,
                'parse_mode': 'HTML'
            }

            if GROUP_TOPIC_ID:
                send_params['message_thread_id'] = GROUP_TOPIC_ID

            await bot.send_message(**send_params)
        except Exception as e:
            logger.error(f"Не удалось отправить объявление в группу: {e}")


@dp.message(Command("force_tier4_check"))
async def cmd_force_tier4_check(message: types.Message):
    """Принудительно проверяет и отправляет уведомления о боссах 4 тира"""
    from scheduler import check_and_send_tier4_alliance_notification

    try:
        await message.answer("🔍 Принудительно проверяю боссов 4 тира...")

        from datetime import datetime
        import pytz
        today = datetime.now(pytz.timezone(TIMEZONE)).strftime('%d.%m')

        await check_and_send_tier4_alliance_notification(bot, today)

        await message.answer("✅ Проверка завершена. Уведомления отправлены, если найдены боссы 4 тира.")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("reset_tier4_notifications"))
async def cmd_reset_tier4_notifications(message: types.Message):
    """Сбрасывает флаг отправки уведомлений о Tier 4 (для тестирования)"""
    from scheduler import tier4_notification_sent_today

    global tier4_notification_sent_today
    tier4_notification_sent_today = False

    await message.answer("✅ Флаг уведомлений о Tier 4 сброшен. Следующее уведомление отправится снова.")


@dp.message(Command("discord_servers"))
async def cmd_discord_servers(message: types.Message):
    """Показывает список всех Discord серверов с уведомлениями"""
    try:
        active_servers = db.get_all_active_discord_servers()

        if not active_servers:
            await message.answer("❌ Нет активных Discord серверов с уведомлениями.")
            return

        text = "📊 **Активные Discord серверы:**\n\n"

        for server in active_servers:
            text += f"**Сервер ID:** {server['guild_id']}\n"
            text += f"**Канал ID:** {server['channel_id']}\n"
            text += f"**Гильдия:** {server['selected_guild']}\n"
            text += "─" * 30 + "\n"

        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("discord_test_all"))
async def cmd_discord_test_all(message: types.Message):
    """Тестовая команда для отправки всех уведомлений во все Discord серверы"""
    try:
        await message.answer("🔄 Отправляю тестовые уведомления во все Discord серверы...")

        # Тест уведомления о боссах
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        schedule_key = now.strftime('%d.%m')

        await discord_bot.send_boss_notification("15:30", ['tier1', 'tier2'], False, schedule_key)

        # Тест уведомления о разломах
        await asyncio.sleep(1)
        await discord_bot.send_rift_notification()

        # Тест уведомления о Tier 4
        await asyncio.sleep(1)
        await discord_bot.send_tier4_notification()

        await message.answer("✅ Тестовые уведомления отправлены во все Discord серверы!")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@dp.message(Command("discord_reset"))
async def cmd_discord_reset(message: types.Message):
    """Сбрасывает все настройки Discord серверов"""
    try:
        # Это административная команда, можно добавить проверку прав
        await message.answer("🔄 Сбрасываю настройки Discord серверов...")

        # Здесь можно добавить логику сброса, например:
        # db.reset_all_discord_settings()

        await message.answer("✅ Настройки Discord сброшены (нужна реализация в db.py)")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# -------------------- Запуск --------------------
async def main():
    init_db()

    print("✅ База данных инициализирована")

    # Запускаем Discord бота в отдельном потоке, чтобы не блокировать asyncio
    def run_discord_bot():
        """Запускает Discord бота в отдельном потоке"""
        try:
            discord_bot.run()  # Просто вызываем метод run нашего экземпляра
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Discord бота: {e}")

    # Запускаем Discord бота в отдельном потоке
    discord_thread = threading.Thread(target=run_discord_bot, daemon=True)
    discord_thread.start()
    print("✅ Discord бот запущен в отдельном потоке")

    # Проверяем подключение к Google Таблице
    if GOOGLE_SHEETS_AVAILABLE and sheets_manager.connected:
        try:
            test_data = sheets_manager.get_today_bosses()
            boss_count = sum(len(test_data.get(tier, [])) for tier in ['tier1', 'tier2', 'tier3', 'tier4', 'tier5'])
            print(f"✅ Подключение к Google Таблице успешно. Получено {boss_count} боссов")
        except Exception as e:
            print(f"❌ Ошибка при тестировании Google Таблицы: {e}")
    else:
        print("❌ Google Sheets недоступен. Бот будет работать с ограниченной функциональностью.")

    setup_scheduler(bot)

    print("✅ Бот запущен и ожидает события...")
    print("\n📋 Доступные команды для Discord:")
    print("  !start_boss_alert <гильдия> - активировать уведомления")
    print("  !stop_boss_alert - отключить уведомления")
    print("  !boss_status - статус уведомлений")
    print("  !today_bosses [гильдия] - боссы на сегодня")
    print("  !random - случайный выбор из списка или диапазона чисел")
    print("  !commands - справка по командам")
    print("  !admincheck - проверка прав администратора")
    print("  !userinfo - информация о пользователе")
    print("  !userstats - статистика пользователей")
    print("  !userlist - список пользователей")
    print("  !ban - забанить пользователя")
    print("  !unban - разбанить пользователя")
    print("  !banguild - забанить гильдию")
    print("  !unbanguild - разбанить гильдию")

    print("\n📋 Доступные команды для Telegram:")
    print("  /start - начать работу")
    print("  /everyone - рассылка всем пользователям")
    print("  /test_discord_bosses - тест уведомления Discord о боссах")
    print("  /test_discord_rift - тест уведомления Discord о разломах")
    print("  /test_discord_tier4 - тест уведомления Discord о Tier 4")
    print("  /test_discord_all - тест всех уведомлений Discord")
    print("  /discord_status - статус Discord бота")
    print("  /discord_servers - список активных Discord серверов")
    print("  /discord_test_all - тест уведомлений на всех серверах")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())