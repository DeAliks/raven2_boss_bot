# main.py (updated with better date handling)
import asyncio
from datetime import datetime
import pytz
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from google_sheets_manager import sheets_manager

    GOOGLE_SHEETS_AVAILABLE = True
except Exception as e:
    logger.error(f"❌ Ошибка импорта Google Sheets manager: {e}")
    GOOGLE_SHEETS_AVAILABLE = False


    # Создаем заглушку
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
        [types.KeyboardButton(text="Mercia"), types.KeyboardButton(text="DarkSyndicate"), types.KeyboardButton(text="HryKings")],
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
        'xray': 'XRAY'
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
    normalized_guild = normalize_guild_name(guild)

    logger.info(
        f"🔍 Поиск боссов для гильдии '{guild}' (нормализовано: '{normalized_guild}') на дату '{schedule_key}' (сегодня: '{today}')")

    if schedule_key != today:
        logger.warning(f"Запрошенная дата {schedule_key} не совпадает с сегодняшней {today}")
        return []

    bosses_data = sheets_manager.get_today_bosses()
    result = []

    # Проверяем все тиры: 1, 2, 3, 4, 5
    for tier in ['tier1', 'tier2', 'tier3', 'tier4', 'tier5']:
        tier_bosses = bosses_data.get(tier, [])
        logger.info(f"🔍 Проверка {tier}: {len(tier_bosses)} боссов")

        for guild_name, boss_name in tier_bosses:
            logger.info(f"🔍 Сравниваем: '{guild_name}' с '{normalized_guild}'")
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


@dp.message(lambda msg: msg.text in ["Mercia", "DarkSyndicate", "HryKings", "XRAY"])
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


# -------------------- Запуск --------------------
async def main():
    init_db()

    print("✅ База данных инициализирована")

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
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())