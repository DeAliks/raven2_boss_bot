# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from datetime import datetime
import pytz
from config import TIMEZONE
from db import get_all_users
from google_sheets_manager import sheets_manager

# Настройки для групповых уведомлений
GROUP_CHAT_ID = "@dark_syndicated"  # Чат/канал для уведомлений
GROUP_TOPIC_ID = 7  # ID темы (если есть)
GROUP_GUILD = "DarkSyndicate"  # Гильдия для групповых уведомлений


def get_schedule_key_for_date(dt: datetime) -> str:
    return dt.strftime("%d.%m")


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
        '23:30': {'tiers': ['tier1', 'tier2', 'tier3', 'tier4', 'tier5'], 'free_farm': False}  # Все тиры
    }

    if time_key not in tiers_info:
        return

    target_tiers = tiers_info[time_key]['tiers']
    is_free_farm = tiers_info[time_key]['free_farm']

    # Отправляем уведомления в группу/канал
    if GROUP_CHAT_ID:
        await send_group_notification(bot, time_key, target_tiers, is_free_farm, schedule_key)

    # Отправляем уведомления пользователям в личку
    users = get_all_users()
    for user_id, guild in users:
        if is_free_farm:
            await send_free_farm_notification(bot, user_id, time_key, target_tiers)
        else:
            await send_guild_notification(bot, user_id, guild, time_key, target_tiers, schedule_key)


async def send_group_notification(bot: Bot, time_key: str, target_tiers: list, is_free_farm: bool, schedule_key: str):
    """Отправляет уведомление в группу/канал"""
    try:
        if is_free_farm:
            message = f"🎯 FREE FARM через 10 минут ({time_key})!\n\n"

            if time_key == '03:30':
                message += "🟢 <b>1 тир</b>\n\n"
                message += "⚔️ Можно бить ВСЕХ боссов 1 тира!\n"
                message += "Независимо от вашей гильдии!"
            elif time_key == '07:30':
                message += "🟢 <b>1 тир</b> + 🟡 <b>2 тир</b>\n\n"
                message += "⚔️ Можно бить ВСЕХ боссов 1 и 2 тира!\n"
                message += "Независимо от вашей гильдии!"

            message += "\n🎉 Удачи в охоте!"

        else:
            # Получаем данные из Google Таблицы
            bosses_data = sheets_manager.get_today_bosses()

            # Фильтруем только нужные тиры для гильдии группы
            bosses_to_show = {}
            for tier in target_tiers:
                if tier in bosses_data:
                    # Фильтруем боссов только для гильдии группы
                    guild_bosses = [boss for guild_name, boss in bosses_data[tier] if guild_name == GROUP_GUILD]
                    if guild_bosses:
                        bosses_to_show[tier] = guild_bosses

            if not bosses_to_show:
                return

            # Формируем сообщение с боссами гильдии
            message = f"⏰ Через 10 минут ({time_key}) появятся боссы:\n"
            message += f"Гильдия: <b>{GROUP_GUILD}</b>\n"
            message += f"Слот: <b>{schedule_key}</b>\n\n"

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

                message += f"{emoji} <b>{tier_name}</b>:\n"
                for boss in bosses:
                    message += f"• {boss}\n"
                message += "\n"

            message += "💀 Удачи в бою!"

        # Отправляем в группу/канал
        send_params = {
            'chat_id': GROUP_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }

        # Добавляем ID темы, если указан
        if GROUP_TOPIC_ID:
            send_params['message_thread_id'] = GROUP_TOPIC_ID

        await bot.send_message(**send_params)

    except Exception as e:
        print(f"Не удалось отправить сообщение в группу/канал: {e}")


async def send_free_farm_notification(bot: Bot, user_id: int, time_key: str, target_tiers: list):
    """Отправляет уведомление о FREE FARM пользователю"""
    message = f"🎯 FREE FARM через 10 минут ({time_key})!\n\n"

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


