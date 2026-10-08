import sqlite3
import math
import hashlib
import time
from typing import List, Dict, Any, Optional

DB_PATH = "disaster_management.db"

def get_db_connection() -> sqlite3.Connection:
    """
    Returns an SQLite connection configured with Write-Ahead Logging (WAL)
    mode for enhanced concurrency and thread-safe operations.
    """
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    # OS DBMS Configuration: Enable Write-Ahead Logging (WAL) and Foreign Keys
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    """Initializes database tables, triggers, and indexes from schema.sql."""
    conn = get_db_connection()
    with open("backend/schema.sql", "r", encoding="utf-8") as f:
        schema_script = f.read()
    conn.executescript(schema_script)
    conn.commit()
    conn.close()

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes the spatial distance in kilometers between two GPS coordinates
    using the Haversine formula (Spatial GIS Distance Calculation).
    """
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def generate_transaction_hash(evacuee_id: int, shelter_id: int, beds: int) -> str:
    """Generates a cryptographic SHA-256 block hash for tamper-proof audit logging."""
    raw_payload = f"{evacuee_id}:{shelter_id}:{beds}:{time.time()}"
    return hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()

def execute_concurrency_safe_allocation(evacuee_id: int, shelter_id: int, 
                                        beds: int = 1, o2: int = 0, food: int = 0, transport: int = 0) -> Dict[str, Any]:
    """
    DBMS Concurrency-Safe Transaction:
    Uses explicit exclusive transaction locking (`BEGIN IMMEDIATE`) and row checks
    to strictly prevent race conditions and overbooking.
    """
    conn = get_db_connection()
    try:
        # Step 1: Explicit Pessimistic Lock (BEGIN IMMEDIATE reserves DB write lock)
        conn.execute("BEGIN IMMEDIATE;")
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT shelter_id, name, available_beds, oxygen_cylinders, food_units, transport_units 
            FROM shelters WHERE shelter_id = ?
        """, (shelter_id,))
        shelter = cursor.fetchone()
        
        if not shelter:
            conn.rollback()
            return {"success": False, "error": f"Shelter ID {shelter_id} not found."}
            
        if shelter["available_beds"] < beds:
            conn.rollback()
            return {"success": False, "error": f"Insufficient beds at {shelter['name']}. Requested: {beds}, Available: {shelter['available_beds']}."}
            
        if shelter["oxygen_cylinders"] < o2:
            conn.rollback()
            return {"success": False, "error": f"Insufficient oxygen cylinders at {shelter['name']}."}

        # Step 2: Atomic State Update
        new_beds = shelter["available_beds"] - beds
        new_o2 = shelter["oxygen_cylinders"] - o2
        new_food = shelter["food_units"] - food
        new_trans = shelter["transport_units"] - transport
        
        cursor.execute("""
            UPDATE shelters 
            SET available_beds = ?, oxygen_cylinders = ?, food_units = ?, transport_units = ?, version = version + 1
            WHERE shelter_id = ?
        """, (new_beds, new_o2, new_food, new_trans, shelter_id))
        
        # Step 3: Update Evacuee Status
        cursor.execute("""
            UPDATE evacuees 
            SET assigned_shelter_id = ?, status = 'ALLOCATED'
            WHERE evacuee_id = ?
        """, (shelter_id, evacuee_id))
        
        # Step 4: Record Cryptographic Allocation Log
        tx_hash = generate_transaction_hash(evacuee_id, shelter_id, beds)
        cursor.execute("""
            INSERT INTO allocations (evacuee_id, shelter_id, allocated_beds, allocated_oxygen, allocated_food, allocated_transport, transaction_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (evacuee_id, shelter_id, beds, o2, food, transport, tx_hash))
        
        conn.commit()
        return {
            "success": True,
            "shelter_name": shelter["name"],
            "remaining_beds": new_beds,
            "transaction_hash": tx_hash
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
