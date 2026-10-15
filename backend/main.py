"""FastAPI application: REST API, static frontend, and startup of the background OS components.

Endpoints are plain `def` functions on purpose: FastAPI runs them in its worker thread pool,
so blocking database work never stalls the asyncio event loop.
Run:  uvicorn backend.main:app --reload     then open http://127.0.0.1:8000
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import allocator, audit, auth, bankers, config, seed, services, sms_daemon, telemetry
from .database import get_conn, init_db, one, rows
from .os_scheduler import MLFQScheduler

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
state = {"scheduler": None, "sms": None}


def scheduler():
    return state["scheduler"]


@asynccontextmanager
async def lifespan(app):
    init_db()
    if seed.seed():
        print("Database seeded from data/*.csv")
    sch = MLFQScheduler(allocator.allocate, workers=config.WORKER_THREADS, capacity=config.BUFFER_SIZE,
                        age_after_s=config.AGE_AFTER_S, aging_interval_s=config.AGING_INTERVAL_S,
                        periodic=lambda: services.requeue_pending(state["scheduler"]),
                        periodic_every_s=config.RETRY_WAITING_S)
    sch.start()
    state["scheduler"] = sch
    services.requeue_pending(sch)                 # recover people left QUEUED/WAITING by a restart
    telemetry.start(sch, config.TELEMETRY_INTERVAL_S)
    if config.ENABLE_SMS:
        try:
            state["sms"] = sms_daemon.start(config.SMS_HOST, config.SMS_PORT, sch)
            print(f"SMS socket daemon listening on {config.SMS_HOST}:{config.SMS_PORT}")
        except OSError as exc:
            print("SMS daemon not started:", exc)
    yield
    telemetry.stop()
    if state["sms"]:
        state["sms"].shutdown()
    sch.stop()


app = FastAPI(title="Disaster Resource Allocation and Shelter Management", lifespan=lifespan)


# ---------- auth helpers ----------
def current_user(authorization: str = Header(default="")):
    token = authorization[7:] if authorization.lower().startswith("bearer ") else ""
    user = auth.user_for_token(token)
    if not user:
        raise HTTPException(401, "Sign in again")
    user["token"] = token
    return user


def admin_user(user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(403, "Administrators only")
    return user


def _run(fn, *a, **k):
    """Map service exceptions to HTTP status codes."""
    try:
        return fn(*a, **k)
    except services.DuplicateError as exc:
        raise HTTPException(409, {"message": str(exc), "existing_id": exc.existing_id})
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


# ---------- auth ----------
@app.post("/api/auth/login")
def login(body: dict = Body(...)):
    res = auth.login(str(body.get("username", "")), str(body.get("password", "")))
    if not res:
        raise HTTPException(401, "Wrong username or password")
    return res


@app.post("/api/auth/logout")
def logout(user=Depends(current_user)):
    auth.logout(user["token"])
    return {"ok": True}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return {k: user[k] for k in ("username", "full_name", "role")}


# ---------- intake ----------
@app.post("/api/intake")
def intake(body: dict = Body(...), user=Depends(current_user)):
    return _run(services.register, body, user["user_id"], body.get("source") or "WEB", scheduler())


@app.post("/api/intake/batch")
def intake_batch(body: dict = Body(...), user=Depends(current_user)):
    """Offline sync: each record carries a client_request_id, so re-sending the batch is safe."""
    results = []
    for rec in (body.get("records") or [])[:500]:
        try:
            r = services.register(rec, user["user_id"], "OFFLINE_SYNC", scheduler(), wait_s=2)
            results.append({"client_request_id": rec.get("client_request_id"), "ok": True, **r})
        except services.DuplicateError as exc:
            results.append({"client_request_id": rec.get("client_request_id"), "ok": False,
                            "duplicate": True, "error": str(exc), "existing_id": exc.existing_id})
        except ValueError as exc:
            results.append({"client_request_id": rec.get("client_request_id"), "ok": False, "error": str(exc)})
    return {"results": results}


@app.get("/api/evacuees")
def evacuees(status: str = None, limit: int = 100, user=Depends(current_user)):
    return services.list_evacuees(status, min(limit, 500))


@app.get("/api/evacuees/{evacuee_id}")
def evacuee(evacuee_id: int, user=Depends(current_user)):
    return _run(services.evacuee_status, evacuee_id)


@app.post("/api/evacuees/{evacuee_id}/discharge")
def discharge(evacuee_id: int, user=Depends(current_user)):
    return _run(services.discharge, evacuee_id, scheduler())


# ---------- shelters, districts, summary ----------
@app.get("/api/districts")
def districts(user=Depends(current_user)):
    return rows("SELECT district_id, district_name, state, hq_latitude, hq_longitude FROM districts "
                "ORDER BY state, district_name")


@app.get("/api/states")
def states(user=Depends(current_user)):
    return [r["state"] for r in rows("SELECT DISTINCT state FROM districts ORDER BY state")]


@app.get("/api/shelters")
def shelters(state_name: str = None, q: str = None, status: str = None, user=Depends(current_user)):
    return services.list_shelters(state_name, q, status)


@app.get("/api/summary")
def summary(user=Depends(current_user)):
    return services.summary(scheduler())


# ---------- alerts ----------
@app.get("/api/alerts")
def alerts(include_ack: bool = False, user=Depends(current_user)):
    where = "" if include_ack else "WHERE a.acknowledged = 0"
    return rows(f"""SELECT a.*, s.shelter_name FROM alert_queue a LEFT JOIN shelters s ON s.shelter_id = a.shelter_id
                    {where} ORDER BY a.alert_id DESC LIMIT 200""")


@app.post("/api/alerts/{alert_id}/ack")
def ack(alert_id: int, user=Depends(admin_user)):
    get_conn().execute("UPDATE alert_queue SET acknowledged = 1 WHERE alert_id = ?", (alert_id,))
    return {"ok": True}


# ---------- scheduler ----------
@app.get("/api/queue")
def queue(user=Depends(current_user)):
    return {"stats": scheduler().stats(), "jobs": scheduler().snapshot(),
            "waiting": services.list_evacuees("WAITING", 100)}


@app.post("/api/queue/retry")
def retry(user=Depends(admin_user)):
    return {"requeued": services.requeue_pending(scheduler())}


# ---------- audit, integrity, telemetry ----------
@app.get("/api/audit")
def audit_log(limit: int = 100, user=Depends(admin_user)):
    return rows("""SELECT a.allocation_id, a.action, a.evacuee_id, e.full_name, s.shelter_name, a.distance_km,
                          a.was_fallback, a.priority, a.queue_wait_ms, a.created_at, a.prev_hash, a.hash
                   FROM allocations a JOIN evacuees e ON e.evacuee_id = a.evacuee_id
                   JOIN shelters s ON s.shelter_id = a.shelter_id
                   ORDER BY a.allocation_id DESC LIMIT ?""", (min(limit, 500),))


@app.get("/api/audit/verify")
def audit_verify(user=Depends(admin_user)):
    return audit.verify_chain(get_conn())


@app.get("/api/integrity")
def integrity(user=Depends(admin_user)):
    return services.integrity_report()


@app.get("/api/telemetry")
def telemetry_logs(limit: int = 60, user=Depends(admin_user)):
    return rows("SELECT * FROM telemetry_logs ORDER BY log_id DESC LIMIT ?", (min(limit, 500),))


# ---------- Banker's algorithm ----------
@app.get("/api/bankers/{state_name}")
def bankers_state(state_name: str, user=Depends(admin_user)):
    return bankers.state_view(state_name)


@app.post("/api/bankers/request")
def bankers_request(body: dict = Body(...), user=Depends(admin_user)):
    return _run(bankers.make_request, int(body.get("shelter_id", 0)), body.get("amounts") or {})


@app.post("/api/bankers/release")
def bankers_release(body: dict = Body(...), user=Depends(admin_user)):
    return _run(bankers.release, int(body.get("shelter_id", 0)), body.get("amounts") or {})


# ---------- frontend ----------
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    # served from the root so the service worker can control the whole app (offline mode)
    return FileResponse(FRONTEND / "sw.js", media_type="application/javascript")


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
