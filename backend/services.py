"""Intake, duplicate prevention, queries and integrity checks used by the API and the SMS daemon."""
from concurrent.futures import TimeoutError as FutureTimeout

from . import allocator, config
from .database import get_conn, one, rows, write_txn
from .os_scheduler import BufferFull
from .triage import LEVELS, triage

INJURIES = ("none", "minor", "serious", "critical")


class DuplicateError(Exception):
    def __init__(self, message, existing_id):
        super().__init__(message)
        self.existing_id = existing_id


def _flag(v):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(v)


def normalize(p):
    """Validate an intake payload. Raises ValueError with a message a volunteer can act on."""
    name = str(p.get("full_name") or "").strip()
    if not 1 <= len(name) <= 100:
        raise ValueError("Enter the person's name (up to 100 characters)")
    age = p.get("age")
    if age in ("", None):
        age = None
    else:
        try:
            age = int(age)
        except (TypeError, ValueError):
            raise ValueError("Age must be a whole number")
        if not 0 <= age <= 120:
            raise ValueError("Age must be between 0 and 120")
    sex = str(p.get("sex") or "O").upper()[:1]
    if sex not in ("F", "M", "O"):
        raise ValueError("Sex must be F, M or O")
    injury = str(p.get("injury_severity") or "none").lower()
    if injury not in INJURIES:
        raise ValueError("Injury must be none, minor, serious or critical")
    lat, lon = p.get("latitude"), p.get("longitude")
    if (lat in (None, "") or lon in (None, "")) and p.get("district_id"):
        d = one("SELECT hq_latitude, hq_longitude FROM districts WHERE district_id = ?", (int(p["district_id"]),))
        if not d:
            raise ValueError("Unknown district")
        lat, lon = d["hq_latitude"], d["hq_longitude"]
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        raise ValueError("Choose a district or give a GPS location")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Location is out of range")
    ext = (str(p.get("external_ref")).strip() or None) if p.get("external_ref") else None
    crid = (str(p.get("client_request_id")).strip() or None) if p.get("client_request_id") else None
    pregnant = _flag(p.get("pregnant"))
    if pregnant and sex == "M":
        raise ValueError("Pregnant is marked for a male record; check the form")
    return {"full_name": name, "age": age, "sex": sex, "pregnant": pregnant, "injury_severity": injury,
            "unconscious": _flag(p.get("unconscious")), "needs_oxygen": _flag(p.get("needs_oxygen")),
            "uses_wheelchair": _flag(p.get("uses_wheelchair")), "latitude": lat, "longitude": lon,
            "external_ref": (ext[:64] if ext else None), "client_request_id": (crid[:64] if crid else None)}


