import time
import os
import threading
from typing import Dict, Any, List

class SystemTelemetryCollector:
    """
    OS Module: Real-Time System Telemetry & Metrics Collector
    Tracks CPU utilization, mutex wait times, lock contention rates, and active thread counts.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.mutex_contention_count = 0
        self.lock_wait_times_ms: List[float] = []
        self.total_requests = 0
        self.start_time = time.time()

    def record_lock_wait(self, duration_ms: float, contended: bool = False):
        with self.lock:
            self.total_requests += 1
            if contended:
                self.mutex_contention_count += 1
            self.lock_wait_times_ms.append(duration_ms)
            if len(self.lock_wait_times_ms) > 100:
                self.lock_wait_times_ms.pop(0)

    def get_telemetry_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            avg_wait = (sum(self.lock_wait_times_ms) / len(self.lock_wait_times_ms)) if self.lock_wait_times_ms else 0.0
            uptime = max(1.0, time.time() - self.start_time)
            rps = round(self.total_requests / uptime, 2)
            
            # Simple CPU approximation for python thread pool
            active_threads = threading.active_count()
            
            return {
                "active_threads": active_threads,
                "mutex_contention_count": self.mutex_contention_count,
                "avg_lock_wait_ms": round(avg_wait, 2),
                "total_requests_processed": self.total_requests,
                "current_rps": rps,
                "uptime_seconds": round(uptime, 1)
            }

telemetry_collector = SystemTelemetryCollector()
