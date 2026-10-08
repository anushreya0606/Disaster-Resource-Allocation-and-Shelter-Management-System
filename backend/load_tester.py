import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List
from backend.database import get_db_connection, execute_concurrency_safe_allocation
from backend.telemetry import telemetry_collector

class LoadTestingBenchmarkRunner:
    """
    Multi-threaded Concurrency Benchmark Engine:
    Simulates high-concurrency surge workloads (50 to 500 parallel evacuee requests)
    to demonstrate DBMS locking integrity vs race conditions.
    """
    def __init__(self):
        self.is_running = False
        self.latest_result: Dict[str, Any] = {}

    def run_benchmark(self, shelter_id: int = 1, num_concurrent_requests: int = 100) -> Dict[str, Any]:
        self.is_running = True
        start_time = time.time()
        
        # Step 1: Check initial shelter beds
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, available_beds FROM shelters WHERE shelter_id = ?", (shelter_id,))
        shelter_before = cursor.fetchone()
        initial_beds = shelter_before["available_beds"] if shelter_before else 0
        conn.close()
        
        successful_allocations = 0
        failed_allocations = 0
        lock_contention_events = 0
        
        def simulate_evacuee_request(req_idx: int):
            nonlocal successful_allocations, failed_allocations, lock_contention_events
            t0 = time.time()
            
            # Create evacuee entry
            conn_thread = get_db_connection()
            cur = conn_thread.cursor()
            cur.execute("""
                INSERT INTO evacuees (full_name, age, gender, triage_priority, medical_conditions, latitude, longitude)
                VALUES (?, 30, 'LOAD_TEST', 2, 'Load Test Simulation', 10.10, 76.35)
            """, (f"LoadUser_{req_idx}",))
            evacuee_id = cur.lastrowid
            conn_thread.commit()
            conn_thread.close()
            
            # Execute Pessimistic Transaction Lock
            res = execute_concurrency_safe_allocation(evacuee_id, shelter_id, beds=1)
            t_duration_ms = (time.time() - t0) * 1000.0
            
            if res["success"]:
                successful_allocations += 1
                telemetry_collector.record_lock_wait(t_duration_ms, contended=False)
            else:
                failed_allocations += 1
                lock_contention_events += 1
                telemetry_collector.record_lock_wait(t_duration_ms, contended=True)

        # Execute Parallel Thread Pool
        with ThreadPoolExecutor(max_workers=20) as executor:
            for i in range(num_concurrent_requests):
                executor.submit(simulate_evacuee_request, i)

        total_time = round(time.time() - start_time, 2)
        
        # Step 2: Check final shelter beds
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, available_beds FROM shelters WHERE shelter_id = ?", (shelter_id,))
        shelter_after = cursor.fetchone()
        final_beds = shelter_after["available_beds"] if shelter_after else 0
        conn.close()

        overbooked = final_beds < 0
        
        self.latest_result = {
            "shelter_name": shelter_before["name"] if shelter_before else f"Shelter #{shelter_id}",
            "concurrent_threads": num_concurrent_requests,
            "initial_beds": initial_beds,
            "final_beds": final_beds,
            "successful_allocations": successful_allocations,
            "failed_allocations": failed_allocations,
            "lock_contention_events": lock_contention_events,
            "total_execution_time_sec": total_time,
            "throughput_requests_per_sec": round(num_concurrent_requests / max(0.1, total_time), 1),
            "zero_overbooking_verified": not overbooked
        }
        self.is_running = False
        return self.latest_result

load_tester = LoadTestingBenchmarkRunner()
