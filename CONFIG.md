# Telegram Bot Configuration

## 🔑 Как получить BOT_TOKEN?

1. Откройте Telegram
2. Найдите @BotFather
3. Напишите `/newbot`
4. Следуйте инструкциям
5. Скопируйте токен в `bot.py`

## 👤 Как получить ADMIN_ID?

1. Напишите боту @userinfobot
2. Скопируйте свой ID
3. Добавьте его в `ADMIN_IDS = [123456789]` в `bot.py`

## 📝 Переменные конфигурации

```python
# Токен вашего бота
BOT_TOKEN = "123456789:ABCdefGHIjklmnoPQRstuvWXYZabcdefgh"

# ID администраторов (может быть несколько)
ADMIN_IDS = [123456789, 987654321]

# Директория для сохранения данных
DATA_DIR = "data/"
```

## 🚀 Запуск

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить бот
python bot.py
```

Бот будет работать в режиме polling (опросе) серверов Telegram.
Для production используйте webhooks.
