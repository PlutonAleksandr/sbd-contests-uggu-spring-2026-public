## Тесты безопасности

| Цель безопасности | Идентификатор | Тесты (файлы) | Комментарий |
|-------------------|---------------|---------------|-------------|
| Авторизованные критичные команды | SG_ADS_Authorized_critical_commands | tests/security/test_sg_authorized_commands.py | Проверка authorize_step |
| Контролируемые операции | SG_ADS_Controlled_operations | tests/security/test_sg_controlled_ops.py | Глубина, RPM, аварийный стоп |
| Сохранение событий безопасности | SG_ADS_Security_events_store | tests/security/test_sg_security_events.py | Журнал событий |