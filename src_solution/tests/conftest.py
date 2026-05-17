import multiprocessing
import pytest
from fastapi.testclient import TestClient
from src_solution.abu.app import app, tcb_request_queue, tcb_response_queue, other_request_queue, other_response_queue
from src_solution.abu.tcb.sys.security_monitor import SecurityMonitorProcess
from src_solution.abu.other.other_worker import OtherWorkerProcess

@pytest.fixture(scope="session")
def processes():
    """Запуск дочерних процессов на всё время сессии."""
    tcb = multiprocessing.Process(
        target=SecurityMonitorProcess.start_static,
        args=(tcb_request_queue, tcb_response_queue),
        name="tcb-test"
    )
    other = multiprocessing.Process(
        target=OtherWorkerProcess.start_static,
        args=(other_request_queue, other_response_queue),
        name="other-test"
    )
    tcb.start()
    other.start()
    yield
    # shutdown
    tcb_request_queue.put({"command": "shutdown"})
    other_request_queue.put({"command": "shutdown"})
    tcb.join(timeout=2)
    other.join(timeout=2)

@pytest.fixture()
def client(processes):
    """Тестовый клиент с уже запущенными процессами."""
    return TestClient(app)

@pytest.fixture(autouse=True)
def reset_mission():
    """Сбрасывать глобальную миссию перед каждым тестом."""
    import src_solution.abu.app as app_module
    app_module._mission = None
    yield