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

## Запуск

```bash
python main.py