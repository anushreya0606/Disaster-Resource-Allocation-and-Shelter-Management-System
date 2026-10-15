"""Shelter allocation: nearest shelter that can actually take the person, with automatic fallback.

Runs inside one pessimistic write transaction (BEGIN IMMEDIATE), so the read -> check -> claim
sequence cannot interleave with another allocation. The guarded UPDATE (available_beds > 0) and
the table CHECK constraint are two more layers that make overbooking impossible.
"""
import math
from datetime import datetime, timezone

from . import audit, config, telemetry
from .database import write_txn

CANDIDATE_LIMIT = 60


def blockers(s, ev):
    reasons = []
    if s["available_beds"] <= 0:
        reasons.append("full")
    if ev["priority"] == 0 and not s["has_icu"]:
        reasons.append("no ICU")
    if ev["needs_oxygen"] and s["oxygen"] <= 0:
        reasons.append("no oxygen left")
    if ev["uses_wheelchair"] and not s["wheelchair_ok"]:
        reasons.append("not wheelchair accessible")
    return reasons


def _candidates(conn, lat, lon, max_km):
    dlat = max_km / 111.0
    dlon = max_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return conn.execute(
        """SELECT s.shelter_id, s.shelter_name, s.available_beds, s.total_beds, s.has_icu, s.wheelchair_ok,
                  s.contact_helpline, d.district_name, d.state,
                  COALESCE(o.quantity, 0) AS oxygen,
                  haversine(?, ?, s.latitude, s.longitude) AS km
           FROM shelters s
           JOIN districts d ON d.district_id = s.district_id
           LEFT JOIN shelter_inventory o ON o.shelter_id = s.shelter_id AND o.resource = 'oxygen_cylinder'
           WHERE s.status <> 'CLOSED'
             AND s.latitude BETWEEN ? AND ? AND s.longitude BETWEEN ? AND ?
           ORDER BY km LIMIT ?""",
        (lat, lon, lat - dlat, lat + dlat, lon - dlon, lon + dlon, CANDIDATE_LIMIT)).fetchall()


def allocate(evacuee_id, queue_wait_ms=None, max_km=None):
    max_km = max_km or config.MAX_ROUTE_KM
    with write_txn() as conn:
        ev = conn.execute("SELECT * FROM evacuees WHERE evacuee_id = ?", (evacuee_id,)).fetchone()
        if ev is None:
            return {"evacuee_id": evacuee_id, "status": "UNKNOWN"}
        if ev["status"] not in ("QUEUED", "WAITING"):
            return {"evacuee_id": evacuee_id, "status": ev["status"], "shelter_id": ev["shelter_id"]}

        ranked = [dict(r) for r in _candidates(conn, ev["latitude"], ev["longitude"], max_km)]
        ranked = [r for r in ranked if r["km"] <= max_km]
        pick, skipped = None, []
        for cand in ranked:
            b = blockers(cand, ev)
            if not b:
                pick = cand
                break
            if len(skipped) < 5:
                skipped.append({"shelter_name": cand["shelter_name"], "km": round(cand["km"], 1), "reasons": b})

        if pick is None:
            conn.execute("UPDATE evacuees SET status = 'WAITING' WHERE evacuee_id = ?", (evacuee_id,))
            return {"evacuee_id": evacuee_id, "status": "WAITING", "skipped": skipped,
                    "message": f"No suitable shelter with a free bed within {max_km:.0f} km"}

        cur = conn.execute("UPDATE shelters SET available_beds = available_beds - 1 "
                           "WHERE shelter_id = ? AND available_beds > 0", (pick["shelter_id"],))
        if cur.rowcount != 1:  # cannot happen under the write lock; kept as a defensive check
            raise RuntimeError("bed claim failed")
        if ev["needs_oxygen"]:
            conn.execute("UPDATE shelter_inventory SET quantity = quantity - 1 WHERE shelter_id = ? "
                         "AND resource = 'oxygen_cylinder' AND quantity > 0", (pick["shelter_id"],))
        was_fallback = int(ranked[0]["shelter_id"] != pick["shelter_id"])
        audit.append(conn, evacuee_id, pick["shelter_id"], "ALLOCATE", pick["km"], was_fallback,
                     ev["priority"], queue_wait_ms)
        conn.execute("UPDATE evacuees SET status = 'ALLOCATED', shelter_id = ?, allocated_at = ? WHERE evacuee_id = ?",
                     (pick["shelter_id"], datetime.now(timezone.utc).isoformat(timespec="seconds"), evacuee_id))
    telemetry.record_allocation()
    return {"evacuee_id": evacuee_id, "status": "ALLOCATED",
            "shelter": {"shelter_id": pick["shelter_id"], "shelter_name": pick["shelter_name"],
                        "district": pick["district_name"], "state": pick["state"],
                        "contact_helpline": pick["contact_helpline"],
                        "beds_left": pick["available_beds"] - 1},
            "distance_km": round(pick["km"], 1), "was_fallback": bool(was_fallback), "skipped": skipped}


def discharge(evacuee_id):
    with write_txn() as conn:
        ev = conn.execute("SELECT * FROM evacuees WHERE evacuee_id = ?", (evacuee_id,)).fetchone()
        if ev is None or ev["status"] != "ALLOCATED":
            raise ValueError("Only people with an allocated bed can be discharged")
        conn.execute("UPDATE shelters SET available_beds = available_beds + 1 "
                     "WHERE shelter_id = ? AND available_beds < total_beds", (ev["shelter_id"],))
        conn.execute("UPDATE evacuees SET status = 'DISCHARGED' WHERE evacuee_id = ?", (evacuee_id,))
        audit.append(conn, evacuee_id, ev["shelter_id"], "DISCHARGE", priority=ev["priority"])
    return {"evacuee_id": evacuee_id, "status": "DISCHARGED"}
