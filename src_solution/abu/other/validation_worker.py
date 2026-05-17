# src_solution/abu/other/validation_worker.py
"""Предварительная валидация и подготовка данных (недоверенный код)."""

from typing import Dict, Any, Optional
from src_solution.abu.tcb.datatypes import SecureStep


class StepValidator:
    """Проверяет и нормализует сырые данные от API."""

    def __init__(self, max_depth: float = 1000.0, max_rpm: float = 500.0,
                 max_pressure: float = 100.0):
        self.max_depth = max_depth
        self.max_rpm = max_rpm
        self.max_pressure = max_pressure

    def validate_and_prepare(
            self, raw: Dict[str, Any]) -> Optional[SecureStep]:
        """
        Возвращает SecureStep, если данные корректны, иначе None.
        """
        # Проверка наличия полей
        required = {
            'depth',
            'rpm',
            'pressure',
            'step_id',
            'operator_id',
            'timestamp'}
        if not required.issubset(raw.keys()):
            return None

        # Проверка типов и диапазонов
        try:
            depth = float(raw['depth'])
            rpm = int(raw['rpm'])
            pressure = float(raw['pressure'])
            step_id = str(raw['step_id'])
            operator_id = str(raw['operator_id'])
            timestamp = float(raw['timestamp'])
        except (ValueError, TypeError):
            return None

        if depth < 0 or rpm <= 0 or pressure < 0:
            return None
        if not step_id.strip() or not operator_id.strip():
            return None

        # Расчёт уровня риска (эвристика, покрывается предположением о
        # благонадёжности)
        risk_level = self._compute_risk(depth, rpm, pressure)
        vib_sample = abs(rpm - 300) / 300  # пример нормализации

        return SecureStep(
            depth=depth,
            rpm=rpm,
            pressure=pressure,
            step_id=step_id,
            operator_id=operator_id,
            timestamp=timestamp,
            risk_level=risk_level,
            vib_sample=vib_sample
        )

    def _compute_risk(self, depth: float, rpm: int, pressure: float) -> str:
        """Эвристика уровня риска."""
        if (depth > self.max_depth * 0.9 or
            pressure > self.max_pressure * 0.9 or
                rpm > self.max_rpm * 0.9):
            return "high"
        if (depth > self.max_depth * 0.7 or
            pressure > self.max_pressure * 0.7 or
                rpm > self.max_rpm * 0.7):
            return "medium"
        return "low"