async def send_guild_notification(bot: Bot, user_id: int, guild: str, time_key: str, target_tiers: list,
                                  schedule_key: str):
    """Отправляет уведомление о боссах гильдии пользователю"""
    # Получаем данные из Google Таблицы
    bosses_data = sheets_manager.get_today_bosses()

    # Фильтруем только нужные тиры
    bosses_to_show = {}
    for tier in target_tiers:
        if tier in bosses_data:
            # Фильтруем боссов только для текущей гильдии
            guild_bosses = [boss for guild_name, boss in bosses_data[tier] if guild_name == guild]
            if guild_bosses:
                bosses_to_show[tier] = guild_bosses

    if not bosses_to_show:
        return

    # Формируем сообщение с боссами гильдии
    message = f"⏰ Через 10 минут ({time_key}) появятся боссы:\n"
    message += f"Гильдия: <b>{guild}</b>\n"
    message += f"Слот: <b>{schedule_key}</b>\n\n"

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

        message += f"{emoji} <b>{tier_name}</b>:\n"
        for boss in bosses:
            message += f"• {boss}\n"
        message += "\n"

    message += "💀 Удачи в бою!"

    try:
        await bot.send_message(user_id, message, parse_mode="HTML")
    except Exception as e:
        print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")


async def send_rift_notification(bot: Bot):
    """Отправляет уведомление о разломах за 10 минут до появления"""
    # Отправляем в группу/канал
    if GROUP_CHAT_ID:
        try:
            message = "🌀 <b>РАЗЛОМЫ СКОРО ПОЯВЯТСЯ!</b>\n\n"
            message += "⏰ Через 10 минут откроются разломы\n"
            message += "⚔️ Готовьтесь к битве!\n\n"
            message += "💎 Не пропустите возможность получить ценные награды!"

            send_params = {
                'chat_id': GROUP_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            }

            # Добавляем ID темы, если указан
            if GROUP_TOPIC_ID:
                send_params['message_thread_id'] = GROUP_TOPIC_ID

            await bot.send_message(**send_params)
        except Exception as e:
            print(f"Не удалось отправить сообщение о разломах в группу/канал: {e}")

    # Отправляем пользователям
    users = get_all_users()
    message = "🌀 <b>РАЗЛОМЫ СКОРО ПОЯВЯТСЯ!</b>\n\n"
    message += "⏰ Через 10 минут откроются разломы\n"
    message += "⚔️ Готовьтесь к битве!\n\n"
    message += "💎 Не пропустите возможность получить ценные награды!"

    for user_id, guild in users:
        try:
            await bot.send_message(user_id, message, parse_mode="HTML")
        except Exception as e:
            print(f"Не удалось отправить сообщение о разломах пользователю {user_id}: {e}")


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
            args=[bot, time_key],
            misfire_grace_time=300,
            coalesce=True
        )
        print(f"✅ Настроено уведомление для {time_key} (запуск в {time_str})")

    # Уведомления о разломах за 10 минут до появления
    rift_times = ['14:20', '22:20']

    for time_str in rift_times:
        hour, minute = map(int, time_str.split(':'))
        scheduler.add_job(
            send_rift_notification,
            "cron",
            hour=hour,
            minute=minute,
            args=[bot],
            misfire_grace_time=300,
            coalesce=True
        )
        print(f"✅ Настроено уведомление о разломах (запуск в {time_str})")

    scheduler.start()
    print("✅ Планировщик уведомлений запущен")

    # Выводим информацию о групповых уведомлениях
    if GROUP_CHAT_ID:
        print(f"✅ Групповые уведомления настроены для: {GROUP_CHAT_ID}")
        print(f"✅ Гильдия для групповых уведомлений: {GROUP_GUILD}")
        if GROUP_TOPIC_ID:
            print(f"✅ ID темы: {GROUP_TOPIC_ID}")
    else:
        print("ℹ️ Групповые уведомления не настроены")