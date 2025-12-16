import gspread
from cachetools import cached, TTLCache
from datetime import datetime, timedelta
import pytz
import logging
import re
from config import SpreadSheet_URL
from typing import List, Dict, Optional

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
        self.boss_spawn_ws = None

        try:
            self.gc = gspread.service_account(filename=credentials_file)
            spreadsheet_url = SpreadSheet_URL
            self.spreadsheet = self.gc.open_by_url(spreadsheet_url)
            self.connected = True
            logger.info("✅ Успешное подключение к Google Таблице")

            # Инициализируем лист для спавнов боссов
            self._init_boss_spawn_sheet()

        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Google Таблице: {e}")
            self.connected = False

    def _init_boss_spawn_sheet(self):
        """Инициализирует лист для спавнов боссов"""
        try:
            # Пытаемся получить существующий лист
            self.boss_spawn_ws = self.spreadsheet.worksheet("BossSpawn")
            logger.info("✅ Лист BossSpawn найден")
        except gspread.exceptions.WorksheetNotFound:
            try:
                # Создаем новый лист
                self.boss_spawn_ws = self.spreadsheet.add_worksheet(
                    title="BossSpawn",
                    rows=100,
                    cols=9
                )

                # Добавляем заголовки
                headers = [
                    "ID",
                    "BossName",
                    "SpawnTime",
                    "CreatedAt",
                    "CreatedBy",
                    "Guild",
                    "ChannelID",
                    "Status",
                    "NotificationTime"
                ]
                self.boss_spawn_ws.append_row(headers)
                logger.info("✅ Создан новый лист BossSpawn с заголовками")
            except Exception as e:
                logger.error(f"❌ Ошибка создания листа BossSpawn: {e}")
                self.boss_spawn_ws = None

    # Существующие методы остаются без изменений...
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

            # Ищем дату в первой строке - каждая дата занимает два столбца
            header_row = all_data[0]  # Первая строка с датами
            logger.info(f"📅 Заголовок таблицы: {header_row}")

            # Ищем индекс колонки для сегодняшней даты
            target_col_index = -1
            for i in range(0, len(header_row), 2):  # Перебираем через один столбец
                if i < len(header_row) and header_row[i].strip() == today:
                    target_col_index = i
                    logger.info(f"✅ Найдена колонка для даты {today}: индекс {i} (столбцы {i} и {i + 1})")
                    break

            if target_col_index == -1:
                logger.error(f"❌ Дата {today} не найдена в таблице")
                logger.error(
                    f"Доступные даты в заголовке: {[header_row[i] for i in range(0, len(header_row), 2) if header_row[i].strip()]}")
                return bosses_data

            # Определяем границы каждого раздела (тира) для НОВОЙ структуры
            sections = self._find_section_boundaries_new_structure(all_data)

            # Обрабатываем каждый раздел
            for section_name, start_row, end_row in sections:
                logger.info(f"🔍 Обрабатываем раздел '{section_name}' (строки {start_row + 1}-{end_row + 1})")

                # Определяем тир на основе названия раздела
                tier = self._get_tier_from_section_name(section_name)
                if not tier:
                    continue

                # Обрабатываем строки в этом разделе
                for row_idx in range(start_row, end_row + 1):
                    if row_idx >= len(all_data):
                        continue

                    row = all_data[row_idx]
                    if len(row) <= target_col_index + 1:
                        continue

                    guild_cell = row[target_col_index].strip() if target_col_index < len(row) and row[
                        target_col_index] else ""
                    boss_cell = row[target_col_index + 1].strip() if target_col_index + 1 < len(row) and row[
                        target_col_index + 1] else ""

                    # Проверяем, что это данные о боссе
                    if (guild_cell and
                            guild_cell not in ['Гильдия', 'ГильдияБоссы', ''] and
                            boss_cell and
                            boss_cell not in ['Боссы', ''] and
                            not any(x in guild_cell for x in ['Тир', 'тир', 'боссы', 'Боссы']) and
                            '.' not in guild_cell and  # не дата
                            not guild_cell.isdigit()):  # не номер

                        # Нормализуем названия гильдий
                        guild_normalized = self.normalize_guild_name(guild_cell)

                        if not guild_normalized:
                            continue

                        # Для боссов бездны определяем тир по скобкам
                        if tier == 'abyss':
                            tier_from_boss = self.extract_tier_from_boss_name(boss_cell)
                            if tier_from_boss:
                                bosses_data[tier_from_boss].append((guild_normalized, boss_cell))
                                logger.info(
                                    f"✅ Добавлен босс бездны: {guild_normalized} - {boss_cell} ({tier_from_boss})")
                        else:
                            bosses_data[tier].append((guild_normalized, boss_cell))
                            logger.info(f"✅ Добавлен босс: {guild_normalized} - {boss_cell} ({tier})")

            # Логируем результаты
            logger.info("📊 Итоговые данные:")
            total_bosses = 0
            for tier, bosses in bosses_data.items():
                logger.info(f"  {tier}: {len(bosses)} боссов")
                total_bosses += len(bosses)
                for guild, boss in bosses:
                    logger.info(f"    {guild}: {boss}")

            logger.info(f"📈 Всего найдено боссов: {total_bosses}")

            return bosses_data

        except Exception as e:
            logger.error(f"❌ Ошибка при чтении данных из Google Таблицы: {e}")
            return {'tier1': [], 'tier2': [], 'tier3': [], 'tier4': [], 'tier5': []}

    def _find_section_boundaries_new_structure(self, all_data):
        """Находит границы разделов (тиров) в таблице для НОВОЙ структуры."""
        sections = []
        current_section = None
        section_start = -1

        for i, row in enumerate(all_data):
            if not row:
                continue

            first_cell = row[0].strip() if row[0] else ""

            # Проверяем, является ли строка началом нового раздела (новая структура)
            section_match = self._detect_section_new_structure(first_cell)
            if section_match:
                # Сохраняем предыдущий раздел
                if current_section and section_start != -1:
                    sections.append((current_section, section_start, i - 1))

                # Начинаем новый раздел
                current_section = section_match
                section_start = i
                logger.info(f"🎯 Найден раздел: {current_section} в строке {i + 1}")

        # Добавляем последний раздел
        if current_section and section_start != -1:
            sections.append((current_section, section_start, len(all_data) - 1))

        return sections

    def _detect_section_new_structure(self, cell_content):
        """Определяет, является ли ячейка началом раздела в НОВОЙ структуре."""
        lower_content = cell_content.lower()

        # Новая структура таблицы
        if 'тир 1' in lower_content or '1 тир' in lower_content:
            return 'tier1'
        elif 'тир 2' in lower_content or '2 тир' in lower_content:
            return 'tier2'
        elif 'тир 3' in lower_content or '3 тир' in lower_content:
            return 'tier3'
        elif 'тир 4' in lower_content or '4 тир' in lower_content:
            return 'tier4'
        elif 'тир 5' in lower_content or '5 тир' in lower_content:
            return 'tier5'
        elif 'боссы бездны' in lower_content or 'бездны' in lower_content:
            return 'abyss'

        return None

    def _get_tier_from_section_name(self, section_name):
        """Получает название тира из имени раздела."""
        if section_name in ['tier1', 'tier2', 'tier3', 'tier4', 'tier5']:
            return section_name
        elif section_name == 'abyss':
            return 'abyss'
        return None

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

        # Сначала проверяем точные соответствия в маппинге
        for key, value in guild_map.items():
            if key == lower_name:
                return value

        # Затем проверяем частичные совпадения
        for key, value in guild_map.items():
            if key in lower_name:
                return value

        # Если гильдия не найдена в маппинге, но соответствует ожидаемым названиям
        if normalized in ['Mercia', 'DarkSyndicate', 'HryKings', 'RussianTeam']:
            return normalized

        logger.warning(f"⚠️ Неизвестное название гильдии: '{guild_name}' (нормализовано: '{normalized}')")
        return None

    def clear_cache(self):
        """Очищает кэш для принудительного обновления данных."""
        cache.clear()
        logger.info("🗑️ Кэш очищен")

    # Новые методы для работы со спавнами боссов
    def add_boss_spawn(self, data: Dict) -> bool:
        """Добавляет запись о спавне босса в таблицу"""
        try:
            if not self.boss_spawn_ws:
                logger.error("❌ Лист BossSpawn не инициализирован")
                return False

            # Генерируем ID на основе текущего времени
            spawn_id = int(datetime.now().timestamp())

            # Подготавливаем строку для записи
            row = [
                spawn_id,
                data['boss_name'],
                data['spawn_time'].strftime('%d/%m/%Y %H:%M'),
                datetime.now(pytz.timezone(TIMEZONE)).strftime('%d/%m/%Y %H:%M'),
                data['created_by'],
                data['guild'],
                data['channel_id'],
                'active',  # Статус по умолчанию
                (data['spawn_time'] - timedelta(minutes=10)).strftime('%d/%m/%Y %H:%M')
            ]

            # Добавляем запись
            self.boss_spawn_ws.append_row(row)
            logger.info(f"✅ Запись о спавне добавлена: {data['boss_name']} на {data['spawn_time']}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении спавна: {e}")
            return False

    def get_active_boss_spawns(self) -> List[Dict]:
        """Получает активные спавны боссов"""
        try:
            if not self.boss_spawn_ws:
                return []

            records = self.boss_spawn_ws.get_all_records()
            active_spawns = []
            current_time = datetime.now(pytz.timezone(TIMEZONE))

            for record in records:
                try:
                    spawn_time = datetime.strptime(record['SpawnTime'], '%d/%m/%Y %H:%M')
                    spawn_time = pytz.timezone(TIMEZONE).localize(spawn_time)

                    # Проверяем, что спавн активен и время еще не наступило
                    if record['Status'] == 'active' and spawn_time > current_time:
                        active_spawns.append({
                            'id': record['ID'],
                            'boss_name': record['BossName'],
                            'spawn_time': spawn_time,
                            'guild': record['Guild'],
                            'channel_id': record['ChannelID'],
                            'notification_time': datetime.strptime(record['NotificationTime'], '%d/%m/%Y %H:%M')
                        })
                except Exception as e:
                    logger.error(f"Ошибка при обработке записи спавна: {e}")
                    continue

            return active_spawns

        except Exception as e:
            logger.error(f"❌ Ошибка при получении активных спавнов: {e}")
            return []

    def update_spawn_status(self, spawn_id: int, status: str) -> bool:
        """Обновляет статус спавна"""
        try:
            if not self.boss_spawn_ws:
                return False

            # Находим строку с нужным ID
            cell = self.boss_spawn_ws.find(str(spawn_id))
            if cell:
                # Обновляем статус (8-й столбец, если считать с 1)
                self.boss_spawn_ws.update_cell(cell.row, 8, status)
                logger.info(f"✅ Статус спавна {spawn_id} обновлен на '{status}'")
                return True

            logger.warning(f"⚠️ Спавн с ID {spawn_id} не найден")
            return False

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении статуса спавна: {e}")
            return False

    def get_tier4_bosses(self) -> List[str]:
        """Получает список всех Tier 4 боссов из сегодняшнего расписания"""
        try:
            bosses_data = self.get_today_bosses()
            tier4_bosses = bosses_data.get('tier4', [])

            # Извлекаем только имена боссов
            boss_names = []
            for guild, boss_name in tier4_bosses:
                if boss_name not in boss_names:
                    boss_names.append(boss_name)

            return boss_names

        except Exception as e:
            logger.error(f"❌ Ошибка при получении списка боссов: {e}")
            return []


# Создаем глобальный экземпляр менеджера
sheets_manager = GoogleSheetsManager()