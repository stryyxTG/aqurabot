# Milfshop / Telegram Account Shop Bot

Telegram-бот магазина Telegram-товаров на `aiogram 3`, `Telethon` и SQLite.

Главная точка входа: `python start.py`.

Этот README написан как “карта проекта” для следующего разработчика или AI-агента: что делает бот, где лежит логика, как запускать, какие места опасные и что важно не сломать.

## Что умеет бот

- Показывает каталог товаров по странам и разделам.
- Продаёт Telegram-товары из `.session`-файлов.
- Хранит баланс пользователя и историю покупок.
- Поддерживает корзину и групповую покупку товаров одного типа.
- После покупки выдаёт телефон, 2FA, код входа из `777000`, `.session` и `tdata`.
- Позволяет админу добавлять товары:
  - по номеру телефона через Telethon-login;
  - одним `.session`-файлом;
  - массовой загрузкой `.session`-файлов.
- Позволяет админу управлять каталогом, странами, разделами, складом, балансами, рассылками, прокси и статистикой.
- Поддерживает CryptoPay для автопополнения баланса.
- Поддерживает ручные заявки на пополнение через украинскую карту.
- Имеет команду `/clean`, которая чистит с сервера сессии только проданных товаров и пытается завершить их Telegram-сессии.

## Текущая важная бизнес-логика

- При `/start` после проверки обязательной подписки показываются условия соглашения, если пользователь ещё не принимал их.
- Обязательное принятие соглашения включено: кнопки “Условия” и “Принять”.
- Старая логика “проверить вход покупателя” и “ливнуть/чистить через 24 часа” убрана из handlers.
- Покупка переводит товар в `sold` сразу после успешного списания баланса.
- Кнопка получения кода читает последние коды из служебного чата Telegram через session-файл товара.
- Удаление проданного товара через карточку должно чистить session-файлы и историю аккуратно.
- `/clean` должен работать только с проданными товарами, не трогая доступные товары.
- Страны каталога добавляются одним сообщением. Можно написать обычный флаг или premium emoji вместе с названием страны; отдельный ввод ID emoji больше не нужен.
- CryptoPay-инвойсы сохраняются в БД до оплаты. При проверке оплаты сумма берётся только из БД, а не из callback-кнопки.

## Структура проекта

```text
start.py                  # Точка входа, вызывает shopbot.app.main()
bot.py                    # Совместимый старый алиас запуска

shopbot/app.py            # Основной файл: bot, dispatcher, handlers, меню, покупки, админка, CryptoPay
shopbot/db.py             # SQLite-схема, миграции и все операции с данными
shopbot/session_flow.py   # Telethon: логин, проверка сессий, получение кодов, logout/cleanup
shopbot/keyboards.py      # Inline-клавиатуры
shopbot/states.py         # FSM-состояния aiogram
shopbot/config.py         # Загрузка config.local.json и env
shopbot/paths.py          # Пути data/runtime/logs/sessions
shopbot/proxy_store.py    # Хранение глобального прокси
shopbot/proxy_utils.py    # Парсинг и проверка прокси
shopbot/telethon_utils.py # Вспомогательная Telethon-логика
shopbot/purchase_logic.py # Вспомогательная логика покупки, если используется handlers

requirements.txt          # Python-зависимости
config.local.json         # Локальный/боевой конфиг, в этом приватном репозитории может быть закоммичен

data/shop.db              # SQLite-база, создаётся автоматически
data/sessions/            # Session-файлы товаров
data/runtime/             # Временные файлы загрузок/экспортов/пользователей
logs/                     # Дополнительные runtime-логи, если используются
bot.log                   # Основной лог приложения
```

Старые документы вроде `QUICKSTART.md`, `INSTALL.md`, `CONFIG.md`, `LOGIC_UPDATE.md`, `LOGIN_VERIFICATION_FIX.md` могут быть историческими и не всегда отражают текущий код. Если есть конфликт, доверять текущему коду и этому README.

## Быстрый запуск локально

Требуется Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python start.py
```

На Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python start.py
```

