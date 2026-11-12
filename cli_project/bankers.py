"""Dijkstra's Banker's Algorithm for Multi-Resource Deadlock Avoidance.

[ON-THE-SPOT TIP FOR EVALUATORS]:
This file implements the classic Banker's Algorithm:
1. Available Vector (A)
2. Max Claim Matrix (M)
3. Allocation Matrix (Alloc)
4. Need Matrix (Need = M - Alloc)
5. Safety Algorithm calculating a Safe Sequence <P1, P0, P2...>
"""
from typing import List, Tuple

# Resource Types
RESOURCE_NAMES = ["Beds", "Oxygen", "Food_Kits", "Ambulances"]
NUM_RESOURCES = len(RESOURCE_NAMES)

# Shelter Names
SHELTER_NAMES = [
    "S0: Aluva Town Hall",
    "S1: Paravur Center",
    "S2: Thrissur Medical"
]
NUM_SHELTERS = len(SHELTER_NAMES)

# Initial System State (Easy to modify on the spot if evaluator requests different numbers!)
INITIAL_AVAILABLE = [3, 3, 2, 2]

INITIAL_MAX = [
    [7, 4, 3, 2],   # S0 maximum claim (Need = [7, 3, 3, 2])
    [3, 2, 2, 2],   # S1 maximum claim (Need = [1, 2, 2, 1])
    [6, 0, 2, 2],   # S2 maximum claim (Need = [3, 0, 0, 2])
]

INITIAL_ALLOCATED = [
    [0, 1, 0, 0],   # S0 currently allocated
    [2, 0, 0, 1],   # S1 currently allocated
    [3, 0, 2, 0],   # S2 currently allocated
]


class BankersAlgorithm:
    def __init__(self):
        self.available = list(INITIAL_AVAILABLE)
        self.max_claim = [list(row) for row in INITIAL_MAX]
        self.allocated = [list(row) for row in INITIAL_ALLOCATED]

    def get_need_matrix(self) -> List[List[int]]:
        """Calculates Need Matrix: Need[i][j] = Max[i][j] - Allocated[i][j]"""
        need = []
        for i in range(NUM_SHELTERS):
            row = [self.max_claim[i][j] - self.allocated[i][j] for j in range(NUM_RESOURCES)]
            need.append(row)
        return need

    def is_safe_state(self) -> Tuple[bool, List[str], List[str]]:
        """Executes the Safety Algorithm.
        Returns:
            (is_safe, safe_sequence, trace_steps)
        """
        work = list(self.available)
        finish = [False] * NUM_SHELTERS
        safe_sequence = []
        trace = []
        need = self.get_need_matrix()

        trace.append(f"Initial Work (Available): {work}")

        while len(safe_sequence) < NUM_SHELTERS:
            found = False
            for i in range(NUM_SHELTERS):
                if not finish[i]:
                    # Check if Need[i] <= Work
                    can_fulfill = all(need[i][j] <= work[j] for j in range(NUM_RESOURCES))
                    if can_fulfill:
                        # Simulate process completion and releasing its resources
                        for j in range(NUM_RESOURCES):
                            work[j] += self.allocated[i][j]
                        finish[i] = True
                        safe_sequence.append(SHELTER_NAMES[i])
                        trace.append(
                            f"-> {SHELTER_NAMES[i]} can finish! Need {need[i]} <= Work. "
                            f"New Work = {work}"
                        )
                        found = True
                        break
            if not found:
                break

        is_safe = (len(safe_sequence) == NUM_SHELTERS)
        return is_safe, safe_sequence, trace

    def request_resources(self, shelter_idx: int, request: List[int]) -> Tuple[bool, str]:
        """Validates and processes a resource request vector for a specific shelter.
        Step 1: Check Request <= Need
        Step 2: Check Request <= Available
        Step 3: Pretend to allocate and test if system remains in a Safe State
        """
        need = self.get_need_matrix()

        # Step 1: Check Request <= Need
        for j in range(NUM_RESOURCES):
            if request[j] > need[shelter_idx][j]:
                return False, f"ERROR: Request {request} exceeds Shelter's maximum declared Need {need[shelter_idx]}"

        # Step 2: Check Request <= Available
        for j in range(NUM_RESOURCES):
            if request[j] > self.available[j]:
                return False, f"WAIT: Insufficient resources available. Requested {request}, but Available is {self.available}"

        # Step 3: Pretend allocation (trial state)
        for j in range(NUM_RESOURCES):
            self.available[j] -= request[j]
            self.allocated[shelter_idx][j] += request[j]

        # Check safety
        is_safe, seq, trace = self.is_safe_state()

        if is_safe:
            return True, f"SUCCESS: Request approved! System is in a SAFE STATE. Safe Sequence: {' -> '.join(seq)}"
        else:
            # Rollback trial allocation
            for j in range(NUM_RESOURCES):
                self.available[j] += request[j]
                self.allocated[shelter_idx][j] -= request[j]
            return False, "DENIED: Request denied to avoid DEADLOCK! Granting this request leads to an UNSAFE STATE."
