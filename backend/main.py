import os
import json
import time
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.database import init_db, get_db_connection, haversine_distance, execute_concurrency_safe_allocation
from backend.os_scheduler import triage_scheduler, EvacueeProcess
from backend.os_concurrency import disaster_event_buffer, bankers_engine
from backend.os_ipc_daemon import sms_ipc_daemon
from backend.telemetry import telemetry_collector
from backend.load_tester import load_tester

app = FastAPI(
    title="Disaster Resource Allocation & Shelter Management System",
    description="OSDBMS PBL Engineering Platform - Integrates OS Kernel Concepts & Advanced DBMS Internals",
    version="2.0.0"
)

# Startup Event: Initialize DB and Start Background OS Daemons
@app.on_event("startup")
def on_startup():
    print("[SYSTEM] Starting OSDBMS Disaster Management Server...")
    init_db()
    # Seed DB if empty
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM shelters;")
    row = cursor.fetchone()
    conn.close()
    if row["cnt"] == 0:
        from scripts.seed_data import seed_database
        seed_database()
        
    sms_ipc_daemon.start_daemon()

# Pydantic Input Schemas
class EvacueeRegisterRequest(BaseModel):
    full_name: str
    age: int
    gender: str
    triage_priority: int  # 0: Critical Medical, 1: Vulnerable, 2: General
    medical_conditions: Optional[str] = "None"
    latitude: float
    longitude: float

class AllocationRequest(BaseModel):
    evacuee_id: int
    shelter_id: int
    beds: int = 1
    oxygen_cylinders: int = 0
    food_units: int = 0
    transport_units: int = 0

class SMSPayloadRequest(BaseModel):
    raw_payload: str

class LoadTestRequest(BaseModel):
    shelter_id: int = 1
    num_concurrent_requests: int = 50

# --- REST API ENDPOINTS ---

@app.get("/api/shelters")
def get_all_shelters():
    """Returns all shelters with calculated capacity percentages and DB status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM shelters ORDER BY shelter_id ASC;")
    shelters = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    for s in shelters:
        s["occupancy_percent"] = round(((s["total_beds"] - s["available_beds"]) / max(1, s["total_beds"])) * 100.0, 1)
    return {"shelters": shelters}

@app.get("/api/shelters/nearest")
def get_nearest_shelters(lat: float, lon: float, min_beds: int = 1):
    """
    DBMS Spatial Query:
    Calculates Haversine distance from evacuee GPS coordinates to all open shelters
    and returns nearest shelters with available capacity.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM shelters WHERE available_beds >= ? AND status != 'CLOSED'", (min_beds,))
    shelters = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    for s in shelters:
        s["distance_km"] = round(haversine_distance(lat, lon, s["latitude"], s["longitude"]), 2)
        s["occupancy_percent"] = round(((s["total_beds"] - s["available_beds"]) / max(1, s["total_beds"])) * 100.0, 1)
        
    shelters.sort(key=lambda x: x["distance_km"])
    return {"nearest_shelters": shelters[:5]}

@app.post("/api/evacuees/register")
def register_evacuee(req: EvacueeRegisterRequest):
    """Enqueues evacuee into database and OS MLFQ Triage Scheduler."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO evacuees (full_name, age, gender, triage_priority, medical_conditions, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (req.full_name, req.age, req.gender, req.triage_priority, req.medical_conditions, req.latitude, req.longitude))
    evacuee_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Enqueue into OS MLFQ Scheduler
    proc = EvacueeProcess(
        evacuee_id=evacuee_id,
        name=req.full_name,
        priority=req.triage_priority,
        age_years=req.age,
        medical_notes=req.medical_conditions or "",
        lat=req.latitude,
        lon=req.longitude
    )
    triage_scheduler.add_evacuee_process(proc)
    
    return {"success": True, "evacuee_id": evacuee_id, "scheduler_status": proc.to_dict()}

@app.post("/api/allocate")
def allocate_resources(req: AllocationRequest):
    """Executes Concurrency-Safe Pessimistic ACID Allocation."""
    res = execute_concurrency_safe_allocation(
        evacuee_id=req.evacuee_id,
        shelter_id=req.shelter_id,
        beds=req.beds,
        o2=req.oxygen_cylinders,
        food=req.food_units,
        transport=req.transport_units
    )
    return res

@app.get("/api/scheduler/queue")
def get_scheduler_queue_snapshot():
    """Returns OS MLFQ Priority Queue snapshot with aging indicators."""
    return triage_scheduler.get_queue_snapshot()

@app.get("/api/telemetry")
def get_system_telemetry():
    """Returns real-time OS and DB system telemetry metrics."""
    tel = telemetry_collector.get_telemetry_snapshot()
    buf = disaster_event_buffer.get_status()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alert_queue ORDER BY alert_id DESC LIMIT 10;")
    alerts = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {
        "telemetry": tel,
        "bounded_buffer": buf,
        "active_alerts": alerts
    }

@app.post("/api/benchmark/run")
def run_concurrency_benchmark(req: LoadTestRequest):
    """Executes multi-threaded concurrency surge load test (50-500 threads)."""
    if load_tester.is_running:
        raise HTTPException(status_code=400, detail="Benchmark load test is already running.")
    res = load_tester.run_benchmark(shelter_id=req.shelter_id, num_concurrent_requests=req.num_concurrent_requests)
    return res

@app.post("/api/ipc/send_sms")
def send_offline_sms_ipc(req: SMSPayloadRequest):
    """Simulates receiving an offline SMS string via socket IPC daemon."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 9999))
        s.sendall(req.raw_payload.encode('utf-8'))
        resp = s.recv(1024).decode('utf-8')
        s.close()
        return {"success": True, "socket_ack": resp.strip(), "logs": sms_ipc_daemon.latest_sms_logs[:5]}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/kerala_floods_data")
def get_kerala_floods_dataset():
    """Returns historical Kerala Floods 2018 Indian disaster dataset."""
    with open("data/kerala_floods_2018.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"kerala_floods_2018": data}

# Serve Frontend Static Files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def serve_index():
    return FileResponse("frontend/index.html")
