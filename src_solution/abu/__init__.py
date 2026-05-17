"""
Пакет ABU - Автоматизированная Буровая Установка
Обеспечивает совместимость со старыми путями импорта
"""
__version__ = "0.1.0"

# Прокси для старых импортов (используются внешними тестами)
from .tcb.event_log import EventLog, EventLevel, default_log  # noqa: F401
from .tcb.safety import enforce_depth_cap, enforce_rpm_cap, should_emergency_stop  # noqa: F401
from .tcb.datatypes import SecureStep  # noqa: F401
from .tcb.sys.security_monitor import SecurityMonitorProcess  # noqa: F401
from .other.numpy_workflow import smooth_vibration_window  # noqa: F401
from .other.pseudo_ai import anomaly_vibration, regime_suggest, risk_flag  # noqa: F401