При старте бот сам создаёт папки `data/`, `data/sessions/`, `data/runtime/`, `logs/` и базу `data/shop.db`.

## Запуск на Debian 12 VPS через nohup

```bash
apt update
apt install -y python3 python3-venv python3-pip git

cd /opt
git clone https://github.com/stryyxTG/Milfshop.git
cd /opt/Milfshop

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

nohup python -u start.py > bot.log 2>&1 &
echo $! > bot.pid
tail -f bot.log
```

Обновление на сервере:

```bash
cd /opt/Milfshop
kill "$(cat bot.pid)" 2>/dev/null || true
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
nohup python -u start.py > bot.log 2>&1 &
echo $! > bot.pid
tail -f bot.log
```

Посмотреть процессы:

```bash
ps aux | grep -E "python|start.py" | grep -v grep
```

## Конфиг

Конфиг читается из `config.local.json` в корне проекта и частично может перекрываться env-переменными.

Минимальный пример без реальных секретов:

```json
{
  "BOT_TOKEN": "telegram-bot-token",
  "ADMIN_IDS": [123456789],
  "API_ID": 123456,
  "API_HASH": "telegram-api-hash",
  "CRYPTOPAY_TOKEN": "",
  "SHOP_TITLE": "Stryx Shop",
  "CURRENCY": "$",
  "CRYPTOPAY_FIAT": "USD",
  "LOG_CHANNEL_ID": -1001234567890,
  "RU_TOPUP_CHAT_ID": -1001234567890,
  "UA_TOPUP_CHAT_ID": -1001234567890,
  "SUPPORT_USERNAME": "@support",
  "REVIEWS_URL": "https://t.me/example/1",
  "REQUIRED_CHANNEL": "-1001234567890",
  "REQUIRED_CHANNEL_URL": "https://t.me/+invite",
  "REQUIRE_PROXY_FOR_LOGIN": false,
  "TG_DEVICE_MODEL": "Samsung Galaxy S24 Ultra",
  "TG_SYSTEM_VERSION": "Android 14",
  "TG_APP_VERSION": "11.5.1",
  "TG_LANG_CODE": "ru",
  "TG_SYSTEM_LANG_CODE": "ru-RU"
}
```

Обязательные поля:

- `BOT_TOKEN`
- `ADMIN_IDS`
- `API_ID`
- `API_HASH`

Важная особенность текущего `shopbot/config.py`: почти все значения берутся как `env -> config.local.json -> default`, но `ADMIN_IDS` сейчас берётся как `config.local.json -> env -> []`. Если нужно, чтобы env всегда перекрывал config для `ADMIN_IDS`, это отдельный маленький фикс.

## Feature flags

Флаги сейчас заданы прямо в `shopbot/app.py`:

```python
FEATURE_TOPUP_RU = False
FEATURE_TOPUP_UA = True
FEATURE_TOPUP_CRYPTO = True
FEATURE_TOPUP_OTHER = False
FEATURE_CATALOG_PREMIUM = False
FEATURE_CATALOG_STARS = False
```

То есть сейчас включены украинская карта и CryptoPay. Российская карта, Other и продажа Premium/Stars отключены в UI/handlers.
Украинская карта считает оплату в UAH по курсу USD -> UAH, а к зачислению показывает сумму в валюте баланса.

## Основные команды

Пользовательские:

- `/start` — открыть главное меню.

Админские:

- `/admin` — открыть админ-панель.
- `/search` — поиск пользователя.
- `/drops` — управление дропами/пользователями со спецдоступом, если используется.
- `/cards` — задать реквизиты украинской карты для пополнения; `-` очищает реквизиты.
- `/delbalance <user_id>` — обнулить баланс пользователя.
- `/scan_sessions` — скан сессий.
- `/cleanup_sessions` — чистка session-файлов по ссылкам в БД.
- `/clean` — очистить с сервера только проданные товары и завершить их Telegram-сессии.

Большая часть управления сделана через inline-кнопки, а не через slash-команды.

## База данных

SQLite лежит в `data/shop.db`. Схема создаётся и мигрируется в `init_db()` внутри `shopbot/db.py`.

