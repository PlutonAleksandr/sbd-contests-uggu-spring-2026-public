# src_solution/abu/tcb/guard.py
"""
Trusted Computing Base Guard Module
Единственная точка входа для авторизации критичных команд бурения
"""

from dataclasses import dataclass
from typing import Dict, Any
import logging

from .event_log import EventLog, EventLevel, default_log
from .safety import enforce_depth_cap, enforce_rpm_cap, should_emergency_stop

logger = logging.getLogger(__name__)


@dataclass
class DrillingStep:
    """Критический шаг бурения"""
    depth: float
    rpm: int
    pressure: float
    step_id: str
    operator_id: str
    timestamp: float
    
    def validate(self) -> bool:
        """Валидация параметров шага"""
        return all([
            self.depth >= 0,
            self.rpm > 0,
            self.pressure >= 0,
            self.operator_id.strip() != "",
            self.step_id.strip() != ""
        ])


@dataclass
class AuthorizationResult:
    """Результат авторизации"""
    authorized: bool
    step_id: str
    reason: str
    safety_checks: Dict[str, bool]
    emergency: bool = False


class TCBGuard:
    """
    Trusted Computing Base Guard
    SG_ADS_Authorized_critical_commands: Все критические команды проходят через authorize_step
    SG_ADS_Controlled_operations: Глубина, RPM, emergency и риск проверяются здесь
    """
    
    def __init__(self, event_log: EventLog = None, max_depth: float = 1000.0, max_rpm: float = 500.0, max_pressure: float = 100.0):
        self.event_log = event_log or default_log
        self.max_depth = max_depth
        self.max_rpm = max_rpm
        self.max_pressure = max_pressure
        self._authorized_steps = set()
        
    def authorize_step(self, step: DrillingStep) -> AuthorizationResult:
        """
        ЕДИНСТВЕННЫЙ доверенный вход для разрешения критичного шага
        
        Args:
            step: Параметры шага бурения
            
        Returns:
            AuthorizationResult с решением
        """
        # 1. Валидация входных данных
        if not step.validate():
            result = AuthorizationResult(
                authorized=False,
                step_id=step.step_id,
                reason="Invalid step parameters",
                safety_checks={}
            )
            self._log_event(result, step)
            return result
        
        # 2. Определяем уровень риска на основе параметров
        risk_level = self._calculate_risk_level(step)
        
        # 3. Конвертируем параметры для проверки вибрации
        # Используем отклонение RPM от нормы как аналог вибрации
        vibration_value = abs(step.rpm - 300) / 300  # Нормализованное отклонение
        vib_samples = [vibration_value]
        
        # 4. Проверка на аварийную остановку (SG_ADS_Controlled_operations)
        if should_emergency_stop(risk_level, vib_samples):
            result = AuthorizationResult(
                authorized=False,
                step_id=step.step_id,
                reason=f"Emergency stop: risk={risk_level}, vibration={vibration_value:.2f}",
                safety_checks={"emergency_stop": True},
                emergency=True
            )
            self._log_event(result, step)
            return result
        
        # 5. Проверка лимитов безопасности (SG_ADS_Controlled_operations)
        safety_checks = {
            "depth_check": enforce_depth_cap(step.depth, self.max_depth),
            "rpm_check": enforce_rpm_cap(step.rpm, self.max_rpm),
            "pressure_check": step.pressure <= self.max_pressure
        }
        
        # 6. Принятие решения
        if all(safety_checks.values()):
            self._authorized_steps.add(step.step_id)
            result = AuthorizationResult(
                authorized=True,
                step_id=step.step_id,
                reason="All safety checks passed",
                safety_checks=safety_checks
            )
        else:
            failed = [k for k, v in safety_checks.items() if not v]
            result = AuthorizationResult(
                authorized=False,
                step_id=step.step_id,
                reason=f"Safety check failed: {', '.join(failed)}",
                safety_checks=safety_checks
            )
        
        # 7. Журналирование (SG_ADS_Security_events_store)
        self._log_event(result, step)
        return result
    
    def revoke_authorization(self, step_id: str) -> bool:
        """Отзыв авторизации (для экстренных ситуаций)"""
        if step_id in self._authorized_steps:
            self._authorized_steps.remove(step_id)
            self.event_log.record(EventLevel.WARNING, f"Authorization revoked for step {step_id}")
            return True
        return False
    
    def _calculate_risk_level(self, step: DrillingStep) -> str:
        """
        Определение уровня риска на основе параметров бурения
        
        Returns:
            "high", "medium", или "low"
        """
        # Высокий риск если:
        # - глубина > 90% от максимума
        # - давление > 90% от максимума
        # - RPM > 90% от максимума
        if (step.depth > self.max_depth * 0.9 or 
            step.pressure > self.max_pressure * 0.9 or 
            step.rpm > self.max_rpm * 0.9):
            return "high"
        
        # Средний риск если параметры > 70% от максимума
        if (step.depth > self.max_depth * 0.7 or 
            step.pressure > self.max_pressure * 0.7 or 
            step.rpm > self.max_rpm * 0.7):
            return "medium"
        
        return "low"
    
    def _log_event(self, result: AuthorizationResult, step: DrillingStep):
        """Журналирование события безопасности"""
        level = EventLevel.INFO if result.authorized else EventLevel.WARNING
        if result.emergency:
            level = EventLevel.CRITICAL
            
        message = (
            f"Step {step.step_id} by {step.operator_id}: "
            f"{'AUTHORIZED' if result.authorized else 'DENIED'} - {result.reason}"
        )
        self.event_log.record(level, message)


# Singleton instance для использования во всем TCB
guard = TCBGuard()


def authorize_step(step_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Публичный API для авторизации шага
    
    Args:
        step_data: Словарь с параметрами шага
        
    Returns:
        Результат авторизации в виде словаря
    """
    step = DrillingStep(**step_data)
    result = guard.authorize_step(step)
    
    return {
        "authorized": result.authorized,
        "step_id": result.step_id,
        "reason": result.reason,
        "safety_checks": result.safety_checks,
        "emergency": result.emergency
    }