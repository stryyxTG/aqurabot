from __future__ import annotations
import json
import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.local.json"
EXAMPLE_CONFIG_PATH = ROOT_DIR / "config.local.example.json"


@dataclass(slots=True)
class Settings:
    bot_token: str
    admin_ids: set[int]
    api_id: int
    api_hash: str
    cryptopay_token: str = ""
    shop_title: str = "Telegram Account Shop"
    currency: str = "$"
    cryptopay_fiat: str = "USD"
    log_channel_id: int = -1003630251872
    ru_topup_chat_id: int = -1003721340861
    ua_topup_chat_id: int = -1004292812805
    support_username: str = "@Ghost_Aura"
    support_url: str = ""
    reviews_url: str = "https://t.me/c/4296916422/2"
    require_proxy_for_login: bool = False
    required_channel: str = "-1004296916422"
    required_channel_url: str = "https://t.me/+5wYNfVbpXJo2YzIy"
    rub_to_uah_rate: float = 0.45
    device_model: str = "Samsung Galaxy S24 Ultra"
    system_version: str = "Android 14"
    app_version: str = "11.5.1"
    lang_code: str = "ru"
    system_lang_code: str = "ru-RU"

    @property
    def primary_admin_id(self) -> int:
        return next(iter(self.admin_ids))


def _load_raw_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def load_settings() -> Settings:
    raw = _load_raw_config()
    bot_token = (os.getenv("BOT_TOKEN") or raw.get("BOT_TOKEN") or "").strip()
    admin_ids_raw = raw.get("ADMIN_IDS") or os.getenv("ADMIN_IDS") or []
    if isinstance(admin_ids_raw, str):
        admin_ids = {int(item.strip()) for item in admin_ids_raw.split(",") if item.strip().isdigit()}
    else:
        admin_ids = {int(item) for item in admin_ids_raw}

    api_id = int(os.getenv("API_ID") or raw.get("API_ID") or 0)
    api_hash = (os.getenv("API_HASH") or raw.get("API_HASH") or "").strip()
    cryptopay_token = (os.getenv("CRYPTOPAY_TOKEN") or raw.get("CRYPTOPAY_TOKEN") or "").strip()
    shop_title = (os.getenv("SHOP_TITLE") or raw.get("SHOP_TITLE") or "Telegram Account Shop").strip()
    currency = (os.getenv("CURRENCY") or raw.get("CURRENCY") or "$").strip()
    cryptopay_fiat = (os.getenv("CRYPTOPAY_FIAT") or raw.get("CRYPTOPAY_FIAT") or "USD").strip().upper()
    log_channel_id = _parse_int(os.getenv("LOG_CHANNEL_ID") or raw.get("LOG_CHANNEL_ID"), -1003630251872)
    ru_topup_chat_id = _parse_int(os.getenv("RU_TOPUP_CHAT_ID") or raw.get("RU_TOPUP_CHAT_ID"), -1003721340861)
    ua_topup_chat_id = _parse_int(os.getenv("UA_TOPUP_CHAT_ID") or raw.get("UA_TOPUP_CHAT_ID"), -1004292812805)
    support_username = (os.getenv("SUPPORT_USERNAME") or raw.get("SUPPORT_USERNAME") or "@Ghost_Aura").strip()
    support_url = _telegram_profile_url(os.getenv("SUPPORT_URL") or raw.get("SUPPORT_URL") or support_username)
    reviews_url = (os.getenv("REVIEWS_URL") or raw.get("REVIEWS_URL") or "https://t.me/c/4296916422/2").strip()
    require_proxy_for_login = _parse_bool(os.getenv("REQUIRE_PROXY_FOR_LOGIN") or raw.get("REQUIRE_PROXY_FOR_LOGIN"), False)
    required_channel = (os.getenv("REQUIRED_CHANNEL") or raw.get("REQUIRED_CHANNEL") or "-1004296916422").strip()
    required_channel_url = (
        os.getenv("REQUIRED_CHANNEL_URL")
        or raw.get("REQUIRED_CHANNEL_URL")
        or "https://t.me/+5wYNfVbpXJo2YzIy"
    ).strip()
    rub_to_uah_rate = _parse_float(os.getenv("RUB_TO_UAH_RATE") or raw.get("RUB_TO_UAH_RATE"), 0.45)
    device_model = (os.getenv("TG_DEVICE_MODEL") or raw.get("TG_DEVICE_MODEL") or "Samsung Galaxy S24 Ultra").strip()
    system_version = (os.getenv("TG_SYSTEM_VERSION") or raw.get("TG_SYSTEM_VERSION") or "Android 14").strip()
    app_version = (os.getenv("TG_APP_VERSION") or raw.get("TG_APP_VERSION") or "11.5.1").strip()
    lang_code = (os.getenv("TG_LANG_CODE") or raw.get("TG_LANG_CODE") or "ru").strip()
    system_lang_code = (os.getenv("TG_SYSTEM_LANG_CODE") or raw.get("TG_SYSTEM_LANG_CODE") or "ru-RU").strip()

    missing = []
    if not bot_token:
        missing.append("BOT_TOKEN")
    if not admin_ids:
        missing.append("ADMIN_IDS")
    if not api_id:
        missing.append("API_ID")
    if not api_hash:
        missing.append("API_HASH")
    if missing:
        raise RuntimeError(
            "Missing config values: " + ", ".join(missing) + f". Fill {CONFIG_PATH.name} using {EXAMPLE_CONFIG_PATH.name}."
        )

    return Settings(
        bot_token=bot_token,
        admin_ids=admin_ids,
        api_id=api_id,
        api_hash=api_hash,
        cryptopay_token=cryptopay_token,
        shop_title=shop_title,
        currency=currency,
        cryptopay_fiat=cryptopay_fiat,
        log_channel_id=log_channel_id,
        ru_topup_chat_id=ru_topup_chat_id,
        ua_topup_chat_id=ua_topup_chat_id,
        support_username=support_username,
        support_url=support_url,
        reviews_url=reviews_url,
        require_proxy_for_login=require_proxy_for_login,
        required_channel=required_channel,
        required_channel_url=required_channel_url,
        rub_to_uah_rate=rub_to_uah_rate,
        device_model=device_model,
        system_version=system_version,
        app_version=app_version,
        lang_code=lang_code,
        system_lang_code=system_lang_code,
    )


def _parse_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "да"}


def _parse_float(value, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(str(value).replace(",", ".").strip())
    except Exception:
        return default
    return parsed if parsed > 0 else default


def _parse_int(value, default: int) -> int:
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _telegram_profile_url(value: str | None) -> str:
    raw_value = (value or "").strip()
    if not raw_value:
        return ""
    if raw_value.startswith(("https://", "http://", "tg://")):
        return raw_value
    return f"https://t.me/{raw_value.lstrip('@')}"
