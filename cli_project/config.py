"""Configuration file for the CLI Project.

All constants are placed here so they can be changed quickly on the spot
if an evaluator or teacher asks you to adjust timings, capacities, or ports.
"""
from pathlib import Path

# Base directory for the CLI project
BASE_DIR = Path(__file__).resolve().parent

# Database file location (stored inside cli_project/ so it is completely self-contained)
DB_PATH = BASE_DIR / "cli_relief.db"

# OS MLFQ Scheduler Timers (IN SECONDS)
# [ON-THE-SPOT TIP]: If your mentor asks to change the aging time, change AGING_THRESHOLD_SECONDS here!
AGING_THRESHOLD_SECONDS = 8    # How long a task waits in Queue 2 before being promoted to Queue 1
AGING_CHECK_INTERVAL = 2       # How frequently the background aging thread wakes up to check
WORKER_THREAD_COUNT = 3        # Number of concurrent worker threads processing the MLFQ queue

# Emergency TCP Socket Port for Offline SMS
# [ON-THE-SPOT TIP]: If port 9999 is blocked, change it here to 9998 or 8888
SOCKET_HOST = "127.0.0.1"
SOCKET_PORT = 9999

# Earth Radius for Haversine Distance (Kilometers)
EARTH_RADIUS_KM = 6371.0
