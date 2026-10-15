"""Load the synthetic dataset CSVs into a fresh database."""
import csv
import random
from pathlib import Path

from . import auth, bankers, config
from .database import get_conn, init_db, write_txn

YES = {"YES": 1, "NO": 0}


def _read(name):
    with open(Path(config.DATA_DIR) / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def is_seeded():
    return get_conn().execute("SELECT COUNT(*) FROM shelters").fetchone()[0] > 0


def seed(reset=False):
    if reset and Path(config.DB_PATH).exists():
        conn = get_conn()
        for t in ("telemetry_logs", "alert_queue", "allocations", "evacuees", "resupply_claims", "depot_stock",
                  "shelter_inventory", "shelters", "districts", "disaster_events", "sessions", "users"):
            conn.execute(f"DROP TABLE IF EXISTS {t}")
    init_db()
    if is_seeded():
        return False
    rng = random.Random(7)
    with write_txn() as c:
        for r in _read("disaster_events.csv"):
            c.execute("INSERT INTO disaster_events VALUES (?,?,?,?,?,?)",
                      (r["event_id"], r["event_name"], r["disaster_type"], r["severity"], r["state"], r["start_time"]))
        for r in _read("districts.csv"):
            c.execute("INSERT INTO districts VALUES (?,?,?,?,?,?)",
                      (r["district_id"], r["district_name"], r["state"], r["hq_latitude"], r["hq_longitude"],
                       YES[r["hilly_terrain"]]))
        for r in _read("shelters.csv"):
            total, occ = int(r["total_beds"]), int(r["occupied_at_start"])
            avail = total - occ
            status = "FULL" if avail == 0 else ("CRITICAL_90" if occ * 10 >= total * 9 else "OPEN")
            c.execute("""INSERT INTO shelters (shelter_id, shelter_name, facility_type, district_id, latitude, longitude,
                         total_beds, initial_occupied, available_beds, has_icu, has_medical_unit, wheelchair_ok,
                         contact_helpline, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (r["shelter_id"], r["shelter_name"], r["facility_type"], r["district_id"], r["latitude"],
                       r["longitude"], total, occ, avail, YES[r["has_icu"]], YES[r["has_medical_unit"]],
                       YES[r["wheelchair_accessible"]], r["contact_helpline"], status))
        for r in _read("shelter_inventory.csv"):
            c.execute("INSERT INTO shelter_inventory VALUES (?,?,?,?,?)",
                      (r["shelter_id"], r["resource"], r["unit"], r["quantity"], r["low_stock_threshold"]))

        auth.create_user(c, "admin", "Relief Administrator", "ADMIN", "admin123")
        auth.create_user(c, "volunteer", "Field Volunteer", "VOLUNTEER", "volunteer123")
        auth.create_user(c, "sms_gateway", "SMS Gateway", "SYSTEM", rng.getrandbits(128).to_bytes(16, "big").hex())

        # Banker's: shelters with a medical unit declare max equipment claims; some already on loan
        med = c.execute("""SELECT s.shelter_id, s.has_icu, d.state FROM shelters s
                           JOIN districts d ON d.district_id = s.district_id WHERE s.has_medical_unit = 1""").fetchall()
        by_state = {}
        for s in med:
            mx = [30, 10, 2] if s["has_icu"] else [10, 4, 1]
            al = [rng.randint(0, m // 2) for m in mx]
            by_state.setdefault(s["state"], []).append((mx, al))
            for res, m, a in zip(bankers.RESOURCES, mx, al):
                c.execute("INSERT INTO resupply_claims VALUES (?,?,?,?)", (s["shelter_id"], res, m, a))
        for state, procs in by_state.items():
            maximum = [p[0] for p in procs]
            allocation = [p[1] for p in procs]
            # Depot stock: start tight (about 15% of total remaining need), then raise until the state is safe
            need_tot = [sum(m[j] - a[j] for m, a in procs) for j in range(3)]
            avail = [max(1, int(0.15 * n)) for n in need_tot]
            while not bankers.is_safe(avail, maximum, allocation)[0]:
                avail = [v + 1 for v in avail]
            for res, v in zip(bankers.RESOURCES, avail):
                c.execute("INSERT INTO depot_stock VALUES (?,?,?)", (state, res, v))
    return True
