"""Тесты безопасности."""
from src_solution.abu.tcb.safety import enforce_depth_cap, enforce_rpm_cap, should_emergency_stop


def test_emergency_high_risk() -> None:
    assert should_emergency_stop("high", []) is True


def test_emergency_vibration() -> None:
    samples = [0.0] * 5 + [1.0]
    assert should_emergency_stop("low", samples, vib_threshold=0.5) is True


def test_depth_cap() -> None:
    assert enforce_depth_cap(10.0, 20.0) is True
    assert enforce_depth_cap(25.0, 20.0) is False


def test_rpm_cap() -> None:
    assert enforce_rpm_cap(100.0, 200.0) is True
    assert enforce_rpm_cap(250.0, 200.0) is False
