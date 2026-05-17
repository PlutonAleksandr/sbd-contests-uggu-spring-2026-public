# src_solution/abu/tcb/guard.py
"""
Монитор безопасности ДВБ.
SG_ADS_Authorized_critical_commands,
SG_ADS_Controlled_operations,
SG_ADS_Security_events_store.
"""

from __future__ import annotations

from .datatypes import SecureStep
from .event_log import EventLog, EventLevel, default_log
from .safety import enforce_depth_cap, enforce_rpm_cap, should_emergency_stop


class SecurityMonitor:
    """Принимает только подготовленные SecureStep от доверенного канала."""

    def __init__(self, event_log: EventLog = None,
                 max_depth: float = 1000.0, max_rpm: float = 500.0,
                 max_pressure: float = 100.0):
        self.event_log = event_log or default_log
        self.max_depth = max_depth
        self.max_rpm = max_rpm
        self.max_pressure = max_pressure

    def authorize_step(self, step: SecureStep) -> dict:
        """
        Единственный вход для критичных команд.
        Возвращает словарь с результатом.
        """
        result = {
            "authorized": False,
            "step_id": step.step_id,
            "reason": "",
            "safety_checks": {},
            "emergency": False
        }

        # Проверка аварийного останова
        if should_emergency_stop(step.risk_level, [step.vib_sample]):
            result["reason"] = "Emergency stop triggered"
            result["emergency"] = True
            self._log(EventLevel.CRITICAL, step, result)
            return result

        # Проверка лимитов
        safety_checks = {
            "depth_check": enforce_depth_cap(step.depth, self.max_depth),
            "rpm_check": enforce_rpm_cap(step.rpm, self.max_rpm),
            "pressure_check": step.pressure <= self.max_pressure
        }
        result["safety_checks"] = safety_checks

        if all(safety_checks.values()):
            result["authorized"] = True
            result["reason"] = "All safety checks passed"
            self._log(EventLevel.INFO, step, result)
        else:
            failed = [k for k, v in safety_checks.items() if not v]
            result["reason"] = f"Safety check failed: {', '.join(failed)}"
            self._log(EventLevel.WARNING, step, result)

        return result

    def _log(self, level: EventLevel, step: SecureStep, result: dict):
        """Запись события безопасности."""
        action = "AUTHORIZED" if result["authorized"] else "DENIED"
        msg = (f"Step {step.step_id} by {step.operator_id}: "
               f"{action} - {result['reason']}")
        self.event_log.record(level, msg)


# Глобальный экземпляр (заглушка для совместимости, пока не разнесены процессы)
security_monitor = SecurityMonitor()


def authorize_step(step_data: dict) -> dict:
    """
    Публичная обёртка для внешнего вызова.
    step_data – словарь, полностью подготовленный в Other (или сразу SecureStep?).
    Ожидаем, что step_data уже является словарём с ключами SecureStep.
    """
    # Для обратной совместимости: если передан словарь, создаём SecureStep
    step = SecureStep(**step_data)
    return security_monitor.authorize_step(step)