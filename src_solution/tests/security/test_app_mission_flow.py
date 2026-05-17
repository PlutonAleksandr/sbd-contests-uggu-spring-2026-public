"""Покрытие app.py и сценариев миссии (безопасность)."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.security
def test_mission_tick_flow(client: TestClient) -> None:
    c = client
    c.post("/api/v1/missions", json={"target_depth_m": 4.0, "max_rpm": 250.0})
    for _ in range(12):
        r = c.post("/api/v1/missions/tick")
        assert r.status_code == 200
    r_ring = c.get("/api/v1/events/ring")
    assert r_ring.status_code == 200
    assert "lines" in r_ring.json()