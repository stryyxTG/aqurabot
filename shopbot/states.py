from aiogram.fsm.state import State, StatesGroup


class AdminAddProductStates(StatesGroup):
    waiting_add_method = State()  # Выбор: номер+код или файл сессии
    waiting_session_file = State()  # Загрузка одного .session файла
    waiting_bulk_sessions = State()  # Загрузка нескольких .session файлов
    waiting_bulk_password = State()  # Общий пароль 2FA для всех сессий
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()
    waiting_country = State()
    waiting_country_search = State()
    waiting_department = State()
    waiting_title = State()
    waiting_price = State()
    waiting_description = State()
    waiting_extra_code = State()


class AdminTopUpStates(StatesGroup):
    waiting_user_id = State()
    waiting_amount = State()


class AdminProxyStates(StatesGroup):
    waiting_proxy_input = State()


class AdminCardsStates(StatesGroup):
    waiting_cards_text = State()


class AdminCatalogStates(StatesGroup):
    waiting_country_name = State()
    waiting_country_rename = State()
    waiting_country_rename_icon = State()
    waiting_department_title = State()
    waiting_department_price = State()
    waiting_department_description = State()
    waiting_department_extra_code = State()

class AdminEditProductStates(StatesGroup):
    waiting_new_value = State()


class AdminEditProductGroupStates(StatesGroup):
    waiting_new_value = State()

class AdminSearchUserStates(StatesGroup):
    waiting_user_query = State()

class AdminSearchProductStates(StatesGroup):
    waiting_product_query = State()

class AdminDropsStates(StatesGroup):
    waiting_user_id = State()

class UserTopUpStates(StatesGroup):
    waiting_amount = State()
    waiting_receipt = State()


class UserCartStates(StatesGroup):
    waiting_group_quantity = State()


class UserCatalogStates(StatesGroup):
    waiting_country_query = State()
    waiting_product_filter = State()


class ServiceOrderStates(StatesGroup):
    waiting_recipient = State()


class AdminScanStates(StatesGroup):
    waiting_interval = State()
    waiting_limit = State()


class AdminBroadcastStates(StatesGroup):
    waiting_text = State()


class AdminCleanStates(StatesGroup):
    waiting_action = State()
    waiting_confirm = State()
