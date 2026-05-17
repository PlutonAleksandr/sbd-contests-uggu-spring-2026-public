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
    depth: float,
    rpm: float,
    pressure: float,
    max_depth: float = 1000.0,
    max_rpm: float = 500.0,
    max_pressure: float = 100.0,
) -> bool:
    """
    Аварийный стоп при превышении критических параметров.

    :param depth: текущая глубина
    :param rpm: текущие обороты
    :param pressure: текущее давление
    :param max_depth: максимальная глубина
    :param max_rpm: максимальные обороты
    :param max_pressure: максимальное давление
    :returns: True если нужна остановка
    """
    if depth > max_depth:
        return True
    if rpm > max_rpm:
        return True
    if pressure > max_pressure:
        return True
    return False