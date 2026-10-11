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


def execute_concurrency_safe_allocation(
    evacuee_id: int,
    shelter_id: int,
    beds: int = 1,
    o2: int = 0,
    food: int = 0,
    transport: int = 0
) -> Dict[str, Any]:
    """
    Allocate shelter resources safely using a SQLite write transaction.

    BEGIN IMMEDIATE serializes competing writers. The transaction ensures
    that resource deductions, evacuee updates, and allocation records
    succeed together or are rolled back together.
    """

    # Step 1: Validate input quantities
    if evacuee_id <= 0 or shelter_id <= 0:
        return {"success": False, "error": "Invalid evacuee or shelter ID."}

    if beds < 1 or o2 < 0 or food < 0 or transport < 0:
        return {"success": False, "error": "Invalid resource quantities."}

    conn = get_db_connection()

    try:
        # Step 2: Acquire SQLite write lock before reading state
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()

        # Step 3: Confirm that the evacuee exists and is waiting
        cursor.execute(
            """
            SELECT evacuee_id, status, assigned_shelter_id
            FROM evacuees
            WHERE evacuee_id = ?
            """,
            (evacuee_id,)
        )
        evacuee = cursor.fetchone()

        if evacuee is None:
            conn.rollback()
            return {"success": False, "error": "Evacuee not found."}

        if (
            evacuee["status"] != "WAITING"
            or evacuee["assigned_shelter_id"] is not None
        ):
            conn.rollback()
            return {
                "success": False,
                "error": "Evacuee is already allocated or is not waiting."
            }

        # Step 4: Read shelter status and available resources
        cursor.execute(
            """
            SELECT shelter_id, name, status, available_beds,
            oxygen_cylinders, food_units, transport_units
            FROM shelters
            WHERE shelter_id = ?
            """,
            (shelter_id,)
        )
        shelter = cursor.fetchone()

        if shelter is None:
            conn.rollback()
            return {"success": False, "error": "Shelter not found."}

        if shelter["status"] == "CLOSED":
            conn.rollback()
            return {"success": False, "error": "Shelter is closed."}

        requested = {
            "beds": (beds, shelter["available_beds"]),
            "oxygen cylinders": (o2, shelter["oxygen_cylinders"]),
            "food units": (food, shelter["food_units"]),
            "transport units": (transport, shelter["transport_units"]),
        }

        for resource, (needed, available) in requested.items():
            if needed > available:
                conn.rollback()
                return {
                    "success": False,
                    "error": (
                        f"Insufficient {resource}. "
                        f"Requested: {needed}, available: {available}."
                    )
                }

        # Step 5: Deduct all resources atomically
        cursor.execute(
            """
            UPDATE shelters
            SET available_beds = available_beds - ?,
                oxygen_cylinders = oxygen_cylinders - ?,
                food_units = food_units - ?,
                transport_units = transport_units - ?,
                version = version + 1
            WHERE shelter_id = ?
                AND status != 'CLOSED'
                AND available_beds >= ?
                AND oxygen_cylinders >= ?
                AND food_units >= ?
                AND transport_units >= ?
            """,
            (
                beds, o2, food, transport, shelter_id,
                beds, o2, food, transport
            )
        )

        if cursor.rowcount != 1:
            conn.rollback()
            return {
                "success": False,
                "error": "Shelter resources changed or are insufficient."
            }

        # Step 6: Update only an unassigned, waiting evacuee
        cursor.execute(
            """
            UPDATE evacuees
            SET assigned_shelter_id = ?, status = 'ALLOCATED'
            WHERE evacuee_id = ?
                AND status = 'WAITING'
                AND assigned_shelter_id IS NULL
            """,
            (shelter_id, evacuee_id)
        )

        if cursor.rowcount != 1:
            conn.rollback()
            return {
                "success": False,
                "error": "Evacuee was already allocated."
            }

        # Step 7: Insert the allocation record
        tx_hash = generate_transaction_hash(evacuee_id, shelter_id, beds)

        cursor.execute(
            """
            INSERT INTO allocations (
                evacuee_id, shelter_id, allocated_beds,
                allocated_oxygen, allocated_food, allocated_transport,
                transaction_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (evacuee_id, shelter_id, beds, o2, food, transport, tx_hash)
        )

        allocation_id = cursor.lastrowid
        remaining_beds = shelter["available_beds"] - beds

        # Step 8: Commit all changes together
        conn.commit()

        return {
            "success": True,
            "message": "Resources allocated successfully.",
            "allocation_id": allocation_id,
            "evacuee_id": evacuee_id,
            "shelter_id": shelter_id,
            "shelter_name": shelter["name"],
            "allocated_beds": beds,
            "remaining_beds": remaining_beds,
            "transaction_hash": tx_hash
        }

    except Exception:
        conn.rollback()
        return {
            "success": False,
            "error": "Allocation failed. No changes were committed."
        }

    finally:
        conn.close()
