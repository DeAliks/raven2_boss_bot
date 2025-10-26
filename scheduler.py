from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from datetime import datetime
import pytz
from config import TIMEZONE
from db import get_all_users, get_bosses_for_guild_and_slot
from bosses_data import BOSSES_SCHEDULE


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


async def send_notification(bot: Bot, time_key: str):
    """
    Отправляет уведомления за 10 минут до появления боссов
    time_key: '03:30', '07:30', '11:30', '15:30', '19:30', '23:30'
    """
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    schedule_key = get_schedule_key_for_date(now)

    # Определяем какие тиры появляются в это время
    tiers_info = {
        '03:30': {'tiers': ['tier1'], 'free_farm': True},  # FREE FARM
        '07:30': {'tiers': ['tier1', 'tier2'], 'free_farm': True},  # FREE FARM
        '11:30': {'tiers': ['tier1'], 'free_farm': False},
        '15:30': {'tiers': ['tier1', 'tier2'], 'free_farm': False},
        '19:30': {'tiers': ['tier1'], 'free_farm': False},
        '23:30': {'tiers': ['tier1', 'tier2', 'tier3'], 'free_farm': False}  # НЕ free farm
    }

    if time_key not in tiers_info:
        return

    target_tiers = tiers_info[time_key]['tiers']
    is_free_farm = tiers_info[time_key]['free_farm']

    users = get_all_users()
    for user_id, guild in users:
        if is_free_farm:
            # Для FREE FARM отправляем общее сообщение без привязки к гильдии
            message = f"🎯 FREE FARM через 10 минут ({time_key})!\n\n"

            # Определяем какие тиры доступны в этот FREE FARM
            if time_key == '03:30':
                message += "🟢 <b>1 тир</b>\n\n"
                message += "⚔️ Можно бить ВСЕХ боссов 1 тира!\n"
                message += "Независимо от вашей гильдии!"
            elif time_key == '07:30':
                message += "🟢 <b>1 тир</b> + 🟡 <b>2 тир</b>\n\n"
                message += "⚔️ Можно бить ВСЕХ боссов 1 и 2 тира!\n"
                message += "Независимо от вашей гильдии!"

            message += "\n🎉 Удачи в охоте!"

            try:
                await bot.send_message(user_id, message, parse_mode="HTML")
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

        else:
            # Для обычного времени показываем боссов гильдии
            if guild not in BOSSES_SCHEDULE.get(schedule_key, {}):
                continue

            # Получаем всех боссов гильдии на этот день
            all_bosses = BOSSES_SCHEDULE[schedule_key][guild]

            # Фильтруем только нужные тиры
            bosses_to_show = {}
            for tier in target_tiers:
                if tier in all_bosses:
                    bosses_to_show[tier] = all_bosses[tier]

            if not bosses_to_show:
                continue

            # Формируем сообщение с боссами гильдии
            message = f"⏰ Через 10 минут ({time_key}) появятся боссы:\n"
            message += f"Гильдия: <b>{guild}</b>\n\n"

            # Добавляем боссов по тирам
            for tier, bosses in bosses_to_show.items():
                emoji = "🟢" if tier == "tier1" else "🟡" if tier == "tier2" else "🔴"
                tier_name = "1 тир" if tier == "tier1" else "2 тир" if tier == "tier2" else "3 тир"
                message += f"{emoji} <b>{tier_name}</b>:\n"
                for boss in bosses:
                    message += f"• {boss}\n"
                message += "\n"

            message += "💀 Удачи в бою!"

            try:
                await bot.send_message(user_id, message, parse_mode="HTML")
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")


def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Уведомления за 10 минут до появления боссов
    notification_times = ['03:20', '07:20', '11:20', '15:20', '19:20', '23:20']

    for time_str in notification_times:
        hour, minute = map(int, time_str.split(':'))
        time_key = f"{hour:02d}:{minute + 10:02d}"  # Время появления боссов

        scheduler.add_job(
            send_notification,
            "cron",
            hour=hour,
            minute=minute,
            args=[bot, time_key]
        )
        print(f"✅ Настроено уведомление для {time_key} (запуск в {time_str})")

    scheduler.start()
    print("✅ Планировщик уведомлений запущен")