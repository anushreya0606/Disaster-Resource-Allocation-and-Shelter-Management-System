# Disaster Resource Allocation & Shelter Management System
### OSDBMS PBL 5th Semester Project | Graphic Era (Deemed to be University)
**Team ID:** `OSDBMS-V-2026-T135`  
**Team Members:** Anushreya Tomar (Lead), Akanchha Singh, Ishani Nautiyal, Simarjeet Kaur  
**Mentor:** Dr. Ankit Tomar  

---

## 📌 Project Overview
This platform is a high-performance **Operating Systems & Database Management Systems (OSDBMS)** engineering system designed for real-time disaster resource allocation, evacuee priority triage, and shelter occupancy management during emergency situations (floods, earthquakes, land slides).

Unlike generic web CRUD applications, this project explicitly implements **OS kernel mechanisms** (CPU scheduling, process preemption, thread synchronization, IPC socket daemons) and **advanced DBMS engine features** (spatial GIS distance calculations, pessimistic ACID transaction locks, active database triggers, and cryptographic audit hashing).

---

## 🛠️ Operating System (OS) Concepts Implemented

1. **Multi-Level Feedback Queue (MLFQ) Priority Scheduler with Aging:**
   - **Triage Queues:** Queue 0 (Critical Medical), Queue 1 (Vulnerable - Pregnant/Elderly), Queue 2 (General Population).
   - **Aging Daemon:** Background thread promotes low-priority evacuees waiting longer than 8 seconds to prevent infinite starvation.
2. **Thread Synchronization & Bounded Buffer:**
   - POSIX/Python Mutexes and Semaphores coordinate field updates into a thread-safe Producer-Consumer Bounded Buffer.
3. **Deadlock Avoidance (Dijkstra's Banker's Algorithm):**
   - Evaluates multi-resource allocation bundles (Beds + Oxygen Cylinders + Transport Units) to ensure the system remains in a safe execution state.
4. **Low-Level Socket Stream IPC Daemon:**
   - Runs a TCP Socket Listener on Port 9999 to parse raw offline SMS/USSD payloads when cellular internet is down during floods.
5. **Real-Time System Telemetry Panel:**
   - Monitors active thread pool counts, mutex wait times in milliseconds, lock contention rates, and system RPS.

---

## 🗄️ Database Management System (DBMS) Concepts Implemented

1. **Spatial GIS Distance & Proximity Engine:**
   - Implements Haversine distance calculations and spatial indexing to find nearest available shelters within a 5km radius.
2. **Pessimistic Concurrency Locking (`BEGIN IMMEDIATE`):**
   - Employs strict row-level write locks to prevent race conditions and overbooking when 500 parallel requests attempt to book the last available bed.
3. **Active Database Triggers:**
   - SQLite/MySQL `AFTER UPDATE` trigger automatically detects when shelter occupancy hits 90% or 100%, writing warning events into `alert_queue`.
4. **Cryptographic SHA-256 Audit Hashing:**
   - Hashes each supply transaction into `allocations` log table to maintain a tamper-proof audit trail for relief aid distribution.
5. **Real Indian Datasets:**
   - Pre-loaded with historical records from **Kerala Floods 2018** (Rainfall, Evacuated Population, Camps) and geocoded Indian emergency shelters (Aluva, Alappuzha, Thrissur, Chennai, Guwahati, Dehradun).

---

## 🚀 How to Run in VS Code

### Step 1: Open Workspace in VS Code
Open VS Code and choose **File > Open Folder...** and select:
`c:\Users\anushreya\OneDrive\Desktop\pbl_phase2`

### Step 2: Initialize Database Data
Open the terminal in VS Code (`Ctrl + ~`) and run:
```bash
python scripts/seed_data.py
```

### Step 3: Launch the Server
Run the FastAPI application server:
```bash
python -m uvicorn backend.main:app --reload --port 8000
```

### Step 4: Open Interactive Web Dashboard
Open your web browser and go to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🧪 How to Demonstrate to Evaluators

1. **Show Concurrency & Pessimistic Locking:**
   - Click **"🚀 Run Load Test"** on the dashboard (50 to 500 parallel threads).
   - Point out that **Zero Overbooking Integrity** is verified under heavy concurrent surge.
2. **Show OS MLFQ Scheduler & Aging Daemon:**
   - Submit a Priority 2 evacuee form. Watch the evacuee enter Queue 2.
   - Wait 8 seconds: Watch the OS Aging Daemon dynamically promote the evacuee to Queue 1 with an **AGED PROMOTED** badge!
3. **Show Offline Socket Stream IPC Daemon:**
   - Click **"📡 Send Socket Stream to IPC Daemon"**.
   - Show how the low-level TCP socket listener on Port 9999 decodes raw SMS strings and allocates beds in real-time.
4. **Show GIS Spatial Buffer Map:**
   - Click on shelter markers on the map to display 5km proximity radius circles, remaining beds, oxygen cylinders, and contact numbers.
