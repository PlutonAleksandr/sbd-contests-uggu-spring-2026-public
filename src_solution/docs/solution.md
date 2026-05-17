## Архитектура решения

Решение состоит из двух изолированных доменов:

- **Доверенная вычислительная база (TCB)** – `src_solution/abu/tcb/`. Включает:
  - `event_log.py` – журнал событий безопасности.
  - `safety.py` – критические проверки глубины, RPM, аварийного останова.
  - `sys/security_monitor.py` – монитор безопасности, единственная точка авторизации критических команд.
  - `datatypes.py` – структуры данных, передаваемые между доменами.
- **Недоверенный код (Other)** – `src_solution/abu/other/`. Включает:
  - `numpy_workflow.py` – обработка телеметрии (numpy).
  - `pseudo_ai.py` – эвристики риска и вибрации.
  - `validation_worker.py` – предварительная валидация и подготовка данных.
  - `other_worker.py` – процесс-обёртка для взаимодействия с TCB.

Взаимодействие между доменами осуществляется только через `multiprocessing.Queue` под контролем `security_monitor`. Политики IPC определены в `tcb/sys/ipc_policies.json`.

## Тесты безопасности

| Цель безопасности | Идентификатор | Тесты (пути к файлам) | Комментарий |
|-------------------|---------------|------------------------|-------------|
| Авторизованные критичные команды | SG_ADS_Authorized_critical_commands | `src_solution/tests/security/test_sg_authorized_commands.py` | Проверка authorize_step |
| Контролируемые операции | SG_ADS_Controlled_operations | `src_solution/tests/security/test_sg_controlled_ops.py` | Глубина, RPM, emergency |
| Сохранение событий безопасности | SG_ADS_Security_events_store | `src_solution/tests/security/test_sg_security_events.py` | Журнал событий |
| Покрытие ДВБ (SecurityMonitor) | SG_ADS_Authorized_critical_commands, SG_ADS_Controlled_operations | `src_solution/tests/security/test_tcb_monitor.py` | Прямые тесты монитора |

Все тесты используют маркер `pytest.mark.security`.