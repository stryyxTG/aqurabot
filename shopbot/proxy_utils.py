from __future__ import annotations

import asyncio
import importlib.util
import logging
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from telethon import TelegramClient
from telethon.sessions import MemorySession
from telethon.network.connection.tcpmtproxy import (
    ConnectionTcpMTProxyAbridged,
    ConnectionTcpMTProxyIntermediate,
    ConnectionTcpMTProxyRandomizedIntermediate,
)

logger = logging.getLogger(__name__)

ProxySettings = dict[str, Any]


def parse_proxy_input(raw_value: str) -> ProxySettings:
    value = (raw_value or "").strip()
    if not value:
        raise ValueError("Прокси пустой.")

    lowered = value.lower()
    if "t.me/proxy" in lowered or lowered.startswith("tg://proxy"):
        return _parse_mtproto_url(value)
    if "t.me/socks" in lowered or lowered.startswith("tg://socks"):
        return _parse_socks_url(value)
    if "://" in value:
        return _parse_proxy_url(value)

    parts = [part.strip() for part in value.split(":")]
    if len(parts) == 2:
        host, port = parts
        return {
            "type": "socks5",
            "host": _validate_host(host),
            "port": _validate_port(port),
            "username": None,
            "password": None,
        }

    if len(parts) == 3 and _looks_like_mtproto_secret(parts[2]):
        host, port, secret = parts
        transport = _detect_mtproto_transport(secret)
        return {
            "type": "mtproto",
            "host": _validate_host(host),
            "port": _validate_port(port),
            "secret": _normalize_secret(secret),
            "transport": transport,
        }

    if len(parts) == 4:
        host, port, username, password = parts
        if not username or not password:
            raise ValueError("Логин и пароль прокси не должны быть пустыми.")
        return {
            "type": "socks5",
            "host": _validate_host(host),
            "port": _validate_port(port),
            "username": username,
            "password": password,
        }

    raise ValueError(
        "Не понял формат прокси. Поддерживаются host:port, host:port:login:password, socks5://login:pass@host:port, http://host:port, host:port:secret, t.me/proxy и t.me/socks."
    )


def normalize_proxy_settings(proxy_settings: ProxySettings | None) -> ProxySettings | None:
    if not proxy_settings:
        return None

    proxy_type = str(proxy_settings.get("type") or "").strip().lower()
    if proxy_type not in {"socks5", "socks4", "http", "mtproto"}:
        return None

    host = _validate_host(str(proxy_settings.get("host") or ""))
    port = _validate_port(proxy_settings.get("port"))

    if proxy_type in {"socks5", "socks4", "http"}:
        return {
            "type": proxy_type,
            "host": host,
            "port": port,
            "username": _empty_to_none(proxy_settings.get("username")),
            "password": _empty_to_none(proxy_settings.get("password")),
        }

    secret = _normalize_secret(str(proxy_settings.get("secret") or ""))
    transport = _detect_mtproto_transport(secret)
    return {
        "type": "mtproto",
        "host": host,
        "port": port,
        "secret": secret,
        "transport": transport,
    }


def format_proxy_summary(proxy_settings: ProxySettings | None) -> str:
    proxy = normalize_proxy_settings(proxy_settings)
    if not proxy:
        return "Прокси не задан."

    lines = [
        f"Тип: {proxy['type'].upper() if proxy['type'] != 'mtproto' else 'MTProto'}",
        f"Сервер: {proxy['host']}",
        f"Порт: {proxy['port']}",
    ]
    if proxy['type'] == 'mtproto':
        lines.append(f"Ключ: {mask_secret(proxy['secret'])}")
    elif proxy.get('username'):
        lines.append(f"Логин: {proxy['username']}")
        lines.append("Авторизация: включена")
    else:
        lines.append("Авторизация: не нужна")
    return "\n".join(lines)


def build_telegram_client(
    session_path,
    api_id: int,
    api_hash: str,
    proxy_settings: ProxySettings | None = None,
    *,
    device_model: str = "Samsung Galaxy S24 Ultra",
    system_version: str = "Android 14",
    app_version: str = "11.5.1",
    lang_code: str = "ru",
    system_lang_code: str = "ru-RU",
) -> TelegramClient:
    proxy = normalize_proxy_settings(proxy_settings)
    kwargs: dict[str, Any] = {
        'timeout': 12,
        'request_retries': 1,
        'connection_retries': 1,
        'retry_delay': 1,
        'auto_reconnect': False,
        'device_model': device_model,
        'system_version': system_version,
        'app_version': app_version,
        'lang_code': lang_code,
        'system_lang_code': system_lang_code,
    }
    if proxy:
        if proxy['type'] in {'socks5', 'socks4', 'http'}:
            if not _has_socks_support():
                raise RuntimeError("Для SOCKS/HTTP прокси нужен PySocks или python-socks. Установи зависимости из requirements.txt.")
            kwargs['proxy'] = (proxy['type'], proxy['host'], int(proxy['port']), True, proxy.get('username'), proxy.get('password'))
        elif proxy['type'] == 'mtproto':
            transport = str(proxy.get('transport') or 'intermediate')
            kwargs['connection'] = _mtproto_connection_class(transport)
            secret = proxy['secret']
            if not isinstance(secret, (bytes, bytearray)):
                secret = str(secret).encode('ascii')
            kwargs['proxy'] = (proxy['host'], int(proxy['port']), secret)
    return TelegramClient(str(session_path), api_id=api_id, api_hash=api_hash, **kwargs)


