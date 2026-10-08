import threading
import queue
import time
from typing import Dict, List, Any, Optional

class EvacueeProcess:
    """Represents an evacuee request as an OS Process in the Triage Scheduler."""
    def __init__(self, evacuee_id: int, name: str, priority: int, age_years: int, medical_notes: str, lat: float, lon: float):
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
    OS Module: Multi-Level Feedback Queue (MLFQ) Triage Scheduler with Aging.
    Demonstrates OS CPU scheduling concepts applied to Emergency Disaster Allocation.
    """
    def __init__(self, aging_threshold_sec: float = 10.0):
        self.q0_critical = queue.Queue()   # Priority 0: Medical Triage 1
        self.q1_vulnerable = queue.Queue() # Priority 1: Elderly, Pregnant
        self.q2_general = queue.Queue()    # Priority 2: General Population
        
        self.aging_threshold = aging_threshold_sec
        self.lock = threading.Lock()
        self.active_processes: Dict[int, EvacueeProcess] = {}
        self.running_process: Optional[EvacueeProcess] = None
        
        # Start OS Aging Daemon Thread
        self.daemon_running = True
        self.aging_thread = threading.Thread(target=self._aging_daemon_loop, daemon=True)
        self.aging_thread.start()

    def add_evacuee_process(self, process: EvacueeProcess):
        """Enqueues an evacuee request into the corresponding MLFQ priority queue."""
        with self.lock:
            self.active_processes[process.evacuee_id] = process
            if process.priority == 0:
                self.q0_critical.put(process)
            elif process.priority == 1:
                self.q1_vulnerable.put(process)
            else:
                self.q2_general.put(process)

    def get_next_process_to_schedule(self) -> Optional[EvacueeProcess]:
        """
        Preemptive MLFQ Dispatcher:
        Always serves Queue 0 (Critical) first. If Q0 is empty, serves Q1, then Q2.
        """
        with self.lock:
            if not self.q0_critical.empty():
                proc = self.q0_critical.get()
                proc.state = "RUNNING"
                return proc
            elif not self.q1_vulnerable.empty():
                proc = self.q1_vulnerable.get()
                proc.state = "RUNNING"
                return proc
            elif not self.q2_general.empty():
                proc = self.q2_general.get()
                proc.state = "RUNNING"
                return proc
            return None

    def _aging_daemon_loop(self):
        """
        OS Aging Daemon:
        Periodically checks processes waiting in lower queues. If wait time exceeds
        aging_threshold, promotes them to higher queues to prevent starvation.
        """
        while self.daemon_running:
            time.sleep(2.0)
            now = time.time()
            with self.lock:
                for proc in list(self.active_processes.values()):
                    if proc.state == "READY" and not proc.aging_boosted:
                        wait_duration = now - proc.created_at
                        if wait_duration >= self.aging_threshold and proc.priority > 0:
                            # Promote Priority (Aging)
                            old_priority = proc.priority
                            proc.priority -= 1
                            proc.aging_boosted = True
                            proc.state = "AGED"
                            
                            # Re-enqueue into promoted priority queue
                            if proc.priority == 0:
                                self.q0_critical.put(proc)
                            elif proc.priority == 1:
                                self.q1_vulnerable.put(proc)
                                
                            print(f"[OS AGING DAEMON] Promoted Evacuee {proc.name} (ID: {proc.evacuee_id}) from Priority {old_priority} -> {proc.priority} after {wait_duration:.1f}s wait.")

    def get_queue_snapshot(self) -> Dict[str, Any]:
        """Returns a snapshot of the OS MLFQ queue states for telemetry visualization."""
        with self.lock:
            all_procs = [p.to_dict() for p in self.active_processes.values() if p.state != "COMPLETED"]
            return {
                "q0_count": self.q0_critical.qsize(),
                "q1_count": self.q1_vulnerable.qsize(),
                "q2_count": self.q2_general.qsize(),
                "active_processes": all_procs
            }

# Global Scheduler Instance
triage_scheduler = MLFQTriageScheduler(aging_threshold_sec=8.0)
