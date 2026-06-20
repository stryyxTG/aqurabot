from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RUNTIME_DIR = DATA_DIR / "runtime"
LOG_DIR = ROOT_DIR / "logs"
SESSIONS_DIR = DATA_DIR / "sessions"
USER_RUNTIME_DIR = RUNTIME_DIR / "users"
DB_PATH = DATA_DIR / "shop.db"

for path in (DATA_DIR, RUNTIME_DIR, LOG_DIR, SESSIONS_DIR, USER_RUNTIME_DIR):
    path.mkdir(parents=True, exist_ok=True)


def admin_user_dir(admin_id: int) -> Path:
    path = USER_RUNTIME_DIR / str(admin_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def admin_sessions_dir(admin_id: int) -> Path:
    path = admin_user_dir(admin_id) / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def temp_session_base_path(admin_id: int, login_id: str) -> Path:
    return admin_sessions_dir(admin_id) / f"temp_session_{admin_id}_{login_id}"


def product_session_base_path(product_id: int) -> Path:
    return SESSIONS_DIR / f"product_{product_id}"
