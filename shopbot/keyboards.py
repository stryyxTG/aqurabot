from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import load_settings


settings = load_settings()

BTN_ICON_ADMIN = "5870982283724328568"
BTN_ICON_BALANCE = "5904462880941545555"
BTN_ICON_CATALOG = "5920332557466997677"
BTN_ICON_CART = "5453980026305274747"
BTN_ICON_HOME = "6042137469204303531"
BTN_ICON_PURCHASES = "5890727932011223292"
BTN_ICON_REVIEW = "5872863028428410654"
BTN_ICON_SUPPORT = "5904248647972820334"
BTN_ICON_TOPUP = "6042098561095570207"
BTN_ICON_CRYPTO = "6037083366438737901"
BTN_ICON_UA = "5264782095531661663"
BTN_ICON_RU = "5424670808700114602"
BTN_ICON_CANCEL = "5774077015388852135"
BTN_ICON_BACK = "5870723666563566827"
BTN_ICON_BUY = "5870633910337015697"
BTN_ICON_PAY = "5891105528356018797"
BTN_ICON_CHECK = "5938252440926163756"
BTN_ICON_REVIEWS = "5870772616305839506"
BTN_ICON_TG_ACCOUNTS = "6028346797368283073"
BTN_ICON_TG_PREMIUM = "6028338546736107668"
BTN_ICON_TG_STARS = "5463289097336405244"
BTN_ICON_PERIOD = "5983150113483134607"
AGREEMENT_URL = "https://telegra.ph/Politika-konfidencialnosti-06-30-45"


def main_menu_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Каталог", callback_data="menu_catalog", icon_custom_emoji_id=BTN_ICON_CATALOG)],
        [
            InlineKeyboardButton(text="Баланс", callback_data="menu_balance", icon_custom_emoji_id=BTN_ICON_BALANCE),
            InlineKeyboardButton(text="Мои покупки", callback_data="menu_purchases", icon_custom_emoji_id=BTN_ICON_PURCHASES),
        ],
        [InlineKeyboardButton(text="Корзина", callback_data="menu_cart", icon_custom_emoji_id=BTN_ICON_CART)],
        [
            InlineKeyboardButton(text="Отзывы", url=settings.reviews_url, icon_custom_emoji_id=BTN_ICON_REVIEWS),
            InlineKeyboardButton(text="Помощь", callback_data="menu_help", icon_custom_emoji_id=BTN_ICON_SUPPORT),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="Админка", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_ADMIN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def help_menu_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Условия", url=AGREEMENT_URL)],
        [InlineKeyboardButton(text="Связаться с поддержкой", url=settings.support_url, icon_custom_emoji_id=BTN_ICON_SUPPORT)],
        [InlineKeyboardButton(text="В меню", callback_data="menu_home", icon_custom_emoji_id=BTN_ICON_HOME)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def agreement_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Условия", url=AGREEMENT_URL)],
            [InlineKeyboardButton(text="Принять", callback_data="agreement_accept", icon_custom_emoji_id=BTN_ICON_CHECK)],
        ]
    )


