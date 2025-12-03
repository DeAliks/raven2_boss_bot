# Raven2 Boss Bot

Бот для уведомлений о боссах в игре и управления через Discord/Telegram.

## Установка

1. Скопируйте репозиторий
2. Установите зависимости: `pip install -r requirements.txt`
3. Настройте конфигурационные файлы:

### Настройка конфигурации

1. Скопируйте `config_template.py` в `config.py` и заполните реальными значениями
2. Скопируйте `credentials_template.json` в `credentials.json` и заполните данными сервисного аккаунта Google
3. Убедитесь, что файлы `config.py` и `credentials.json` добавлены в `.gitignore`

### Получение токенов

- **Discord Token**: Создайте приложение на [Discord Developer Portal](https://discord.com/developers/applications)
- **Telegram Token**: Создайте бота через [@BotFather](https://t.me/BotFather) в Telegram
- **Google Sheets API**: Создайте сервисный аккаунт в [Google Cloud Console](https://console.cloud.google.com/)

## 📋 Команды бота
👤 Для всех пользователей
1. !запрос	Создание новой заявки	!запрос
2. !статус	Просмотр ваших заявок	!статус
3. !очередь [ресурс]	Просмотр очереди	
4. !очередь "Петля Настойчивости"

👑 Для администраторов
Команда	Описание	Пример
1. !start_stashkeep [канал]	Активация бота	!start_stashkeep #заявки
2. !stop_stashkeep [канал]	Деактивация бота	!stop_stashkeep
3. !set_priority @пользователь	Установить приоритет	!set_priority @User1 @User2
4. !remove_priority @пользователь	Удалить приоритет
5. !remove_priority @User1
6. !list_priority	Список приоритетов	
7. !clear_priority	Очистить все приоритеты	

## Таблица со структурой
CreatedAt, DiscordID, DiscordName, CharacterName, ResourceGrade, ResourceName, 
Quantity, PriorityLevel, RequestTimestamp, QueuePosition, Status, ChannelID, 
MessageID, RowID, Screenshoot, PurpleApproval, ApproverID, Notes

## Запуск

```bash
python main.py