"""Тесты безопасности для ДВБ (SecurityMonitor)."""

import pytest
from multiprocessing import Queue
from src_solution.abu.tcb.sys.security_monitor import SecurityMonitorProcess
from src_solution.abu.tcb.datatypes import SecureStep


@pytest.mark.security
def test_authorize_valid_step():
    q_in, q_out = Queue(), Queue()
    monitor = SecurityMonitorProcess(q_in, q_out)
    step = SecureStep(
        depth=500.0,
        rpm=200,
        pressure=50.0,
        step_id="test-1",
        operator_id="op1",
        timestamp=1234567890.0,
        risk_level="low",
        vib_sample=0.1
    )
    result = monitor._authorize(step.__dict__)
    assert result["authorized"] is True
    assert result["emergency"] is False
    assert result["reason"] == "All safety checks passed"


@pytest.mark.security
def test_authorize_emergency_stop():
    q_in, q_out = Queue(), Queue()
    monitor = SecurityMonitorProcess(q_in, q_out)
    step = SecureStep(
        depth=950.0,
        rpm=480,
        pressure=95.0,
        step_id="test-2",
        operator_id="op2",
        timestamp=1234567890.0,
        risk_level="high",
        vib_sample=0.9
    )
    result = monitor._authorize(step.__dict__)
    assert result["authorized"] is False
    assert result["emergency"] is True


@pytest.mark.security
def test_authorize_invalid_payload():
    q_in, q_out = Queue(), Queue()
    monitor = SecurityMonitorProcess(q_in, q_out)
    result = monitor._authorize({"invalid": "data"})
    assert result["authorized"] is False
    assert "Invalid step data" in result["reason"]
