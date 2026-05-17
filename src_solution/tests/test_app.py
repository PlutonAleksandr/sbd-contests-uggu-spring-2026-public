"""Тесты основного API."""

import os
from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_mission_flow(client: TestClient) -> None:
    # Старт миссии
    resp = client.post("/api/v1/missions", json={
        "target_depth_m": 5.0,
        "max_rpm": 200.0
    })
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True

    # Несколько тиков
    for _ in range(12):
        resp = client.post("/api/v1/missions/tick")
        assert resp.status_code == 200
        data = resp.json()
        mission = data.get("mission", {})
        if mission.get("status") != "running":
            break
    else:
        mission = data.get("mission", {})
    assert mission.get("status") in (
        "completed",
        "emergency",
        "stopped_depth",
        "stopped_rpm")


def test_ai_suggest(client: TestClient) -> None:
    resp = client.post("/api/v1/ai/suggest", json={
        "depth_m": 10.0,
        "torque_nm": 3000.0
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "suggested_rpm" in data
    assert "suggested_feed_mm_rev" in data


def test_rpm_env_cap(client: TestClient) -> None:
    os.environ["ABU_MAX_RPM"] = "100"
    try:
        client.post("/api/v1/missions", json={"target_depth_m": 5.0})
        resp = client.post("/api/v1/missions/tick")
        assert resp.status_code == 200
        mission = resp.json()["mission"]
        assert mission["rpm"] <= 100
    finally:
        del os.environ["ABU_MAX_RPM"]


def test_tick_without_mission(client: TestClient) -> None:
    resp = client.post("/api/v1/missions/tick")
    assert resp.status_code == 400