Главные таблицы:

- `users` — пользователи, баланс, даты.
- `users.agreement_accepted_at` — дата принятия условий соглашения.
- `products` — товары, session path, телефон, 2FA, статус.
- `purchases` — история покупок.
- `cart_items` — корзина.
- `balance_events` — аудит изменений баланса.
- `catalog_countries` — страны каталога, включая `icon_custom_emoji_id`.
- `catalog_departments` — разделы/пакеты внутри стран.
- `removed_product_departments` — история удалённых разделов.
- `crypto_invoices` — созданные CryptoPay-инвойсы до/после оплаты.
- `crypto_payments` — уже обработанные CryptoPay-инвойсы, защита от двойного зачисления.
- `topup_requests` — ручные заявки на пополнение.
- `topup_reviewers` — операторы ручных пополнений.
- `service_orders` — заказы Premium/Stars, если включить фичи.
- `app_meta` — простое key/value-хранилище.
- `channel_join_requests` — заявки/статус обязательного канала.

Статусы товаров, которые реально встречаются в логике:

- `available` — товар в продаже.
- `sold` — товар продан.
- `removed` — товар удалён/скрыт.
- также в коде остались следы старых статусов вроде `waiting_code`/`verifying`; их надо считать legacy, если нет активного handler-пути.

## Покупка товара

Упрощённый текущий путь:

1. Пользователь выбирает товар или группу товаров.
2. `purchase_product()` или `purchase_cart()` в `shopbot/db.py` атомарно:
   - проверяет баланс;
   - списывает деньги;
   - переводит товар в `sold`;
   - пишет `purchases` и `balance_events`.
3. Handler в `shopbot/app.py` показывает данные покупки.
4. Пользователь может запросить код входа.
5. `ShopSessionManager.fetch_code_from_telegram()` в `shopbot/session_flow.py` читает код из Telegram `777000` через session-файл товара.
6. Пользователь может скачать `.session` или `tdata`.

Важно: старая логика автоматического ожидания/подтверждения входа покупателя больше не является основным flow.

## CryptoPay

Код находится в `shopbot/app.py` около handlers пополнения:

- `call_crypto_pay()`
- `user_topup_amount()`
- `check_pay_callback()`

БД-функции находятся в `shopbot/db.py`:

- `record_crypto_invoice()`
- `get_crypto_invoice()`
- `mark_crypto_invoice_status()`
- `process_crypto_topup()`

Текущий безопасный flow:

1. Пользователь вводит сумму.
2. Бот вызывает CryptoPay `createInvoice`.
3. Бот сохраняет invoice в `crypto_invoices`.
4. Кнопка проверки содержит только `invoice_id`: `check_pay:{invoice_id}`.
5. При проверке бот ищет invoice в локальной БД.
6. Бот проверяет, что invoice принадлежит текущему user_id.
7. Бот вызывает CryptoPay `getInvoices`.
8. Если статус `paid`, бот сверяет сумму/fiat, если API вернул эти поля.
9. `process_crypto_topup()` через `crypto_payments` не даёт зачислить один invoice дважды.

Если пользователь оплатил старый invoice, созданный до появления `crypto_invoices`, автоматическое зачисление может отказать с “Счет не найден”. Тогда баланс нужно выдать вручную админом.

## Telethon-сессии

Основная логика в `shopbot/session_flow.py`.

Что важно:

- Session-файлы товаров хранятся как `data/sessions/product_<product_id>.session`.
- Для добавления товаров используется `API_ID`/`API_HASH` из конфига.
- Глобальный прокси можно настроить через админку; хранение в `proxy_store.py`.
- Если `REQUIRE_PROXY_FOR_LOGIN = true`, логин без прокси должен блокироваться.
- `logout_and_delete_product_session()` используется при очистке проданных товаров и удалении проданного товара.
- Получение кода из `777000` может найти не тот код, если в чате несколько свежих кодов. Это известная зона риска.

## `/clean`

Команда `/clean` нужна для безопасной очистки только проданных товаров.

Ожидаемое поведение:

