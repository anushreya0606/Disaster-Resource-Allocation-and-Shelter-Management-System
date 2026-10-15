"""Collects lock-wait times and throughput; a daemon thread writes a row to telemetry_logs."""
import threading
from collections import deque

_lock = threading.Lock()
_waits = deque(maxlen=5000)
_allocs = 0
_stop = threading.Event()


def record_lock_wait(ms):
    with _lock:
        _waits.append(ms)


def record_allocation():
    global _allocs
    with _lock:
        _allocs += 1


def _drain():
    global _allocs
    with _lock:
        waits, n = list(_waits), _allocs
        _waits.clear()
        _allocs = 0
    return waits, n


def snapshot_and_store(scheduler):
    from . import database
    waits, n = _drain()
    q = scheduler.stats() if scheduler else {"levels": [0, 0, 0], "promotions": 0}
    row = (threading.active_count(), *q["levels"], q["promotions"],
           round(sum(waits) / len(waits), 3) if waits else 0.0,
           round(max(waits), 3) if waits else 0.0, n)
    database.get_conn().execute(
        "INSERT INTO telemetry_logs (active_threads, queue_p0, queue_p1, queue_p2, promotions,"
        " lock_wait_avg_ms, lock_wait_max_ms, allocations) VALUES (?,?,?,?,?,?,?,?)", row)


def start(scheduler, interval):
    _stop.clear()

    def loop():
        while not _stop.wait(interval):
            try:
                snapshot_and_store(scheduler)
            except Exception as exc:  # telemetry must never crash the server
                print("telemetry error:", exc)

    t = threading.Thread(target=loop, name="telemetry-daemon", daemon=True)
    t.start()
    return t


def stop():
    _stop.set()
