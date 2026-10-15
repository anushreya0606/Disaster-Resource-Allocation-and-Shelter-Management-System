"""Create the database and load data/*.csv.   python scripts/seed_data.py [--reset]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import config, seed  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--reset", action="store_true", help="drop all tables and reload (deletes registrations)")
args = ap.parse_args()
print("Seeded" if seed.seed(reset=args.reset) else "Already seeded (use --reset to start over)", "->", config.DB_PATH)
