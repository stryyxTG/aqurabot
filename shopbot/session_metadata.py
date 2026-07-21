from __future__ import annotations

import json
import random
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DESKTOP_PROFILES = [
    ("Desktop", "Windows 10"),
    ("Desktop", "Windows 11"),
    ("PC", "Windows 10"),
    ("PC", "Windows 11"),
    ("Laptop", "Windows 10"),
    ("Laptop", "Windows 11"),
    ("Workstation", "Windows 11"),
    ("ThinkPad X1 Carbon", "Windows 11"),
    ("ThinkPad T14", "Windows 10"),
    ("Dell XPS 13", "Windows 11"),
    ("Dell XPS 15", "Windows 11"),
    ("Dell Latitude 7420", "Windows 10"),
    ("HP EliteBook 840", "Windows 11"),
    ("HP ProBook 450", "Windows 10"),
    ("Surface Laptop", "Windows 11"),
    ("Surface Pro", "Windows 11"),
    ("ASUS ZenBook", "Windows 11"),
    ("ASUS ROG Zephyrus", "Windows 11"),
    ("Lenovo Legion", "Windows 11"),
    ("Acer Aspire", "Windows 10"),
    ("MSI Modern", "Windows 11"),
]

DESKTOP_APP_VERSIONS = [
    "6.9.3 x64",
]


def session_json_path(session_path: str | Path) -> Path:
    path = Path(session_path)
    if path.suffix == ".session":
        return path.with_suffix(".json")
    return Path(f"{path}.json")


def session_original_json_path(session_path: str | Path) -> Path:
    path = Path(session_path)
    if path.suffix == ".session":
        return path.with_suffix(".original.json")
    return Path(f"{path}.original.json")


def normalize_match_key(value: object) -> str:
    text = Path(str(value or "")).stem.casefold()
    text = re.sub(r"(?:\.session|\.json)$", "", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def match_key_candidates(value: object) -> set[str]:
    text = str(value or "")
    normalized = normalize_match_key(text)
    keys = {normalized} if normalized else set()
    for digits in re.findall(r"\d{5,}", Path(text).stem):
        keys.add(digits)
    return keys


def metadata_match_keys(file_name: str | Path, metadata: dict[str, Any] | None = None) -> set[str]:
    keys = match_key_candidates(file_name)
    metadata = metadata or {}
    for key in ("phone", "user_id", "telegram_id", "id", "session_file", "session"):
        value = metadata.get(key)
        if value:
            keys.update(match_key_candidates(value))
    return {key for key in keys if key}


def random_desktop_profile() -> dict[str, Any]:
    device_model, system_version = random.choice(DESKTOP_PROFILES)
    return {
        "device_model": device_model,
        "system_version": system_version,
        "app_version": random.choice(DESKTOP_APP_VERSIONS),
        "lang_code": "en",
        "system_lang_code": "en-US",
        "lang_pack": "tdesktop",
    }


def _first_value(raw: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = raw.get(key)
        if value not in (None, ""):
            return value
    return None


def _usable_api_secret(value: Any) -> bool:
    if value in (None, ""):
        return False
    if isinstance(value, str) and value.strip().casefold() in {"null", "none"}:
        return False
    return True


def _first_api_secret(raw: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = raw.get(key)
        if _usable_api_secret(value):
            return value
    return None


def _flatten_common_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in ("app", "client", "telegram", "telethon", "authorization", "account"):
        value = raw.get(key)
        if isinstance(value, dict):
            merged.update(value)
    merged.update(raw)
    return merged


def normalize_session_metadata(
    raw: dict[str, Any] | None,
    *,
    default_api_id: int,
    default_api_hash: str,
    fallback_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = _flatten_common_metadata(raw or {})
    profile = dict(fallback_profile or random_desktop_profile())

    api_id = _first_value(raw, "api_id", "app_id", "apiId", "appId")
    api_hash = _first_api_secret(raw, "api_hash", "app_hash", "apiHash", "appHash")
    try:
        api_id = int(api_id) if api_id else int(default_api_id)
    except Exception:
        api_id = int(default_api_id)

    profile.update(
        {
            "api_id": api_id,
            "api_hash": str(api_hash or default_api_hash),
            "device_model": str(_first_value(raw, "device_model", "deviceModel", "device") or profile["device_model"]),
            "system_version": str(_first_value(raw, "system_version", "systemVersion", "sdk") or profile["system_version"]),
            "app_version": str(_first_value(raw, "app_version", "appVersion") or profile["app_version"]),
            "lang_code": "en",
            "system_lang_code": "en-US",
            "lang_pack": "tdesktop",
        }
    )

    optional_map = {
        "phone": ("phone", "phone_number"),
        "user_id": ("user_id", "telegram_id", "id"),
        "username": ("username",),
        "first_name": ("first_name", "firstName"),
        "last_name": ("last_name", "lastName"),
        "twofa_password": ("twofa_password", "twoFA", "twofa", "password", "cloud_password"),
        "session_file": ("session_file", "session"),
    }
    for target_key, aliases in optional_map.items():
        value = _first_value(raw, *aliases)
        if value not in (None, ""):
            profile[target_key] = value

    if "created_at" not in profile:
        profile["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return profile


def serialize_session_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(metadata)
    api_id = serialized.pop("api_id", None)
    if api_id not in (None, "") and "app_id" not in serialized:
        serialized["app_id"] = api_id
    api_hash = serialized.pop("api_hash", None)
    app_hash = serialized.get("app_hash")
    if _usable_api_secret(app_hash):
        serialized["app_hash"] = str(app_hash)
    elif _usable_api_secret(api_hash):
        serialized["app_hash"] = str(api_hash)
    else:
        serialized.pop("app_hash", None)
    device_model = serialized.pop("device_model", None)
    if device_model not in (None, "") and "device" not in serialized:
        serialized["device"] = device_model
    system_version = serialized.pop("system_version", None)
    if system_version not in (None, "") and "sdk" not in serialized:
        serialized["sdk"] = system_version
    twofa_password = serialized.pop("twofa_password", None)
    if "twoFA" not in serialized:
        serialized["twoFA"] = twofa_password if twofa_password not in (None, "") else None
    return serialized


def load_metadata_file(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_session_metadata(
    session_path: str | Path,
    *,
    default_api_id: int,
    default_api_hash: str,
) -> dict[str, Any]:
    path = session_json_path(session_path)
    raw = load_metadata_file(path) if path.exists() else {}
    return normalize_session_metadata(raw, default_api_id=default_api_id, default_api_hash=default_api_hash)


def write_session_metadata(
    session_path: str | Path,
    metadata: dict[str, Any] | None,
    *,
    default_api_id: int,
    default_api_hash: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    normalized = normalize_session_metadata(
        metadata,
        default_api_id=default_api_id,
        default_api_hash=default_api_hash,
    )
    if extra:
        normalized.update({key: value for key, value in extra.items() if value not in (None, "")})
    path = session_json_path(session_path)
    path.write_text(json.dumps(serialize_session_metadata(normalized), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_original_session_json(session_path: str | Path, content: str | bytes) -> Path:
    path = session_original_json_path(session_path)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_bytes(content.encode("utf-8"))
    return path


def copy_session_metadata(source_session_path: str | Path, target_session_path: str | Path) -> Path | None:
    source = session_json_path(source_session_path)
    copied: Path | None = None
    if source.exists():
        target = session_json_path(target_session_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied = target
    original_source = session_original_json_path(source_session_path)
    if original_source.exists():
        original_target = session_original_json_path(target_session_path)
        original_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original_source, original_target)
        copied = original_target
    return copied
