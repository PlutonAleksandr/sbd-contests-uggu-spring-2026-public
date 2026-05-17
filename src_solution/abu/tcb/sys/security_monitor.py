# src_solution/abu/tcb/security_monitor.py
from __future__ import annotations

import json
import multiprocessing
import signal
from datetime import datetime
from pathlib import Path
from typing import Any

from src_solution.abu.tcb.event_log import EventLog, EventLevel
from src_solution.abu.tcb.safety import enforce_depth_cap, enforce_rpm_cap, should_emergency_stop
from src_solution.abu.tcb.datatypes import SecureStep


class SecurityMonitorProcess:
    """Монитор безопасности ДВБ (отдельный процесс)."""

    def __init__(self, request_queue: multiprocessing.Queue,
                 response_queue: multiprocessing.Queue,
                 max_depth: float = 1000.0, max_rpm: float = 500.0,
                 max_pressure: float = 100.0, log_dir: Path | None = None,
                 policies_path: Path | None = None):
        self.req = request_queue
        self.resp = response_queue
        self.max_depth = max_depth
        self.max_rpm = max_rpm
        self.max_pressure = max_pressure
        self.log = EventLog(log_dir)
        self.policies = self._load_policies(policies_path)

    def _load_policies(self, policies_path: Path | None) -> dict:
        """Загружает политики из JSON-файла."""
        if policies_path is None:
            # Путь по умолчанию относительно этого файла
            default_path = Path(__file__).parent / "ipc_policies.json"
            policies_path = default_path
        try:
            with open(policies_path, "r") as f:
                data = json.load(f)
            return data
        except Exception as e:
            # При ошибке загрузки используем безопасные политики по умолчанию
            self.log.record(EventLevel.CRITICAL, f"Failed to load policies: {e}. Using default DENY-ALL.")
            return {"default_action": "deny", "policies": []}

    def _check_policy(self, source: str, target: str, command: str, payload: dict) -> tuple[bool, str]:
        """
        Проверяет, разрешена ли команда согласно политикам.
        Возвращает (разрешено, причина отказа).
        """
        policies = self.policies.get("policies", [])
        default = self.policies.get("default_action", "deny")

        for pol in policies:
            if pol.get("action") != "allow":
                continue
            # Проверяем source (может быть строкой или списком)
            pol_src = pol.get("source")
            if pol_src != source and (not isinstance(pol_src, list) or source not in pol_src):
                continue
            # Проверяем target
            pol_tgt = pol.get("target")
            if pol_tgt != target and (not isinstance(pol_tgt, list) or target not in pol_tgt):
                continue
            # Проверяем command
            if pol.get("command") != command:
                continue

            # Если есть ограничения на payload, проверяем их
            constraints = pol.get("payload_constraints")
            if constraints:
                if not self._validate_payload(payload, constraints):
                    return False, f"Payload validation failed for command '{command}'"
            # Политика подошла
            return True, ""

        if default == "allow":
            return True, ""
        return False, f"No policy allows {source} -> {target} command '{command}'"

    def _validate_payload(self, payload: dict, constraints: dict) -> bool:
        """Проверяет payload на соответствие ограничениям (упрощённая версия)."""
        for field, rules in constraints.items():
            if field not in payload:
                return False
            value = payload[field]
            if "type" in rules:
                if rules["type"] == "number" and not isinstance(value, (int, float)):
                    return False
                if rules["type"] == "array" and not isinstance(value, list):
                    return False
            if "minimum" in rules and value < rules["minimum"]:
                return False
            if "maximum" in rules and value > rules["maximum"]:
                return False
            if "maxItems" in rules and isinstance(value, list) and len(value) > rules["maxItems"]:
                return False
        return True

    def _log_decision(self, source: str, target: str, command: str,
                      decision: str, reason: str = "", payload: dict = None):
        """Запись решения о безопасности в журнал (IPC или бизнес-логика)."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": source,
            "target": target,
            "command": command,
            "decision": decision,
            "reason": reason,
            "payload": payload or {}
        }
        self.log.record(EventLevel.INFO, f"SECURITY_DECISION: {json.dumps(entry)}")

    def start(self):
        self._running = True
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        while self._running:
            try:
                msg = self.req.get(timeout=0.1)
                if msg is None or msg.get("command") == "shutdown":
                    self._running = False
                    break

                # Извлекаем метаданные для политики
                source = msg.get("source", "unknown")
                target = msg.get("target", "security_monitor")
                command = msg.get("command", "")
                payload = msg.get("payload", {})

                # Проверка политик IPC
                allowed, reason = self._check_policy(source, target, command, payload)
                if not allowed:
                    self._log_decision(source, target, command, "DENY_IPC", reason, payload)
                    self.resp.put({"error": f"IPC policy denied: {reason}"})
                    continue

                # Если политика разрешила, обрабатываем команду
                response = self._handle_command(command, payload)
                # Логируем успешное разрешение IPC (бизнес-логика залогируется отдельно)
                self._log_decision(source, target, command, "ALLOW_IPC", "IPC policy allowed", payload)
                self.resp.put(response)
            except Exception as e:
                self.log.record(EventLevel.ERROR, f"Monitor error: {e}")
                continue

    def _handle_command(self, cmd: str, payload: dict) -> dict:
        """Обрабатывает команду после проверки политик."""
        if cmd == "authorize":
            return self._authorize(payload)
        elif cmd == "health":
            return {"status": "ok", "service": "security_monitor"}
        elif cmd == "events_ring":
            return {"lines": self.log.ring_snapshot()}
        elif cmd == "events_full":
            return {"log": self.log.read_full_tail()}
        else:
            return {"error": f"Unknown command: {cmd}"}

    @staticmethod
    def start_static(req_q, resp_q):
        monitor = SecurityMonitorProcess(req_q, resp_q)
        monitor.start()

    def _authorize(self, payload: dict) -> dict:
        """Авторизация шага бурения с логированием решения."""
        try:
            step = SecureStep(**payload)
        except TypeError as e:
            return {"authorized": False, "reason": f"Invalid step data: {e}"}

        result = {
            "authorized": False,
            "step_id": step.step_id,
            "reason": "",
            "safety_checks": {},
            "emergency": False
        }

        # Аварийная остановка
        if should_emergency_stop(step.risk_level, [step.vib_sample]):
            result["reason"] = "Emergency stop triggered"
            result["emergency"] = True
            self.log.record(EventLevel.CRITICAL, f"Step {step.step_id} emergency stop")
            self._log_decision("security_monitor", "abu", "authorize_decision",
                               "DENY_BUSINESS", result["reason"], payload)
            return result

        # Проверки безопасности
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
            self._log_decision("security_monitor", "abu", "authorize_decision",
                               "ALLOW_BUSINESS", result["reason"], payload)
        else:
            failed = [k for k, v in checks.items() if not v]
            result["reason"] = f"Safety check failed: {', '.join(failed)}"
            self.log.record(EventLevel.WARNING, f"Step {step.step_id} DENIED")
            self._log_decision("security_monitor", "abu", "authorize_decision",
                               "DENY_BUSINESS", result["reason"], payload)
        return result