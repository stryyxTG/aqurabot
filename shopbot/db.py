from __future__ import annotations
import logging
import uuid
import aiosqlite
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import DB_PATH, product_session_base_path

logger = logging.getLogger(__name__)
MONEY_EPSILON = 0.000001


def normalize_money(value: float) -> float:
    value = round(float(value), 8)
    return 0.0 if abs(value) < MONEY_EPSILON else value


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@asynccontextmanager
async def get_db_conn():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.execute("PRAGMA busy_timeout=30000")
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    async with get_db_conn() as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance REAL NOT NULL DEFAULT 0,
                joined_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                agreement_accepted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                country TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT,
                extra_code TEXT,
                session_path TEXT NOT NULL,
                phone TEXT,
                telegram_id INTEGER,
                username TEXT,
                first_name TEXT,
                twofa_password TEXT,
                status TEXT NOT NULL DEFAULT 'available',
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                sold_to INTEGER,
                sold_at TEXT,
                sold_price REAL,
                purchase_started_at TEXT,
                skip_session_cleanup INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                price REAL NOT NULL,
                batch_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(product_id) REFERENCES products(product_id)
            );

            CREATE TABLE IF NOT EXISTS cart_items (
                cart_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                added_at TEXT NOT NULL,
                UNIQUE(user_id, product_id),
                FOREIGN KEY(product_id) REFERENCES products(product_id)
            );

            CREATE TABLE IF NOT EXISTS balance_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                kind TEXT NOT NULL,
                note TEXT,
                actor_id INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS catalog_countries (
                country_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon_custom_emoji_id TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS catalog_departments (
                department_id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                price REAL NOT NULL,
                description TEXT,
                extra_code TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                UNIQUE(country_id, title, price),
                FOREIGN KEY(country_id) REFERENCES catalog_countries(country_id)
            );

            CREATE TABLE IF NOT EXISTS removed_product_departments (
                department_id INTEGER PRIMARY KEY AUTOINCREMENT,
                country TEXT NOT NULL,
                title TEXT NOT NULL,
                price REAL NOT NULL,
                removed_by INTEGER,
                removed_at TEXT NOT NULL,
                UNIQUE(country, title, price)
            );

            CREATE TABLE IF NOT EXISTS crypto_payments (
                invoice_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                processed_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS crypto_invoices (
                invoice_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                fiat TEXT NOT NULL,
                pay_url TEXT,
                status TEXT NOT NULL DEFAULT 'created',
                created_at TEXT NOT NULL,
                paid_at TEXT,
                processed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS topup_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                method TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                credit_amount REAL NOT NULL DEFAULT 0,
                receipt_type TEXT NOT NULL,
                receipt_file_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                reviewed_by INTEGER,
                reviewed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS topup_reviewers (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER NOT NULL,
                added_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS service_orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                service_type TEXT NOT NULL,
                service_label TEXT NOT NULL,
                recipient TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                reviewed_by INTEGER,
                reviewed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS channel_join_requests (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                chat_username TEXT,
                invite_link TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        async with db.execute("PRAGMA table_info(catalog_countries)") as cursor:
            catalog_country_columns = {row["name"] for row in await cursor.fetchall()}
        if "icon_custom_emoji_id" not in catalog_country_columns:
            await db.execute("ALTER TABLE catalog_countries ADD COLUMN icon_custom_emoji_id TEXT")
            logger.info("Добавлена колонка icon_custom_emoji_id в таблицу catalog_countries")

        await db.execute(
            """
            INSERT INTO catalog_countries (name, icon_custom_emoji_id, is_active, created_at)
            SELECT DISTINCT country, NULL, 1, ?
            FROM products
            WHERE TRIM(country) != ''
            ON CONFLICT(name) DO NOTHING
            """,
            (utcnow(),),
        )

        async with db.execute("PRAGMA table_info(products)") as cursor:
            product_columns = {row["name"] for row in await cursor.fetchall()}
        if "purchase_started_at" not in product_columns:
            await db.execute("ALTER TABLE products ADD COLUMN purchase_started_at TEXT")
        if "code_fetched_at" not in product_columns:
            await db.execute("ALTER TABLE products ADD COLUMN code_fetched_at TEXT")
            logger.info("Добавлена колонка code_fetched_at в таблицу products")
        if "skip_session_cleanup" not in product_columns:
            await db.execute("ALTER TABLE products ADD COLUMN skip_session_cleanup INTEGER NOT NULL DEFAULT 0")
            logger.info("Добавлена колонка skip_session_cleanup в таблицу products")

        async with db.execute("PRAGMA table_info(users)") as cursor:
            user_columns = {row["name"] for row in await cursor.fetchall()}
        if "agreement_accepted_at" not in user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN agreement_accepted_at TEXT")
            logger.info("Добавлена колонка agreement_accepted_at в таблицу users")

        async with db.execute("PRAGMA table_info(purchases)") as cursor:
            purchase_columns = {row["name"] for row in await cursor.fetchall()}
        if "batch_id" not in purchase_columns:
            await db.execute("ALTER TABLE purchases ADD COLUMN batch_id TEXT")
            await db.execute("UPDATE purchases SET batch_id = CAST(purchase_id AS TEXT) WHERE batch_id IS NULL OR TRIM(batch_id) = ''")
            logger.info("Добавлена колонка batch_id в таблицу purchases")
        
        async with db.execute("PRAGMA table_info(topup_requests)") as cursor:
            topup_columns = {row["name"] for row in await cursor.fetchall()}
        if topup_columns and "credit_amount" not in topup_columns:
            await db.execute("ALTER TABLE topup_requests ADD COLUMN credit_amount REAL NOT NULL DEFAULT 0")
            await db.execute("UPDATE topup_requests SET credit_amount = amount WHERE credit_amount = 0")
            logger.info("Добавлена колонка credit_amount в таблицу topup_requests")

        async with db.execute("PRAGMA table_info(service_orders)") as cursor:
            service_order_columns = {row["name"] for row in await cursor.fetchall()}
        if service_order_columns and "reviewed_by" not in service_order_columns:
            await db.execute("ALTER TABLE service_orders ADD COLUMN reviewed_by INTEGER")
        if service_order_columns and "reviewed_at" not in service_order_columns:
            await db.execute("ALTER TABLE service_orders ADD COLUMN reviewed_at TEXT")

        async with db.execute("PRAGMA table_info(channel_join_requests)") as cursor:
            join_request_columns = {row["name"] for row in await cursor.fetchall()}
        if join_request_columns and "status" not in join_request_columns:
            await db.execute("ALTER TABLE channel_join_requests ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
        if join_request_columns and "updated_at" not in join_request_columns:
            await db.execute("ALTER TABLE channel_join_requests ADD COLUMN updated_at TEXT")
            await db.execute("UPDATE channel_join_requests SET updated_at = requested_at WHERE updated_at IS NULL")
        
        await db.commit()


async def record_channel_join_request(
    user_id: int,
    chat_id: int,
    chat_username: str | None,
    invite_link: str | None,
) -> None:
    async with get_db_conn() as db:
        now = utcnow()
        await db.execute(
            """
            INSERT INTO channel_join_requests (user_id, chat_id, chat_username, invite_link, status, requested_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                chat_username = excluded.chat_username,
                invite_link = excluded.invite_link,
                status = 'pending',
                requested_at = excluded.requested_at,
                updated_at = excluded.updated_at
            """,
            (user_id, chat_id, chat_username or "", invite_link or "", now, now),
        )
        await db.commit()


async def record_channel_member(
    user_id: int,
    chat_id: int,
    chat_username: str | None,
    status: str = "joined",
) -> None:
    async with get_db_conn() as db:
        now = utcnow()
        await db.execute(
            """
            INSERT INTO channel_join_requests (user_id, chat_id, chat_username, invite_link, status, requested_at, updated_at)
            VALUES (?, ?, ?, '', ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                chat_username = excluded.chat_username,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (user_id, chat_id, chat_username or "", status, now, now),
        )
        await db.commit()


async def get_channel_join_request(user_id: int):
    async with get_db_conn() as db:
        async with db.execute("SELECT * FROM channel_join_requests WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def has_channel_join_request(user_id: int) -> bool:
    return await get_channel_join_request(user_id) is not None


async def update_channel_join_status(user_id: int, status: str) -> None:
    async with get_db_conn() as db:
        await db.execute(
            "UPDATE channel_join_requests SET status = ?, updated_at = ? WHERE user_id = ?",
            (status, utcnow(), user_id),
        )
        await db.commit()


async def remove_channel_join_request(user_id: int) -> None:
    async with get_db_conn() as db:
        await db.execute("DELETE FROM channel_join_requests WHERE user_id = ?", (user_id,))
        await db.commit()


async def get_app_meta(key: str) -> str | None:
    async with get_db_conn() as db:
        async with db.execute("SELECT value FROM app_meta WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row["value"] if row else None


async def set_app_meta(key: str, value: str) -> None:
    async with get_db_conn() as db:
        await db.execute(
            """
            INSERT INTO app_meta (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        await db.commit()


async def upsert_user(user_id: int, username: str | None, first_name: str | None) -> None:
    now = utcnow()
    async with get_db_conn() as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, first_name, joined_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_seen_at = excluded.last_seen_at
            """,
            (user_id, username or "", first_name or "", now, now),
        )
        await db.commit()


async def get_user(user_id: int):
    async with get_db_conn() as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()


async def has_user_accepted_agreement(user_id: int) -> bool:
    async with get_db_conn() as db:
        async with db.execute("SELECT agreement_accepted_at FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row and (row["agreement_accepted_at"] or "").strip())


async def accept_user_agreement(user_id: int) -> None:
    async with get_db_conn() as db:
        now = utcnow()
        await db.execute(
            """
            INSERT INTO users (user_id, username, first_name, joined_at, last_seen_at, agreement_accepted_at)
            VALUES (?, '', '', ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                agreement_accepted_at = COALESCE(users.agreement_accepted_at, excluded.agreement_accepted_at)
            """,
            (user_id, now, now, now),
        )
        await db.commit()


async def list_user_ids() -> list[int]:
    async with get_db_conn() as db:
        async with db.execute("SELECT user_id FROM users ORDER BY joined_at ASC") as cursor:
            rows = await cursor.fetchall()
            return [int(row["user_id"]) for row in rows]


async def get_balance(user_id: int) -> float:
    row = await get_user(user_id)
    return float(row["balance"]) if row else 0.0


async def add_balance(user_id: int, amount: float, kind: str, note: str, actor_id: int | None = None) -> float:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
        current = float(row["balance"]) if row else 0.0
        new_balance = normalize_money(current + amount)
        if row:
            await db.execute(
                "UPDATE users SET balance = ?, last_seen_at = ? WHERE user_id = ?",
                (new_balance, utcnow(), user_id),
            )
        else:
            await db.execute(
                "INSERT INTO users (user_id, username, first_name, balance, joined_at, last_seen_at) VALUES (?, '', '', ?, ?, ?)",
                (user_id, new_balance, utcnow(), utcnow()),
            )
        await db.execute(
            "INSERT INTO balance_events (user_id, amount, kind, note, actor_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, amount, kind, note, actor_id, utcnow()),
        )
        await db.commit()
        return new_balance


async def create_service_order_with_charge(
    *,
    user_id: int,
    username: str | None,
    first_name: str | None,
    service_type: str,
    service_label: str,
    recipient: str,
    quantity: int,
    amount: float,
) -> tuple[bool, float, int | None]:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if not user:
            await db.rollback()
            return False, 0.0, None
        balance = float(user["balance"])
        if balance + MONEY_EPSILON < amount:
            await db.rollback()
            return False, balance, None
        new_balance = normalize_money(balance - amount)
        now = utcnow()
        await db.execute("UPDATE users SET balance = ?, last_seen_at = ? WHERE user_id = ?", (new_balance, now, user_id))
        await db.execute(
            "INSERT INTO balance_events (user_id, amount, kind, note, actor_id, created_at) VALUES (?, ?, 'service_order', ?, NULL, ?)",
            (user_id, -amount, service_label, now),
        )
        async with db.execute(
            """
            INSERT INTO service_orders (
                user_id, username, first_name, service_type, service_label,
                recipient, quantity, amount, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            RETURNING order_id
            """,
            (user_id, username, first_name, service_type, service_label, recipient, quantity, amount, now),
        ) as cursor:
            row = await cursor.fetchone()
        await db.commit()
        return True, new_balance, int(row["order_id"])


async def get_service_order(order_id: int):
    async with get_db_conn() as db:
        async with db.execute("SELECT * FROM service_orders WHERE order_id = ?", (order_id,)) as cursor:
            return await cursor.fetchone()


async def approve_service_order(order_id: int, reviewer_id: int) -> tuple[bool, str, float | None, int | None]:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM service_orders WHERE order_id = ?", (order_id,)) as cursor:
            order = await cursor.fetchone()
        if not order:
            await db.rollback()
            return False, "not_found", None, None
        if order["status"] != "pending":
            await db.rollback()
            return False, order["status"], float(order["amount"]), int(order["user_id"])

        await db.execute(
            "UPDATE service_orders SET status = 'delivered', reviewed_by = ?, reviewed_at = ? WHERE order_id = ?",
            (reviewer_id, utcnow(), order_id),
        )
        await db.commit()
        return True, "delivered", float(order["amount"]), int(order["user_id"])


async def reject_service_order(order_id: int, reviewer_id: int) -> tuple[bool, str, float | None, int | None, float | None]:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM service_orders WHERE order_id = ?", (order_id,)) as cursor:
            order = await cursor.fetchone()
        if not order:
            await db.rollback()
            return False, "not_found", None, None, None
        if order["status"] != "pending":
            await db.rollback()
            return False, order["status"], float(order["amount"]), int(order["user_id"]), None

        amount = float(order["amount"])
        user_id = int(order["user_id"])
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if user:
            new_balance = float(user["balance"]) + amount
            await db.execute(
                "UPDATE users SET balance = ?, last_seen_at = ? WHERE user_id = ?",
                (new_balance, utcnow(), user_id),
            )
        else:
            new_balance = amount
            await db.execute(
                "INSERT INTO users (user_id, username, first_name, balance, joined_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, order["username"] or "", order["first_name"] or "", new_balance, utcnow(), utcnow()),
            )
        await db.execute(
            "INSERT INTO balance_events (user_id, amount, kind, note, actor_id, created_at) VALUES (?, ?, 'service_refund', ?, ?, ?)",
            (user_id, amount, f"Возврат по заявке #{order_id}: {order['service_label']}", reviewer_id, utcnow()),
        )
        await db.execute(
            "UPDATE service_orders SET status = 'rejected', reviewed_by = ?, reviewed_at = ? WHERE order_id = ?",
            (reviewer_id, utcnow(), order_id),
        )
        await db.commit()
        return True, "rejected", amount, user_id, new_balance


async def create_product(*, title: str, country: str, price: float, description: str, extra_code: str, session_path: str, phone: str, telegram_id: int | None, username: str, first_name: str, twofa_password: str, created_by: int) -> int:
    async with get_db_conn() as db:
        await db.execute(
            "DELETE FROM removed_product_departments WHERE country = ? AND title = ? AND price = ?",
            (country, title, price),
        )
        async with db.execute(
            "SELECT country_id FROM catalog_countries WHERE name = ? AND is_active = 1",
            (country,),
        ) as cursor:
            catalog_country = await cursor.fetchone()
        if catalog_country:
            await db.execute(
                """
                INSERT INTO catalog_departments (
                    country_id, title, price, description, extra_code, is_active, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(country_id, title, price) DO UPDATE SET
                    description = COALESCE(NULLIF(excluded.description, ''), catalog_departments.description),
                    extra_code = COALESCE(NULLIF(excluded.extra_code, ''), catalog_departments.extra_code),
                    is_active = 1
                """,
                (catalog_country["country_id"], title, float(price), description or "", extra_code or "", created_by, utcnow()),
            )
        cursor = await db.execute(
            """
            INSERT INTO products (
                title, country, price, description, extra_code, session_path,
                phone, telegram_id, username, first_name, twofa_password,
                created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, country, price, description, extra_code, session_path, phone, telegram_id, username, first_name, twofa_password, created_by, utcnow()),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def update_product_session_path(product_id: int, session_path: str) -> None:
    async with get_db_conn() as db:
        await db.execute("UPDATE products SET session_path = ? WHERE product_id = ?", (session_path, product_id))
        await db.commit()


async def get_product(product_id: int):
    async with get_db_conn() as db:
        async with db.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)) as cursor:
            return await cursor.fetchone()


async def find_existing_product_identity(
    *,
    session_path: str = "",
    phone: str = "",
    telegram_id: int | None = None,
    extra_code: str = "",
):
    conditions: list[str] = []
    args: list[object] = []
    session_path = (session_path or "").strip()
    phone = (phone or "").strip()
    extra_code = (extra_code or "").strip()
    if session_path:
        conditions.append("session_path = ?")
        args.append(session_path)
    if phone:
        conditions.append("phone = ?")
        args.append(phone)
    if telegram_id is not None:
        conditions.append("telegram_id = ?")
        args.append(int(telegram_id))
    if extra_code:
        conditions.append("extra_code = ?")
        args.append(extra_code)
    if not conditions:
        return None
    async with get_db_conn() as db:
        async with db.execute(
            f"""
            SELECT *
            FROM products
            WHERE status != 'removed'
              AND ({' OR '.join(conditions)})
            ORDER BY product_id DESC
            LIMIT 1
            """,
            tuple(args),
        ) as cursor:
            return await cursor.fetchone()


async def search_products(query: str, limit: int = 20):
    value = (query or "").strip()
    if not value:
        return []
    phone_like = f"%{value}%"
    args: list[object] = []
    conditions = ["phone LIKE ?"]
    args.append(phone_like)
    if value.isdigit():
        conditions.insert(0, "product_id = ?")
        args.insert(0, int(value))
    async with get_db_conn() as db:
        async with db.execute(
            f"""
            SELECT *
            FROM products
            WHERE {" OR ".join(conditions)}
            ORDER BY
                CASE WHEN product_id = ? THEN 0 ELSE 1 END,
                product_id DESC
            LIMIT ?
            """,
            tuple(args + [int(value) if value.isdigit() else -1, limit]),
        ) as cursor:
            return await cursor.fetchall()


async def mark_product_session_cleanup_disabled(product_id: int) -> None:
    async with get_db_conn() as db:
        await db.execute("UPDATE products SET skip_session_cleanup = 1 WHERE product_id = ?", (product_id,))
        await db.commit()


async def list_country_counts():
    async with get_db_conn() as db:
        async with db.execute(
            """
            SELECT c.country_id, c.name AS country, c.icon_custom_emoji_id, COUNT(p.product_id) AS total
            FROM catalog_countries c
            LEFT JOIN products p ON p.country = c.name AND p.status = 'available'
            WHERE c.is_active = 1
            GROUP BY c.country_id, c.name, c.icon_custom_emoji_id, c.created_at
            ORDER BY c.created_at ASC, c.country_id ASC
            """
        ) as cursor:
            return await cursor.fetchall()


async def list_catalog_countries(*, include_inactive: bool = False):
    query = "SELECT * FROM catalog_countries"
    if not include_inactive:
        query += " WHERE is_active = 1"
    query += " ORDER BY created_at ASC, country_id ASC"
    async with get_db_conn() as db:
        async with db.execute(query) as cursor:
            return await cursor.fetchall()


async def get_catalog_country(country_id: int):
    async with get_db_conn() as db:
        async with db.execute(
            "SELECT * FROM catalog_countries WHERE country_id = ? AND is_active = 1",
            (country_id,),
        ) as cursor:
            return await cursor.fetchone()


async def create_catalog_department(*, country_id: int, title: str, price: float, description: str, extra_code: str, created_by: int) -> int:
    normalized_title = " ".join((title or "").strip().split())
    if len(normalized_title) < 3:
        raise ValueError("Название отдела слишком короткое.")
    if price < 0:
        raise ValueError("Цена не может быть отрицательной.")
    async with get_db_conn() as db:
        async with db.execute(
            "SELECT country_id FROM catalog_countries WHERE country_id = ? AND is_active = 1",
            (country_id,),
        ) as cursor:
            country = await cursor.fetchone()
        if not country:
            raise ValueError("Страна не найдена.")
        async with db.execute(
            """
            INSERT INTO catalog_departments (
                country_id, title, price, description, extra_code, is_active, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(country_id, title, price) DO UPDATE SET
                description = excluded.description,
                extra_code = excluded.extra_code,
                is_active = 1,
                created_by = excluded.created_by
            RETURNING department_id
            """,
            (country_id, normalized_title, float(price), description or "", extra_code or "", created_by, utcnow()),
        ) as cursor:
            row = await cursor.fetchone()
            await db.commit()
            return int(row["department_id"])


async def get_catalog_department(department_id: int):
    async with get_db_conn() as db:
        async with db.execute(
            """
            SELECT d.*, c.name AS country
            FROM catalog_departments d
            JOIN catalog_countries c ON c.country_id = d.country_id
            WHERE d.department_id = ? AND d.is_active = 1 AND c.is_active = 1
            """,
            (department_id,),
        ) as cursor:
            return await cursor.fetchone()


async def add_catalog_country(name: str, icon_custom_emoji_id: str | None = None) -> int:
    normalized = " ".join((name or "").strip().split())
    if len(normalized) < 2:
        raise ValueError("Название страны слишком короткое.")
    icon_id = (icon_custom_emoji_id or "").strip() or None
    async with get_db_conn() as db:
        async with db.execute(
            """
            INSERT INTO catalog_countries (name, icon_custom_emoji_id, is_active, created_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(name) DO UPDATE SET
                is_active = 1,
                icon_custom_emoji_id = COALESCE(excluded.icon_custom_emoji_id, catalog_countries.icon_custom_emoji_id)
            RETURNING country_id
            """,
            (normalized, icon_id, utcnow()),
        ) as cursor:
            row = await cursor.fetchone()
            country_id = int(row["country_id"])
            await db.commit()
            return country_id


async def remove_catalog_country(country_id: int) -> bool:
    async with get_db_conn() as db:
        cursor = await db.execute(
            "UPDATE catalog_countries SET is_active = 0 WHERE country_id = ?",
            (country_id,),
        )
        await db.commit()
        return cursor.rowcount > 0


async def rename_catalog_country(country_id: int, new_name: str, icon_custom_emoji_id: str | None = None, *, keep_icon: bool = True) -> bool:
    normalized = " ".join((new_name or "").strip().split())
    if len(normalized) < 2:
        raise ValueError("Название страны слишком короткое.")
    icon_id = (icon_custom_emoji_id or "").strip() or None
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute(
            "SELECT name FROM catalog_countries WHERE country_id = ? AND is_active = 1",
            (country_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            await db.rollback()
            return False
        old_name = row["name"]
        try:
            if keep_icon:
                cursor = await db.execute(
                    "UPDATE catalog_countries SET name = ? WHERE country_id = ?",
                    (normalized, country_id),
                )
            else:
                cursor = await db.execute(
                    "UPDATE catalog_countries SET name = ?, icon_custom_emoji_id = ? WHERE country_id = ?",
                    (normalized, icon_id, country_id),
                )
            await db.execute("UPDATE products SET country = ? WHERE country = ?", (normalized, old_name))
            await db.commit()
            return cursor.rowcount > 0
        except Exception:
            await db.rollback()
            raise


async def list_products(*, country: str | None = None, status: str = "available", limit: int = 8, offset: int = 0):
    if status == "available":
        query = "SELECT * FROM products WHERE status = 'available'"
        args: list[object] = []
    else:
        query = "SELECT * FROM products WHERE status = ?"
        args: list[object] = [status]
    if country:
        query += " AND country = ?"
        args.append(country)
    if status == "sold":
        query += " ORDER BY sold_at DESC, product_id DESC LIMIT ? OFFSET ?"
    else:
        query += " ORDER BY product_id DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    async with get_db_conn() as db:
        async with db.execute(query, tuple(args)) as cursor:
            return await cursor.fetchall()


async def count_products(*, country: str | None = None, status: str = "available") -> int:
    if status == "available":
        query = "SELECT COUNT(*) AS total FROM products WHERE status = 'available'"
        args: list[object] = []
    else:
        query = "SELECT COUNT(*) AS total FROM products WHERE status = ?"
        args: list[object] = [status]
    if country:
        query += " AND country = ?"
        args.append(country)
    async with get_db_conn() as db:
        async with db.execute(query, tuple(args)) as cursor:
            row = await cursor.fetchone()
        return int(row["total"]) if row else 0


async def list_product_groups(*, country: str | None = None, status: str = "available", limit: int = 8, offset: int = 0):
    query = """
        SELECT
            MIN(product_id) AS sample_product_id,
            title,
            country,
            price,
            COUNT(*) AS stock_count,
            (
                SELECT description
                FROM products p2
                WHERE p2.status = p.status
                  AND p2.country = p.country
                  AND p2.title = p.title
                  AND p2.price = p.price
                ORDER BY p2.product_id DESC
                LIMIT 1
            ) AS description,
            (
                SELECT extra_code
                FROM products p3
                WHERE p3.status = p.status
                  AND p3.country = p.country
                  AND p3.title = p.title
                  AND p3.price = p.price
                ORDER BY p3.product_id DESC
                LIMIT 1
            ) AS extra_code,
            MAX(product_id) AS last_product_id
        FROM products p
        WHERE status = ?
    """
    args: list[object] = [status]
    if country:
        query += " AND country = ?"
        args.append(country)
    query += """
        GROUP BY country, title, price
        ORDER BY last_product_id DESC
        LIMIT ? OFFSET ?
    """
    args.extend([limit, offset])
    async with get_db_conn() as db:
        async with db.execute(query, tuple(args)) as cursor:
            return await cursor.fetchall()


async def count_product_groups(*, country: str | None = None, status: str = "available") -> int:
    query = """
        SELECT COUNT(*) AS total
        FROM (
            SELECT 1
            FROM products
            WHERE status = ?
    """
    args: list[object] = [status]
    if country:
        query += " AND country = ?"
        args.append(country)
    query += " GROUP BY country, title, price)"
    async with get_db_conn() as db:
        async with db.execute(query, tuple(args)) as cursor:
            row = await cursor.fetchone()
        return int(row["total"]) if row else 0


async def get_product_group(sample_product_id: int, *, status: str = "available"):
    async with get_db_conn() as db:
        async with db.execute("SELECT * FROM products WHERE product_id = ?", (sample_product_id,)) as cursor:
            sample = await cursor.fetchone()
        if not sample:
            return None
        async with db.execute(
            """
            SELECT
                MIN(product_id) AS sample_product_id,
                title,
                country,
                price,
                COUNT(*) AS stock_count,
                (
                    SELECT description
                    FROM products p2
                    WHERE p2.status = ?
                      AND p2.country = ?
                      AND p2.title = ?
                      AND p2.price = ?
                    ORDER BY p2.product_id DESC
                    LIMIT 1
                ) AS description,
                (
                    SELECT extra_code
                    FROM products p3
                    WHERE p3.status = ?
                      AND p3.country = ?
                      AND p3.title = ?
                      AND p3.price = ?
                    ORDER BY p3.product_id DESC
                    LIMIT 1
                ) AS extra_code
            FROM products
            WHERE status = ?
              AND country = ?
              AND title = ?
              AND price = ?
            GROUP BY country, title, price
            """,
            (
                status, sample["country"], sample["title"], sample["price"],
                status, sample["country"], sample["title"], sample["price"],
                status, sample["country"], sample["title"], sample["price"],
            ),
        ) as cursor:
            return await cursor.fetchone()


async def list_product_departments(*, country: str | None = None, limit: int = 50, offset: int = 0):
    query = """
        SELECT
            MIN(product_id) AS sample_product_id,
            title,
            country,
            price,
            SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS stock_count,
            COUNT(*) AS total_count,
            (
                SELECT description
                FROM products p2
                WHERE p2.status != 'removed'
                  AND p2.country = p.country
                  AND p2.title = p.title
                  AND p2.price = p.price
                ORDER BY p2.product_id DESC
                LIMIT 1
            ) AS description,
            (
                SELECT extra_code
                FROM products p3
                WHERE p3.status != 'removed'
                  AND p3.country = p.country
                  AND p3.title = p.title
                  AND p3.price = p.price
                ORDER BY p3.product_id DESC
                LIMIT 1
            ) AS extra_code,
            MAX(product_id) AS last_product_id
        FROM products p
        WHERE status != 'removed'
          AND NOT EXISTS (
              SELECT 1 FROM removed_product_departments r
              WHERE r.country = p.country AND r.title = p.title AND r.price = p.price
          )
    """
    args: list[object] = []
    if country:
        query += " AND country = ?"
        args.append(country)
    query += """
        GROUP BY country, title, price
        ORDER BY last_product_id DESC
    """
    async with get_db_conn() as db:
        async with db.execute(query, tuple(args)) as cursor:
            product_rows = [dict(row) for row in await cursor.fetchall()]
        dept_query = """
            SELECT
                -d.department_id AS sample_product_id,
                d.title,
                c.name AS country,
                d.price,
                0 AS stock_count,
                0 AS total_count,
                d.description,
                d.extra_code,
                0 AS last_product_id
            FROM catalog_departments d
            JOIN catalog_countries c ON c.country_id = d.country_id
            WHERE d.is_active = 1
              AND c.is_active = 1
              AND NOT EXISTS (
                  SELECT 1 FROM removed_product_departments r
                  WHERE r.country = c.name AND r.title = d.title AND r.price = d.price
              )
        """
        dept_args: list[object] = []
        if country:
            dept_query += " AND c.name = ?"
            dept_args.append(country)
        async with db.execute(dept_query, tuple(dept_args)) as cursor:
            dept_rows = [dict(row) for row in await cursor.fetchall()]

    merged: dict[tuple[str, str, float], dict] = {}
    for row in dept_rows:
        merged[(row["country"], row["title"], float(row["price"]))] = row
    for row in product_rows:
        key = (row["country"], row["title"], float(row["price"]))
        base = merged.get(key, {})
        if base.get("description") and not row.get("description"):
            row["description"] = base["description"]
        if base.get("extra_code") and not row.get("extra_code"):
            row["extra_code"] = base["extra_code"]
        merged[key] = row
    rows = sorted(
        merged.values(),
        key=lambda row: (int(row.get("last_product_id") or 0), row["country"].lower(), row["title"].lower()),
        reverse=True,
    )
    return rows[offset:offset + limit]


async def count_product_departments(*, country: str | None = None) -> int:
    return len(await list_product_departments(country=country, limit=100000, offset=0))


async def get_product_department(sample_product_id: int):
    async with get_db_conn() as db:
        if sample_product_id < 0:
            department_id = abs(sample_product_id)
            async with db.execute(
                """
                SELECT d.*, c.name AS country
                FROM catalog_departments d
                JOIN catalog_countries c ON c.country_id = d.country_id
                WHERE d.department_id = ? AND d.is_active = 1 AND c.is_active = 1
                  AND NOT EXISTS (
                      SELECT 1 FROM removed_product_departments r
                      WHERE r.country = c.name AND r.title = d.title AND r.price = d.price
                  )
                """,
                (department_id,),
            ) as cursor:
                department = await cursor.fetchone()
            if not department:
                return None
            async with db.execute(
                """
                SELECT
                    MIN(product_id) AS sample_product_id,
                    SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS stock_count,
                    COUNT(*) AS total_count,
                    MAX(product_id) AS last_product_id
                FROM products
                WHERE status != 'removed'
                  AND country = ?
                  AND title = ?
                  AND price = ?
                """,
                (department["country"], department["title"], department["price"]),
            ) as cursor:
                counts = await cursor.fetchone()
            real_sample_id = int(counts["sample_product_id"] or 0) if counts else 0
            return {
                "sample_product_id": real_sample_id or -department_id,
                "title": department["title"],
                "country": department["country"],
                "price": department["price"],
                "stock_count": int(counts["stock_count"] or 0) if counts else 0,
                "total_count": int(counts["total_count"] or 0) if counts else 0,
                "description": department["description"] or "",
                "extra_code": department["extra_code"] or "",
                "last_product_id": int(counts["last_product_id"] or 0) if counts else 0,
            }
        async with db.execute(
            """
            SELECT *
            FROM products p
            WHERE p.product_id = ? AND p.status != 'removed'
              AND NOT EXISTS (
                  SELECT 1 FROM removed_product_departments r
                  WHERE r.country = p.country AND r.title = p.title AND r.price = p.price
              )
            """,
            (sample_product_id,),
        ) as cursor:
            sample = await cursor.fetchone()
        if not sample:
            return None
        async with db.execute(
            """
            SELECT d.description, d.extra_code
            FROM catalog_departments d
            JOIN catalog_countries c ON c.country_id = d.country_id
            WHERE d.is_active = 1
              AND c.is_active = 1
              AND c.name = ?
              AND d.title = ?
              AND d.price = ?
            LIMIT 1
            """,
            (sample["country"], sample["title"], sample["price"]),
        ) as cursor:
            catalog_department = await cursor.fetchone()
        async with db.execute(
            """
            SELECT
                MIN(product_id) AS sample_product_id,
                title,
                country,
                price,
                SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS stock_count,
                COUNT(*) AS total_count,
                (
                    SELECT description
                    FROM products p2
                    WHERE p2.status != 'removed'
                      AND p2.country = ?
                      AND p2.title = ?
                      AND p2.price = ?
                    ORDER BY p2.product_id DESC
                    LIMIT 1
                ) AS description,
                (
                    SELECT extra_code
                    FROM products p3
                    WHERE p3.status != 'removed'
                      AND p3.country = ?
                      AND p3.title = ?
                      AND p3.price = ?
                    ORDER BY p3.product_id DESC
                    LIMIT 1
                ) AS extra_code
            FROM products
            WHERE status != 'removed'
              AND country = ?
              AND title = ?
              AND price = ?
              AND NOT EXISTS (
                  SELECT 1 FROM removed_product_departments r
                  WHERE r.country = products.country AND r.title = products.title AND r.price = products.price
              )
            GROUP BY country, title, price
            """,
            (
                sample["country"], sample["title"], sample["price"],
                sample["country"], sample["title"], sample["price"],
                sample["country"], sample["title"], sample["price"],
            ),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        if catalog_department:
            result["description"] = catalog_department["description"] or result.get("description") or ""
            result["extra_code"] = catalog_department["extra_code"] or result.get("extra_code") or ""
        return result


async def list_available_products_in_department(sample_product_id: int, limit: int = 20):
    async with get_db_conn() as db:
        if sample_product_id < 0:
            async with db.execute(
                """
                SELECT c.name AS country, d.title, d.price
                FROM catalog_departments d
                JOIN catalog_countries c ON c.country_id = d.country_id
                WHERE d.department_id = ? AND d.is_active = 1 AND c.is_active = 1
                """,
                (abs(sample_product_id),),
            ) as cursor:
                sample = await cursor.fetchone()
        else:
            async with db.execute(
                """
                SELECT country, title, price
                FROM products p
                WHERE p.product_id = ? AND p.status != 'removed'
                  AND NOT EXISTS (
                      SELECT 1 FROM removed_product_departments r
                      WHERE r.country = p.country AND r.title = p.title AND r.price = p.price
                  )
                """,
                (sample_product_id,),
            ) as cursor:
                sample = await cursor.fetchone()
        if not sample:
            return []
        async with db.execute(
            """
            SELECT *
            FROM products
            WHERE status = 'available'
              AND country = ?
              AND title = ?
              AND price = ?
            ORDER BY product_id ASC
            LIMIT ?
            """,
            (sample["country"], sample["title"], sample["price"], limit),
        ) as cursor:
            return await cursor.fetchall()


async def count_available_products_in_department(sample_product_id: int, *, exclude_cart_user_id: int | None = None) -> int:
    async with get_db_conn() as db:
        if sample_product_id < 0:
            async with db.execute(
                """
                SELECT c.name AS country, d.title, d.price
                FROM catalog_departments d
                JOIN catalog_countries c ON c.country_id = d.country_id
                WHERE d.department_id = ? AND d.is_active = 1 AND c.is_active = 1
                """,
                (abs(sample_product_id),),
            ) as cursor:
                sample = await cursor.fetchone()
        else:
            async with db.execute(
                """
                SELECT country, title, price
                FROM products p
                WHERE p.product_id = ? AND p.status != 'removed'
                  AND NOT EXISTS (
                      SELECT 1 FROM removed_product_departments r
                      WHERE r.country = p.country AND r.title = p.title AND r.price = p.price
                  )
                """,
                (sample_product_id,),
            ) as cursor:
                sample = await cursor.fetchone()
        if not sample:
            return 0
        query = """
            SELECT COUNT(*) AS total
            FROM products p
            WHERE p.status = 'available'
              AND p.country = ?
              AND p.title = ?
              AND p.price = ?
        """
        args: list[object] = [sample["country"], sample["title"], sample["price"]]
        if exclude_cart_user_id is not None:
            query += """
              AND NOT EXISTS (
                  SELECT 1 FROM cart_items c
                  WHERE c.user_id = ? AND c.product_id = p.product_id
              )
            """
            args.append(exclude_cart_user_id)
        async with db.execute(query, tuple(args)) as cursor:
            row = await cursor.fetchone()
        return int(row["total"]) if row else 0


async def list_products_in_department(sample_product_id: int, *, limit: int = 20, offset: int = 0):
    async with get_db_conn() as db:
        if sample_product_id < 0:
            async with db.execute(
                """
                SELECT c.name AS country, d.title, d.price
                FROM catalog_departments d
                JOIN catalog_countries c ON c.country_id = d.country_id
                WHERE d.department_id = ? AND d.is_active = 1 AND c.is_active = 1
                """,
                (abs(sample_product_id),),
            ) as cursor:
                sample = await cursor.fetchone()
        else:
            async with db.execute(
                """
                SELECT country, title, price
                FROM products p
                WHERE p.product_id = ? AND p.status != 'removed'
                  AND NOT EXISTS (
                      SELECT 1 FROM removed_product_departments r
                      WHERE r.country = p.country AND r.title = p.title AND r.price = p.price
                  )
                """,
                (sample_product_id,),
            ) as cursor:
                sample = await cursor.fetchone()
        if not sample:
            return []
        async with db.execute(
            """
            SELECT *
            FROM products
            WHERE status != 'removed'
              AND country = ?
              AND title = ?
              AND price = ?
            ORDER BY
              CASE status
                WHEN 'available' THEN 0
                WHEN 'dead' THEN 1
                WHEN 'sold' THEN 2
                ELSE 3
              END,
              product_id DESC
            LIMIT ? OFFSET ?
            """,
            (sample["country"], sample["title"], sample["price"], limit, offset),
        ) as cursor:
            return await cursor.fetchall()


async def count_products_in_department(sample_product_id: int) -> int:
    async with get_db_conn() as db:
        if sample_product_id < 0:
            async with db.execute(
                """
                SELECT c.name AS country, d.title, d.price
                FROM catalog_departments d
                JOIN catalog_countries c ON c.country_id = d.country_id
                WHERE d.department_id = ? AND d.is_active = 1 AND c.is_active = 1
                """,
                (abs(sample_product_id),),
            ) as cursor:
                sample = await cursor.fetchone()
        else:
            async with db.execute(
                """
                SELECT country, title, price
                FROM products p
                WHERE p.product_id = ? AND p.status != 'removed'
                  AND NOT EXISTS (
                      SELECT 1 FROM removed_product_departments r
                      WHERE r.country = p.country AND r.title = p.title AND r.price = p.price
                  )
                """,
                (sample_product_id,),
            ) as cursor:
                sample = await cursor.fetchone()
        if not sample:
            return 0
        async with db.execute(
            """
            SELECT COUNT(*) AS total
            FROM products
            WHERE status != 'removed'
              AND country = ?
              AND title = ?
              AND price = ?
            """,
            (sample["country"], sample["title"], sample["price"]),
        ) as cursor:
            row = await cursor.fetchone()
        return int(row["total"]) if row else 0


async def add_product_group_to_cart(user_id: int, sample_product_id: int) -> tuple[bool, str, int | None]:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        if sample_product_id < 0:
            async with db.execute(
                """
                SELECT c.name AS country, d.title, d.price
                FROM catalog_departments d
                JOIN catalog_countries c ON c.country_id = d.country_id
                WHERE d.department_id = ? AND d.is_active = 1 AND c.is_active = 1
                  AND NOT EXISTS (
                      SELECT 1 FROM removed_product_departments r
                      WHERE r.country = c.name AND r.title = d.title AND r.price = d.price
                  )
                """,
                (abs(sample_product_id),),
            ) as cursor:
                sample = await cursor.fetchone()
        else:
            async with db.execute(
                """
                SELECT country, title, price
                FROM products p
                WHERE p.product_id = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM removed_product_departments r
                      WHERE r.country = p.country AND r.title = p.title AND r.price = p.price
                  )
                """,
                (sample_product_id,),
            ) as cursor:
                sample = await cursor.fetchone()
        if not sample:
            await db.rollback()
            return False, "product_not_found", None
        async with db.execute(
            """
            SELECT p.product_id
            FROM products p
            WHERE p.status = 'available'
              AND p.country = ?
              AND p.title = ?
              AND p.price = ?
              AND NOT EXISTS (
                  SELECT 1 FROM cart_items c
                  WHERE c.user_id = ? AND c.product_id = p.product_id
              )
            ORDER BY p.product_id ASC
            LIMIT 1
            """,
            (sample["country"], sample["title"], sample["price"], user_id),
        ) as cursor:
            product = await cursor.fetchone()
        if not product:
            async with db.execute(
                """
                SELECT COUNT(*) AS total
                FROM products
                WHERE status = 'available' AND country = ? AND title = ? AND price = ?
                """,
                (sample["country"], sample["title"], sample["price"]),
            ) as cursor:
                row = await cursor.fetchone()
            await db.rollback()
            return False, "already_in_cart" if row and int(row["total"]) > 0 else "not_available", None
        product_id = int(product["product_id"])
        await db.execute(
            "INSERT INTO cart_items (user_id, product_id, added_at) VALUES (?, ?, ?)",
            (user_id, product_id, utcnow()),
        )
        await db.commit()
        return True, "ok", product_id


async def list_user_purchases(user_id: int):
    async with get_db_conn() as db:
        async with db.execute(
            """
            SELECT p.*, pr.title, pr.country, pr.phone, pr.username, pr.first_name,
                   pr.extra_code, pr.twofa_password, pr.session_path
            FROM purchases p
            JOIN products pr ON pr.product_id = p.product_id
            WHERE p.user_id = ?
            ORDER BY p.purchase_id DESC
            """,
            (user_id,),
        ) as cursor:
            return await cursor.fetchall()


async def list_user_purchase_groups(user_id: int):
    async with get_db_conn() as db:
        async with db.execute(
            """
            WITH grouped_purchases AS (
                SELECT
                    p.*,
                    COALESCE(NULLIF(p.batch_id, ''), CAST(p.purchase_id AS TEXT)) AS group_id
                FROM purchases p
                WHERE p.user_id = ?
            )
            SELECT
                gp.group_id,
                COUNT(*) AS items_count,
                COALESCE(SUM(gp.price), 0) AS total_price,
                MIN(gp.created_at) AS created_at,
                MAX(gp.purchase_id) AS last_purchase_id,
                (
                    SELECT pr.title
                    FROM grouped_purchases gp2
                    JOIN products pr ON pr.product_id = gp2.product_id
                    WHERE gp2.group_id = gp.group_id
                    ORDER BY gp2.purchase_id ASC
                    LIMIT 1
                ) AS first_title,
                (
                    SELECT pr.phone
                    FROM grouped_purchases gp2
                    JOIN products pr ON pr.product_id = gp2.product_id
                    WHERE gp2.group_id = gp.group_id
                    ORDER BY gp2.purchase_id ASC
                    LIMIT 1
                ) AS first_phone
            FROM grouped_purchases gp
            GROUP BY gp.group_id
            ORDER BY last_purchase_id DESC
            """,
            (user_id,),
        ) as cursor:
            return await cursor.fetchall()


async def list_user_batch_purchases(user_id: int, batch_id: str):
    async with get_db_conn() as db:
        async with db.execute(
            """
            SELECT p.*, pr.title, pr.country, pr.phone, pr.username, pr.first_name,
                   pr.extra_code, pr.twofa_password, pr.session_path, pr.status, pr.sold_to
            FROM purchases p
            JOIN products pr ON pr.product_id = p.product_id
            WHERE p.user_id = ?
              AND COALESCE(NULLIF(p.batch_id, ''), CAST(p.purchase_id AS TEXT)) = ?
            ORDER BY p.purchase_id ASC
            """,
            (user_id, batch_id),
        ) as cursor:
            return await cursor.fetchall()


async def count_user_purchases(user_id: int) -> int:
    async with get_db_conn() as db:
        async with db.execute("SELECT COUNT(*) AS total FROM purchases WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return int(row["total"]) if row else 0


async def add_product_to_cart(user_id: int, product_id: int) -> tuple[bool, str]:
    async with get_db_conn() as db:
        async with db.execute(
            """
            SELECT status
            FROM products p
            WHERE p.product_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM removed_product_departments r
                  WHERE r.country = p.country AND r.title = p.title AND r.price = p.price
              )
            """,
            (product_id,),
        ) as cursor:
            product = await cursor.fetchone()
        if not product:
            return False, "product_not_found"
        if product["status"] != "available":
            return False, "not_available"
        try:
            await db.execute(
                "INSERT INTO cart_items (user_id, product_id, added_at) VALUES (?, ?, ?)",
                (user_id, product_id, utcnow()),
            )
            await db.commit()
            return True, "ok"
        except aiosqlite.IntegrityError:
            await db.rollback()
            return False, "already_in_cart"


async def remove_product_from_cart(user_id: int, product_id: int) -> bool:
    async with get_db_conn() as db:
        cursor = await db.execute(
            "DELETE FROM cart_items WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def clear_cart(user_id: int) -> None:
    async with get_db_conn() as db:
        await db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await db.commit()


async def list_cart_items(user_id: int) -> list:
    async with get_db_conn() as db:
        async with db.execute(
            """
            SELECT c.cart_item_id, c.added_at, p.*
            FROM cart_items c
            JOIN products p ON p.product_id = c.product_id
            WHERE c.user_id = ?
            ORDER BY c.cart_item_id DESC
            """,
            (user_id,),
        ) as cursor:
            return await cursor.fetchall()


async def list_recent_products(status: str | None = None, limit: int = 20):
    query = "SELECT * FROM products"
    args: list[object] = []
    if status:
        query += " WHERE status = ?"
        args.append(status)
    query += " ORDER BY product_id DESC LIMIT ?"
    args.append(limit)
    async with get_db_conn() as db:
        async with db.execute(query, tuple(args)) as cursor:
            return await cursor.fetchall()


async def remove_product(product_id: int) -> bool:
    """Снять товар с продажи (только если в статусе available)."""
    async with get_db_conn() as db:
        async with db.execute("SELECT status FROM products WHERE product_id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
        if not row or row["status"] != "available":
            return False
        await db.execute("UPDATE products SET status = 'removed' WHERE product_id = ?", (product_id,))
        await db.commit()
        return True


async def force_remove_product(product_id: int) -> bool:
    """Принудительно удалить товар в любом статусе (для снятия застрявших товаров)."""
    async with get_db_conn() as db:
        async with db.execute("SELECT product_id FROM products WHERE product_id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            return False
        await db.execute("UPDATE products SET status = 'removed' WHERE product_id = ?", (product_id,))
        await db.commit()
        logger.info(f"Товар {product_id} принудительно удален")
        return True


async def return_product_to_catalog(product_id: int) -> bool:
    """Вернуть товар в каталог из статуса waiting_code/verifying (при таймауте покупки)."""
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute(
            "SELECT status, sold_to, sold_price, price FROM products WHERE product_id = ?",
            (product_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row or row["status"] not in ("waiting_code", "verifying"):
            await db.rollback()
            return False

        buyer_id = row["sold_to"]
        refund_amount = float(row["sold_price"] or row["price"] or 0)
        if buyer_id and refund_amount > 0:
            await db.execute(
                "UPDATE users SET balance = balance + ?, last_seen_at = ? WHERE user_id = ?",
                (refund_amount, utcnow(), buyer_id),
            )
            await db.execute(
                "INSERT INTO balance_events (user_id, amount, kind, note, actor_id, created_at) VALUES (?, ?, 'refund', ?, NULL, ?)",
                (buyer_id, refund_amount, f"Возврат за товар #{product_id} (таймаут входа)", utcnow()),
            )

        # Возвращаем товар в available и очищаем информацию о покупателе
        await db.execute(
            """UPDATE products 
               SET status = 'available', sold_to = NULL, sold_at = NULL, sold_price = NULL, purchase_started_at = NULL
               WHERE product_id = ?""",
            (product_id,)
        )
        await db.commit()
        logger.info(f"Товар {product_id} возвращен в каталог (таймаут покупки)")
        return True


async def process_crypto_topup(invoice_id: str, user_id: int, amount: float) -> tuple[bool, float]:
    """Atomically process a CryptoPay invoice once and return (processed, balance)."""
    async with get_db_conn() as db:
        try:
            await db.execute("BEGIN IMMEDIATE")
            now = utcnow()
            amount = normalize_money(amount)
            await db.execute(
                "INSERT INTO crypto_payments (invoice_id, user_id, amount, processed_at) VALUES (?, ?, ?, ?)",
                (str(invoice_id), user_id, amount, now),
            )
            async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
            current = float(row["balance"]) if row else 0.0
            new_balance = normalize_money(current + amount)
            if row:
                await db.execute(
                    "UPDATE users SET balance = ?, last_seen_at = ? WHERE user_id = ?",
                    (new_balance, now, user_id),
                )
            else:
                await db.execute(
                    "INSERT INTO users (user_id, username, first_name, balance, joined_at, last_seen_at) VALUES (?, '', '', ?, ?, ?)",
                    (user_id, new_balance, now, now),
                )
            await db.execute(
                "INSERT INTO balance_events (user_id, amount, kind, note, actor_id, created_at) VALUES (?, ?, 'topup', ?, NULL, ?)",
                (user_id, amount, f"CryptoPay Invoice #{invoice_id}", now),
            )
            await db.execute(
                """
                UPDATE crypto_invoices
                SET status = 'paid',
                    paid_at = COALESCE(paid_at, ?),
                    processed_at = ?
                WHERE invoice_id = ?
                """,
                (now, now, str(invoice_id)),
            )
            await db.commit()
            return True, new_balance
        except aiosqlite.IntegrityError:
            await db.rollback()
            balance = await get_balance(user_id)
            return False, balance


async def record_crypto_invoice(
    *,
    invoice_id: str,
    user_id: int,
    amount: float,
    fiat: str,
    pay_url: str | None = None,
) -> None:
    async with get_db_conn() as db:
        await db.execute(
            """
            INSERT INTO crypto_invoices (
                invoice_id, user_id, amount, fiat, pay_url, status, created_at
            ) VALUES (?, ?, ?, ?, ?, 'created', ?)
            """,
            (str(invoice_id), user_id, normalize_money(amount), (fiat or "").upper(), pay_url or "", utcnow()),
        )
        await db.commit()


async def get_crypto_invoice(invoice_id: str):
    async with get_db_conn() as db:
        async with db.execute("SELECT * FROM crypto_invoices WHERE invoice_id = ?", (str(invoice_id),)) as cursor:
            return await cursor.fetchone()


async def mark_crypto_invoice_status(invoice_id: str, status: str, paid_at: str | None = None) -> None:
    async with get_db_conn() as db:
        if paid_at:
            await db.execute(
                "UPDATE crypto_invoices SET status = ?, paid_at = COALESCE(paid_at, ?) WHERE invoice_id = ?",
                (status, paid_at, str(invoice_id)),
            )
        else:
            await db.execute(
                "UPDATE crypto_invoices SET status = ? WHERE invoice_id = ?",
                (status, str(invoice_id)),
            )
        await db.commit()


async def create_topup_request(
    *,
    user_id: int,
    username: str | None,
    first_name: str | None,
    method: str,
    amount: float,
    currency: str,
    credit_amount: float,
    receipt_type: str,
    receipt_file_id: str,
) -> int:
    async with get_db_conn() as db:
        cursor = await db.execute(
            """
            INSERT INTO topup_requests (
                user_id, username, first_name, method, amount, currency,
                credit_amount, receipt_type, receipt_file_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                username or "",
                first_name or "",
                method,
                amount,
                currency,
                credit_amount,
                receipt_type,
                receipt_file_id,
                utcnow(),
            ),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_topup_request(request_id: int):
    async with get_db_conn() as db:
        async with db.execute("SELECT * FROM topup_requests WHERE request_id = ?", (request_id,)) as cursor:
            return await cursor.fetchone()


async def approve_topup_request(request_id: int, reviewer_id: int) -> tuple[bool, str, float | None, int | None, str | None]:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM topup_requests WHERE request_id = ?", (request_id,)) as cursor:
            request = await cursor.fetchone()
        if not request:
            await db.rollback()
            return False, "not_found", None, None, None
        if request["status"] != "pending":
            await db.rollback()
            return False, request["status"], float(request["credit_amount"] or request["amount"]), int(request["user_id"]), request["currency"]

        user_id = int(request["user_id"])
        amount = float(request["credit_amount"] or request["amount"])
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if user:
            await db.execute(
                "UPDATE users SET balance = balance + ?, last_seen_at = ? WHERE user_id = ?",
                (amount, utcnow(), user_id),
            )
        else:
            await db.execute(
                "INSERT INTO users (user_id, username, first_name, balance, joined_at, last_seen_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, request["username"] or "", request["first_name"] or "", amount, utcnow(), utcnow()),
            )
        await db.execute(
            "INSERT INTO balance_events (user_id, amount, kind, note, actor_id, created_at) VALUES (?, ?, 'manual_topup', ?, ?, ?)",
            (user_id, amount, f"Ручное пополнение по заявке #{request_id}", reviewer_id, utcnow()),
        )
        await db.execute(
            "UPDATE topup_requests SET status = 'approved', reviewed_by = ?, reviewed_at = ? WHERE request_id = ?",
            (reviewer_id, utcnow(), request_id),
        )
        await db.commit()
        return True, "approved", amount, user_id, request["currency"]


async def reject_topup_request(request_id: int, reviewer_id: int) -> tuple[bool, str, float | None, int | None, str | None]:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT * FROM topup_requests WHERE request_id = ?", (request_id,)) as cursor:
            request = await cursor.fetchone()
        if not request:
            await db.rollback()
            return False, "not_found", None, None, None
        if request["status"] != "pending":
            await db.rollback()
            return False, request["status"], float(request["credit_amount"] or request["amount"]), int(request["user_id"]), request["currency"]
        await db.execute(
            "UPDATE topup_requests SET status = 'rejected', reviewed_by = ?, reviewed_at = ? WHERE request_id = ?",
            (reviewer_id, utcnow(), request_id),
        )
        await db.commit()
        return True, "rejected", float(request["credit_amount"] or request["amount"]), int(request["user_id"]), request["currency"]


async def add_topup_reviewer(user_id: int, added_by: int) -> bool:
    async with get_db_conn() as db:
        cursor = await db.execute(
            """
            INSERT INTO topup_reviewers (user_id, added_by, added_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (user_id, added_by, utcnow()),
        )
        await db.commit()
        return cursor.rowcount > 0


async def remove_topup_reviewer(user_id: int) -> bool:
    async with get_db_conn() as db:
        cursor = await db.execute("DELETE FROM topup_reviewers WHERE user_id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount > 0


async def is_topup_reviewer(user_id: int) -> bool:
    async with get_db_conn() as db:
        async with db.execute("SELECT 1 FROM topup_reviewers WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone() is not None


async def list_topup_reviewers():
    async with get_db_conn() as db:
        async with db.execute(
            """
            SELECT r.user_id, r.added_by, r.added_at, u.username, u.first_name
            FROM topup_reviewers r
            LEFT JOIN users u ON u.user_id = r.user_id
            ORDER BY r.added_at DESC
            """
        ) as cursor:
            return await cursor.fetchall()


async def check_purchase_timeouts(timeout_seconds: int = 900) -> list[int]:
    """Проверяет товары с истекшим таймаутом покупки (по умолчанию 15 минут).
    Возвращает список product_id которые были возвращены в каталог."""
    from datetime import datetime, timedelta
    
    async with get_db_conn() as db:
        # Находим товары с истекшим таймаутом
        cutoff_time = (datetime.utcnow() - timedelta(seconds=timeout_seconds)).isoformat(timespec="seconds")
        async with db.execute(
            """SELECT product_id FROM products
               WHERE status IN ('waiting_code', 'verifying')
               AND purchase_started_at IS NOT NULL
               AND purchase_started_at < ?""",
            (cutoff_time,)
        ) as cursor:
            expired = await cursor.fetchall()
        
        returned_products = []
        for row in expired:
            product_id = row["product_id"]
            if await return_product_to_catalog(product_id):
                returned_products.append(product_id)
        
        return returned_products


async def update_product_status(product_id: int, status: str) -> bool:
    async with get_db_conn() as db:
        cursor = await db.execute(
            "UPDATE products SET status = ? WHERE product_id = ?",
            (status, product_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def update_code_fetched_at(product_id: int) -> bool:
    """Обновляет время получения кода товара."""
    async with get_db_conn() as db:
        cursor = await db.execute(
            "UPDATE products SET code_fetched_at = ? WHERE product_id = ?",
            (utcnow(), product_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def claim_product_for_admin(admin_id: int, product_id: int) -> bool:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT status FROM products WHERE product_id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
        if not row or row["status"] not in {"available", "waiting_code"}:
            await db.rollback()
            return False
        await db.execute(
            "UPDATE products SET status = 'sold', sold_to = ?, sold_at = ?, sold_price = 0 WHERE product_id = ?",
            (admin_id, utcnow(), product_id),
        )
        await db.commit()
        return True


async def get_product_session_path(product_id: int) -> str | None:
    async with get_db_conn() as db:
        async with db.execute("SELECT session_path FROM products WHERE product_id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
            return row["session_path"] if row else None


async def list_sold_products_for_manual_cleanup() -> list:
    async with get_db_conn() as db:
        async with db.execute(
            """
            SELECT product_id, title, phone, username, first_name, session_path, sold_at
            FROM products
            WHERE status = 'sold'
              AND session_path IS NOT NULL
              AND TRIM(session_path) != ''
            ORDER BY product_id ASC
            """
        ) as cursor:
            return await cursor.fetchall()


async def list_product_session_references() -> list:
    async with get_db_conn() as db:
        async with db.execute(
            """
            SELECT product_id, status, session_path
            FROM products
            WHERE session_path IS NOT NULL
              AND TRIM(session_path) != ''
              AND session_path != 'pending'
            """
        ) as cursor:
            return await cursor.fetchall()


async def delete_sold_product_with_history(
    product_id: int,
    expected_session_path: str,
    *,
    allow_session_cleared: bool = False,
) -> str:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            async with db.execute(
                "SELECT status, session_path FROM products WHERE product_id = ?",
                (product_id,),
            ) as cursor:
                row = await cursor.fetchone()

            if not row:
                await db.rollback()
                return "not_found"
            if row["status"] != "sold":
                await db.rollback()
                return "status_changed"
            current_session_path = (row["session_path"] or "").strip()
            expected_session_path = (expected_session_path or "").strip()
            session_matches = current_session_path == expected_session_path
            if allow_session_cleared and expected_session_path and not current_session_path:
                session_matches = True
            if not session_matches:
                await db.rollback()
                return "path_changed"

            await db.execute("DELETE FROM cart_items WHERE product_id = ?", (product_id,))
            await db.execute("DELETE FROM purchases WHERE product_id = ?", (product_id,))
            cursor = await db.execute(
                "DELETE FROM products WHERE product_id = ? AND status = 'sold'",
                (product_id,),
            )
            if cursor.rowcount != 1:
                await db.rollback()
                return "status_changed"

            await db.commit()
            logger.info("Проданный товар %s полностью удален ручной очисткой", product_id)
            return "deleted"
        except Exception:
            await db.rollback()
            raise


async def list_product_session_paths() -> list[str]:
    async with get_db_conn() as db:
        async with db.execute(
            """
            SELECT session_path
            FROM products
            WHERE session_path IS NOT NULL
              AND TRIM(session_path) != ''
              AND session_path != 'pending'
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [row["session_path"] for row in rows]


@dataclass
class PurchaseResult:
    ok: bool
    reason: str
    balance: float = 0.0
    product_id: int | None = None
    product_ids: list[int] | None = None
    products: list | None = None
    total: float = 0.0
    unavailable_ids: list[int] | None = None
    batch_id: str | None = None


async def purchase_product(user_id: int, product_id: int) -> PurchaseResult:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if not user:
            await db.rollback()
            return PurchaseResult(False, "user_not_found", 0.0)
        async with db.execute(
            """
            SELECT *
            FROM products p
            WHERE p.product_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM removed_product_departments r
                  WHERE r.country = p.country AND r.title = p.title AND r.price = p.price
              )
            """,
            (product_id,),
        ) as cursor:
            product = await cursor.fetchone()
        if not product:
            await db.rollback()
            return PurchaseResult(False, "product_not_found", float(user["balance"]))
        if product["status"] != "available":
            await db.rollback()
            return PurchaseResult(False, "not_available", float(user["balance"]))

        balance = float(user["balance"])
        price = float(product["price"])
        if balance + MONEY_EPSILON < price:
            await db.rollback()
            return PurchaseResult(False, "insufficient_funds", balance)

        new_balance = normalize_money(balance - price)
        await db.execute("UPDATE users SET balance = ?, last_seen_at = ? WHERE user_id = ?", (new_balance, utcnow(), user_id))
        await db.execute(
            "INSERT INTO balance_events (user_id, amount, kind, note, actor_id, created_at) VALUES (?, ?, 'purchase', ?, NULL, ?)",
            (user_id, -price, f"Покупка товара #{product_id}", utcnow()),
        )
        sold_at = utcnow()
        batch_id = uuid.uuid4().hex
        await db.execute(
            "UPDATE products SET status = 'sold', sold_to = ?, sold_at = ?, sold_price = ?, purchase_started_at = NULL WHERE product_id = ?",
            (user_id, sold_at, price, product_id),
        )
        await db.execute(
            "INSERT INTO purchases (user_id, product_id, price, batch_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, product_id, price, batch_id, utcnow()),
        )
        await db.execute("DELETE FROM cart_items WHERE product_id = ?", (product_id,))
        await db.commit()
        return PurchaseResult(True, "ok", new_balance, product_id, [product_id], [product], price, batch_id=batch_id)


async def purchase_cart(user_id: int) -> PurchaseResult:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()
        if not user:
            await db.rollback()
            return PurchaseResult(False, "user_not_found", 0.0)

        async with db.execute(
            """
            SELECT p.*
            FROM cart_items c
            JOIN products p ON p.product_id = c.product_id
            WHERE c.user_id = ?
            ORDER BY c.cart_item_id ASC
            """,
            (user_id,),
        ) as cursor:
            products = await cursor.fetchall()

        if not products:
            await db.rollback()
            return PurchaseResult(False, "cart_empty", float(user["balance"]))

        unavailable_ids = [int(product["product_id"]) for product in products if product["status"] != "available"]
        if unavailable_ids:
            await db.rollback()
            return PurchaseResult(False, "not_available", float(user["balance"]), unavailable_ids=unavailable_ids)

        total = normalize_money(sum(float(product["price"]) for product in products))
        balance = float(user["balance"])
        if balance + MONEY_EPSILON < total:
            await db.rollback()
            return PurchaseResult(False, "insufficient_funds", balance, total=total)

        new_balance = normalize_money(balance - total)
        now = utcnow()
        batch_id = uuid.uuid4().hex
        product_ids = [int(product["product_id"]) for product in products]
        await db.execute("UPDATE users SET balance = ?, last_seen_at = ? WHERE user_id = ?", (new_balance, now, user_id))
        await db.execute(
            "INSERT INTO balance_events (user_id, amount, kind, note, actor_id, created_at) VALUES (?, ?, 'purchase', ?, NULL, ?)",
            (user_id, -total, f"Покупка корзины: {', '.join(str(pid) for pid in product_ids)}", now),
        )
        for product in products:
            pid = int(product["product_id"])
            price = float(product["price"])
            await db.execute(
                "UPDATE products SET status = 'sold', sold_to = ?, sold_at = ?, sold_price = ?, purchase_started_at = NULL WHERE product_id = ?",
                (user_id, now, price, pid),
            )
            await db.execute(
                "INSERT INTO purchases (user_id, product_id, price, batch_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, pid, price, batch_id, now),
            )
        await db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
        await db.commit()
        return PurchaseResult(True, "ok", new_balance, product_ids=product_ids, products=products, total=total, batch_id=batch_id)


async def get_stats() -> dict:
    async with get_db_conn() as db:
        async with db.execute("SELECT value FROM app_meta WHERE key = 'revenue_reset_at'") as cursor:
            revenue_reset_row = await cursor.fetchone()
        revenue_reset_at = revenue_reset_row["value"] if revenue_reset_row else None
        async with db.execute("SELECT COUNT(*) AS total FROM users") as cursor:
            users = (await cursor.fetchone())["total"]
        async with db.execute("SELECT COUNT(*) AS total FROM products WHERE status = 'available'") as cursor:
            available = (await cursor.fetchone())["total"]
        async with db.execute("SELECT COALESCE(SUM(price), 0) AS total FROM products WHERE status = 'available'") as cursor:
            stock_value = (await cursor.fetchone())["total"]
        async with db.execute("SELECT COUNT(*) AS total FROM products WHERE status = 'waiting_code'") as cursor:
            waiting = (await cursor.fetchone())["total"]
        async with db.execute("SELECT COUNT(*) AS total FROM products WHERE status = 'sold'") as cursor:
            sold = (await cursor.fetchone())["total"]
        revenue_query = "SELECT COALESCE(SUM(sold_price), 0) AS total FROM products WHERE status IN ('sold', 'waiting_code')"
        revenue_params: tuple[str, ...] = ()
        if revenue_reset_at:
            revenue_query += " AND sold_at >= ?"
            revenue_params = (revenue_reset_at,)
        async with db.execute(revenue_query, revenue_params) as cursor:
            revenue = (await cursor.fetchone())["total"]
        service_revenue_query = "SELECT COALESCE(SUM(amount), 0) AS total FROM service_orders WHERE status = 'delivered'"
        service_revenue_params: tuple[str, ...] = ()
        if revenue_reset_at:
            service_revenue_query += " AND COALESCE(reviewed_at, created_at) >= ?"
            service_revenue_params = (revenue_reset_at,)
        async with db.execute(service_revenue_query, service_revenue_params) as cursor:
            service_revenue = (await cursor.fetchone())["total"]
        total_revenue = float(revenue or 0) + float(service_revenue or 0)
        return {
            "users": int(users),
            "available": int(available),
            "waiting": int(waiting),
            "sold": int(sold),
            "revenue": total_revenue,
            "accounts_revenue": float(revenue or 0),
            "services_revenue": float(service_revenue or 0),
            "stock_value": float(stock_value or 0),
            "revenue_reset_at": revenue_reset_at,
        }


async def reset_revenue_stats() -> str:
    reset_at = utcnow()
    async with get_db_conn() as db:
        await db.execute(
            """
            INSERT INTO app_meta (key, value)
            VALUES ('revenue_reset_at', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (reset_at,),
        )
        await db.commit()
    return reset_at

async def revert_expired_product(product_id: int) -> bool:
    """Возвращает товар в каталог, если он в статусе waiting_code"""
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        async with db.execute(
            "SELECT status, sold_to FROM products WHERE product_id = ?",
            (product_id,)
        ) as cursor:
            product = await cursor.fetchone()

        if not product or product["status"] != "waiting_code":
            await db.rollback()
            return False

        # Возвращаем товар в available
        await db.execute(
            "UPDATE products SET status = 'available', sold_to = NULL, sold_at = NULL WHERE product_id = ?",
            (product_id,)
        )

        # Возвращаем деньги покупателю
        if product["sold_to"]:
            buyer_id = product["sold_to"]
            async with db.execute("SELECT price FROM products WHERE product_id = ?", (product_id,)) as cursor:
                product_data = await cursor.fetchone()
            if product_data:
                price = float(product_data["price"])
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                    (price, buyer_id)
                )
                await db.execute(
                    "INSERT INTO balance_events (user_id, amount, kind, note, actor_id, created_at) VALUES (?, ?, 'refund', ?, NULL, ?)",
                    (buyer_id, price, f"Возврат за товар #{product_id} (истекло время входа)", utcnow())
                )

        await db.commit()
        return True


async def reset_stats() -> None:
    """Сбрасывает статистику: очищает покупки и баланс пользователей (товары НЕ удаляются)"""
    async with get_db_conn() as db:
        try:
            await db.execute("BEGIN IMMEDIATE")
            # Отключаем проверку foreign key для удаления
            await db.execute("PRAGMA foreign_keys=OFF")
            
            # Удаляем только покупки и события баланса
            await db.execute("DELETE FROM purchases")  # очищаем историю покупок
            await db.execute("UPDATE users SET balance = 0")  # очищаем баланс
            await db.execute("DELETE FROM balance_events")  # очищаем события баланса
            # ❌ НЕ УДАЛЯЕМ products - товары остаются!
            
            # Включаем обратно проверку foreign key
            await db.execute("PRAGMA foreign_keys=ON")
            await db.commit()
            logger.info("Статистика сброшена (товары сохранены)")
        except Exception as e:
            await db.rollback()
            logger.error(f"Ошибка при сбросе статистики: {e}")
            raise


async def get_stuck_products() -> list:
    """Получает все товары которые застряли в статусах waiting_code/verifying"""
    async with get_db_conn() as db:
        async with db.execute(
            "SELECT product_id, title, country, price, status, sold_to, sold_at FROM products WHERE status IN ('waiting_code', 'verifying') ORDER BY sold_at"
        ) as cursor:
            return await cursor.fetchall()


async def get_products_by_country(country: str) -> list:
    """Получает товары конкретной страны (только в наличии)"""
    async with get_db_conn() as db:
        async with db.execute(
            "SELECT product_id, title, country, price, description FROM products WHERE country = ? AND status = 'available'",
            (country,)
        ) as cursor:
            return await cursor.fetchall()


async def update_product_info(product_id: int, **fields) -> bool:
    if not fields:
        return False
    set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
    values = list(fields.values())
    values.append(product_id)
    async with get_db_conn() as db:
        cursor = await db.execute(f"UPDATE products SET {set_clause} WHERE product_id = ?", tuple(values))
        await db.commit()
        return cursor.rowcount > 0


async def update_product_group_info(sample_product_id: int, **fields) -> int:
    allowed = {"title", "price", "description", "extra_code"}
    update_fields = {key: value for key, value in fields.items() if key in allowed}
    if not update_fields:
        return 0
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        if sample_product_id < 0:
            async with db.execute(
                """
                SELECT d.department_id, c.name AS country, d.title, d.price
                FROM catalog_departments d
                JOIN catalog_countries c ON c.country_id = d.country_id
                WHERE d.department_id = ? AND d.is_active = 1 AND c.is_active = 1
                """,
                (abs(sample_product_id),),
            ) as cursor:
                sample = await cursor.fetchone()
            if not sample:
                await db.rollback()
                return 0
            set_clause = ", ".join(f"{field} = ?" for field in update_fields)
            values = list(update_fields.values())
            values.append(abs(sample_product_id))
            await db.execute(
                f"UPDATE catalog_departments SET {set_clause} WHERE department_id = ?",
                tuple(values),
            )
            product_fields = dict(update_fields)
            if product_fields:
                set_clause = ", ".join(f"{field} = ?" for field in product_fields)
                values = list(product_fields.values())
                values.extend([sample["country"], sample["title"], sample["price"]])
                cursor = await db.execute(
                    f"""
                    UPDATE products
                    SET {set_clause}
                    WHERE status != 'removed'
                      AND country = ?
                      AND title = ?
                      AND price = ?
                    """,
                    tuple(values),
                )
                changed = int(cursor.rowcount or 0)
            else:
                changed = 0
            await db.commit()
            return max(changed, 1)
        async with db.execute("SELECT country, title, price FROM products WHERE product_id = ?", (sample_product_id,)) as cursor:
            sample = await cursor.fetchone()
        if not sample:
            await db.rollback()
            return 0
        set_clause = ", ".join(f"{field} = ?" for field in update_fields)
        values = list(update_fields.values())
        values.extend([sample["country"], sample["title"], sample["price"]])
        cursor = await db.execute(
            f"""
            UPDATE products
            SET {set_clause}
            WHERE status != 'removed'
              AND country = ?
              AND title = ?
              AND price = ?
            """,
            tuple(values),
        )
        await db.execute(
            f"""
            UPDATE catalog_departments
            SET {set_clause}
            WHERE department_id IN (
                SELECT d.department_id
                FROM catalog_departments d
                JOIN catalog_countries c ON c.country_id = d.country_id
                WHERE c.name = ? AND d.title = ? AND d.price = ?
            )
            """,
            tuple(list(update_fields.values()) + [sample["country"], sample["title"], sample["price"]]),
        )
        await db.commit()
        return cursor.rowcount


async def remove_product_department(sample_product_id: int, removed_by: int) -> dict:
    async with get_db_conn() as db:
        await db.execute("BEGIN IMMEDIATE")
        if sample_product_id < 0:
            async with db.execute(
                """
                SELECT d.department_id, c.name AS country, d.title, d.price
                FROM catalog_departments d
                JOIN catalog_countries c ON c.country_id = d.country_id
                WHERE d.department_id = ? AND d.is_active = 1 AND c.is_active = 1
                """,
                (abs(sample_product_id),),
            ) as cursor:
                sample = await cursor.fetchone()
        else:
            async with db.execute(
                "SELECT country, title, price FROM products WHERE product_id = ? AND status != 'removed'",
                (sample_product_id,),
            ) as cursor:
                sample = await cursor.fetchone()
        if not sample:
            await db.rollback()
            return {"ok": False, "reason": "not_found"}

        async with db.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS available_count
            FROM products
            WHERE status != 'removed' AND country = ? AND title = ? AND price = ?
            """,
            (sample["country"], sample["title"], sample["price"]),
        ) as cursor:
            counts = await cursor.fetchone()
        available_count = int(counts["available_count"] or 0) if counts else 0
        if available_count > 0:
            await db.rollback()
            return {
                "ok": False,
                "reason": "has_available",
                "country": sample["country"],
                "title": sample["title"],
                "price": float(sample["price"]),
                "available": available_count,
            }

        if sample_product_id < 0:
            await db.execute(
                "UPDATE catalog_departments SET is_active = 0 WHERE department_id = ?",
                (abs(sample_product_id),),
            )
        else:
            async with db.execute(
                """
                SELECT d.department_id
                FROM catalog_departments d
                JOIN catalog_countries c ON c.country_id = d.country_id
                WHERE c.name = ? AND d.title = ? AND d.price = ?
                """,
                (sample["country"], sample["title"], sample["price"]),
            ) as cursor:
                catalog_department = await cursor.fetchone()
            if catalog_department:
                await db.execute(
                    "UPDATE catalog_departments SET is_active = 0 WHERE department_id = ?",
                    (catalog_department["department_id"],),
                )
        await db.execute(
            """
            INSERT INTO removed_product_departments (country, title, price, removed_by, removed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(country, title, price) DO UPDATE SET
                removed_by = excluded.removed_by,
                removed_at = excluded.removed_at
            """,
            (sample["country"], sample["title"], sample["price"], removed_by, utcnow()),
        )
        cart_cursor = await db.execute(
            """
            DELETE FROM cart_items
            WHERE product_id IN (
                SELECT product_id
                FROM products
                WHERE country = ? AND title = ? AND price = ? AND status = 'available'
            )
            """,
            (sample["country"], sample["title"], sample["price"]),
        )
        await db.commit()
        return {
            "ok": True,
            "country": sample["country"],
            "title": sample["title"],
            "price": float(sample["price"]),
            "total": int(counts["total"] or 0) if counts else 0,
            "available": available_count,
            "cart_removed": int(cart_cursor.rowcount or 0),
        }


async def get_available_countries() -> list:
    """Получает список стран которые есть в наличии (available статус)"""
    async with get_db_conn() as db:
        async with db.execute(
            "SELECT DISTINCT country, COUNT(*) as count FROM products WHERE status = 'available' GROUP BY country ORDER BY country"
        ) as cursor:
            return await cursor.fetchall()


async def get_all_users_with_purchases() -> list:
    """Получает всех юзеров со статистикой их покупок (для экспорта в Excel)"""
    async with get_db_conn() as db:
        async with db.execute(
            """
            SELECT 
                u.user_id,
                u.username,
                u.first_name,
                u.joined_at,
                u.balance,
                COUNT(p.purchase_id) as purchase_count,
                GROUP_CONCAT(p.product_id, ',') as product_ids
            FROM users u
            LEFT JOIN purchases p ON u.user_id = p.user_id
            GROUP BY u.user_id
            ORDER BY u.joined_at DESC
            """
        ) as cursor:
            return await cursor.fetchall()


async def get_purchase_details(product_id: int):
    """Получает полные детали о конкретном товаре для админа"""
    async with get_db_conn() as db:
        async with db.execute(
            "SELECT * FROM products WHERE product_id = ?",
            (product_id,)
        ) as cursor:
            return await cursor.fetchone()
