from __future__ import annotations

import asyncio
import importlib.util
import logging
import time
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
            "rdns": True,
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
            "rdns": True,
        }

    raise ValueError(
        "Не понял формат прокси. Поддерживаются host:port, host:port:login:password, socks5://login:pass@host:port, socks4://host:port, http://host:port, host:port:secret, t.me/proxy и t.me/socks."
    )


def normalize_proxy_settings(proxy_settings: ProxySettings | None) -> ProxySettings | None:
    if not proxy_settings:
        return None

    proxy_type = str(proxy_settings.get("type") or "").strip().lower()
    proxy_type = _normalize_proxy_type(proxy_type)
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
            "rdns": _parse_bool(proxy_settings.get("rdns"), True),
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
    elif proxy['type'] in {'socks5', 'socks4'}:
        lines.append(f"DNS через прокси: {'да' if proxy.get('rdns', True) else 'нет'}")
        if proxy.get('username'):
            lines.append(f"Логин: {proxy['username']}")
            lines.append("Авторизация: включена")
        else:
            lines.append("Авторизация: не нужна")
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
    device_model: str = "Desktop",
    system_version: str = "Windows 11",
    app_version: str = "6.9.3 x64",
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
            kwargs['proxy'] = _pysocks_proxy_tuple(proxy)
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
    device_model: str = "Desktop",
    system_version: str = "Windows 11",
    app_version: str = "6.9.3 x64",
    lang_code: str = "ru",
    system_lang_code: str = "ru-RU",
) -> dict[str, Any]:
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
            started_at = time.perf_counter()
            await asyncio.wait_for(client.connect(), timeout=timeout)
        except (OSError, ConnectionError, EOFError, asyncio.IncompleteReadError, asyncio.TimeoutError, ValueError) as exc:
            raise RuntimeError(str(exc) or type(exc).__name__) from exc
        if not client.is_connected():
            raise RuntimeError("Telethon не смог установить соединение через прокси.")
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return {"ok": True, "latency_ms": latency_ms}
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


def _proxy_kwargs(proxy: ProxySettings) -> dict[str, Any]:
    if proxy['type'] in {'socks5', 'socks4', 'http'}:
        return {'proxy': _pysocks_proxy_tuple(proxy)}
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
    proxy_type = _normalize_proxy_type((parsed.scheme or "").strip().lower())
    if proxy_type not in {"socks5", "socks4", "http"}:
        raise ValueError("Ссылка прокси должна начинаться с socks5://, socks4://, http:// или https://.")
    if not parsed.hostname:
        raise ValueError("В ссылке прокси не указан сервер.")
    query = parse_qs(parsed.query)
    return {
        "type": proxy_type,
        "host": _validate_host(parsed.hostname),
        "port": _validate_port(parsed.port),
        "username": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
        "rdns": _parse_bool(query.get("rdns", [None])[0], True),
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
        "rdns": True,
    }


def _parse_mtproto_url(value: str) -> ProxySettings:
    parsed = urlparse(value)
    query = parse_qs(parsed.query)
    host = _validate_host(query.get("server", [""])[0])
    port = _validate_port(query.get("port", [""])[0])
    secret = _normalize_secret(query.get("secret", [""])[0])
    transport = _detect_mtproto_transport(secret)
    return {"type": "mtproto", "host": host, "port": port, "secret": secret, "transport": transport}


def _normalize_proxy_type(proxy_type: str) -> str:
    normalized = (proxy_type or "").strip().lower()
    if normalized in {"socks", "socks5h"}:
        return "socks5"
    if normalized == "socks4a":
        return "socks4"
    if normalized == "https":
        return "http"
    return normalized


def _pysocks_proxy_tuple(proxy: ProxySettings) -> tuple:
    socks_module = _load_socks_module()
    proxy_type = proxy["type"]
    proxy_type_map = {
        "socks5": socks_module.SOCKS5,
        "socks4": socks_module.SOCKS4,
        "http": socks_module.HTTP,
    }
    if proxy_type not in proxy_type_map:
        raise RuntimeError(f"Неподдерживаемый тип прокси: {proxy_type}")
    return (
        proxy_type_map[proxy_type],
        proxy["host"],
        int(proxy["port"]),
        bool(proxy.get("rdns", True)),
        proxy.get("username"),
        proxy.get("password"),
    )


def _load_socks_module():
    if not _has_socks_support():
        raise RuntimeError("Для SOCKS/HTTP прокси нужен PySocks. Установи зависимости из requirements.txt.")
    try:
        import socks
    except Exception as exc:
        raise RuntimeError("PySocks установлен некорректно. Переустанови зависимости из requirements.txt.") from exc
    return socks


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


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "да"}


def _has_socks_support() -> bool:
    return bool(importlib.util.find_spec("socks"))
