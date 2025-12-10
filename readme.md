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

**📋 Основные команды уведомлений:**

`!start_boss_alert <гильдия>` - активировать уведомления

• `!start_boss_alert All` - для всех гильдий

• `!start_boss_alert DarkSyndicate` - только для DarkSyndicate

• `!start_boss_alert Mercia` - только для Mercia

• `!start_boss_alert HryKings` - только для HryKings

• `!start_boss_alert RussianTeam` - только для RussianTeam


`!stop_boss_alert` - отключить уведомления
`!boss_status` - статус уведомлений
`!today_bosses [гильдия]` - боссы на сегодня

**🎲 Случайный выбор:**

`!random <данные>` - случайный выбор

• `!random 1-10` - случайное число от 1 до 10

• `!random 7` - случайное число от 1 до 7

• Многострочный ввод для списка:!random Ника
Леся
Лось

**🤖 Автоматические уведомления:**
Бот автоматически отправляет уведомления о боссах и разломах за 10 минут до их появления.




    print("✅ Бот запущен и ожидает события...")
    print("\n📋 Доступные команды для Discord:")
    print("  !start_boss_alert <гильдия> - активировать уведомления")
    print("  !stop_boss_alert - отключить уведомления")
    print("  !boss_status - статус уведомлений")
    print("  !today_bosses [гильдия] - боссы на сегодня")
    print("  !random - случайный выбор из списка или диапазона чисел")
    print("  !commands - справка по командам")
    print("  !admincheck - проверка прав администратора")
    print("  !userinfo - информация о пользователе")
    print("  !userstats - статистика пользователей")
    print("  !userlist - список пользователей")
    print("  !ban - забанить пользователя")
    print("  !unban - разбанить пользователя")
    print("  !banguild - забанить гильдию")
    print("  !unbanguild - разбанить гильдию")

    print("\n📋 Доступные команды для Telegram:")
    print("  /start - начать работу")
    print("  /everyone - рассылка всем пользователям")
    print("  /test_discord_bosses - тест уведомления Discord о боссах")
    print("  /test_discord_rift - тест уведомления Discord о разломах")
    print("  /test_discord_tier4 - тест уведомления Discord о Tier 4")
    print("  /test_discord_all - тест всех уведомлений Discord")
    print("  /discord_status - статус Discord бота")
    print("  /discord_servers - список активных Discord серверов")
    print("  /discord_test_all - тест уведомлений на всех серверах")


```bash
python main.py