# src_solution/abu/tcb/datatypes.py
"""Общие структуры данных для взаимодействия TCB и Other."""

from dataclasses import dataclass


@dataclass
class SecureStep:
    """Шаг бурения, прошедший предварительную валидацию в Other."""
    depth: float
    rpm: int
    pressure: float
    step_id: str
    operator_id: str
    timestamp: float
    risk_level: str          # "low", "medium", "high" – уже вычислен
    vib_sample: float        # нормализованная вибрация (0..1)