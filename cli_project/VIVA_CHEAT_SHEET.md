# 🎓 OSDBMS PBL Viva Cheat Sheet & On-the-Spot Code Modification Guide

**Project:** Disaster Resource Allocation & Shelter Management System (CLI Project)  
**Team ID:** `OSDBMS-V-2026-T135` | Graphic Era (Deemed to be University)  

This guide is designed for **on-the-spot code changes** during evaluation.

---

## ⚡ Quick Run Commands

```bash
# 1. Navigate to the CLI folder
cd c:\Users\anushreya\OneDrive\Desktop\pbl_phase2\cli_project

# 2. Run the Interactive Menu
python main.py

# 3. Direct One-Line Demos (Great for fast demonstrations):
python main.py --shelters       # Show shelter capacity bars
python main.py --stress-test     # Show 50-thread concurrency & pessimistic lock
python main.py --bankers         # Show Dijkstra's Banker's safe sequence
python main.py --verify-audit    # Show SHA-256 hash chain verification
python main.py --sms-test        # Test offline TCP socket stream (Port 9999)
```

---

## 🛠️ On-the-Spot Code Modifications (Where to Change Code)

### 1. "Change the Aging Threshold (e.g., from 8s to 5s)"
- **File:** `config.py`
- **Line:** Line 14
- **Code:**
  ```python
  AGING_THRESHOLD_SECONDS = 5    # Changed from 8 to 5
  ```

---

### 2. "Show me the lock that prevents overbooking / race conditions"
- **File:** `database.py`
- **Function:** `pessimistic_write_lock()`
- **Explanation:**
  > *"Sir/Ma'am, in `database.py`, we use `conn.execute('BEGIN IMMEDIATE')`. This is an exclusive pessimistic write lock in SQLite. It ensures that two concurrent allocation threads can never interleave their read-check-update steps. Even if 100 threads hit the database at once, only available beds can be booked and zero overbooking occurs."*

---

### 3. "Change the Triage Priority Rules (e.g., make children <= 10 high priority)"
- **File:** `scheduler.py`
- **Function:** `calculate_triage_priority(age, injury_severity, pregnant)`
- **Code:**
  ```python
  def calculate_triage_priority(age: int, injury_severity: str, pregnant: bool = False) -> int:
      if injury_severity == "critical":
          return 0
      # Change age <= 5 to age <= 10 here:
      if injury_severity == "serious" or age >= 60 or age <= 10 or pregnant:
          return 1
      return 2
  ```

---

### 4. "Show me where the Active Database Triggers are created"
- **File:** `database.py`
- **Function:** `init_database()`
- **Key Triggers:**
  1. `trg_capacity_90`: Automatically inserts an alert and sets status to `CRITICAL_90` when beds used $\ge 90\%$.
  2. `trg_capacity_full`: Automatically inserts an emergency alert and sets status to `FULL` when `available_beds = 0`.
  3. `trg_capacity_reopen`: Automatically reopens the shelter to `OPEN` when evacuees leave.

---

### 5. "Show me the Banker's Algorithm Matrices and Safety Check"
- **File:** `bankers.py`
- **Matrices defined at top:**
  - `INITIAL_AVAILABLE = [3, 3, 2, 2]` (Available resources: Beds, Oxygen, Food Kits, Ambulances)
  - `INITIAL_MAX` (Max demand matrix)
  - `INITIAL_ALLOCATED` (Currently held resources)
- **Algorithm Function:** `is_safe_state()` (Iteratively searches for a process where `Need <= Work`, releases resources, and builds the safe sequence `<S1 -> S0 -> S2>`).

---

### 6. "Show me where the Cryptographic SHA-256 Hash Chain is computed"
- **File:** `database.py`
- **Function:** `calculate_sha256(prev_hash, evacuee_id, shelter_id, timestamp)`
- **Explanation:**
  > *"Every allocation record takes the hash of the preceding record (`prev_hash`) and hashes it with the new allocation details using `hashlib.sha256()`. This forms a tamper-proof blockchain ledger. If any person modifies an old allocation in the database, the hash chain breaks instantly."*

---

### 7. "How does the Offline Socket IPC Daemon work?"
- **File:** `sms_server.py`
- **Class:** `SMSSocketServer`
- **Explanation:**
  > *"We run a raw TCP Stream Socket on Port 9999. In natural disasters when web cellular data is broken, field radios or GSM modules can stream raw text strings like `NAME:Ravi,AGE:55,INJURY:serious`. The socket daemon receives this stream, calculates priority, and submits it to the MLFQ scheduler without needing HTTP or internet."*

---

## 📋 File-by-File Summary of the CLI Project

| File | Primary Role | OS / DBMS Concept |
| :--- | :--- | :--- |
| `config.py` | Central configuration constants | Modifiable timers & ports |
| `database.py` | SQLite WAL connection, triggers, lock, hashes | Triggers, Pessimistic Locking, SHA-256 |
| `scheduler.py` | 3-tier MLFQ Priority Scheduler & Aging Daemon | CPU Scheduling, Starvation Prevention |
| `bankers.py` | Dijkstra's Banker's Algorithm | Deadlock Avoidance, Safe State |
| `stress_test.py`| Multi-threaded 50-thread load test | ThreadPoolExecutor, Race Conditions |
| `sms_server.py` | Low-level TCP socket listener on Port 9999 | Socket Stream IPC, Fault Tolerance |
| `main.py` | Interactive ASCII CLI Menu & command parser | CLI User Interface & Workflow |
