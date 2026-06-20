"""
Логика покупки и верификации товаров.
Этот файл содержит всю бизнес-логику для обработки покупок, получения кодов и верификации.
"""

from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# === КОНСТАНТЫ ===
PURCHASE_TIMEOUT_SECONDS = 600  # 10 минут
CODE_REQUEST_COOLDOWN_SECONDS = 5  # Минимум 5 сек между запросами кода
VERIFICATION_TIMEOUT_SECONDS = 600  # 10 минут на верификацию


class PurchasePhase(Enum):
    """Фазы покупки"""
    WAITING_CODE = "waiting_code"  # Товар куплен, ждем кода
    VERIFYING = "verifying"  # Код получен, ожидаем входа
    SOLD = "sold"  # Успешно продан
    EXPIRED = "expired"  # Таймаут, товар возвращен


@dataclass
class PurchaseStatus:
    """Статус покупки товара"""
    product_id: int
    user_id: int
    phase: PurchasePhase
    started_at: datetime
    code_requested_at: Optional[datetime] = None
    code: Optional[str] = None
    is_expired: bool = False
    time_left_seconds: int = 0
    can_request_code: bool = False
    can_verify: bool = False
    error: Optional[str] = None
    
    @property
    def elapsed_seconds(self) -> int:
        """Сколько секунд прошло с начала покупки"""
        return int((datetime.utcnow() - self.started_at).total_seconds())
    
    @property
    def is_timed_out(self) -> bool:
        """Истек ли таймаут"""
        return self.elapsed_seconds >= PURCHASE_TIMEOUT_SECONDS
    
    def check_timeout(self) -> None:
        """Проверить таймаут и обновить статус"""
        if self.is_timed_out:
            self.is_expired = True
            self.phase = PurchasePhase.EXPIRED
            self.error = "Таймаут 10 минут истёк"
        self.time_left_seconds = max(0, PURCHASE_TIMEOUT_SECONDS - self.elapsed_seconds)
    
    def update_permissions(self) -> None:
        """Обновить доступные действия"""
        self.check_timeout()
        
        if self.is_expired:
            self.can_request_code = False
            self.can_verify = False
            return
        
        if self.phase == PurchasePhase.WAITING_CODE:
            # Можно запрашивать код
            can_request = True
            if self.code_requested_at:
                elapsed = (datetime.utcnow() - self.code_requested_at).total_seconds()
                can_request = elapsed >= CODE_REQUEST_COOLDOWN_SECONDS
            self.can_request_code = can_request
            self.can_verify = self.code is not None
        
        elif self.phase == PurchasePhase.VERIFYING:
            # Можно проверять верификацию
            self.can_verify = True
            self.can_request_code = True  # Можно вернуться за новым кодом


class PurchaseManager:
    """Управляет логикой покупок"""
    
    @staticmethod
    def build_purchase_message(status: PurchaseStatus, product_title: str, phone: str) -> str:
        """Собирает сообщение о статусе покупки"""
        if status.is_expired:
            return (
                f"❌ <b>Таймаут покупки истёк</b>\n\n"
                f"Товар «{product_title}» возвращен в каталог.\n"
                f"Баланс возвращен."
            )
        
        time_min = status.time_left_seconds // 60
        time_sec = status.time_left_seconds % 60
        
        if status.phase == PurchasePhase.WAITING_CODE:
            return (
                f"📦 <b>{product_title}</b>\n"
                f"📱 Телефон: <code>{phone}</code>\n\n"
                f"Статус: <b>Ожидаю кода</b>\n"
                f"⏱ Время: <b>{time_min}:{time_sec:02d}</b> осталось\n\n"
                f"Нажми кнопку ниже, чтобы получить код."
            )
        
        elif status.phase == PurchasePhase.VERIFYING:
            return (
                f"📦 <b>{product_title}</b>\n"
                f"🔑 Код получен\n\n"
                f"Статус: <b>Ожидаю входа в аккаунт</b>\n"
                f"⏱ Время: <b>{time_min}:{time_sec:02d}</b> осталось\n\n"
                f"Пожалуйста, войдите в аккаунт с помощью полученного кода.\n"
                f"Когда войдёте, нажмите кнопку ниже."
            )
        
        return ""
    
    @staticmethod
    def get_action_buttons(status: PurchaseStatus, product_id: int) -> list[tuple[str, str]]:
        """Получить доступные кнопки действий"""
        buttons = []
        
        if status.is_expired:
            return [("⬅️ Вернуться", "menu_home")]
        
        if status.phase == PurchasePhase.WAITING_CODE:
            if status.can_request_code:
                buttons.append(("📨 Получить код", f"get_code:{product_id}"))
            else:
                buttons.append(("⏳ Код ещё не готов", "noop"))
            
            if status.code:
                buttons.append(("✅ Я вошел!", f"start_verify:{product_id}"))
        
        elif status.phase == PurchasePhase.VERIFYING:
            buttons.append(("🔄 Проверить вход", f"check_verify:{product_id}"))
            buttons.append(("📨 Получить код заново", f"get_code:{product_id}"))
        
        buttons.append(("⬅️ В меню", "menu_home"))
        return buttons
