# db.py
import sqlite3
from typing import List, Tuple, Optional

DB_PATH = "raven2.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

# -------------------- ИНИЦИАЛИЗАЦИЯ --------------------
def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            guild TEXT
        )
    """)

    # таблица записей боссов (с сохранением позиции/порядка)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bosses_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            guild TEXT NOT NULL,
            tier TEXT NOT NULL,
            schedule_key TEXT NOT NULL,
            position INTEGER NOT NULL,
            UNIQUE(name, guild, tier, schedule_key)
        )
    """)

    conn.commit()
    conn.close()

# -------------------- Пользователи --------------------
def set_guild(user_id: int, guild: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("REPLACE INTO users (user_id, guild) VALUES (?, ?)", (user_id, guild))
    conn.commit()
    conn.close()

def get_guild(user_id: int) -> Optional[str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT guild FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def get_all_users() -> List[Tuple[int, str]]:
    """
    Возвращает список всех подписанных пользователей: [(user_id, guild), ...]
    Используется в scheduler для рассылки уведомлений.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, guild FROM users")
    rows = cur.fetchall()
    conn.close()
    return rows

# -------------------- СИНХРОНИЗАЦИЯ И УПРАВЛЕНИЕ boss_records --------------------
def clear_boss_records():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM bosses_records")
    conn.commit()
    conn.close()

def sync_bosses_from_schedule(bosses_schedule: dict):
    """
    Перезаписывает таблицу bosses_records из словаря BOSSES_SCHEDULE.
    Формат bosses_schedule:
      { "25.10": { "Mercia": {"tier1":[...], "tier2":[...], "tier3":[...]}, ...}, ... }
    Сохраняем порядок (position) для каждой гильдии в каждом слоте.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM bosses_records")
    conn.commit()

    # Проходим по ключам в порядке словаря (важно чтобы порядок в BOSSES_SCHEDULE был корректным)
    for schedule_key in bosses_schedule.keys():
        guilds = bosses_schedule[schedule_key]
        for guild, tiers in guilds.items():
            pos = 0
            # Сохраняем порядок: tier1, tier2, tier3 (сортировка ключей гарантирует порядок)
            for tier_name in sorted(tiers.keys()):
                names = tiers[tier_name]
                for name in names:
                    pos += 1
                    try:
                        cur.execute(
                            "INSERT OR IGNORE INTO bosses_records (name, guild, tier, schedule_key, position) VALUES (?, ?, ?, ?, ?)",
                            (name, guild, tier_name, schedule_key, pos)
                        )
                    except Exception:
                        # пропускаем ошибку конкретной записи, чтобы не ломать всю синхронизацию
                        pass

    conn.commit()
    conn.close()

# -------------------- ЗАПРОСЫ (чтение боссов) --------------------
def get_bosses_for_guild_and_slot(guild: str, schedule_key: str) -> List[Tuple[str, str]]:
    """
    Возвращает список (tier, name) отсортированных по position для указанной гильдии и слота (schedule_key).
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT tier, name FROM bosses_records
        WHERE guild = ? AND schedule_key = ?
        ORDER BY position ASC
    """, (guild, schedule_key))
    rows = cur.fetchall()
    conn.close()
    return rows  # [(tier, name), ...]

def get_all_bosses_for_guild(guild: str) -> List[Tuple[str, int]]:
    """
    Возвращает уникальные боссы для гильдии с сортировкой по первой позиции появления в расписании.
    Результат: [(name, first_position), ...]
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT name, MIN(position) as first_pos
        FROM bosses_records
        WHERE guild = ?
        GROUP BY name
        ORDER BY first_pos ASC
    """, (guild,))
    rows = cur.fetchall()
    conn.close()
    return rows  # [(name, first_pos), ...]

def get_all_schedule_keys() -> List[str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT schedule_key FROM bosses_records ORDER BY schedule_key")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows

# -------------------- Утилиты (для отладки) --------------------
def print_stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    users_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM bosses_records")
    bosses_count = cur.fetchone()[0]
    conn.close()
    print(f"DB stats: users={users_count}, boss_records={bosses_count}")
