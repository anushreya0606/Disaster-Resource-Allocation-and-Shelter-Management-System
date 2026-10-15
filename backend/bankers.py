"""Banker's algorithm for loaning reusable equipment (oxygen cylinders, stretchers, generators)
from a state depot to shelters.

Why it fits: each shelter with a medical unit declares, at the start of the operation, the maximum
equipment it may need (max claim). Equipment is loaned and returned later. A request is granted only
if, after granting, there is still an order in which every shelter could receive its remaining need
and return its loan (a safe state). That is exactly the Banker's precondition.
"""
import threading

from .database import get_conn, write_txn

RESOURCES = ("oxygen_cylinder", "stretcher", "generator")
_lock = threading.Lock()   # serialises Banker's decisions in this process (DB txn also locks)


def is_safe(available, maximum, allocation):
    """Return (safe, order) where order is a safe sequence of process indices."""
    n, m = len(maximum), len(available)
    need = [[maximum[i][j] - allocation[i][j] for j in range(m)] for i in range(n)]
    work, finish, order = list(available), [False] * n, []
    progress = True
    while progress:
        progress = False
        for i in range(n):
            if not finish[i] and all(need[i][j] <= work[j] for j in range(m)):
                for j in range(m):
                    work[j] += allocation[i][j]
                finish[i] = True
                order.append(i)
                progress = True
    return all(finish), order


def request(i, req, available, maximum, allocation):
    """Pure Banker's request check. Returns (granted, reason, order)."""
    m = len(available)
    need_i = [maximum[i][j] - allocation[i][j] for j in range(m)]
    if any(req[j] > need_i[j] for j in range(m)):
        return False, "Request is more than the shelter's declared maximum", []
    if any(req[j] > available[j] for j in range(m)):
        return False, "Depot does not have enough stock right now; the shelter must wait", []
    new_av = [available[j] - req[j] for j in range(m)]
    new_alloc = [row[:] for row in allocation]
    new_alloc[i] = [allocation[i][j] + req[j] for j in range(m)]
    safe, order = is_safe(new_av, maximum, new_alloc)
    if not safe:
        return False, "Granting this would leave the depot in an unsafe state (possible deadlock)", []
    return True, "Granted: the system stays in a safe state", order


def _load(conn, state):
    procs = conn.execute(
        """SELECT DISTINCT s.shelter_id, s.shelter_name FROM resupply_claims c
           JOIN shelters s ON s.shelter_id = c.shelter_id JOIN districts d ON d.district_id = s.district_id
           WHERE d.state = ? ORDER BY s.shelter_id""", (state,)).fetchall()
    ids = [p["shelter_id"] for p in procs]
    claims = {(r["shelter_id"], r["resource"]): r for r in conn.execute(
        "SELECT * FROM resupply_claims WHERE shelter_id IN (%s)" % ",".join("?" * len(ids)), ids)} if ids else {}
    maximum = [[claims[(sid, r)]["max_claim"] for r in RESOURCES] for sid in ids]
    allocation = [[claims[(sid, r)]["allocated"] for r in RESOURCES] for sid in ids]
    stock = {r["resource"]: r["available"] for r in conn.execute(
        "SELECT resource, available FROM depot_stock WHERE state = ?", (state,))}
    available = [stock.get(r, 0) for r in RESOURCES]
    return procs, ids, available, maximum, allocation


def state_view(state):
    procs, ids, available, maximum, allocation = _load(get_conn(), state)
    safe, order = is_safe(available, maximum, allocation)
    return {"state": state, "resources": RESOURCES, "available": available,
            "processes": [{"shelter_id": p["shelter_id"], "shelter_name": p["shelter_name"],
                           "max": maximum[i], "allocated": allocation[i],
                           "need": [maximum[i][j] - allocation[i][j] for j in range(len(RESOURCES))]}
                          for i, p in enumerate(procs)],
            "safe": safe, "safe_sequence": [ids[i] for i in order]}


def _state_of(conn, shelter_id):
    r = conn.execute("SELECT d.state FROM shelters s JOIN districts d ON d.district_id = s.district_id "
                     "WHERE s.shelter_id = ?", (shelter_id,)).fetchone()
    if not r:
        raise ValueError("Unknown shelter")
    return r["state"]


def _vector(d):
    v = [int(d.get(r, 0) or 0) for r in RESOURCES]
    if any(x < 0 for x in v) or not any(v):
        raise ValueError("Enter at least one positive quantity")
    return v


def make_request(shelter_id, amounts):
    req = _vector(amounts)
    with _lock, write_txn() as conn:
        state = _state_of(conn, shelter_id)
        procs, ids, available, maximum, allocation = _load(conn, state)
        if shelter_id not in ids:
            raise ValueError("This shelter has no declared equipment claim")
        i = ids.index(shelter_id)
        granted, reason, order = request(i, req, available, maximum, allocation)
        if granted:
            for j, res in enumerate(RESOURCES):
                if req[j]:
                    conn.execute("UPDATE depot_stock SET available = available - ? WHERE state = ? AND resource = ?",
                                 (req[j], state, res))
                    conn.execute("UPDATE resupply_claims SET allocated = allocated + ? WHERE shelter_id = ? AND resource = ?",
                                 (req[j], shelter_id, res))
            if req[0]:  # oxygen loaned to the shelter becomes usable stock there
                conn.execute("UPDATE shelter_inventory SET quantity = quantity + ? WHERE shelter_id = ? "
                             "AND resource = 'oxygen_cylinder'", (req[0], shelter_id))
    return {"granted": granted, "reason": reason, "safe_sequence": [ids[k] for k in order]}


def release(shelter_id, amounts):
    rel = _vector(amounts)
    with _lock, write_txn() as conn:
        state = _state_of(conn, shelter_id)
        procs, ids, available, maximum, allocation = _load(conn, state)
        if shelter_id not in ids:
            raise ValueError("This shelter has no declared equipment claim")
        i = ids.index(shelter_id)
        if any(rel[j] > allocation[i][j] for j in range(len(RESOURCES))):
            raise ValueError("Cannot return more than the shelter has on loan")
        for j, res in enumerate(RESOURCES):
            if rel[j]:
                conn.execute("UPDATE depot_stock SET available = available + ? WHERE state = ? AND resource = ?",
                             (rel[j], state, res))
                conn.execute("UPDATE resupply_claims SET allocated = allocated - ? WHERE shelter_id = ? AND resource = ?",
                             (rel[j], shelter_id, res))
        if rel[0]:
            conn.execute("UPDATE shelter_inventory SET quantity = MAX(0, quantity - ?) WHERE shelter_id = ? "
                         "AND resource = 'oxygen_cylinder'", (rel[0], shelter_id))
    return {"returned": dict(zip(RESOURCES, rel))}
