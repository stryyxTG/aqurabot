from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import DATA_DIR

PROXY_PATH = DATA_DIR / "global_proxy.json"


def load_global_proxy() -> dict[str, Any] | None:
    if not PROXY_PATH.exists():
        return None
    try:
        data = json.loads(PROXY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data or None


def save_global_proxy(proxy_settings: dict[str, Any] | None) -> None:
    if not proxy_settings:
        if PROXY_PATH.exists():
            PROXY_PATH.unlink()
        return
    PROXY_PATH.write_text(json.dumps(proxy_settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
