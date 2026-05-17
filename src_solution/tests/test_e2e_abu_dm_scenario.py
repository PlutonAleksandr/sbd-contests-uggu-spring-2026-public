"""Сквозной тест АБУ (основной сценарий)."""

from fastapi.testclient import TestClient


def test_e2e_dm_registers_rig_and_mission_reaches_abu(client: TestClient) -> None:
    ...
    """Полный цикл: старт миссии, тики, завершение."""
    # 1. Старт миссии
    resp = client.post("/api/v1/missions", json={
        "target_depth_m": 3.0,
        "max_rpm": 200.0
    })
    assert resp.status_code == 200
    mission_id = resp.json()["mission_id"]
    assert mission_id

    # 2. Выполняем шаги, пока миссия активна
    status = None
    for _ in range(10):
        resp = client.post("/api/v1/missions/tick")
        assert resp.status_code == 200
        data = resp.json()
        mission = data.get("mission", {})
        status = mission.get("status")
        if status != "running":
            break

    # 3. Проверяем, что миссия завершена или остановлена
    assert status in ("completed", "emergency", "stopped_depth", "stopped_rpm")

    # 4. Проверяем журнал событий (через TCB)
    resp = client.get("/api/v1/events/ring")
    assert resp.status_code == 200
    lines = resp.json()["lines"]
    assert len(lines) > 0
    # В TCB-журнале должны быть записи авторизации (AUTHORIZED/DENIED)
    assert any("AUTHORIZED" in line or "DENIED" in line for line in lines)