def purchase_success_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Оставить отзыв", url=settings.reviews_url, icon_custom_emoji_id=BTN_ICON_REVIEW)],
        [InlineKeyboardButton(text="В меню", callback_data="menu_home", icon_custom_emoji_id=BTN_ICON_HOME)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_main_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Пополнить баланс", callback_data="user_topup_start", icon_custom_emoji_id=BTN_ICON_TOPUP)],
        [InlineKeyboardButton(text="В меню", callback_data="menu_home", icon_custom_emoji_id=BTN_ICON_HOME)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def menu_only_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="В меню", callback_data="menu_home", icon_custom_emoji_id=BTN_ICON_HOME)]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def purchases_nav_kb(*, purchase_rows: list[list[InlineKeyboardButton]] | None = None, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = list(purchase_rows or [])
    nav = []
    if total_pages > 1:
        if page > 0:
            nav.append(InlineKeyboardButton(text="<", callback_data=f"menu_purchases:{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"{page + 1}/{max(total_pages, 1)}", callback_data="noop"))
        if page + 1 < total_pages:
            nav.append(InlineKeyboardButton(text=">", callback_data=f"menu_purchases:{page + 1}"))
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="В меню", callback_data="menu_home", icon_custom_emoji_id=BTN_ICON_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def purchase_history_detail_kb(page: int, product_id: int | None = None, batch_id: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if product_id is not None:
        rows.append([InlineKeyboardButton(text="Получить к0d", callback_data=f"request_code:{product_id}", icon_custom_emoji_id=BTN_ICON_CHECK)])
        rows.append([
            InlineKeyboardButton(text=".session", callback_data=f"user_download_session:{product_id}"),
            InlineKeyboardButton(text="tdata", callback_data=f"user_download_tdata:{product_id}"),
        ])
    back_callback = f"purchase_batch:{batch_id}:{page}" if batch_id else f"menu_purchases:{page}"
    rows.extend([
        [InlineKeyboardButton(text="Назад", callback_data=back_callback)],
        [InlineKeyboardButton(text="В меню", callback_data="menu_home", icon_custom_emoji_id=BTN_ICON_HOME)],
    ])
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def purchase_batch_kb(
    *,
    batch_id: str,
    page: int,
    account_rows: list[list[InlineKeyboardButton]] | None = None,
    can_bulk_download: bool,
) -> InlineKeyboardMarkup:
    rows = list(account_rows or [])
    if can_bulk_download:
        rows.append([InlineKeyboardButton(text="Скачать tdata аккаунтов", callback_data=f"batch_download_ask:tdata:{batch_id}:{page}")])
        rows.append([InlineKeyboardButton(text="Скачать .session аккаунтов", callback_data=f"batch_download_ask:session:{batch_id}:{page}")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data=f"menu_purchases:{page}", icon_custom_emoji_id=BTN_ICON_BACK)])
    rows.append([InlineKeyboardButton(text="В меню", callback_data="menu_home", icon_custom_emoji_id=BTN_ICON_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def batch_download_confirm_kb(batch_id: str, page: int, file_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, скачать", callback_data=f"batch_download:{file_type}:{batch_id}:{page}", icon_custom_emoji_id=BTN_ICON_CHECK)],
            [InlineKeyboardButton(text="Нет", callback_data=f"purchase_batch:{batch_id}:{page}", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )


def cart_kb(*, item_rows: list[list[InlineKeyboardButton]] | None = None, can_checkout: bool) -> InlineKeyboardMarkup:
    rows = list(item_rows or [])
    if can_checkout:
        rows.append([InlineKeyboardButton(text="Очистить корзину", callback_data="cart_clear", icon_custom_emoji_id=BTN_ICON_CANCEL)])
        rows.append([InlineKeyboardButton(text="Оплатить всё", callback_data="cart_checkout", icon_custom_emoji_id=BTN_ICON_PAY)])
    rows.append([InlineKeyboardButton(text="В меню", callback_data="menu_home", icon_custom_emoji_id=BTN_ICON_HOME)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def open_cart_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть корзину", callback_data="menu_cart")],
        ]
    )


def admin_sold_history_kb(*, product_rows: list[list[InlineKeyboardButton]] | None = None, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = list(product_rows or [])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="<", callback_data=f"admin_stock_sold_list:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{max(total_pages, 1)}", callback_data="noop"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text=">", callback_data=f"admin_stock_sold_list:{page + 1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton(text="В админку", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_ADMIN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topup_methods_kb(
    crypto_enabled: bool,
    *,
    ru_enabled: bool = True,
    ua_enabled: bool = True,
    other_enabled: bool = True,
) -> InlineKeyboardMarkup:
    rows = []
    if ru_enabled:
        rows.append([InlineKeyboardButton(text="Российской картой", callback_data="topup_method:ru", icon_custom_emoji_id=BTN_ICON_RU)])
    if ua_enabled:
        rows.append([InlineKeyboardButton(text="Украинской картой", callback_data="topup_method:ua", icon_custom_emoji_id=BTN_ICON_UA)])
    if crypto_enabled:
        rows.append([InlineKeyboardButton(text="Crypto Bot", callback_data="topup_method:crypto", icon_custom_emoji_id=BTN_ICON_CRYPTO)])
    if other_enabled:
        rows.append([InlineKeyboardButton(text="Другие способы", callback_data="topup_other", icon_custom_emoji_id=BTN_ICON_TOPUP)])
    if not rows:
        rows.append([InlineKeyboardButton(text="Пополнение временно недоступно", callback_data="noop")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="menu_balance", icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topup_other_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Связаться с поддержкой", url=settings.support_url, icon_custom_emoji_id=BTN_ICON_SUPPORT)],
            [InlineKeyboardButton(text="Назад", callback_data="user_topup_methods", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )


def topup_receipt_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Связаться с поддержкой", url=settings.support_url, icon_custom_emoji_id=BTN_ICON_SUPPORT)],
            [InlineKeyboardButton(text="Отменить", callback_data="cancel_topup_receipt", icon_custom_emoji_id=BTN_ICON_CANCEL)],
        ]
    )


def topup_review_kb(request_id: int, user_id: int, username: str | None = None) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="Одобрить", callback_data=f"topup_approve:{request_id}"),
        InlineKeyboardButton(text="Отказать", callback_data=f"topup_reject:{request_id}"),
    ]]
    if username:
        rows.append([InlineKeyboardButton(text="Профиль клиента", url=f"https://t.me/{username}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topup_confirm_kb(action: str, request_id: int, user_id: int, username: str | None = None) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="Да", callback_data=f"topup_confirm:{action}:{request_id}"),
        InlineKeyboardButton(text="Нет", callback_data=f"topup_cancel:{request_id}"),
    ]]
    if username:
        rows.append([InlineKeyboardButton(text="Профиль клиента", url=f"https://t.me/{username}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Связаться с поддержкой", url=settings.support_url, icon_custom_emoji_id=BTN_ICON_SUPPORT)]]
    )


def drops_menu_kb(reviewer_rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    rows = list(reviewer_rows)
    rows.append([InlineKeyboardButton(text="Добавить", callback_data="drops_add")])
    rows.append([InlineKeyboardButton(text="В админку", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_ADMIN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def drop_manage_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Удалить доступ", callback_data=f"drops_remove:{user_id}")],
            [InlineKeyboardButton(text="Профиль", url=f"tg://user?id={user_id}")],
            [InlineKeyboardButton(text="Назад", callback_data="drops_menu", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )


def catalog_home_kb(country_rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    rows = list(country_rows)
    rows.append([InlineKeyboardButton(text="Назад", callback_data="menu_catalog", icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_sections_kb(*, premium_enabled: bool = True, stars_enabled: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="ТГ", callback_data="catalog_accounts", icon_custom_emoji_id=BTN_ICON_TG_ACCOUNTS)],
    ]
    if premium_enabled:
        rows.append([InlineKeyboardButton(text="Premium", callback_data="catalog_premium", icon_custom_emoji_id=BTN_ICON_TG_PREMIUM)])
    if stars_enabled:
        rows.append([InlineKeyboardButton(text="Stars", callback_data="catalog_stars", icon_custom_emoji_id=BTN_ICON_TG_STARS)])
    rows.append([InlineKeyboardButton(text="В меню", callback_data="menu_home", icon_custom_emoji_id=BTN_ICON_HOME)])
    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def premium_periods_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="3 месяца", callback_data="premium_period:3", icon_custom_emoji_id=BTN_ICON_PERIOD)],
            [InlineKeyboardButton(text="6 месяцев", callback_data="premium_period:6", icon_custom_emoji_id=BTN_ICON_PERIOD)],
            [InlineKeyboardButton(text="1 год", callback_data="premium_period:12", icon_custom_emoji_id=BTN_ICON_PERIOD)],
            [InlineKeyboardButton(text="Назад", callback_data="menu_catalog", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )


def stars_packages_kb(packages: list[int]) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(packages), 3):
        rows.append([
            InlineKeyboardButton(text=str(amount), callback_data=f"stars_package:{amount}")
            for amount in packages[i:i + 3]
        ])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="menu_catalog", icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def service_detail_kb(buy_callback: str, back_callback: str, *, can_buy: bool = True) -> InlineKeyboardMarkup:
    rows = []
    if can_buy:
        rows.append([InlineKeyboardButton(text="Купить", callback_data=buy_callback, icon_custom_emoji_id=BTN_ICON_BUY)])
    rows.append([InlineKeyboardButton(text="Назад", callback_data=back_callback, icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def service_recipient_cancel_kb(back_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отменить", callback_data="service_order_cancel", icon_custom_emoji_id=BTN_ICON_CANCEL)]]
    )


def service_order_review_kb(order_id: int, username: str | None = None) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="Выдано", callback_data=f"service_done:{order_id}", icon_custom_emoji_id=BTN_ICON_CHECK),
        InlineKeyboardButton(text="Отказано", callback_data=f"service_reject:{order_id}", icon_custom_emoji_id=BTN_ICON_CANCEL),
    ]]
    if username:
        rows.append([InlineKeyboardButton(text="Профиль клиента", url=f"https://t.me/{username}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def service_order_confirm_kb(action: str, order_id: int, username: str | None = None) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text="Да", callback_data=f"service_confirm:{action}:{order_id}", icon_custom_emoji_id=BTN_ICON_CHECK),
        InlineKeyboardButton(text="Нет", callback_data=f"service_review_cancel:{order_id}", icon_custom_emoji_id=BTN_ICON_BACK),
    ]]
    if username:
        rows.append([InlineKeyboardButton(text="Профиль клиента", url=f"https://t.me/{username}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_list_kb(*, prefix: str, product_rows: list[list[InlineKeyboardButton]], page: int, total_pages: int, back_callback: str) -> InlineKeyboardMarkup:
    rows = list(product_rows)
    nav = []
    def page_callback(next_page: int) -> str:
        return f"{prefix}{next_page}" if prefix.endswith(":") else f"{prefix}_{next_page}"

    if total_pages > 1:
        if page > 0:
            nav.append(InlineKeyboardButton(text="<", callback_data=page_callback(page - 1)))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{max(total_pages, 1)}", callback_data="noop"))
        if page + 1 < total_pages:
            nav.append(InlineKeyboardButton(text=">", callback_data=page_callback(page + 1)))
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="Назад", callback_data=back_callback, icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_detail_kb(product_id: int, *, can_buy: bool, back_callback: str, can_claim: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if can_claim:
        rows.append([InlineKeyboardButton(text="Забрать аkkаунт", callback_data=f"admin_claim_ask:{product_id}")])
    if can_buy:
        rows.append([InlineKeyboardButton(text="Купить", callback_data=f"buy_{product_id}")])
        rows.append([InlineKeyboardButton(text="Добавить в корзину", callback_data=f"cart_add:{product_id}")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_group_detail_kb(sample_product_id: int, *, can_buy: bool, back_callback: str, picker_callback: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if can_buy:
        rows.append([InlineKeyboardButton(text="Добавить в корзину", callback_data=picker_callback or f"cart_picker_open:{sample_product_id}:1")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_group_cart_kb(
    sample_product_id: int,
    *,
    selected_qty: int,
    max_qty: int,
    back_callback: str,
) -> InlineKeyboardMarkup:
    qty = max(1, min(int(selected_qty or 1), int(max_qty or 1)))
    rows = [
        [
            InlineKeyboardButton(text="-", callback_data=f"cart_picker:{sample_product_id}:{max(1, qty - 1)}"),
            InlineKeyboardButton(text=str(qty), callback_data="noop"),
            InlineKeyboardButton(text="+", callback_data=f"cart_picker:{sample_product_id}:{min(int(max_qty or qty), qty + 1)}"),
        ],
        [InlineKeyboardButton(text="Ввести вручную", callback_data=f"cart_add_group_manual:{sample_product_id}")],
        [InlineKeyboardButton(text=f"Добавить в корзину ({qty})", callback_data=f"cart_add_group_qty:{sample_product_id}:{qty}")],
        [InlineKeyboardButton(text="Назад", callback_data=back_callback)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить аккаунт", callback_data="admin_add")],
            [
                InlineKeyboardButton(text="Товары", callback_data="admin_stock"),
                InlineKeyboardButton(text="Статистика", callback_data="admin_stats"),
            ],
            [
                InlineKeyboardButton(text="Выдать баланс", callback_data="admin_topup"),
                InlineKeyboardButton(text="Прокси", callback_data="admin_proxy"),
            ],
            [InlineKeyboardButton(text="Поиск пользователя", callback_data="admin_user_search")],
            [InlineKeyboardButton(text="Поиск товара", callback_data="admin_product_search")],
            [InlineKeyboardButton(text="Страны каталога", callback_data="admin_catalog")],
            [InlineKeyboardButton(text="Застрявшие товары", callback_data="admin_stuck_products")],
            [InlineKeyboardButton(text="История продаж", callback_data="admin_stock_sold_list")],
            [InlineKeyboardButton(text="Скан аккаунтов", callback_data="admin_scan_accounts")],
            [InlineKeyboardButton(text="Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="В меню", callback_data="menu_home", icon_custom_emoji_id=BTN_ICON_HOME)],
        ]
    )


def admin_clean_kb(flow_id: str, can_clean: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Обновить список", callback_data=f"clean_refresh:{flow_id}")],
    ]
    if can_clean:
        rows.append([
            InlineKeyboardButton(
                text="Очистить проданные сессии",
                callback_data=f"clean_confirm:{flow_id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text="В админку",
            callback_data="cancel_flow:admin_home",
            icon_custom_emoji_id=BTN_ICON_ADMIN,
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_clean_confirm_kb(flow_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, очистить",
                    callback_data=f"clean_execute:{flow_id}",
                    style="danger",
                )
            ],
            [InlineKeyboardButton(text="Назад", callback_data=f"clean_back:{flow_id}", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )


def admin_stats_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Экспорт БД", callback_data="admin_export_database")],
            [InlineKeyboardButton(text="Сбросить выручку", callback_data="admin_reset_revenue")],
            [InlineKeyboardButton(text="Сбросить статистику", callback_data="admin_reset_stats")],
            [InlineKeyboardButton(text="Назад", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )


def admin_scan_settings_kb(interval: int, limit: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="30 сек", callback_data="admin_scan_interval:30"),
                InlineKeyboardButton(text="60 сек", callback_data="admin_scan_interval:60"),
                InlineKeyboardButton(text="120 сек", callback_data="admin_scan_interval:120"),
            ],
            [InlineKeyboardButton(text=f"Свой интервал: {interval} сек", callback_data="admin_scan_interval_custom")],
            [
                InlineKeyboardButton(text="3 акка", callback_data="admin_scan_limit:3"),
                InlineKeyboardButton(text="5 акков", callback_data="admin_scan_limit:5"),
                InlineKeyboardButton(text="10 акков", callback_data="admin_scan_limit:10"),
            ],
            [InlineKeyboardButton(text=f"Свой лимит: {limit}", callback_data="admin_scan_limit_custom")],
            [InlineKeyboardButton(text="Начать глубокую проверку", callback_data="admin_scan_confirm")],
            [InlineKeyboardButton(text="Назад", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )


def admin_scan_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, начать", callback_data="admin_scan_start", icon_custom_emoji_id=BTN_ICON_CHECK)],
            [InlineKeyboardButton(text="Нет", callback_data="admin_scan_accounts", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )


def admin_catalog_kb(country_rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    rows = list(country_rows)
    rows.append([InlineKeyboardButton(text="Добавить регион", callback_data="admin_country_add")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_country_kb(country_id: int, group_rows: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    rows = list(group_rows or [])
    rows.extend(
        [
            [InlineKeyboardButton(text="Создать отдел", callback_data=f"admin_department_create:{country_id}")],
            [InlineKeyboardButton(text="Переименовать", callback_data=f"admin_country_rename:{country_id}")],
            [InlineKeyboardButton(text="Удалить регион", callback_data=f"admin_country_remove_ask:{country_id}", icon_custom_emoji_id=BTN_ICON_CANCEL)],
            [InlineKeyboardButton(text="Назад", callback_data="admin_catalog", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_group_kb(
    sample_product_id: int,
    country_id: int,
    *,
    account_rows: list[list[InlineKeyboardButton]] | None = None,
    page: int = 0,
    total_pages: int = 1,
) -> InlineKeyboardMarkup:
    rows = list(account_rows or [])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="<", callback_data=f"admin_product_group:{sample_product_id}:{country_id}:{page-1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page+1}/{max(total_pages, 1)}", callback_data="noop"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text=">", callback_data=f"admin_product_group:{sample_product_id}:{country_id}:{page+1}"))
    if nav:
        rows.append(nav)
    rows.extend([
        [InlineKeyboardButton(text="Редачить", callback_data=f"admin_edit_group:{sample_product_id}:{country_id}")],
        [InlineKeyboardButton(text="Удалить отдел", callback_data=f"admin_remove_group_ask:{sample_product_id}:{country_id}", icon_custom_emoji_id=BTN_ICON_CANCEL)],
        [InlineKeyboardButton(text="Назад", callback_data=f"admin_country:{country_id}", icon_custom_emoji_id=BTN_ICON_BACK)],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_group_remove_confirm_kb(sample_product_id: int, country_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, удалить", callback_data=f"admin_remove_group:{sample_product_id}:{country_id}", icon_custom_emoji_id=BTN_ICON_CANCEL),
                InlineKeyboardButton(text="Нет", callback_data=f"admin_product_group:{sample_product_id}:{country_id}", icon_custom_emoji_id=BTN_ICON_BACK),
            ],
        ]
    )


def admin_country_remove_confirm_kb(country_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, удалить", callback_data=f"admin_country_remove:{country_id}", icon_custom_emoji_id=BTN_ICON_CANCEL),
                InlineKeyboardButton(text="Нет", callback_data=f"admin_country:{country_id}", icon_custom_emoji_id=BTN_ICON_BACK),
            ],
        ]
    )


def country_select_kb(country_rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    rows = list(country_rows)
    rows.append([InlineKeyboardButton(text="Отменить", callback_data="cancel_flow:admin_home", icon_custom_emoji_id=BTN_ICON_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_stock_list_kb(product_rows: list[list[InlineKeyboardButton]], *, page: int, total_pages: int, status: str) -> InlineKeyboardMarkup:
    prefix = f"admin_stock_{status}"
    rows = list(product_rows)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="<", callback_data=f"{prefix}_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{max(total_pages, 1)}", callback_data="noop"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text=">", callback_data=f"{prefix}_{page+1}"))
    rows.append(nav)
    if status == "available":
        rows.append([InlineKeyboardButton(text="Проданные", callback_data="admin_stock_sold_0")])
    else:
        rows.append([InlineKeyboardButton(text="Доступные", callback_data="admin_stock_available_0")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_kb(product_id: int, *, removable: bool, back_callback: str) -> InlineKeyboardMarkup:
    rows = []
    if removable:
        rows.append([InlineKeyboardButton(text="Удалить товар", callback_data=f"admin_remove_{product_id}")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data=back_callback, icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cancel_flow_kb(back_callback: str = "admin_home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отменить", callback_data=f"cancel_flow:{back_callback}", icon_custom_emoji_id=BTN_ICON_CANCEL)]]
    )


def proxy_menu_kb(has_proxy: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="Установить / Заменить", callback_data="admin_proxy_set")]]
    if has_proxy:
        rows.append([InlineKeyboardButton(text="Удалить прокси", callback_data="admin_proxy_clear")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def code_keypad_kb(can_submit: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="1", callback_data="code_digit:1"),
            InlineKeyboardButton(text="2", callback_data="code_digit:2"),
            InlineKeyboardButton(text="3", callback_data="code_digit:3"),
        ],
        [
            InlineKeyboardButton(text="4", callback_data="code_digit:4"),
            InlineKeyboardButton(text="5", callback_data="code_digit:5"),
            InlineKeyboardButton(text="6", callback_data="code_digit:6"),
        ],
        [
            InlineKeyboardButton(text="7", callback_data="code_digit:7"),
            InlineKeyboardButton(text="8", callback_data="code_digit:8"),
            InlineKeyboardButton(text="9", callback_data="code_digit:9"),
        ],
        [InlineKeyboardButton(text="0", callback_data="code_digit:0")],
        [
            InlineKeyboardButton(text="Стереть", callback_data="code_backspace"),
            InlineKeyboardButton(text="Очистить", callback_data="code_clear"),
        ],
    ]
    if can_submit:
        rows.append([InlineKeyboardButton(text="Отправить", callback_data="code_submit")])
    rows.append([InlineKeyboardButton(text="Отменить", callback_data="cancel_flow:admin_home", icon_custom_emoji_id=BTN_ICON_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def purchase_waiting_kb(product_id: int, back_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Получить к0d", callback_data=f"request_code:{product_id}")],
            [
                InlineKeyboardButton(text=".session", callback_data=f"user_download_session:{product_id}"),
                InlineKeyboardButton(text="tdata", callback_data=f"user_download_tdata:{product_id}"),
            ],
        ]
    )


def code_received_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Запросить к0d снова", callback_data=f"request_code:{product_id}")],
            [
                InlineKeyboardButton(text=".session", callback_data=f"user_download_session:{product_id}"),
                InlineKeyboardButton(text="tdata", callback_data=f"user_download_tdata:{product_id}"),
            ],
            [InlineKeyboardButton(text="Связаться с поддержкой", url=settings.support_url, icon_custom_emoji_id=BTN_ICON_SUPPORT)],
        ]
    )


def stuck_products_kb(stuck_rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    rows = list(stuck_rows)
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def subscription_kb(channel_url: str) -> InlineKeyboardMarkup:
    url = channel_url if channel_url.startswith("http") else f"https://t.me/{channel_url.lstrip('@')}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться", url=url)],
            [InlineKeyboardButton(text="Проверить", callback_data="check_sub")],
        ]
    )


def admin_countries_available_kb(country_rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    rows = list(country_rows)
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_products_by_country_kb(product_rows: list[list[InlineKeyboardButton]], country: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = list(product_rows)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="<", callback_data=f"admin_stock_country:{country}:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{max(total_pages, 1)}", callback_data="noop"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton(text=">", callback_data=f"admin_stock_country:{country}:{page+1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin_stock_catalog", icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_detail_kb(
    product_id: int,
    back_callback: str = "admin_stock_catalog",
    *,
    can_terminate_sessions: bool = False,
    can_fetch_code: bool = False,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Проверить аккаунт", callback_data=f"admin_verify_account:{product_id}")],
        [InlineKeyboardButton(text="Редактировать", callback_data=f"admin_edit_product:{product_id}")],
        [
            InlineKeyboardButton(text=".session", callback_data=f"admin_download_session:{product_id}"),
            # TData functionality removed
        ],
        [InlineKeyboardButton(text="Забрать со склада", callback_data=f"admin_claim_ask:{product_id}")],
    ]
    if can_fetch_code:
        rows.append([InlineKeyboardButton(text="Получить к0d", callback_data=f"admin_get_code:{product_id}", icon_custom_emoji_id=BTN_ICON_CHECK)])
    if can_terminate_sessions:
        rows.append([InlineKeyboardButton(text="Завершить с3ccuu", callback_data=f"admin_terminate_sessions_ask:{product_id}", icon_custom_emoji_id=BTN_ICON_CANCEL)])
    rows.append([InlineKeyboardButton(text="Удалить товар", callback_data=f"admin_remove_{product_id}", icon_custom_emoji_id=BTN_ICON_CANCEL)])
    rows.append([InlineKeyboardButton(text="Назад", callback_data=back_callback, icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_product_search_results_kb(product_rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    rows = list(product_rows)
    rows.append([InlineKeyboardButton(text="Новый поиск", callback_data="admin_product_search")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_BACK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_terminate_sessions_step1_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, завершить", callback_data=f"admin_terminate_sessions_confirm:{product_id}", icon_custom_emoji_id=BTN_ICON_CANCEL)],
            [InlineKeyboardButton(text="Нет", callback_data=f"admin_stock_product:{product_id}", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )


def admin_terminate_sessions_step2_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, завершить", callback_data=f"admin_terminate_sessions_confirm:{product_id}", icon_custom_emoji_id=BTN_ICON_CANCEL)],
            [InlineKeyboardButton(text="Нет", callback_data=f"admin_stock_product:{product_id}", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )


def admin_claim_confirm_kb(product_id: int, back_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, забрать", callback_data=f"admin_claim:{product_id}:{back_callback}", icon_custom_emoji_id=BTN_ICON_CHECK)],
            [InlineKeyboardButton(text="Нет", callback_data=back_callback, icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )


def admin_user_manage_kb(target_user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Покупки", callback_data=f"admin_user_purchases:{target_user_id}")],
            [InlineKeyboardButton(text="Пополнение баланса", callback_data=f"admin_user_topup:{target_user_id}")],
            [InlineKeyboardButton(text="Обнулить баланс", callback_data=f"admin_user_reset:{target_user_id}")],
            [InlineKeyboardButton(text="Новый поиск", callback_data="admin_user_search")],
            [InlineKeyboardButton(text="Назад", callback_data="admin_home", icon_custom_emoji_id=BTN_ICON_BACK)],
        ]
    )
