class BankersAlgorithm:
def **init**(self, available, allocation, maximum):
self.available = available
self.allocation = allocation
self.maximum = maximum

```
    self.processes = len(allocation)
    self.resources = len(available)

    if self.processes == 0:
        raise ValueError("At least one process is required.")

    if len(maximum) != self.processes:
        raise ValueError("Allocation and maximum matrices must have the same number of processes.")

    if any(len(row) != self.resources for row in allocation):
        raise ValueError("Invalid allocation matrix dimensions.")

    if any(len(row) != self.resources for row in maximum):
        raise ValueError("Invalid maximum matrix dimensions.")

    if any(value < 0 for value in available):
        raise ValueError("Available resources cannot be negative.")

    if any(value < 0 for row in allocation + maximum for value in row):
        raise ValueError("Resource values cannot be negative.")

    for i in range(self.processes):
        for j in range(self.resources):
            if allocation[i][j] > maximum[i][j]:
                raise ValueError("Allocation cannot exceed maximum demand.")

    self.need = [
        [
            maximum[i][j] - allocation[i][j]
            for j in range(self.resources)
        ]
        for i in range(self.processes)
    ]

def is_safe(self):
    work = self.available.copy()
    finish = [False] * self.processes
    safe_sequence = []

    while len(safe_sequence) < self.processes:
        found = False

        for i in range(self.processes):
            if not finish[i] and all(
                self.need[i][j] <= work[j]
                for j in range(self.resources)
            ):
                for j in range(self.resources):
                    work[j] += self.allocation[i][j]

                finish[i] = True
                safe_sequence.append(i)
                found = True

        if not found:
            return {
                "safe": False,
                "safe_sequence": [],
                "message": "System is not in a safe state."
            }

    return {
        "safe": True,
        "safe_sequence": safe_sequence,
        "message": "System is in a safe state."
    }

def request_resources(self, process_id, request):
    if not 0 <= process_id < self.processes:
        raise ValueError("Invalid process ID.")

    if len(request) != self.resources:
        raise ValueError("Invalid request dimensions.")

    if any(value < 0 for value in request):
        raise ValueError("Resource request cannot be negative.")

    if any(
        request[j] > self.need[process_id][j]
        for j in range(self.resources)
    ):
        return {
            "granted": False,
            "message": "Request exceeds the process's maximum remaining need."
        }

    if any(
        request[j] > self.available[j]
        for j in range(self.resources)
    ):
        return {
            "granted": False,
            "message": "Insufficient available resources."
        }

    old_available = self.available.copy()
    old_allocation = [
        row.copy() for row in self.allocation
    ]
    old_need = [row.copy() for row in self.need]

    for j in range(self.resources):
        self.available[j] -= request[j]
        self.allocation[process_id][j] += request[j]
        self.need[process_id][j] -= request[j]

    result = self.is_safe()

    if result["safe"]:
        return {
            "granted": True,
            "safe_sequence": result["safe_sequence"],
            "message": "Request granted. System remains in a safe state."
        }

    self.available = old_available
    self.allocation = old_allocation
    self.need = old_need

    return {
        "granted": False,
        "message": "Request denied. It would leave the system in an unsafe state."
    }
```
