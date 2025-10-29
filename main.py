# main.py (updated with rift notifications)
import asyncio
from datetime import datetime
import pytz

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from config import BOT_TOKEN, TIMEZONE
from bosses_data import BOSSES_SCHEDULE
from db import (
    init_db,
    set_guild,
    get_guild,
    sync_bosses_from_schedule,
    get_bosses_for_guild_and_slot,
    get_all_bosses_for_guild,
    get_all_users,
)
from scheduler import setup_scheduler, send_notification, send_rift_notification

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# -------------------- Keyboards --------------------
def main_menu_keyboard():
    buttons = [
        [types.KeyboardButton(text="Моя гильдия"), types.KeyboardButton(text="Сменить гильдию")],
        [types.KeyboardButton(text="Сегодняшние боссы"), types.KeyboardButton(text="Все боссы гильдии")],
        [types.KeyboardButton(text="Скрыть клавиатуру")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def guild_selection_keyboard():
    buttons = [
        [types.KeyboardButton(text="Mercia"), types.KeyboardButton(text="Dark Syndicate")],
        [types.KeyboardButton(text="HryKings"), types.KeyboardButton(text="XRAY")],
        [types.KeyboardButton(text="Назад в меню")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# -------------------- Schedule helpers --------------------
def get_schedule_key_for_date(dt: datetime) -> str:
    cycle_keys = list(BOSSES_SCHEDULE.keys())
    if not cycle_keys:
        return dt.strftime("%d.%m")

    base_key = cycle_keys[0]
    try:
        base_day, base_month = map(int, base_key.split("."))
    except Exception:
        return dt.strftime("%d.%m")

    year = dt.year
    try:
        base_dt = datetime(year, base_month, base_day)
    except ValueError:
        return dt.strftime("%d.%m")

    if base_dt.date() > dt.date():
        try:
            base_dt = datetime(year - 1, base_month, base_day)
        except ValueError:
            base_dt = datetime(year, base_month, base_day)

    days_diff = (dt.date() - base_dt.date()).days
    if days_diff < 0:
        days_diff = abs(days_diff)

    index = days_diff % len(cycle_keys)
    return cycle_keys[index]


def format_bosses_grouped_rows(rows):
    tiers_order = ["tier1", "tier2", "tier3"]
    grouped = {t: [] for t in tiers_order}
    for tier, name in rows:
        grouped.setdefault(tier, []).append(name)

    text = ""
    for t in tiers_order:
        if grouped.get(t):
            emoji = "🟢" if t == "tier1" else "🟡" if t == "tier2" else "🔴"
            tier_name = "1 тир" if t == "tier1" else "2 тир" if t == "tier2" else "3 тир"
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
        text = (
            f"✅ Вы уже выбрали гильдию: <b>{guild}</b>\n\n"
            "Выберите действие кнопкой ниже."
        )
        await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    else:
        await message.answer("Привет! Выберите вашу гильдию:", reply_markup=guild_selection_keyboard())


@dp.message(lambda msg: msg.text in ["Mercia", "Dark Syndicate", "HryKings", "XRAY"])
async def handle_choose_guild(message: types.Message):
    set_guild(message.from_user.id, message.text)
    await message.answer(f"✅ Ваша гильдия установлена: <b>{message.text}</b>", parse_mode="HTML")
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
    await message.answer(f"🏷 Ваша гильдия: <b>{guild}</b>\n\nВыберите действие кнопкой.", parse_mode="HTML",
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

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    schedule_key = get_schedule_key_for_date(now)

    rows = get_bosses_for_guild_and_slot(guild, schedule_key)
    if not rows:
        await message.answer(f"На сегодня (слот {schedule_key}) для гильдии <b>{guild}</b> данных нет.",
                             parse_mode="HTML")
        return

    header = f"📅 Боссы для гильдии <b>{guild}</b> (слот {schedule_key}):\n\n"
    body = format_bosses_grouped_rows(rows)
    text = header + body
    await message.answer(text, parse_mode="HTML")


@dp.message(lambda msg: msg.text == "Все боссы гильдии")
async def handle_all_bosses(message: types.Message):
    guild = get_guild(message.from_user.id)
    if not guild:
        await message.answer("⚠️ Сначала выберите гильдию:", reply_markup=guild_selection_keyboard())
        return

    rows = get_all_bosses_for_guild(guild)
    if not rows:
        await message.answer(f"В расписании нет записей для гильдии <b>{guild}</b>.", parse_mode="HTML")
        return

    text = f"📦 Все боссы для гильдии <b>{guild}</b> (по порядку первого появления):\n\n"
    for name, _pos in rows:
        text += f"• {name}\n"

    if len(text) <= 4000:
        await message.answer(text, parse_mode="HTML")
    else:
        await send_text_chunks(message, text, parse_mode="HTML")


# -------------------- Test Notification --------------------
@dp.message(Command("test_notification"))
async def cmd_test_notification(message: types.Message):
    """Тестовая команда для проверки уведомлений"""
    guild = get_guild(message.from_user.id)
    if not guild:
        await message.answer("⚠️ Сначала выберите гильдию:", reply_markup=guild_selection_keyboard())
        return

    await message.answer("🔔 Тестовые уведомления:")

    # Тестируем разные типы уведомлений
    test_times = ['03:30', '07:30', '11:30', '15:30', '19:30', '23:30']

    for time_key in test_times:
        await message.answer(f"--- Тест для {time_key} ---")
        await send_notification(bot, time_key)
        await asyncio.sleep(1)  # Небольшая задержка между сообщениями


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

    text = f"🛠 DEBUG\nUser id: {user_id}\nSaved guild: {guild}\nSlot (schedule_key): {schedule_key}\n\n"

    if not guild:
        text += "Гильдия не сохранена.\n"
        await message.answer(text)
        return

    rows = get_bosses_for_guild_and_slot(guild, schedule_key)
    text += f"Rows from DB (tier, name): {rows}\n\n"
    all_rows = get_all_bosses_for_guild(guild)
    text += f"All bosses for guild (name, first_pos): {all_rows}\n"
    await message.answer(text)


@dp.message(Command("rebuild_bosses"))
async def cmd_rebuild_bosses(message: types.Message):
    try:
        sync_bosses_from_schedule(BOSSES_SCHEDULE)
        await message.answer("✅ Rebuild done: bosses_records перезаписаны из BOSSES_SCHEDULE.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при rebuild: {e}")


# Алиасы для совместимости
@dp.message(Command("today"))
async def cmd_today_alias(message: types.Message):
    await handle_today_bosses(message)


@dp.message(Command("my_bosses"))
async def cmd_my_bosses_alias(message: types.Message):
    await handle_all_bosses(message)


# -------------------- Запуск --------------------
async def main():
    init_db()

    # синхронизируем при старте
    try:
        sync_bosses_from_schedule(BOSSES_SCHEDULE)
        print("✅ Синхронизация расписания выполнена.")
    except Exception as e:
        print("⚠️ Ошибка при синхронизации расписания:", e)

    setup_scheduler(bot)

    print("✅ Бот запущен и ожидает события...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())