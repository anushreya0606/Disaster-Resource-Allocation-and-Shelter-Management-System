"""Tamper-evident audit trail: each allocation row stores SHA-256(prev_hash + record).
Changing or deleting any old row breaks every hash after it, and verify_chain() finds the first break."""
import hashlib
import json
from datetime import datetime, timezone

GENESIS = "0" * 64


def _digest(prev_hash, rec):
    body = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


def _record(row):
    return {k: row[k] for k in ("evacuee_id", "shelter_id", "action", "distance_km",
                                "was_fallback", "priority", "created_at")}


def append(conn, evacuee_id, shelter_id, action, distance_km=None, was_fallback=0,
           priority=None, queue_wait_ms=None):
    """Must be called inside write_txn so the chain is extended by one writer at a time."""
    last = conn.execute("SELECT hash FROM allocations ORDER BY allocation_id DESC LIMIT 1").fetchone()
    prev = last["hash"] if last else GENESIS
    rec = {"evacuee_id": evacuee_id, "shelter_id": shelter_id, "action": action,
           "distance_km": None if distance_km is None else round(distance_km, 3),
           "was_fallback": int(was_fallback), "priority": priority,
           "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds")}
    h = _digest(prev, rec)
    conn.execute(
        "INSERT INTO allocations (evacuee_id, shelter_id, action, distance_km, was_fallback, priority,"
        " queue_wait_ms, created_at, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (evacuee_id, shelter_id, action, rec["distance_km"], rec["was_fallback"], priority,
         queue_wait_ms, rec["created_at"], prev, h))
    return h


def verify_chain(conn):
    prev = GENESIS
    n = 0
    for row in conn.execute("SELECT * FROM allocations ORDER BY allocation_id"):
        n += 1
        if row["prev_hash"] != prev or _digest(prev, _record(row)) != row["hash"]:
            return {"valid": False, "checked": n, "broken_at": row["allocation_id"]}
        prev = row["hash"]
    return {"valid": True, "checked": n, "broken_at": None}
