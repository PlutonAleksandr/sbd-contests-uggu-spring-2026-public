"""HTTP API прототипа АБУ."""

from __future__ import annotations

import multiprocessing
import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from abu.tcb.event_log import EventLog, EventLevel
from abu.tcb.sys.security_monitor import SecurityMonitorProcess
from abu.other.other_worker import OtherWorkerProcess

# Очереди для IPC
tcb_request_queue = multiprocessing.Queue()
tcb_response_queue = multiprocessing.Queue()
other_request_queue = multiprocessing.Queue()
other_response_queue = multiprocessing.Queue()

# Глобальные процессы (инициализируются в startup)
tcb_process = None
other_process = None

# Флаг, запущены ли процессы
_processes_started = False

# Резервные обработчики (fallback, если процессы не запущены)
_tcb_monitor = SecurityMonitorProcess(tcb_request_queue, tcb_response_queue)
_other_worker = OtherWorkerProcess(other_request_queue, other_response_queue)

app = FastAPI(title="АБУ (прототип)", version="0.1.0")
default_log = EventLog()


class MissionIn(BaseModel):
    """Входное задание на бурение."""
    target_depth_m: float = Field(gt=0, le=200)
    max_rpm: float = Field(default=300.0, gt=0)


class MissionState(BaseModel):
    """Состояние текущей миссии."""
    mission_id: str
    target_depth_m: float
    depth_m: float = 0.0
    rpm: float = 0.0
    torque_nm: float = 2000.0
    pressure: float = 120.0
    vibration_samples: list[float] = Field(default_factory=list)
    status: str = "running"


_mission: MissionState | None = None


def _start_processes():
    """Запуск дочерних процессов."""
    global tcb_process, other_process, _processes_started
    if _processes_started:
        return
    tcb_process = multiprocessing.Process(
        target=SecurityMonitorProcess.start_static,
        args=(tcb_request_queue, tcb_response_queue),
        name="tcb-process"
    )
    other_process = multiprocessing.Process(
        target=OtherWorkerProcess.start_static,
        args=(other_request_queue, other_response_queue),
        name="other-process"
    )
    tcb_process.start()
    other_process.start()
    _processes_started = True


def _send_tcb(command: str, payload: dict = None) -> dict:
    if _processes_started:
        tcb_request_queue.put({"command": command, "payload": payload or {}})
        return tcb_response_queue.get(timeout=5.0)
    else:
        return _tcb_monitor._handle_direct(command, payload or {})


def _send_other(command: str, payload: dict = None) -> dict:
    if _processes_started:
        other_request_queue.put({"command": command, "payload": payload or {}})
        return other_response_queue.get(timeout=5.0)
    else:
        return _other_worker._handle_direct(command, payload or {})


@app.on_event("startup")
def startup():
    """Запуск процессов при старте uvicorn."""
    _start_processes()


@app.on_event("shutdown")
def shutdown():
    """Остановка процессов."""
    if not _processes_started:
        return
    tcb_request_queue.put({"command": "shutdown"})
    other_request_queue.put({"command": "shutdown"})
    tcb_process.join(timeout=2)
    other_process.join(timeout=2)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    """Проверка работоспособности."""
    default_log.record(EventLevel.INFO, "health_check")
    tcb_health = _send_tcb("health")
    other_health = _send_other("health")
    return {
        "status": "ok",
        "service": "abu",
        "tcb": tcb_health.get("status", "unknown"),
        "other": other_health.get("status", "unknown"),
    }


@app.get("/api/v1/events/ring")
def events_ring() -> dict[str, list[str]]:
    """Снимок кольцевого буфера событий из TCB."""
    return _send_tcb("events_ring")


@app.get("/api/v1/events/full")
def events_full_tail() -> dict[str, str]:
    """Хвост полного журнала событий из TCB."""
    return _send_tcb("events_full")


