from __future__ import annotations

import asyncio
import inspect
import logging
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon.errors import (
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberFloodError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest

from .config import Settings
from .db import get_product_session_path, update_code_fetched_at, get_product, update_product_session_path
from .paths import product_session_base_path, temp_session_base_path
from .proxy_store import load_global_proxy
from .proxy_utils import build_telegram_client, format_proxy_summary

logger = logging.getLogger(__name__)
LOGIN_STEP_TIMEOUT = 25


@dataclass(slots=True)
class ActiveLogin:
    login_id: str
    phone: str
    temp_session_base: Path
    client: object
    phone_code_hash: str
    proxy_settings: dict | None = None
    password_used: str = ""


class LoginExpiredError(RuntimeError):
    pass


class ShopSessionManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.active: dict[int, ActiveLogin] = {}

    async def cleanup(self, admin_id: int) -> None:
        flow = self.active.pop(admin_id, None)
        if not flow:
            return
        try:
            await flow.client.disconnect()
        except Exception:
            pass
        for suffix in (".session", ".session-journal", ".session-wal", ".session-shm"):
            path = Path(f"{flow.temp_session_base}{suffix}")
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass

    def _cleanup_temp_files(self, temp_session_base: Path) -> None:
        for suffix in (".session", ".session-journal", ".session-wal", ".session-shm"):
            path = Path(f"{temp_session_base}{suffix}")
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    logger.warning("Could not remove temp session file: %s", path)

    def _build_client(self, session_base: Path, proxy_settings: dict | None):
        return build_telegram_client(
            session_base,
            self.settings.api_id,
            self.settings.api_hash,
            proxy_settings,
            device_model=self.settings.device_model,
            system_version=self.settings.system_version,
            app_version=self.settings.app_version,
            lang_code=self.settings.lang_code,
            system_lang_code=self.settings.system_lang_code,
        )

    async def _get_product_session_path(self, product_id: int) -> str | None:
        session_path = get_product_session_path(product_id)
        if inspect.isawaitable(session_path):
            session_path = await session_path
        return session_path

    async def logout_and_delete_product_session(self, product_id: int) -> bool:
        session_path = await self._get_product_session_path(product_id)
        if not session_path:
            return False

        session_file = Path(session_path)
        proxy_settings = load_global_proxy()
        client = None
        try:
            if session_file.exists():
                client = self._build_client(session_file, proxy_settings)
                await client.connect()
                if await client.is_user_authorized():
                    await client.log_out()
        except Exception:
            logger.exception("Could not logout product session #%s", product_id)
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass

        removed_any = False
        candidates = {session_file}
        base_text = str(session_file)
        if base_text.endswith(".session"):
            base_text = base_text[:-8]
        for suffix in (".session", ".session-journal", ".session-wal", ".session-shm"):
            candidates.add(Path(f"{base_text}{suffix}"))
        for path in candidates:
            if path.exists():
                try:
                    path.unlink()
                    removed_any = True
                except Exception:
                    logger.warning("Could not remove product session file: %s", path)

        await update_product_session_path(product_id, "")
        return removed_any

    def _parse_dt(self, value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc) - timedelta(minutes=10)
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    async def _get_telegram_dialog(self, client):
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            entity_id = getattr(entity, "id", None)
            entity_username = getattr(entity, "username", None)
            if entity_id == 777000 or (entity_username and entity_username.lower() == "telegram"):
                return dialog
        return await client.get_entity(777000)

    def _looks_like_new_login_notice(self, text: str) -> bool:
        normalized = (text or "").casefold()
        if not normalized:
            logger.debug(f"[_looks_like_new_login_notice] Пустой текст")
            return False
        
        # Отфильтровываем ТОЛЬКО явные сообщения о коде подтверждения
        code_only_markers = ("login code is:", "к0d для входа:", "к0d входа:", "your login code")
        for marker in code_only_markers:
            if marker in normalized:
                logger.debug(f"[_looks_like_new_login_notice] ❌ Это сообщение о К0D (найден маркер '{marker}')")
                return False
        
        login_markers = (
            # Английские маркеры
            "new login",
            "login from",
            "login into",
            "logged in",
            "new device",
            "new session",
            "successful login",
            "login confirmed",
            "new location",
            "unknown location",
            # Русские маркеры
            "новый вход",
            "вход в аккаунт",
            "вход с нового",
            "обнаружили вход",
            "новая сессия",
            "новое устройство",
            "выполнен вход",
            "вход выполнен",
            "вы вошли",
            "успешно вошли",
            "вход успешен",
            "вход с неизвестного",
            "вход из неизвестной",
            "подтвердили вход",
            "вход подтвержден",
        )
        
        for marker in login_markers:
            if marker in normalized:
                logger.info(f"[_looks_like_new_login_notice] ✅ СОВПАДЕНИЕ! Найден маркер '{marker}'")
                return True
        
        logger.debug(f"[_looks_like_new_login_notice] ❌ Не подходит ни под один маркер входа. Текст: {text[:80]}")
        return False

    async def _connect_with_backoff(self, client, max_retries: int = 2, base_delay: float = 1.0) -> None:
        for attempt in range(max_retries):
            try:
                await asyncio.wait_for(client.connect(), timeout=LOGIN_STEP_TIMEOUT)
                if not client.is_connected():
                    raise ConnectionError("Telethon не установил соединение.")
                return
            except (ValueError, OSError, ConnectionError, EOFError, asyncio.IncompleteReadError, asyncio.TimeoutError) as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning("Telegram connect failed on attempt %s/%s: %s", attempt + 1, max_retries, e)
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

    async def _run_once(self, awaitable, *, timeout: int = LOGIN_STEP_TIMEOUT):
        return await asyncio.wait_for(awaitable, timeout=timeout)

    def _format_login_error(self, exc: Exception, proxy_settings: dict | None = None) -> str:
        if isinstance(exc, PhoneNumberBannedError):
            return "Номер забанен/заморожен Telegram и не может войти через API."
        if isinstance(exc, PhoneNumberInvalidError):
            return "Telegram считает номер некорректным."
        if isinstance(exc, PhoneNumberFloodError):
            return "Слишком много попыток входа по этому номеру. Нужно подождать."
        if isinstance(exc, FloodWaitError):
            return f"Telegram просит подождать {exc.seconds} сек. перед новой попыткой."
        if isinstance(exc, PhoneCodeExpiredError):
            return "Код уже истёк. Начни добавление заново."
        if isinstance(exc, PasswordHashInvalidError):
            return "Неверный пароль 2FA."

        details = str(exc).strip() or type(exc).__name__
        if proxy_settings:
            return (
                "Не удалось выполнить вход через заданный прокси.\n\n"
                f"{format_proxy_summary(proxy_settings)}\n\n"
                f"Ошибка: {details}"
            )
        return details

    async def send_code(self, admin_id: int, phone: str) -> None:
        await self.cleanup(admin_id)
        login_id = str(int(time.time() * 1000))
        temp_base = temp_session_base_path(admin_id, login_id)
        proxy_settings = load_global_proxy()

        client = None
        try:
            client = self._build_client(temp_base, proxy_settings)
            await self._connect_with_backoff(client, max_retries=2)
            sent = await self._run_once(client.send_code_request(phone))
        except (RuntimeError, ValueError, OSError, ConnectionError, EOFError, asyncio.IncompleteReadError, asyncio.TimeoutError) as e:
            if client is not None:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            self._cleanup_temp_files(temp_base)
            if proxy_settings:
                logger.warning("Ошибка подключения через заданный прокси: %s", e)
                raise RuntimeError(self._format_login_error(e, proxy_settings)) from e
            raise
        except Exception as e:
            if client is not None:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            self._cleanup_temp_files(temp_base)
            raise RuntimeError(self._format_login_error(e, proxy_settings)) from e

        self.active[admin_id] = ActiveLogin(
            login_id=login_id,
            phone=phone,
            temp_session_base=temp_base,
            client=client,
            phone_code_hash=sent.phone_code_hash,
            proxy_settings=proxy_settings,
        )

    def get(self, admin_id: int) -> ActiveLogin:
        flow = self.active.get(admin_id)
        if not flow:
            raise LoginExpiredError("Сессия логина истекла. Начни добавление заново.")
        return flow

    async def submit_code(self, admin_id: int, code: str):
        flow = self.get(admin_id)
        try:
            async def sign_in():
                await flow.client.sign_in(phone=flow.phone, code=code, phone_code_hash=flow.phone_code_hash)
                me = await flow.client.get_me()
                return me
            
            me = await self._run_once(sign_in())
            return {"ok": True, "need_password": False, "me": me}
        except SessionPasswordNeededError:
            return {"ok": True, "need_password": True, "me": None}
        except PhoneCodeInvalidError:
            return {"ok": False, "reason": "invalid_code"}
        except Exception as exc:
            raise RuntimeError(self._format_login_error(exc, flow.proxy_settings)) from exc

    async def submit_password(self, admin_id: int, password: str):
        flow = self.get(admin_id)
        
        async def sign_with_password():
            await flow.client.sign_in(password=password)
            me = await flow.client.get_me()
            return me
        
        try:
            me = await self._run_once(sign_with_password())
        except Exception as exc:
            raise RuntimeError(self._format_login_error(exc, flow.proxy_settings)) from exc
        flow.password_used = password
        return me

    async def finalize_product_session(self, admin_id: int, product_id: int) -> Path:
        flow = self.get(admin_id)
        final_base = product_session_base_path(product_id)
        final_session = Path(f"{final_base}.session")
        source_session = Path(f"{flow.temp_session_base}.session")
        if not source_session.exists():
            raise RuntimeError("Файл сессии не найден после логина.")
        try:
            await flow.client.disconnect()
        except Exception:
            pass
        final_session.parent.mkdir(parents=True, exist_ok=True)
        if final_session.exists():
            final_session.unlink()
        shutil.copy2(source_session, final_session)
        for suffix in (".session", ".session-journal", ".session-wal", ".session-shm"):
            path = Path(f"{flow.temp_session_base}{suffix}")
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass
        self.active.pop(admin_id, None)
        return final_session

    async def fetch_code_from_telegram(self, product_id: int) -> str:
        """
        Получает ПЕРВЫЙ полученный код из чата Telegram (за последние 5 минут).
        Если несколько кодов - вернет самый первый (самый старый).
        Возвращает код.
        """
        session_path = await self._get_product_session_path(product_id)
        if not session_path or not Path(session_path).exists():
            raise RuntimeError("Сессия товара не найдена. Обратитесь к администратору.")
        
        proxy_settings = load_global_proxy()
        client = self._build_client(Path(session_path), proxy_settings)
        
        try:
            await self._connect_with_backoff(client, max_retries=2)
            
            if not await client.is_user_authorized():
                raise RuntimeError("Сессия товара недействительна. Обратитесь к администратору.")
            
            # Получаем текущее время в UTC
            now = datetime.now(timezone.utc)
            five_minutes_ago = now - timedelta(minutes=5)
            
            logger.info(f"[product={product_id}] Ищу k0dы с {five_minutes_ago.isoformat()}")
            
            # Ищем диалог с Telegram (служебный аккаунт)
            target_dialog = None
            async for dialog in client.iter_dialogs():
                entity = dialog.entity
                entity_id = getattr(entity, 'id', None)
                entity_username = getattr(entity, 'username', None)
                
                if entity_id == 777000 or (entity_username and entity_username.lower() == "telegram"):
                    target_dialog = dialog
                    logger.info(f"[product={product_id}] Найден диалог с Telegram")
                    break
            
            if not target_dialog:
                # Пробуем найти через get_entity по ID
                try:
                    target_dialog = await client.get_entity(777000)
                    logger.info(f"[product={product_id}] Диалог с Telegram получен через get_entity")
                except Exception:
                    raise RuntimeError("Не удалось найти чат с @Telegram.")
            
            # Ищем ПОСЛЕДНИЙ (самый новый) полученный код за последние 5 минут
            found_codes = []
            messages_checked = 0
            
            logger.info(f"[product={product_id}] === НАЧИНАЮ ПОИСК КОДОВ ===")
            logger.info(f"[product={product_id}] Ищу коды с {five_minutes_ago.isoformat()}")
            
            async for msg in client.iter_messages(target_dialog, limit=20):
                messages_checked += 1
                msg_date = msg.date.astimezone(timezone.utc) if hasattr(msg.date, 'astimezone') else msg.date
                if msg_date.tzinfo is None:
                    msg_date = msg_date.replace(tzinfo=timezone.utc)
                    
                text = msg.text or ""
                logger.info(f"[product={product_id}] msg#{messages_checked}: {msg_date.isoformat()} | ТЕКСТ: {text[:150]}")
                
                if msg_date < five_minutes_ago:
                    logger.info(f"[product={product_id}] msg#{messages_checked}: ⏱️ ПРОПУСКАЮ - старше 5 минут")
                    continue  # Сообщение старше 5 минут, пропускаем
                
                logger.info(f"[product={product_id}] msg#{messages_checked}: ⏳ ПРОВЕРЯЮ - ищу k0d (5-6 цифр)...")
                
                # Ищем код в сообщении (5-6 цифр)
                match = re.search(r'\b(\d{5,6})\b', text)
                if match:
                    code = match.group(1)
                    found_codes.append((msg_date, code))
                    logger.info(f"[product={product_id}] ✅ НАЙДЕН КОД: {code} в сообщении от {msg_date.isoformat()}")
                else:
                    logger.debug(f"[product={product_id}] msg#{messages_checked}: ❌ Кода нет в этом сообщении")
            
            if not found_codes:
                logger.warning(f"[product={product_id}] Кодов не найдено. Проверено {messages_checked} сообщений")
                raise RuntimeError("Пока новых к0dов нет.")
            
            # Сортируем по дате, берём ПОСЛЕДНИЙ (самый новый) полученный код
            found_codes.sort(key=lambda x: x[0])
            last_code = found_codes[-1][1]  # Последний элемент - самый новый код
            
            logger.info(f"[product={product_id}] Найдено {len(found_codes)} к0dов, отправляю последний (самый новый): {last_code}")
            
            # Сохраняем время получения кода в БД
            try:
                await update_code_fetched_at(product_id)
                logger.info(f"[product={product_id}] Время получения к0dа сохранено в БД")
            except Exception as db_error:
                logger.warning(f"[product={product_id}] Не удалось сохранить время получения к0dа: {db_error}")
            
            await client.disconnect()
            return last_code
            
        except Exception as e:
            logger.exception(f"[product={product_id}] Ошибка при получении к0dа: {e}")
            try:
                await client.disconnect()
            except:
                pass
            raise RuntimeError(f"Ошибка при получении к0dа: {str(e)}")

    async def detect_buyer_login(self, product_id: int, since: str | None) -> dict:
        """Detect buyer login by checking for new active sessions in account.
        
        Uses GetAuthorizationsRequest API to get sessions with creation dates,
        filters for sessions created after deal start (sold_at).
        More reliable than message text search.
        """
        session_path = await self._get_product_session_path(product_id)
        if not session_path or not Path(session_path).exists():
            return {"confirmed": False, "error": "Сессия товара не найдена"}

        proxy_settings = load_global_proxy()
        client = self._build_client(Path(session_path), proxy_settings)
        
        # Ищем входы ПОСЛЕ момента начала сделки (sold_at)
        # Используем sold_at как границу поиска - сессия должна быть создана ПОСЛЕ этого времени
        search_since_dt = self._parse_dt(since)
        logger.info(f"[product={product_id}] === ПРОВЕРКА СЕССИЙ В АККАУНТЕ ===")
        logger.info(f"[product={product_id}] Ищу НОВЫЕ сессии, созданные ПОСЛЕ: {search_since_dt.isoformat()} (sold_at={since})")

        try:
            await self._connect_with_backoff(client, max_retries=1)
            if not await client.is_user_authorized():
                return {"confirmed": False, "error": "Сессия товара недействительна"}

            # Get all active sessions using GetAuthorizationsRequest API
            auth_request = GetAuthorizationsRequest()
            result = await client(auth_request)
            
            sessions_total = len(result.authorizations) if hasattr(result, 'authorizations') else 0
            logger.info(f"[product={product_id}] Всего сессий в аккаунте: {sessions_total}")
            
            for idx, session in enumerate(result.authorizations, 1):
                session_date = session.date_created
                
                # Ensure session_date is timezone-aware (UTC)
                if hasattr(session_date, 'astimezone'):
                    session_date = session_date.astimezone(timezone.utc)
                elif session_date.tzinfo is None:
                    session_date = session_date.replace(tzinfo=timezone.utc)
                
                device_info = getattr(session, 'device_model', 'unknown')
                app_name = getattr(session, 'app_name', 'unknown')
                
                logger.info(f"[product={product_id}] Сессия #{idx}: created={session_date.isoformat()} | device={device_info} | app={app_name}")
                
                # Check if session was created STRICTLY AFTER deal start
                if session_date > search_since_dt:
                    logger.info(f"[product={product_id}] ✅✅✅ НАЙДЕНА НОВАЯ СЕССИЯ!")
                    logger.info(f"[product={product_id}] Время создания: {session_date.isoformat()} > {search_since_dt.isoformat()}")
                    return {
                        "confirmed": True,
                        "session_date": session_date.isoformat(timespec="seconds"),
                        "device": f"{device_info}",
                    }
                else:
                    logger.info(f"[product={product_id}] Сессия #{idx}: ❌ СТАРАЯ - {session_date.isoformat()} <= {search_since_dt.isoformat()}")
            
            logger.warning(f"[product={product_id}] === НОВАЯ СЕССИЯ НЕ НАЙДЕНА ===")
            logger.warning(f"[product={product_id}] Проверено {sessions_total} сессий, ни одна не соответствует критериям")
            logger.warning(f"[product={product_id}] Нужно найти сессию, созданную ПОСЛЕ: {search_since_dt.isoformat()}")
            return {"confirmed": False, "error": "Новая сессия в аккаунте не обнаружена"}
        except Exception as e:
            logger.exception(f"[product={product_id}] Ошибка при проверке сессий: {e}")
            return {"confirmed": False, "error": str(e) or type(e).__name__}
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def verify_account_alive(self, product_id: int) -> dict:
        """
        Проверяет живой ли аккаунт:
        - Может ли мы к нему подключиться
        - Авторизован ли он
        - Получаем инфо о профиле
        """
        session_path = await self._get_product_session_path(product_id)
        if not session_path or not Path(session_path).exists():
            return {"alive": False, "error": "Сессия не найдена"}
        
        proxy_settings = load_global_proxy()
        client = self._build_client(Path(session_path), proxy_settings)
        
        try:
            await self._connect_with_backoff(client, max_retries=1)
            
            if not await client.is_user_authorized():
                return {"alive": False, "error": "Аккаунт не авторизован"}
            
            # Получаем инфо о пользователе
            me = await client.get_me()
            
            await client.disconnect()
            
            return {
                "alive": True,
                "user_id": me.id,
                "phone": me.phone,
                "username": me.username or "нет",
                "first_name": me.first_name or "User"
            }
            
        except Exception as e:
            try:
                await client.disconnect()
            except:
                pass
            return {"alive": False, "error": f"Ошибка: {str(e)}"}

    async def verify_session_file_alive(self, session_path: str | Path) -> dict:
        """Check a raw .session file before creating a product row."""
        session_file = Path(session_path)
        if not session_file.exists():
            return {"alive": False, "error": "Сессия не найдена"}

        proxy_settings = load_global_proxy()
        client = self._build_client(session_file, proxy_settings)
        try:
            await self._connect_with_backoff(client, max_retries=1)
            if not await client.is_user_authorized():
                return {"alive": False, "error": "Аккаунт не авторизован"}

            me = await client.get_me()
            return {
                "alive": True,
                "user_id": me.id,
                "phone": me.phone,
                "username": me.username or "",
                "first_name": me.first_name or "User",
            }
        except Exception as e:
            return {"alive": False, "error": f"Ошибка: {str(e)}"}
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def terminate_other_sessions(self, product_id: int) -> dict:
        """Terminate all active authorizations except the server session itself."""
        session_path = await self._get_product_session_path(product_id)
        if not session_path or not Path(session_path).exists():
            return {"ok": False, "error": "Сессия товара не найдена"}

        proxy_settings = load_global_proxy()
        client = self._build_client(Path(session_path), proxy_settings)
        try:
            await self._connect_with_backoff(client, max_retries=1)
            if not await client.is_user_authorized():
                return {"ok": False, "error": "Сессия не авторизована"}

            result = await client(GetAuthorizationsRequest())
            authorizations = getattr(result, "authorizations", []) or []
            total = len(authorizations)
            current = 0
            terminated = 0
            failed = 0
            for authorization in authorizations:
                if getattr(authorization, "current", False):
                    current += 1
                    continue
                auth_hash = getattr(authorization, "hash", None)
                if auth_hash is None:
                    failed += 1
                    continue
                try:
                    await client(ResetAuthorizationRequest(hash=auth_hash))
                    terminated += 1
                    await asyncio.sleep(1)
                except Exception:
                    failed += 1
                    logger.warning("Could not terminate authorization for product #%s", product_id, exc_info=True)

            return {"ok": True, "total": total, "current": current, "terminated": terminated, "failed": failed}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
