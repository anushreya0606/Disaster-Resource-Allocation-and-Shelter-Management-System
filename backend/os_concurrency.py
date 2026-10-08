"""
Disaster Resource Allocation & Shelter Management System
OS Concurrency Bounded Buffer & Banker's Algorithm Engine
Module Lead: Simarjeet Kaur (24021248)
"""
import threading
import time
from typing import Dict, List, Any, Tuple

class ProducerConsumerBuffer:
    """
    OS Synchronization Concept: Producer-Consumer Bounded Buffer
    Uses POSIX/Python Mutexes and Semaphores to coordinate intake threads and worker threads.
    """
    def __init__(self, capacity: int = 20):
        self.capacity = capacity
        self.buffer: List[Dict[str, Any]] = []
        self.mutex = threading.Lock()
        self.empty_slots = threading.Semaphore(capacity)
        self.full_slots = threading.Semaphore(0)
        
        self.stats_produced = 0
        self.stats_consumed = 0

    def produce(self, item: Dict[str, Any], timeout: float = 2.0) -> bool:
        """Producer Thread: Inserts event into bounded buffer."""
        if not self.empty_slots.acquire(timeout=timeout):
            return False  # Buffer full timeout
            
        with self.mutex:
            self.buffer.append(item)
            self.stats_produced += 1
            
        self.full_slots.release()
        return True

    def consume(self, timeout: float = 2.0) -> Tuple[bool, Any]:
        """Consumer Thread: Extracts event from bounded buffer."""
        if not self.full_slots.acquire(timeout=timeout):
            return False, None
            
        with self.mutex:
            item = self.buffer.pop(0)
            self.stats_consumed += 1
            
        self.empty_slots.release()
        return True, item

    def get_status(self) -> Dict[str, Any]:
        with self.mutex:
            return {
                "buffer_size": len(self.buffer),
                "capacity": self.capacity,
                "produced_total": self.stats_produced,
                "consumed_total": self.stats_consumed
            }

class BankersDeadlockAvoidance:
    """
    OS Deadlock Prevention Concept: Dijkstra's Banker's Algorithm
    Evaluates whether allocating a multi-resource bundle (Beds, Oxygen, Transport)
    leaves the shelter system in a SAFE state.
    """
    def __init__(self):
        # Resource Types: [Beds, Oxygen Cylinders, Transport Vehicles]
        self.lock = threading.Lock()

    def is_safe_state(self, available: List[int], max_claim: List[List[int]], allocation: List[List[int]]) -> Tuple[bool, List[int]]:
        """
        Executes Banker's Algorithm Safety Check.
        Returns (is_safe, safe_execution_sequence).
        """
        with self.lock:
            num_shelters = len(max_claim)
            num_resources = len(available)
            
            # Need matrix = Max - Allocation
            need = [[max_claim[i][j] - allocation[i][j] for j in range(num_resources)] for i in range(num_shelters)]
            
            work = list(available)
            finish = [False] * num_shelters
            safe_sequence = []
            
            for _ in range(num_shelters):
                found_candidate = False
                for i in range(num_shelters):
                    if not finish[i]:
                        # Check if Need[i] <= Work
                        if all(need[i][j] <= work[j] for j in range(num_resources)):
                            for j in range(num_resources):
                                work[j] += allocation[i][j]
                            finish[i] = True
                            safe_sequence.append(i)
                            found_candidate = True
                            break
                            
                if not found_candidate:
                    break
                    
            is_safe = (len(safe_sequence) == num_shelters)
            return is_safe, safe_sequence

# Global Instances
disaster_event_buffer = ProducerConsumerBuffer(capacity=50)
bankers_engine = BankersDeadlockAvoidance()
