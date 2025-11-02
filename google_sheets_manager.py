# google_sheets_manager.py
import gspread
from cachetools import cached, TTLCache
from datetime import datetime
import pytz
import logging
import re

# Настройки
TIMEZONE = 'Europe/Moscow'
CACHE_TTL = 600  # 10 минут

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройка кэша
cache = TTLCache(maxsize=100, ttl=CACHE_TTL)


class GoogleSheetsManager:
    def __init__(self, credentials_file='credentials.json', spreadsheet_url=None):
        self.connected = False
        self.gc = None
        self.spreadsheet = None

        try:
            self.gc = gspread.service_account(filename=credentials_file)

            # URL вашей таблицы
            spreadsheet_url = "https://docs.google.com/spreadsheets/d/1juCUmpWicnz8OQvUgzBqAI9zVnm1RM1k-Hcj1-N4v3Y/edit"
            self.spreadsheet = self.gc.open_by_url(spreadsheet_url)
            self.connected = True
            logger.info("✅ Успешное подключение к Google Таблице")

        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Google Таблице: {e}")
            self.connected = False

    @cached(cache)
    def get_today_bosses(self):
        """Получает данные о боссах на сегодня из Google Таблицы с кэшированием."""
        if not self.connected:
            logger.error("Нет подключения к Google Таблице")
            return {'tier1': [], 'tier2': [], 'tier3': [], 'tier4': [], 'tier5': []}

        try:
            # Используем первый лист
            worksheet = self.spreadsheet.sheet1
            all_data = worksheet.get_all_values()

            today = datetime.now(pytz.timezone(TIMEZONE)).strftime('%d.%m')
            logger.info(f"🔍 Ищем данные для даты: {today}")

            bosses_data = {'tier1': [], 'tier2': [], 'tier3': [], 'tier4': [], 'tier5': []}

            # Находим индекс колонки для сегодняшней даты
            date_row = all_data[0]  # Первая строка с датами
            target_col_index = -1

            for i, cell in enumerate(date_row):
                if cell.strip() == today:
                    target_col_index = i
                    logger.info(f"✅ Найдена колонка для даты {today}: индекс {i}")
                    break

            if target_col_index == -1:
                logger.error(f"❌ Дата {today} не найдена в таблице")
                return bosses_data

            # Проходим по всем строкам и собираем данные для целевой даты
            current_tier = None

            for i, row in enumerate(all_data):
                if not row:
                    continue

                first_cell = row[0].strip() if row[0] else ""

                # Проверяем, является ли строка заголовком тира
                if 'Тир 1' in first_cell or 'тир 1' in first_cell.lower():
                    current_tier = 'tier1'
                    logger.info("🎯 Найден раздел: Тир 1")
                elif 'Тир 2' in first_cell or 'тир 2' in first_cell.lower():
                    current_tier = 'tier2'
                    logger.info("🎯 Найден раздел: Тир 2")
                elif 'Тир 3' in first_cell or 'тир 3' in first_cell.lower():
                    current_tier = 'tier3'
                    logger.info("🎯 Найден раздел: Тир 3")
                elif 'Тир 4' in first_cell or 'тир 4' in first_cell.lower():
                    current_tier = 'tier4'
                    logger.info("🎯 Найден раздел: Тир 4")
                elif 'Тир 5' in first_cell or 'тир 5' in first_cell.lower():
                    current_tier = 'tier5'
                    logger.info("🎯 Найден раздел: Тир 5")
                elif 'Боссы бездны' in first_cell:
                    current_tier = 'abyss'
                    logger.info("🎯 Найден раздел: Боссы бездны")
                elif current_tier and len(row) > target_col_index + 1:
                    # Берем данные из колонки для целевой даты (гильдия) и следующей колонки (босс)
                    guild_cell = row[target_col_index].strip() if len(row) > target_col_index else ""
                    boss_cell = row[target_col_index + 1].strip() if len(row) > target_col_index + 1 else ""

                    # Проверяем, что это не заголовок и не пустые данные
                    if (guild_cell and
                            guild_cell not in ['Гильдия', 'ГильдияБоссы'] and
                            not any(x in guild_cell for x in ['Тир', 'тир', 'боссы', 'Боссы']) and
                            '.' not in guild_cell and  # не дата
                            boss_cell and
                            not boss_cell.isdigit()):  # не номер

                        # Нормализуем названия гильдий
                        guild_normalized = self.normalize_guild_name(guild_cell)

                        # Для боссов бездны определяем тир по скобкам
                        if current_tier == 'abyss':
                            tier_from_boss = self.extract_tier_from_boss_name(boss_cell)
                            if tier_from_boss and guild_normalized:
                                bosses_data[tier_from_boss].append((guild_normalized, boss_cell))
                                logger.info(
                                    f"✅ Добавлен босс бездны: {guild_normalized} - {boss_cell} ({tier_from_boss})")
                        elif guild_normalized:
                            bosses_data[current_tier].append((guild_normalized, boss_cell))
                            logger.info(f"✅ Добавлен босс: {guild_normalized} - {boss_cell} ({current_tier})")

            # Логируем результаты
            logger.info("📊 Итоговые данные:")
            for tier, bosses in bosses_data.items():
                logger.info(f"  {tier}: {len(bosses)} боссов")
                for guild, boss in bosses:
                    logger.info(f"    {guild}: {boss}")

            return bosses_data

        except Exception as e:
            logger.error(f"❌ Ошибка при чтении данных из Google Таблицы: {e}")
            return {'tier1': [], 'tier2': [], 'tier3': [], 'tier4': [], 'tier5': []}

    def extract_tier_from_boss_name(self, boss_name):
        """Извлекает тир из названия босса бездны по скобкам."""
        # Ищем паттерны: (т2), (т3), (т4), (т5), (Т2), (Т3) и т.д.
        match = re.search(r'\([тТ]?(\d)\)', boss_name)
        if match:
            tier_num = match.group(1)
            return f'tier{tier_num}'
        return None

    def normalize_guild_name(self, guild_name):
        """Нормализует названия гильдий для единообразия."""
        guild_map = {
            'darksyndicate': 'DarkSyndicate',
            'dark syndicate': 'DarkSyndicate',
            'darksindikat': 'DarkSyndicate',
            'dark sindikat': 'DarkSyndicate',
            'mercia': 'Mercia',
            'xray': 'XRAY',
            'hrykings': 'HryKings'
        }

        normalized = guild_name.strip()
        lower_name = normalized.lower()

        for key, value in guild_map.items():
            if key in lower_name:
                return value

        return normalized if normalized in ['Mercia', 'DarkSyndicate', 'HryKings', 'XRAY'] else None

    def clear_cache(self):
        """Очищает кэш для принудительного обновления данных."""
        cache.clear()
        logger.info("🗑️ Кэш очищен")


# Создаем глобальный экземпляр менеджера
sheets_manager = GoogleSheetsManager()