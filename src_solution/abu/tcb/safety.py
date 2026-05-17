"""Проверки безопасности (ДВБ)."""

from __future__ import annotations


def enforce_depth_cap(depth_m: float, max_depth_m: float) -> bool:
    """
    Проверка верхнего предела глубины.

    :param depth_m: текущая глубина
    :param max_depth_m: допустимый максимум
    :returns: True если можно продолжать
    """
    return depth_m <= max_depth_m


def enforce_rpm_cap(rpm: float, max_rpm: float) -> bool:
    """Проверка верхнего предела оборотов."""
    return rpm <= max_rpm


def should_emergency_stop(
    risk: str,
    vib_samples: list[float],
    vib_threshold: float = 0.9,
) -> bool:
    """
    Аварийный стоп при высоком риске или аномальной вибрации.

    :param risk: уровень риска ("high", "medium", "low")
    :param vib_samples: последние замеры вибрации
    :param vib_threshold: порог для определения аномальной вибрации
    :returns: True если нужна остановка
    """
    # Проверка высокого риска
    if risk == "high":
        return True
    
    # Проверка аномальной вибрации
    if vib_samples and len(vib_samples) > 0:
        # Простая проверка: если есть значения выше порога
        if max(vib_samples) >= vib_threshold:
            return True
    
    return False