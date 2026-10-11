
"""
OS Multi-Level Feedback Queue (MLFQ) Triage Scheduler & Aging Daemon
"""

import threading
import queue
import time
from typing import Dict, Any, Optional


class EvacueeProcess:
    """Represents an evacuee request as an OS process in the triage scheduler."""

    def __init__(
        self,
        evacuee_id: int,
        name: str,
        priority: int,
        age_years: int,
        medical_notes: str,
        lat: float,
        lon: float
    ):
        self.evacuee_id = evacuee_id
        self.name = name
        self.priority = priority  # 0: Critical Medical, 1: Vulnerable, 2: General
        self.initial_priority = priority
        self.age_years = age_years
        self.medical_notes = medical_notes
        self.lat = lat
        self.lon = lon
        self.created_at = time.time()
        self.state = "READY"  # READY, RUNNING, PREEMPTED, AGED, COMPLETED
        self.assigned_shelter_id: Optional[int] = None
        self.aging_boosted = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evacuee_id": self.evacuee_id,
            "name": self.name,
            "priority": self.priority,
            "initial_priority": self.initial_priority,
            "age_years": self.age_years,
            "medical_notes": self.medical_notes,
            "lat": self.lat,
            "lon": self.lon,
            "wait_time_sec": round(time.time() - self.created_at, 1),
            "state": self.state,
            "aging_boosted": self.aging_boosted
        }


class MLFQTriageScheduler:
    """
    Multi-Level Feedback Queue (MLFQ) triage scheduler with aging.

    Priority 0: Critical medical
    Priority 1: Vulnerable
    Priority 2: General population
    """

    def __init__(self, aging_threshold_sec: float = 10.0):
        self.q0_critical = queue.Queue()
        self.q1_vulnerable = queue.Queue()
        self.q2_general = queue.Queue()

        self.aging_threshold = aging_threshold_sec
        self.lock = threading.Lock()
        self.active_processes: Dict[int, EvacueeProcess] = {}
        self.running_process: Optional[EvacueeProcess] = None

        # Start the OS aging daemon.
        self.daemon_running = True
        self.aging_thread = threading.Thread(
            target=self._aging_daemon_loop,
            daemon=True
        )
        self.aging_thread.start()

    def add_evacuee_process(self, process: EvacueeProcess) -> None:
        """Add an evacuee to the queue matching their priority."""

        with self.lock:
            if process.evacuee_id in self.active_processes:
                raise ValueError(
                    f"Evacuee {process.evacuee_id} is already registered."
                )

            self.active_processes[process.evacuee_id] = process

            if process.priority == 0:
                self.q0_critical.put(process)
            elif process.priority == 1:
                self.q1_vulnerable.put(process)
            else:
                self.q2_general.put(process)

    def get_next_process_to_schedule(
        self
    ) -> Optional[EvacueeProcess]:
        """
        Dispatcher: select from Q0 first, then Q1, then Q2.
        Remove the selected process from its queue and mark it RUNNING.
        """

        with self.lock:
            if not self.q0_critical.empty():
                proc = self.q0_critical.get()
            elif not self.q1_vulnerable.empty():
                proc = self.q1_vulnerable.get()
            elif not self.q2_general.empty():
                proc = self.q2_general.get()
            else:
                return None

            proc.state = "RUNNING"
            self.running_process = proc
            return proc

    def _remove_from_queue(
        self,
        target_queue: queue.Queue,
        process: EvacueeProcess
    ) -> bool:
        """
        Remove a process from a queue safely while holding self.lock.

        queue.Queue does not expose a public arbitrary-removal method.
        Its internal mutex is acquired while modifying the underlying queue.
        """

        with target_queue.mutex:
            try:
                target_queue.queue.remove(process)
            except ValueError:
                return False

            # Keep queue.Queue bookkeeping consistent.
            target_queue.unfinished_tasks -= 1
            if target_queue.unfinished_tasks == 0:
                target_queue.all_tasks_done.notify_all()

            target_queue.not_full.notify()
            return True

    def _aging_daemon_loop(self) -> None:
        """
        Promote waiting processes after the aging threshold to reduce starvation.
        """

        while self.daemon_running:
            time.sleep(2.0)
            now = time.time()

            with self.lock:
                for proc in list(self.active_processes.values()):
                    if proc.state != "READY" or proc.aging_boosted:
                        continue

                    wait_duration = now - proc.created_at

                    if (
                        wait_duration < self.aging_threshold
                        or proc.priority <= 0
                    ):
                        continue

                    old_priority = proc.priority

                    # Remove the old queue entry before promotion.
                    if old_priority == 1:
                        removed = self._remove_from_queue(
                            self.q1_vulnerable, proc
                        )
                    else:
                        removed = self._remove_from_queue(
                            self.q2_general, proc
                        )

                    # Do not enqueue again if the process is no longer waiting
                    # in its expected queue.
                    if not removed:
                        continue

                    proc.priority -= 1
                    proc.aging_boosted = True
                    proc.state = "AGED"

                    if proc.priority == 0:
                        self.q0_critical.put(proc)
                    elif proc.priority == 1:
                        self.q1_vulnerable.put(proc)

                    print(
                        f"[OS AGING DAEMON] Promoted evacuee "
                        f"{proc.name} (ID: {proc.evacuee_id}) "
                        f"from priority {old_priority} to "
                        f"{proc.priority} after {wait_duration:.1f}s."
                    )

    def get_queue_snapshot(self) -> Dict[str, Any]:
        """Return queue counts and active process details for telemetry."""

        with self.lock:
            all_procs = [
                proc.to_dict()
                for proc in self.active_processes.values()
                if proc.state != "COMPLETED"
            ]

            return {
                "q0_count": self.q0_critical.qsize(),
                "q1_count": self.q1_vulnerable.qsize(),
                "q2_count": self.q2_general.qsize(),
                "active_processes": all_procs
            }


# Global scheduler instance
triage_scheduler = MLFQTriageScheduler(aging_threshold_sec=8.0)
