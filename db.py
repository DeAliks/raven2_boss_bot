import sqlite3
from datetime import datetime
import pytz
import json
from typing import List, Dict, Optional
import logging



logger = logging.getLogger(__name__)


# Подключение к базе данных
def get_connection():
    """Создает подключение к базе данных"""
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
    return conn


def init_db():
    """Инициализирует базу данных и создает таблицы"""
    conn = get_connection()
    cursor = conn.cursor()

    # Таблица пользователей Telegram
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            guild TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned INTEGER DEFAULT 0,
            ban_reason TEXT,
            banned_at TIMESTAMP,
            banned_by TEXT
        )
    ''')

    # Таблица Discord серверов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS discord_servers (
            guild_id TEXT PRIMARY KEY,
            channel_id TEXT,
            selected_guild TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица Discord пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS discord_users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            guild TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned INTEGER DEFAULT 0,
            ban_reason TEXT,
            banned_at TIMESTAMP,
            banned_by TEXT
        )
    ''')

    # Таблица забаненных гильдий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banned_guilds (
            guild_name TEXT PRIMARY KEY,
            ban_reason TEXT,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            banned_by TEXT
        )
    ''')

    # Таблица спавнов боссов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boss_spawns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boss_name TEXT NOT NULL,
            spawn_time TEXT NOT NULL,
            guild TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            notified INTEGER DEFAULT 0,
            notification_time TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")


def set_guild(user_id: int, guild: str):
    """Устанавливает гильдию для пользователя"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, guild, created_at)
        VALUES (?, ?, datetime('now'))
    ''', (user_id, guild))

    conn.commit()
    conn.close()


def get_guild(user_id: int) -> Optional[str]:
    """Получает гильдию пользователя"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT guild FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()

    return result['guild'] if result else None


def get_all_users() -> List[Dict]:
    """Получает всех пользователей"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_id, username, guild, created_at, is_banned, ban_reason 
        FROM users 
        ORDER BY created_at DESC
    ''')

    users = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return users


# Discord функции
def set_discord_guild(guild_id: str, channel_id: str, selected_guild: str):
    """Сохраняет настройки Discord сервера"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO discord_servers 
        (guild_id, channel_id, selected_guild, updated_at, is_active)
        VALUES (?, ?, ?, datetime('now'), 1)
    ''', (guild_id, channel_id, selected_guild))

    conn.commit()
    conn.close()


def get_discord_guild(guild_id: str) -> Optional[Dict]:
    """Получает настройки Discord сервера"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT guild_id, channel_id, selected_guild, is_active
        FROM discord_servers 
        WHERE guild_id = ? AND is_active = 1
    ''', (guild_id,))

    result = cursor.fetchone()
    conn.close()

    return dict(result) if result else None


def get_all_active_discord_servers() -> List[Dict]:
    """Получает все активные Discord серверы"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT guild_id, channel_id, selected_guild
        FROM discord_servers 
        WHERE is_active = 1
    ''')

    servers = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return servers


def deactivate_discord_server(guild_id: str):
    """Деактивирует Discord сервер"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE discord_servers 
        SET is_active = 0, updated_at = datetime('now')
        WHERE guild_id = ?
    ''', (guild_id,))

    conn.commit()
    conn.close()


# Функции для управления пользователями
def add_or_update_user(user_id: str, username: str):
    """Добавляет или обновляет пользователя Discord"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO discord_users (user_id, username, created_at)
        VALUES (?, ?, datetime('now'))
    ''', (user_id, username))

    conn.commit()
    conn.close()


def get_user(user_id: str) -> Optional[Dict]:
    """Получает информацию о пользователе Discord"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM discord_users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()

    return dict(result) if result else None


def ban_user(user_id: str, reason: str, banned_by: str):
    """Банит пользователя"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE discord_users 
        SET is_banned = 1, ban_reason = ?, banned_at = datetime('now'), banned_by = ?
        WHERE user_id = ?
    ''', (reason, banned_by, user_id))

    conn.commit()
    conn.close()


def unban_user(user_id: str):
    """Разбанивает пользователя"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE discord_users 
        SET is_banned = 0, ban_reason = NULL, banned_at = NULL, banned_by = NULL
        WHERE user_id = ?
    ''', (user_id,))

    conn.commit()
    conn.close()


def ban_guild(guild_name: str, reason: str, banned_by: str):
    """Банит гильдию"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO banned_guilds (guild_name, ban_reason, banned_by, banned_at)
        VALUES (?, ?, ?, datetime('now'))
    ''', (guild_name, reason, banned_by))

    conn.commit()
    conn.close()


def unban_guild(guild_name: str):
    """Разбанивает гильдию"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM banned_guilds WHERE guild_name = ?', (guild_name,))
    conn.commit()
    conn.close()


def is_guild_banned(guild_name: str) -> bool:
    """Проверяет, забанена ли гильдия"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT 1 FROM banned_guilds WHERE guild_name = ?', (guild_name,))
    result = cursor.fetchone()
    conn.close()

    return bool(result)


