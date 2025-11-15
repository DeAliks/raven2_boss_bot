# db.py
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = 'boss_bot.db'


def init_db():
    """Инициализирует базу данных"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            guild TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE,
            ban_reason TEXT,
            banned_at TIMESTAMP,
            banned_by TEXT
        )
    ''')

    # Таблица забаненных гильдий
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banned_guilds (
            guild_name TEXT PRIMARY KEY,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            banned_by TEXT,
            ban_reason TEXT
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")


def add_or_update_user(user_id: str, username: str = None, guild: str = None):
    """Добавляет или обновляет пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if username is None:
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, guild, created_at)
            VALUES (?, ?, ?)
        ''', (user_id, guild, datetime.now()))
    else:
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, guild, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, guild, datetime.now()))

    conn.commit()
    conn.close()


def get_user(user_id: str):
    """Получает информацию о пользователе"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_id, username, guild, created_at, is_banned, ban_reason, banned_at, banned_by
        FROM users WHERE user_id = ?
    ''', (user_id,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            'user_id': result[0],
            'username': result[1],
            'guild': result[2],
            'created_at': result[3],
            'is_banned': bool(result[4]),
            'ban_reason': result[5],
            'banned_at': result[6],
            'banned_by': result[7]
        }
    return None


def get_all_users():
    """Получает всех пользователей"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_id, username, guild, created_at, is_banned, ban_reason
        FROM users ORDER BY created_at DESC
    ''')

    users = []
    for row in cursor.fetchall():
        users.append({
            'user_id': row[0],
            'username': row[1],
            'guild': row[2],
            'created_at': row[3],
            'is_banned': bool(row[4]),
            'ban_reason': row[5]
        })

    conn.close()
    return users


def ban_user(user_id: str, ban_reason: str, banned_by: str):
    """Банит пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE users 
        SET is_banned = TRUE, ban_reason = ?, banned_at = ?, banned_by = ?
        WHERE user_id = ?
    ''', (ban_reason, datetime.now(), banned_by, user_id))

    conn.commit()
    conn.close()
    logger.info(f"✅ Пользователь {user_id} забанен. Причина: {ban_reason}")


def unban_user(user_id: str):
    """Разбанивает пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE users 
        SET is_banned = FALSE, ban_reason = NULL, banned_at = NULL, banned_by = NULL
        WHERE user_id = ?
    ''', (user_id,))

    conn.commit()
    conn.close()
    logger.info(f"✅ Пользователь {user_id} разбанен")


def ban_guild(guild_name: str, ban_reason: str, banned_by: str):
    """Банит гильдию"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO banned_guilds (guild_name, banned_by, ban_reason)
        VALUES (?, ?, ?)
    ''', (guild_name, banned_by, ban_reason))

    conn.commit()
    conn.close()
    logger.info(f"✅ Гильдия {guild_name} забанена. Причина: {ban_reason}")


def unban_guild(guild_name: str):
    """Разбанивает гильдию"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('DELETE FROM banned_guilds WHERE guild_name = ?', (guild_name,))

    conn.commit()
    conn.close()
    logger.info(f"✅ Гильдия {guild_name} разбанена")


def get_banned_guilds():
    """Получает список забаненных гильдий"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT guild_name, banned_by, ban_reason, banned_at FROM banned_guilds')

    guilds = []
    for row in cursor.fetchall():
        guilds.append({
            'guild_name': row[0],
            'banned_by': row[1],
            'ban_reason': row[2],
            'banned_at': row[3]
        })

    conn.close()
    return guilds


def is_guild_banned(guild_name: str):
    """Проверяет, забанена ли гильдия"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT 1 FROM banned_guilds WHERE guild_name = ?', (guild_name,))
    result = cursor.fetchone() is not None

    conn.close()
    return result


def set_guild(user_id: str, guild: str):
    """Устанавливает гильдию для пользователя"""
    add_or_update_user(user_id, guild=guild)


def get_guild(user_id: str):
    """Получает гильдию пользователя"""
    user = get_user(user_id)
    return user['guild'] if user else None


def get_user_stats():
    """Получает статистику пользователей"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Общее количество пользователей
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]

    # Забаненные пользователи
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = TRUE')
    banned_users = cursor.fetchone()[0]

    # Активные пользователи
    active_users = total_users - banned_users

    # Распределение по гильдиям
    cursor.execute('''
        SELECT guild, COUNT(*) as count 
        FROM users 
        WHERE is_banned = FALSE AND guild IS NOT NULL
        GROUP BY guild
    ''')
    guild_distribution = {row[0]: row[1] for row in cursor.fetchall()}

    conn.close()

    return {
        'total_users': total_users,
        'active_users': active_users,
        'banned_users': banned_users,
        'guild_distribution': guild_distribution
    }