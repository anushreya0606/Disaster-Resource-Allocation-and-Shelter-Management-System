"""Central settings. Override any of them with environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = os.environ.get("RELIEF_DB", str(DATA_DIR / "relief.db"))

WORKER_THREADS = int(os.environ.get("RELIEF_WORKERS", 8))      # consumer threads in the scheduler
BUFFER_SIZE = int(os.environ.get("RELIEF_BUFFER", 1000))        # bounded buffer capacity
AGING_INTERVAL_S = float(os.environ.get("RELIEF_AGING_INTERVAL", 5))
AGE_AFTER_S = float(os.environ.get("RELIEF_AGE_AFTER", 30))     # wait this long -> promoted one level
RETRY_WAITING_S = float(os.environ.get("RELIEF_RETRY_WAITING", 20))
MAX_ROUTE_KM = float(os.environ.get("RELIEF_MAX_KM", 150))
INTAKE_WAIT_S = float(os.environ.get("RELIEF_INTAKE_WAIT", 5))  # how long an HTTP call waits for a bed decision

SMS_HOST = os.environ.get("RELIEF_SMS_HOST", "127.0.0.1")
SMS_PORT = int(os.environ.get("RELIEF_SMS_PORT", 9999))
ENABLE_SMS = os.environ.get("RELIEF_ENABLE_SMS", "1") == "1"

TELEMETRY_INTERVAL_S = float(os.environ.get("RELIEF_TELEMETRY_INTERVAL", 5))
SESSION_HOURS = 12