def get_banned_guilds() -> List[Dict]:
    """Получает список забаненных гильдий"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM banned_guilds ORDER BY banned_at DESC')
    guilds = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return guilds


def get_user_stats() -> Dict:
    """Получает статистику пользователей"""
    conn = get_connection()
    cursor = conn.cursor()

    # Общая статистика
    cursor.execute('SELECT COUNT(*) as total FROM users')
    total_users = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as active FROM users WHERE is_banned = 0')
    active_users = cursor.fetchone()['active']

    cursor.execute('SELECT COUNT(*) as banned FROM users WHERE is_banned = 1')
    banned_users = cursor.fetchone()['banned']

    # Распределение по гильдиям
    cursor.execute('''
        SELECT guild, COUNT(*) as count 
        FROM users 
        WHERE guild IS NOT NULL 
        GROUP BY guild
    ''')

    guild_distribution = {}
    for row in cursor.fetchall():
        guild_distribution[row['guild']] = row['count']

    conn.close()

    return {
        'total_users': total_users,
        'active_users': active_users,
        'banned_users': banned_users,
        'guild_distribution': guild_distribution
    }


def get_all_discord_users() -> List[Dict]:
    """Получает всех пользователей Discord"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM discord_users ORDER BY created_at DESC')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return users


def get_all_active_discord_users() -> List[Dict]:
    """Получает всех активных пользователей Discord"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM discord_users WHERE is_banned = 0 ORDER BY created_at DESC')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return users


# Функции для спавнов боссов
def add_spawn_notification(boss_name: str, spawn_time: datetime, guild: str,
                           channel_id: str, created_by: str) -> int:
    """Добавляет запись о спавне босса в базу данных"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        created_at = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M:%S')
        spawn_time_str = spawn_time.strftime('%Y-%m-%d %H:%M:%S')
        notification_time = (spawn_time - timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')

        logger.info(
            f"💾 Сохранение в базу: {boss_name}, время спавна: {spawn_time_str}, уведомление: {notification_time}")

        cursor.execute('''
            INSERT INTO boss_spawns 
            (boss_name, spawn_time, guild, channel_id, created_by, created_at, notification_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (boss_name, spawn_time_str, guild, channel_id, created_by, created_at, notification_time))

        spawn_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"✅ Спавн сохранен в базу с ID: {spawn_id}")
        return spawn_id

    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении спавна в базу: {e}")
        return 0


def get_active_spawns() -> List[Dict]:
    """Получает активные спавны боссов"""
    conn = get_connection()
    cursor = conn.cursor()

    current_time = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        SELECT * FROM boss_spawns 
        WHERE status = 'active' 
        AND spawn_time > ?
        ORDER BY spawn_time
    ''', (current_time,))

    spawns = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return spawns


def get_active_spawns_by_channel(channel_id: str) -> List[Dict]:
    """Получает активные спавны боссов для конкретного канала"""
    conn = get_connection()
    cursor = conn.cursor()

    current_time = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        SELECT * FROM boss_spawns 
        WHERE status = 'active' 
        AND spawn_time > ?
        AND channel_id = ?
        ORDER BY spawn_time
    ''', (current_time, channel_id))

    spawns = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return spawns


def update_spawn_status(spawn_id: int, status: str):
    """Обновляет статус спавна"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE boss_spawns 
        SET status = ? 
        WHERE id = ?
    ''', (status, spawn_id))

    conn.commit()
    conn.close()


def mark_spawn_notified(spawn_id: int):
    """Отмечает спавн как уведомленный"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE boss_spawns 
        SET notified = 1 
        WHERE id = ?
    ''', (spawn_id,))

    conn.commit()
    conn.close()


def get_spawns_for_notification() -> List[Dict]:
    """Получает спавны, для которых нужно отправить уведомление"""
    conn = get_connection()
    cursor = conn.cursor()

    current_time = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%Y-%m-%d %H:%M:%S')

    # ДЛЯ ОТЛАДКИ: получим все активные спавны
    cursor.execute('''
        SELECT * FROM boss_spawns 
        WHERE status = 'active' 
        AND spawn_time > ?
        ORDER BY spawn_time
    ''', (current_time,))

    all_spawns = [dict(row) for row in cursor.fetchall()]
    logger.info(f"📋 Всего активных спавнов в базе: {len(all_spawns)}")
    for spawn in all_spawns:
        logger.info(f"   - {spawn['boss_name']} в {spawn['spawn_time']}, уведомление в {spawn['notification_time']}")

    # Теперь ищем те, для которых нужно отправить уведомление
    cursor.execute('''
        SELECT * FROM boss_spawns 
        WHERE status = 'active' 
        AND notification_time <= ?
        AND spawn_time > ?
        AND notified = 0
        ORDER BY spawn_time
    ''', (current_time, current_time))

    spawns = [dict(row) for row in cursor.fetchall()]
    conn.close()

    logger.info(f"🔍 Найдено спавнов для уведомления: {len(spawns)}")
    return spawns


def get_all_active_spawns() -> List[Dict]:
    """Получает все активные спавны боссов (для отладки)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM boss_spawns 
        WHERE status = 'active'
        ORDER BY spawn_time
    ''')

    spawns = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return spawns
def delete_old_spawns(days: int = 7):
    """Удаляет старые спавны"""
    conn = get_connection()
    cursor = conn.cursor()

    cutoff_date = (datetime.now(pytz.timezone('Europe/Moscow')) - timedelta(days=days)).strftime('%Y-%m-%d')

    cursor.execute('''
        DELETE FROM boss_spawns 
        WHERE date(spawn_time) < ?
    ''', (cutoff_date,))

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    return deleted_count


from datetime import timedelta