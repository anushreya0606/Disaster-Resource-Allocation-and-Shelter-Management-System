"""Concurrent check-in load test (multi-threaded, standard library only).

Replays arrivals from data/arrival_events.csv against the running server. Each person is sent with
external_ref = DS-<evacuee_id>, so the dataset's duplicate submissions must come back as HTTP 409.
After the run it asks the server to verify: no overbooking, counters consistent, audit chain intact.

  python scripts/loadtest.py --concurrency 60 --requests 300
  python scripts/loadtest.py --concurrency 100 --requests 500 --district 56   # everyone at one hotspot
"""
import argparse
import csv
import json
import statistics
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def call(base, path, token=None, body=None):
    req = urllib.request.Request(base + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def login(base, user, pw):
    code, body = call(base, "/api/auth/login", body={"username": user, "password": pw})
    if code != 200:
        raise SystemExit(f"Login failed for {user}: {body}")
    return body["token"]


def payloads(n, district):
    ev = {r["evacuee_id"]: r for r in csv.DictReader(open(DATA / "evacuees.csv", encoding="utf-8"))}
    out = []
    for a in csv.DictReader(open(DATA / "arrival_events.csv", encoding="utf-8")):
        if len(out) >= n:
            break
        e = ev[a["evacuee_id"]]
        p = {"full_name": e["full_name"], "age": int(e["age"]), "sex": e["sex"], "injury_severity": e["injury_severity"],
             "pregnant": e["pregnant"] == "YES", "unconscious": e["unconscious"] == "YES",
             "needs_oxygen": e["needs_oxygen"] == "YES", "uses_wheelchair": e["uses_wheelchair"] == "YES",
             "external_ref": "DS-" + e["evacuee_id"], "client_request_id": f"{a['device_id']}-{a['arrival_id']}",
             "source": "LOADTEST"}
        if district:
            p["district_id"] = district
        else:
            p["latitude"], p["longitude"] = float(e["latitude"]), float(e["longitude"])
        out.append((p, a["is_duplicate_submission"] == "YES"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--concurrency", type=int, default=60)
    ap.add_argument("--requests", type=int, default=300)
    ap.add_argument("--district", type=int, default=0, help="send everyone to this district (stress one area)")
    ap.add_argument("--user", default="volunteer"); ap.add_argument("--password", default="volunteer123")
    ap.add_argument("--admin", default="admin"); ap.add_argument("--admin-password", default="admin123")
    args = ap.parse_args()

    token = login(args.url, args.user, args.password)
    jobs = payloads(args.requests, args.district)
    expected_dups = sum(d for _, d in jobs)
    barrier = threading.Barrier(min(args.concurrency, len(jobs)))
    results, lock = [], threading.Lock()

    def send(i_job):
        i, (p, _) = i_job
        if i < barrier.parties:
            barrier.wait()                         # first wave fires at exactly the same moment
        t0 = time.perf_counter()
        code, body = call(args.url, "/api/intake", token, p)
        with lock:
            results.append((code, body, (time.perf_counter() - t0) * 1000))

    print(f"Sending {len(jobs)} check-ins with {args.concurrency} threads "
          f"({expected_dups} are deliberate duplicates)…")
    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        list(pool.map(send, enumerate(jobs)))
    elapsed = time.perf_counter() - t_start

    lat = sorted(r[2] for r in results)
    status = {}
    for code, body, _ in results:
        key = body.get("status") if code == 200 and isinstance(body, dict) else f"HTTP {code}"
        status[key] = status.get(key, 0) + 1
    fallback = sum(1 for c, b, _ in results if c == 200 and b.get("was_fallback"))
    print("\nResults")
    for k, v in sorted(status.items()):
        print(f"  {k:<12} {v}")
    print(f"  fallback routings: {fallback}")
    print(f"  duplicates rejected (HTTP 409): {status.get('HTTP 409', 0)} of {expected_dups} expected")
    print(f"\nLatency ms: p50 {statistics.median(lat):.0f}  p95 {lat[int(0.95 * (len(lat) - 1))]:.0f}  max {lat[-1]:.0f}")
    print(f"Throughput: {len(results) / elapsed:.1f} requests/s over {elapsed:.1f} s")

    admin = login(args.url, args.admin, args.admin_password)
    _, integ = call(args.url, "/api/integrity", admin)
    _, chain = call(args.url, "/api/audit/verify", admin)
    print(f"\nOverbooked shelters: {integ['overbooked']}   counter mismatches: {integ['counter_mismatches']}")
    print(f"Audit chain: {'intact' if chain['valid'] else 'BROKEN at ' + str(chain['broken_at'])} ({chain['checked']} records)")


if __name__ == "__main__":
    main()