async def check_proxy_connectivity(
    api_id: int,
    api_hash: str,
    proxy_settings: ProxySettings,
    *,
    timeout: int = 20,
    device_model: str = "Samsung Galaxy S24 Ultra",
    system_version: str = "Android 14",
    app_version: str = "11.5.1",
    lang_code: str = "ru",
    system_lang_code: str = "ru-RU",
) -> None:
    proxy = normalize_proxy_settings(proxy_settings)
    if not proxy:
        raise RuntimeError("Прокси не задан.")
    client = TelegramClient(
        MemorySession(),
        api_id=api_id,
        api_hash=api_hash,
        timeout=10,
        request_retries=1,
        connection_retries=1,
        retry_delay=1,
        auto_reconnect=False,
        device_model=device_model,
        system_version=system_version,
        app_version=app_version,
        lang_code=lang_code,
        system_lang_code=system_lang_code,
        **_proxy_kwargs(proxy),
    )
    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=timeout)
        except (OSError, ConnectionError, EOFError, asyncio.IncompleteReadError, asyncio.TimeoutError, ValueError) as exc:
            raise RuntimeError(str(exc) or type(exc).__name__) from exc
        if not client.is_connected():
            raise RuntimeError("Telethon не смог установить соединение через прокси.")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def _proxy_kwargs(proxy: ProxySettings) -> dict[str, Any]:
    if proxy['type'] in {'socks5', 'socks4', 'http'}:
        if not _has_socks_support():
            raise RuntimeError("Для SOCKS/HTTP прокси нужен PySocks или python-socks. Установи зависимости из requirements.txt.")
        return {'proxy': (proxy['type'], proxy['host'], int(proxy['port']), True, proxy.get('username'), proxy.get('password'))}
    if proxy['type'] == 'mtproto':
        transport = str(proxy.get('transport') or 'intermediate')
        secret = proxy['secret']
        if not isinstance(secret, (bytes, bytearray)):
            secret = str(secret).encode('ascii')
        return {
            'connection': _mtproto_connection_class(transport),
            'proxy': (proxy['host'], int(proxy['port']), secret),
        }
    return {}


def _parse_proxy_url(value: str) -> ProxySettings:
    parsed = urlparse(value)
    proxy_type = (parsed.scheme or "").strip().lower()
    if proxy_type not in {"socks5", "socks4", "http"}:
        raise ValueError("Ссылка прокси должна начинаться с socks5://, socks4:// или http://.")
    if not parsed.hostname:
        raise ValueError("В ссылке прокси не указан сервер.")
    return {
        "type": proxy_type,
        "host": _validate_host(parsed.hostname),
        "port": _validate_port(parsed.port),
        "username": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
    }


def _parse_socks_url(value: str) -> ProxySettings:
    parsed = urlparse(value)
    query = parse_qs(parsed.query)

    if parsed.scheme in {"http", "https"}:
        path = parsed.path.strip("/").lower()
        if parsed.netloc.lower() != "t.me" or path != "socks":
            raise ValueError("Ссылка SOCKS должна быть вида t.me/socks или tg://socks.")

    host = query.get("server", [""])[0]
    port = query.get("port", [""])[0]
    username = query.get("user", [""])[0] or query.get("username", [""])[0]
    password = query.get("pass", [""])[0] or query.get("password", [""])[0]
    return {
        "type": "socks5",
        "host": _validate_host(unquote(host)),
        "port": _validate_port(port),
        "username": _empty_to_none(unquote(username)),
        "password": _empty_to_none(unquote(password)),
    }


def _parse_mtproto_url(value: str) -> ProxySettings:
    parsed = urlparse(value)
    query = parse_qs(parsed.query)
    host = _validate_host(query.get("server", [""])[0])
    port = _validate_port(query.get("port", [""])[0])
    secret = _normalize_secret(query.get("secret", [""])[0])
    transport = _detect_mtproto_transport(secret)
    return {"type": "mtproto", "host": host, "port": port, "secret": secret, "transport": transport}


def mask_secret(value: str | None) -> str:
    if not value:
        return "—"
    if len(value) <= 12:
        return value
    return f"{value[:6]}...{value[-6:]}"


def _validate_host(host: str) -> str:
    normalized = (host or "").strip()
    if not normalized:
        raise ValueError("Не указан сервер прокси.")
    return normalized


def _validate_port(port: Any) -> int:
    try:
        value = int(str(port).strip())
    except Exception as exc:
        raise ValueError("Порт прокси должен быть числом.") from exc
    if not 1 <= value <= 65535:
        raise ValueError("Порт прокси должен быть в диапазоне 1-65535.")
    return value


def _normalize_secret(secret: str) -> str:
    normalized = (secret or "").strip()
    if not normalized:
        raise ValueError("Не указан ключ MTProto.")
    return normalized


def _looks_like_mtproto_secret(value: str) -> bool:
    normalized = (value or "").strip().lower()
    return len(normalized) >= 8 and all(ch in '0123456789abcdef' for ch in normalized)


def _detect_mtproto_transport(secret: str) -> str:
    normalized = (secret or "").strip().lower()
    if normalized.startswith("ee"):
        return "fake_tls"
    if normalized.startswith("dd"):
        return "randomized_intermediate"
    return "intermediate"


def _mtproto_connection_class(transport: str):
    if transport == "randomized_intermediate":
        return ConnectionTcpMTProxyRandomizedIntermediate
    if transport == "fake_tls":
        return ConnectionTcpMTProxyAbridged
    return ConnectionTcpMTProxyIntermediate


def _empty_to_none(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _has_socks_support() -> bool:
    return bool(importlib.util.find_spec("python_socks") or importlib.util.find_spec("socks"))
