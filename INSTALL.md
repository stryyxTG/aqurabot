# УСТАНОВКА И ЗАПУСК БОТА

## 📋 Требования

- Python 3.9+
- pip

## 🔧 Пошаговая установка

### 1. Перейдите в папку проекта
```bash
cd c:\Users\ziyod\Desktop\tg_akk_shop
```

### 2. Создайте виртуальное окружение (опционально, но рекомендуется)
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Установите зависимости
```bash
pip install -r requirements.txt
```

### 4. Настройте бота

Откройте `bot.py` и найдите строки:
```python
BOT_TOKEN = "8683238666:AAFTk8XtfRI_78A1semVezTPrqj1BLE8_mA"
ADMIN_IDS = [8208898956]
```

**Важно!** Замените:
- `BOT_TOKEN` на токен вашего бота (получить у @BotFather)
- `ADMIN_IDS` на свой Telegram ID

### 5. Запустите бота
```bash
python bot.py
```

## ✅ Проверка работы

1. Откройте Telegram
2. Найдите своего бота по имени (если вы его создали через @BotFather)
3. Напишите `/start`
4. Должно появиться меню

## 📊 Структура проекта

```
tg_akk_shop/
├── bot.py                 # Основной файл бота
├── requirements.txt       # Зависимости
├── README.md             # Документация
├── CONFIG.md             # Конфигурация
├── INSTALL.md            # Этот файл
├── .gitignore            # Git ignore
└── data/                 # Автоматически создаётся
    ├── accounts.json     # Аккаунты
    ├── balances.json     # Балансы
    ├── transactions.json # История
    ├── countries.json    # Страны
    ├── feedback.json     # Обратная связь
    └── users.json        # Пользователи
```

## 🐛 Решение проблем

### Ошибка: ModuleNotFoundError: No module named 'telegram'
```bash
pip install --upgrade python-telegram-bot
```

### Ошибка подключения
- Проверьте интернет
- Проверьте токен бота
- Убедитесь, что бот зарегистрирован через @BotFather

### Бот не отвечает
- Посмотрите логи в `bot.log`
- Убедитесь, что процесс запущен

## 🚀 Советы

1. **Используйте screen или nohup для фонового запуска:**
   ```bash
   python bot.py &
   ```

2. **Для production используйте systemd сервис или Docker**

3. **Регулярно проверяйте bot.log для отладки**

4. **Сохраняйте резервные копии папки `data/`**

## 📞 Нужна помощь?

Посмотрите:
- Логи в `bot.log`
- README.md для описания функционала
- Комментарии в `bot.py`

---

**Создано: 2024**  
**Версия: 1.0**  
**Статус: Production Ready** ✨
