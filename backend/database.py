"""SQLite access layer: WAL mode, one connection per thread, write transactions with lock timing.

SQLite has no row-level locks. BEGIN IMMEDIATE takes the database RESERVED (write) lock up front,
which is a pessimistic lock: two allocations can never interleave their read-check-update steps.
On MySQL/PostgreSQL the equivalent is SELECT ... FOR UPDATE on the shelter row.
"""
import math
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from . import config, telemetry

_local = threading.local()
EARTH_RADIUS_KM = 6371.0088


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two (lat, lon) points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _connect(path):
    conn = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.create_function("haversine", 4, haversine, deterministic=True)
    return conn


def get_conn():
    """Each thread gets its own connection (sqlite3 connections must not be shared across threads)."""
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != config.DB_PATH:
        conn = _connect(config.DB_PATH)
        _local.conn, _local.path = conn, config.DB_PATH
    return conn


def init_db():
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    get_conn().executescript(schema)


@contextmanager
def write_txn():
    """Exclusive write transaction. Records how long we waited for the lock (telemetry)."""
    conn = get_conn()
    t0 = time.perf_counter()
    conn.execute("BEGIN IMMEDIATE")
    telemetry.record_lock_wait((time.perf_counter() - t0) * 1000)
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def rows(sql, params=()):
    return [dict(r) for r in get_conn().execute(sql, params).fetchall()]


def one(sql, params=()):
    r = get_conn().execute(sql, params).fetchone()
    return dict(r) if r else None
