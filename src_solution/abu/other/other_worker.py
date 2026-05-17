# src_solution/abu/other/other_worker.py
"""
Недоверенный процесс (Other).
Выполняет numpy-вычисления, псевдо-ИИ и предварительную валидацию.
"""

from __future__ import annotations

import multiprocessing
import signal

from .numpy_workflow import smooth_vibration_window
from .pseudo_ai import anomaly_vibration, regime_suggest, risk_flag
from .validation_worker import StepValidator


class OtherWorkerProcess:
    """Запускается как отдельный процесс."""

    def __init__(
        self,
        request_queue: multiprocessing.Queue,
        response_queue: multiprocessing.Queue,
    ):
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.validator = StepValidator()
        self._running = False

    def start(self):
        """Основной цикл обработки."""
        self._running = True
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        while self._running:
            try:
                msg = self.request_queue.get(timeout=0.1)
                if msg is None or msg.get("command") == "shutdown":
                    self._running = False
                    break
                response = self.handle(msg)
                self.response_queue.put(response)
            except Exception:
                continue

    def handle(self, msg: dict) -> dict:
        """Обработка входящей команды."""
        command = msg.get("command")
        payload = msg.get("payload", {})

        if command == "validate":
            return self._handle_validate(payload)
        elif command == "compute":
            return self._handle_compute(payload)
        elif command == "health":
            return {"status": "ok", "service": "other_worker"}
        else:
            return {"error": f"Unknown command: {command}"}

    def _handle_validate(self, payload: dict) -> dict:
        """Предварительная валидация шага."""
        secure_step = self.validator.validate_and_prepare(payload)
        if secure_step:
            return {"valid": True, "step": secure_step.__dict__}
        else:
            return {"valid": False, "reason": "Validation failed"}

    def _handle_compute(self, payload: dict) -> dict:
        """Тяжёлые вычисления."""
        vib_samples = payload.get("vibration_samples", [])
        depth = payload.get("depth_m", 0.0)
        torque = payload.get("torque_nm", 2000.0)
        pressure = payload.get("pressure", 120.0)

        smooth = smooth_vibration_window(vib_samples)
        vib_score = anomaly_vibration(vib_samples) if vib_samples else 0.0
        rpm_suggest, feed = regime_suggest(depth, torque)
        risk = risk_flag(vib_score, pressure, depth)

        return {
            "smooth_vibration": smooth,
            "vibration_score": vib_score,
            "suggested_rpm": rpm_suggest,
            "suggested_feed": feed,
            "risk": risk,
        }


def run_other_worker(request_queue, response_queue):
    """Точка входа для multiprocessing.Process."""
    worker = OtherWorkerProcess(request_queue, response_queue)
    worker.start()