- показывает проданные товары, у которых есть session-файлы/данные для очистки;
- по подтверждению вызывает cleanup/logout;
- удаляет session-файлы с сервера;
- не должен трогать `available` товары;
- не должен чистить непроданные товары.

Связанные места:

- handlers `/clean` в `shopbot/app.py`;
- `list_sold_products_for_manual_cleanup()` и функции удаления в `shopbot/db.py`;
- `logout_and_delete_product_session()` в `shopbot/session_flow.py`.

## Каталог стран

Добавление страны сейчас сделано без отдельного запроса `icon_custom_emoji_id`.

Админ может отправить:

```text
🇺🇸 USA
```

или название с premium emoji. Если Telegram передал premium emoji entity, бот сохранит `icon_custom_emoji_id`, а название очистит от emoji.

Связанная логика:

- `parse_country_name_and_icon()` в `shopbot/app.py`;
- `AdminCatalogStates.waiting_country_name` в `shopbot/states.py`;
- `catalog_countries.icon_custom_emoji_id` в `shopbot/db.py`.

## Обязательная подписка на канал

Middleware:

- `SubscriptionMiddleware` в `shopbot/app.py`.

Конфиг:

- `REQUIRED_CHANNEL`
- `REQUIRED_CHANNEL_URL`

Логика хранит join/request status в `channel_join_requests`.

Если бот не имеет прав видеть участника канала или канал указан неверно, пользователи могут застревать на проверке подписки.

## Логи и диагностика

Основной лог:

```bash
tail -f bot.log
```

Проверить, что бот запущен:

```bash
ps aux | grep -E "python|start.py" | grep -v grep
```

Проверка синтаксиса:

```bash
python -m py_compile bot.py shopbot/config.py shopbot/paths.py shopbot/db.py shopbot/states.py shopbot/keyboards.py shopbot/proxy_store.py shopbot/proxy_utils.py shopbot/session_flow.py shopbot/app.py
```

## Где что править

Для следующего AI/разработчика:

- Нужно изменить меню или flow пользователя — сначала `shopbot/app.py`, потом `shopbot/keyboards.py`.
- Нужно изменить данные/атомарность покупки/баланс — `shopbot/db.py`.
- Нужно изменить добавление/проверку товаров — `shopbot/session_flow.py`.
- Нужно изменить конфиг — `shopbot/config.py`.
- Нужно добавить состояние диалога — `shopbot/states.py`.
- Нужно изменить пути хранения файлов — `shopbot/paths.py`.
- Нужно изменить CryptoPay — `shopbot/app.py` + `shopbot/db.py`, не хранить сумму в callback.
- Нужно изменить `/clean` — смотреть `shopbot/app.py`, `shopbot/db.py`, `shopbot/session_flow.py`.

## Известные технические долги

- `shopbot/app.py` очень большой; новые большие фичи лучше выносить в отдельные модули постепенно.
- В коде остались legacy-следы старой проверки входа/таймаутов, хотя основной flow уже убран.
- `ADMIN_IDS` имеет особый порядок приоритета config/env, см. раздел “Конфиг”.
- `primary_admin_id` берётся из `set`, порядок не гарантирован.
- Получение кода из `777000` эвристическое и может ошибиться при нескольких свежих кодах.
- Логи могут содержать чувствительные данные, особенно ответы внешних API и данные товаров.
- Экспорт Excel пишет файлы в `data/`; после отправки их можно чистить отдельной задачей.
- Если репозиторий станет публичным, `config.local.json`, `data/`, session-файлы и логи нельзя хранить в Git.

## Правила аккуратной разработки

- Перед изменениями смотреть `git status --short`.
- Не трогать чужие локальные изменения без необходимости.
- После изменения Python-кода запускать `py_compile`.
- Для БД-изменений добавлять миграцию в `init_db()`.
- Для денежных операций использовать атомарные транзакции (`BEGIN IMMEDIATE`) и писать `balance_events`.
- Не доверять callback_data для суммы, user_id и других критичных значений.
- Для session cleanup всегда проверять, что операция относится к нужному товару и статусу.