def register(payload, user_id, source, scheduler, wait_s=None):
    e = normalize(payload)
    level, reasons = triage(e)
    replay, evacuee_id = False, None
    with write_txn() as c:
        if e["client_request_id"]:
            prev = c.execute("SELECT evacuee_id FROM evacuees WHERE client_request_id = ?",
                             (e["client_request_id"],)).fetchone()
            if prev:  # same submission sent twice (e.g. offline sync retry): idempotent replay
                replay, evacuee_id = True, prev["evacuee_id"]
        if not replay:
            if e["external_ref"]:
                dup = c.execute("SELECT evacuee_id FROM evacuees WHERE external_ref = ?", (e["external_ref"],)).fetchone()
                if dup:
                    raise DuplicateError("This ID number is already registered", dup["evacuee_id"])
            # name+age+place check only when no ID was given (an ID number is the stronger identity)
            dup = None if e["external_ref"] else c.execute(
                """SELECT evacuee_id FROM evacuees
                   WHERE lower(full_name) = lower(?) AND age IS ? AND status <> 'DISCHARGED'
                     AND created_at >= strftime('%Y-%m-%dT%H:%M:%f','now','-15 minutes')
                     AND haversine(latitude, longitude, ?, ?) < 2""",
                (e["full_name"], e["age"], e["latitude"], e["longitude"])).fetchone()
            if dup:
                raise DuplicateError("Same name and age registered nearby in the last 15 minutes", dup["evacuee_id"])
            cur = c.execute(
                """INSERT INTO evacuees (client_request_id, external_ref, full_name, age, sex, pregnant,
                   injury_severity, unconscious, needs_oxygen, uses_wheelchair, latitude, longitude,
                   priority, triage_reasons, registered_by, source)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (e["client_request_id"], e["external_ref"], e["full_name"], e["age"], e["sex"], int(e["pregnant"]),
                 e["injury_severity"], int(e["unconscious"]), int(e["needs_oxygen"]), int(e["uses_wheelchair"]),
                 e["latitude"], e["longitude"], level, "; ".join(reasons), user_id, source))
            evacuee_id = cur.lastrowid

    base = {"evacuee_id": evacuee_id, "priority": level, "priority_label": LEVELS[level],
            "reasons": reasons, "replayed": replay}
    if replay:
        return {**base, **evacuee_status(evacuee_id)}
    try:
        fut = scheduler.submit(evacuee_id, level)
        result = fut.result(timeout=config.INTAKE_WAIT_S if wait_s is None else wait_s)
    except BufferFull:
        result = {"status": "QUEUED", "message": "System busy; the person is saved and will be placed shortly"}
    except FutureTimeout:
        result = {"status": "QUEUED", "message": "Saved and waiting in the triage queue"}
    return {**base, **result}


def evacuee_status(evacuee_id):
    r = one("""SELECT e.evacuee_id, e.full_name, e.status, e.priority, e.shelter_id,
                      s.shelter_name, s.contact_helpline
               FROM evacuees e LEFT JOIN shelters s ON s.shelter_id = e.shelter_id
               WHERE e.evacuee_id = ?""", (evacuee_id,))
    if not r:
        raise LookupError("No such person")
    return r


def requeue_pending(scheduler, limit=300):
    """Put QUEUED/WAITING people back into the scheduler (after discharges, restarts, or periodically)."""
    n = 0
    for r in rows("SELECT evacuee_id, priority FROM evacuees WHERE status IN ('QUEUED','WAITING') "
                  "ORDER BY priority, created_at LIMIT ?", (limit,)):
        try:
            scheduler.submit(r["evacuee_id"], r["priority"], block_timeout=0)
            n += 1
        except BufferFull:
            break
    return n


def discharge(evacuee_id, scheduler):
    out = allocator.discharge(evacuee_id)
    requeue_pending(scheduler, limit=50)
    return out


def integrity_report():
    """Overbooking check: occupied beds must equal initial occupancy + people currently allocated."""
    bad = rows("""
        SELECT s.shelter_id, s.shelter_name, s.total_beds, s.available_beds, s.initial_occupied,
               (SELECT COUNT(*) FROM evacuees e WHERE e.shelter_id = s.shelter_id AND e.status = 'ALLOCATED') AS active
        FROM shelters s""")
    mismatched = [r for r in bad if r["total_beds"] - r["available_beds"] != r["initial_occupied"] + r["active"]]
    overbooked = [r for r in bad if r["initial_occupied"] + r["active"] > r["total_beds"] or r["available_beds"] < 0]
    return {"shelters_checked": len(bad), "overbooked": len(overbooked), "counter_mismatches": len(mismatched),
            "examples": (overbooked + mismatched)[:5]}


def summary(scheduler):
    s = one("""SELECT COUNT(*) AS shelters, SUM(total_beds) AS total_beds, SUM(available_beds) AS free_beds,
                      SUM(status='FULL') AS full, SUM(status='CRITICAL_90') AS critical,
                      SUM(has_icu) AS icu FROM shelters""")
    e = {r["status"]: r["n"] for r in rows("SELECT status, COUNT(*) AS n FROM evacuees GROUP BY status")}
    alerts = one("SELECT COUNT(*) AS n FROM alert_queue WHERE acknowledged = 0")["n"]
    return {"shelters": s, "evacuees": e, "open_alerts": alerts, "queue": scheduler.stats()}


def list_shelters(state=None, q=None, status=None, limit=400):
    sql = ["""SELECT s.shelter_id, s.shelter_name, s.facility_type, d.district_name, d.state, s.total_beds,
                     s.available_beds, s.status, s.has_icu, s.wheelchair_ok, s.contact_helpline,
                     ROUND(100.0 * (s.total_beds - s.available_beds) / s.total_beds, 1) AS occupancy,
                     COALESCE((SELECT quantity FROM shelter_inventory i WHERE i.shelter_id = s.shelter_id
                               AND i.resource = 'oxygen_cylinder'), 0) AS oxygen,
                     COALESCE((SELECT quantity FROM shelter_inventory i WHERE i.shelter_id = s.shelter_id
                               AND i.resource = 'food'), 0) AS food_kg
              FROM shelters s JOIN districts d ON d.district_id = s.district_id WHERE 1=1"""]
    args = []
    if state:
        sql.append("AND d.state = ?"); args.append(state)
    if status:
        sql.append("AND s.status = ?"); args.append(status)
    if q:
        sql.append("AND (s.shelter_name LIKE ? OR d.district_name LIKE ?)"); args += [f"%{q}%", f"%{q}%"]
    sql.append("ORDER BY occupancy DESC LIMIT ?"); args.append(limit)
    return rows(" ".join(sql), args)


def list_evacuees(status=None, limit=100):
    sql = """SELECT e.evacuee_id, e.full_name, e.age, e.sex, e.priority, e.triage_reasons, e.status,
                    e.source, e.created_at, s.shelter_name
             FROM evacuees e LEFT JOIN shelters s ON s.shelter_id = e.shelter_id"""
    if status:
        return rows(sql + " WHERE e.status = ? ORDER BY e.priority, e.evacuee_id DESC LIMIT ?", (status, limit))
    return rows(sql + " ORDER BY e.evacuee_id DESC LIMIT ?", (limit,))
