from __future__ import annotations

import multiprocessing
import signal
from pathlib import Path

from ..event_log import EventLog, EventLevel
from ..safety import enforce_depth_cap, enforce_rpm_cap, should_emergency_stop
from ..datatypes import SecureStep


class SecurityMonitorProcess:
    """Монитор безопасности ДВБ (отдельный процесс)."""

    def __init__(self, request_queue: multiprocessing.Queue,
                 response_queue: multiprocessing.Queue,
                 max_depth: float = 1000.0, max_rpm: float = 500.0,
                 max_pressure: float = 100.0, log_dir: Path | None = None):
        self.req = request_queue
        self.resp = response_queue
        self.max_depth = max_depth
        self.max_rpm = max_rpm
        self.max_pressure = max_pressure
        self.log = EventLog(log_dir)

    def start(self):
        self._running = True
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        while self._running:
            try:
                msg = self.req.get(timeout=0.1)
                if msg is None or msg.get("command") == "shutdown":
                    self._running = False
                    break
                response = self.handle(msg)
                self.resp.put(response)
            except Exception:
                continue

    def handle(self, msg: dict) -> dict:
        cmd = msg.get("command")
        payload = msg.get("payload", {})
        if cmd == "authorize":
            return self._authorize(payload)
        elif cmd == "health":
            return {"status": "ok", "service": "security_monitor"}
        elif cmd == "events_ring":
            return {"lines": self.log.ring_snapshot()}
        elif cmd == "events_full":
            return {"log": self.log.read_full_tail()}
        return {"error": f"Unknown command: {cmd}"}

    def _authorize(self, payload: dict) -> dict:
        try:
            step = SecureStep(**payload)
        except TypeError:
            return {"authorized": False, "reason": "Invalid step data"}
        result = {"authorized": False, "step_id": step.step_id, "reason": "",
                  "safety_checks": {}, "emergency": False}
        if should_emergency_stop(step.risk_level, [step.vib_sample]):
            result["reason"] = "Emergency stop triggered"
            result["emergency"] = True
            self.log.record(EventLevel.CRITICAL, f"Step {step.step_id} emergency stop")
            return result
        checks = {
            "depth_check": enforce_depth_cap(step.depth, self.max_depth),
            "rpm_check": enforce_rpm_cap(step.rpm, self.max_rpm),
            "pressure_check": step.pressure <= self.max_pressure
        }
        result["safety_checks"] = checks
        if all(checks.values()):
            result["authorized"] = True
            result["reason"] = "All safety checks passed"
            self.log.record(EventLevel.INFO, f"Step {step.step_id} AUTHORIZED")
        else:
            failed = [k for k, v in checks.items() if not v]
            result["reason"] = f"Safety check failed: {', '.join(failed)}"
            self.log.record(EventLevel.WARNING, f"Step {step.step_id} DENIED")
        return result

    def _handle_direct(self, command: str, payload: dict) -> dict:
        return self.handle({"command": command, "payload": payload})

    @staticmethod
    def start_static(req_q, resp_q):
        monitor = SecurityMonitorProcess(req_q, resp_q)
        monitor.start()
        