@app.get("/api/v1/status")
def status() -> dict[str, Any]:
    """Текущий статус и телеметрия."""
    if _mission is None:
        return {"idle": True}
    m = _mission
    comp = _send_other("compute", {
        "vibration_samples": m.vibration_samples,
        "depth_m": m.depth_m,
        "torque_nm": m.torque_nm,
        "pressure": m.pressure,
    })
    return {
        "idle": False,
        "mission_id": m.mission_id,
        "depth_m": m.depth_m,
        "rpm": m.rpm,
        "torque_nm": m.torque_nm,
        "pressure": m.pressure,
        "vibration_score": comp.get("vibration_score", 0.0),
        "risk": comp.get("risk", "low"),
        "mission_status": m.status,
    }


@app.post("/api/v1/missions")
def start_mission(body: MissionIn) -> dict[str, Any]:
    """Принять новое задание."""
    global _mission
    mid = str(uuid.uuid4())
    _mission = MissionState(
        mission_id=mid,
        target_depth_m=body.target_depth_m,
        rpm=min(150.0, body.max_rpm),
    )
    default_log.record(
        EventLevel.INFO,
        f"mission_started mission_id={mid}",
    )
    return {"accepted": True, "mission_id": mid}


@app.get("/api/v1/missions/current")
def current_mission() -> dict[str, Any]:
    """Текущая миссия или 404."""
    if _mission is None:
        raise HTTPException(status_code=404, detail="нет активной миссии")
    return _mission.model_dump()


@app.post("/api/v1/missions/tick")
def tick_step() -> dict[str, Any]:
    """Один шаг симуляции."""
    global _mission
    if _mission is None:
        raise HTTPException(status_code=400, detail="нет миссии")
    m = _mission
    if m.status != "running":
        return {"done": True, "status": m.status}

    m.depth_m = round(min(m.depth_m + 0.5, m.target_depth_m), 2)
    m.vibration_samples.append(0.1 + 0.05 * (m.depth_m % 3))
    m.torque_nm = 2000 + m.depth_m * 30
    m.pressure = 120 + m.depth_m * 0.4

    comp = _send_other("compute", {
        "vibration_samples": m.vibration_samples,
        "depth_m": m.depth_m,
        "torque_nm": m.torque_nm,
        "pressure": m.pressure,
    })
    rpm_suggest = comp.get("suggested_rpm", 150.0)
    risk = comp.get("risk", "low")
    vib_score = comp.get("vibration_score", 0.0)

    try:
        cap = float(os.environ.get("ABU_MAX_RPM", "300"))
    except ValueError:
        cap = 300.0
    m.rpm = min(rpm_suggest, cap)

    step_data = {
        "depth": m.depth_m,
        "rpm": int(m.rpm),
        "pressure": m.pressure,
        "step_id": m.mission_id,
        "operator_id": "auto",
        "timestamp": 0.0,
        "risk_level": risk,
        "vib_sample": vib_score,
    }

    auth = _send_tcb("authorize", step_data)

    if auth.get("emergency") or not auth.get("authorized"):
        m.status = "emergency"
        default_log.record(
            EventLevel.CRITICAL,
            f"authorize_step denied: {auth.get('reason', 'unknown')}"
        )
    else:
        if m.depth_m >= m.target_depth_m:
            m.status = "completed"
            default_log.record(EventLevel.INFO, "mission_completed_target_depth")

    return {"mission": m.model_dump(), "risk": risk, "auth": auth}


class AISuggestIn(BaseModel):
    """Вход для псевдо-ИИ."""
    depth_m: float = Field(ge=0)
    torque_nm: float = Field(ge=0)


@app.post("/api/v1/ai/suggest")
def ai_suggest(body: AISuggestIn) -> dict[str, float]:
    """Псевдо-ИИ: рекомендации режима через Other."""
    comp = _send_other("compute", {
        "depth_m": body.depth_m,
        "torque_nm": body.torque_nm,
    })
    return {
        "suggested_rpm": comp.get("suggested_rpm", 150.0),
        "suggested_feed_mm_rev": comp.get("suggested_feed", 0.2),
    }
    