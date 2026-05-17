"""Модульные тесты журнала событий."""

from __future__ import annotations

from src_solution.abu.tcb.event_log import EventLevel, EventLog


def test_ring_maxlen(tmp_path) -> None:
    """Кольцо не больше 10 записей."""
    log = EventLog(tmp_path)
    for i in range(12):
        log.record(EventLevel.INFO, str(i))
    assert len(log.ring_snapshot()) == 10
