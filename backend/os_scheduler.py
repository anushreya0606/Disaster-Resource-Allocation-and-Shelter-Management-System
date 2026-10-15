"""OS-inspired triage scheduler.

* Multilevel queue: P0 (critical medical), P1 (vulnerable), P2 (general). Workers always serve the
  highest non-empty level, like a multilevel feedback queue (MLFQ).
* Aging daemon: a job that waits longer than AGE_AFTER_S is promoted one level, so P2 cannot starve.
  Unlike CPU MLFQ there is no demotion: a person's medical priority must never drop because they waited.
* Producer-consumer bounded buffer: HTTP/SMS handlers are producers, worker threads are consumers.
  Classic three-primitive solution: `empty` and `full` counting semaphores plus a mutex.
  threading.Lock / Semaphore are built on POSIX pthread mutexes/condition variables in CPython on Linux.
"""
import threading
import time
from collections import deque
from concurrent.futures import Future

LEVEL_NAMES = ("P0 Critical", "P1 Vulnerable", "P2 General")


class BufferFull(Exception):
    pass


class Job:
    __slots__ = ("evacuee_id", "base_level", "level", "enqueued_at", "level_since", "future", "promoted")

    def __init__(self, evacuee_id, level):
        now = time.monotonic()
        self.evacuee_id, self.base_level, self.level = evacuee_id, level, level
        self.enqueued_at = self.level_since = now
        self.future = Future()
        self.promoted = 0


class MLFQScheduler:
    def __init__(self, handler, workers=8, capacity=1000, age_after_s=30.0, aging_interval_s=5.0,
                 periodic=None, periodic_every_s=20.0):
        self.handler = handler                      # handler(evacuee_id, queue_wait_ms) -> result
        self.queues = [deque(), deque(), deque()]
        self.mutex = threading.Lock()
        self.empty = threading.Semaphore(capacity)  # free slots
        self.full = threading.Semaphore(0)          # filled slots
        self.capacity, self.n_workers = capacity, workers
        self.age_after_s, self.aging_interval_s = age_after_s, aging_interval_s
        self.periodic, self.periodic_every_s = periodic, periodic_every_s
        self.jobs = {}                              # evacuee_id -> Job (queued or running)
        self.promotions = self.processed = self.busy = 0
        self._stop = threading.Event()
        self._threads = []

    # ---------- producer side ----------
    def submit(self, evacuee_id, level, block_timeout=0.5):
        with self.mutex:
            if evacuee_id in self.jobs:
                return self.jobs[evacuee_id].future
        if not self.empty.acquire(timeout=block_timeout):
            raise BufferFull("Scheduler buffer is full")
        with self.mutex:
            if evacuee_id in self.jobs:            # another producer queued it meanwhile
                self.empty.release()
                return self.jobs[evacuee_id].future
            job = Job(evacuee_id, level)
            self.jobs[evacuee_id] = job
            self.queues[level].append(job)
        self.full.release()
        return job.future

    # ---------- consumer side ----------
    def _take(self):
        while not self._stop.is_set():
            if self.full.acquire(timeout=0.5):
                with self.mutex:
                    for q in self.queues:           # highest priority first
                        if q:
                            job = q.popleft()
                            break
                    self.busy += 1
                self.empty.release()
                return job
        return None

    def _worker(self):
        while True:
            job = self._take()
            if job is None:
                return
            wait_ms = (time.monotonic() - job.enqueued_at) * 1000
            try:
                result = self.handler(job.evacuee_id, wait_ms)
                if isinstance(result, dict):
                    result.update(queue_wait_ms=round(wait_ms, 1), promoted_levels=job.promoted)
                job.future.set_result(result)
            except Exception as exc:
                job.future.set_exception(exc)
            finally:
                with self.mutex:
                    self.jobs.pop(job.evacuee_id, None)
                    self.busy -= 1
                    self.processed += 1

    # ---------- aging daemon ----------
    def age_once(self, now=None):
        now = time.monotonic() if now is None else now
        moved = 0
        with self.mutex:
            for lvl in (1, 2):
                keep = deque()
                while self.queues[lvl]:
                    job = self.queues[lvl].popleft()
                    if now - job.level_since >= self.age_after_s:
                        job.level, job.level_since = lvl - 1, now
                        job.promoted += 1
                        self.queues[lvl - 1].append(job)
                        moved += 1
                    else:
                        keep.append(job)
                self.queues[lvl] = keep
            self.promotions += moved
        return moved

    def _aging_daemon(self):
        last_periodic = time.monotonic()
        while not self._stop.wait(self.aging_interval_s):
            self.age_once()
            if self.periodic and time.monotonic() - last_periodic >= self.periodic_every_s:
                last_periodic = time.monotonic()
                try:
                    self.periodic()
                except Exception as exc:
                    print("periodic task error:", exc)

    # ---------- lifecycle and inspection ----------
    def start(self):
        self._stop.clear()
        for i in range(self.n_workers):
            t = threading.Thread(target=self._worker, name=f"alloc-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        t = threading.Thread(target=self._aging_daemon, name="aging-daemon", daemon=True)
        t.start()
        self._threads.append(t)

    def stop(self):
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2)
        self._threads.clear()

    def stats(self):
        now = time.monotonic()
        with self.mutex:
            oldest = [round(now - q[0].enqueued_at, 1) if q else 0 for q in self.queues]
            return {"levels": [len(q) for q in self.queues], "level_names": LEVEL_NAMES,
                    "oldest_wait_s": oldest, "promotions": self.promotions, "processed": self.processed,
                    "busy_workers": self.busy, "workers": self.n_workers, "capacity": self.capacity,
                    "age_after_s": self.age_after_s}

    def snapshot(self, limit=50):
        now = time.monotonic()
        with self.mutex:
            out = []
            for lvl, q in enumerate(self.queues):
                for job in list(q)[:limit]:
                    out.append({"evacuee_id": job.evacuee_id, "level": lvl, "base_level": job.base_level,
                                "wait_s": round(now - job.enqueued_at, 1), "promoted": job.promoted})
            return out
