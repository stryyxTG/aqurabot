from __future__ import annotations

from .proxy_utils import build_telegram_client as _build_telegram_client


def build_telegram_client(session_base, api_id: int, api_hash: str, proxy_settings=None):
    return _build_telegram_client(session_base, api_id, api_hash, proxy_settings)
