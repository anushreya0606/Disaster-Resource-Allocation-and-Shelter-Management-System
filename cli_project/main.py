"""Interactive Command-Line Interface (CLI) for OSDBMS Disaster Management System.

Usage:
  Interactive Menu:
    python main.py
    
  One-line Commands:
    python main.py --shelters
    python main.py --stress-test
    python main.py --bankers
    python main.py --verify-audit
    python main.py --sms-test
"""
import argparse
import sys
import time

# Ensure UTF-8 output on Windows terminal without crashing on cp1252
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from .bankers import BankersAlgorithm, RESOURCE_NAMES, SHELTER_NAMES
    from .database import (
        calculate_sha256,
        get_connection,
        init_database,
    )
    from .scheduler import MLFQScheduler, Task, calculate_triage_priority
    from .sms_server import SMSSocketServer, send_test_sms
    from .stress_test import run_concurrency_stress_test
except ImportError:
    from bankers import BankersAlgorithm, RESOURCE_NAMES, SHELTER_NAMES
    from database import (
        calculate_sha256,
        get_connection,
        init_database,
    )
    from scheduler import MLFQScheduler, Task, calculate_triage_priority
    from sms_server import SMSSocketServer, send_test_sms
    from stress_test import run_concurrency_stress_test


def print_banner():
    banner = r"""
================================================================================
  [!] DISASTER RESOURCE ALLOCATION & SHELTER MANAGEMENT (OSDBMS CLI)
  Team ID: OSDBMS-V-2026-T135 | Graphic Era (Deemed to be University)
  Operating Systems & Database Management Systems Applied Systems Laboratory
================================================================================
"""
    print(banner)


def show_shelters():
    """Displays all shelters with formatted ASCII progress bars."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT shelter_id, name, district, total_beds, available_beds, has_icu, status
    FROM shelters
    ORDER BY shelter_id ASC;
    """)
    rows = cur.fetchall()
    conn.close()

    print("\n" + "=" * 80)
    print(" [*] SHELTER DIRECTORY & REAL-TIME CAPACITY STATUS")
    print("=" * 80)
    print(f" {'ID':<3} | {'Shelter Name':<25} | {'District':<12} | {'Occupancy Bar':<20} | {'Status':<10}")
    print("-" * 80)

    for r in rows:
        tot = r["total_beds"]
        avail = r["available_beds"]
        occ = tot - avail
        pct = (occ / tot) if tot > 0 else 0
        bars = int(pct * 15)
        bar_str = "[" + "#" * bars + "-" * (15 - bars) + f"] {int(pct*100)}%"
        print(f" {r['shelter_id']:<3} | {r['name']:<25} | {r['district']:<12} | {bar_str:<20} | {r['status']:<10}")
    print("=" * 80 + "\n")


def show_evacuees():
    """Displays recently registered evacuees and their allocation status."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT e.evacuee_id, e.name, e.age, e.injury_severity, e.priority, e.status, s.name AS shelter_name
    FROM evacuees e
    LEFT JOIN shelters s ON e.shelter_id = s.shelter_id
    ORDER BY e.evacuee_id DESC
    LIMIT 15;
    """)
    rows = cur.fetchall()
    conn.close()

    print("\n" + "=" * 85)
    print(" [+] RECENT EVACUEES DIRECTORY (Latest 15)")
    print("=" * 85)
    print(f" {'ID':<4} | {'Name':<20} | {'Age':<4} | {'Injury':<10} | {'Priority':<8} | {'Status':<10} | {'Assigned Shelter'}")
    print("-" * 85)
    for r in rows:
        p_label = f"P{r['priority']} (" + ("Critical" if r['priority']==0 else ("Vulnerable" if r['priority']==1 else "Standard")) + ")"
        s_name = r['shelter_name'] if r['shelter_name'] else "Awaiting Bed..."
        print(f" {r['evacuee_id']:<4} | {r['name']:<20} | {r['age']:<4} | {r['injury_severity']:<10} | {p_label:<14} | {r['status']:<10} | {s_name}")
    print("=" * 85 + "\n")


def register_evacuee_interactive(scheduler: MLFQScheduler):
    """Guides user through manual evacuee admission with priority triage."""
    print("\n" + "-" * 50)
    print(" [!] MANUAL EVACUEE INTAKE & MEDICAL TRIAGE")
    print("-" * 50)
    name = input(" Enter Evacuee Full Name: ").strip()
    if not name:
        name = "Anonymous Evacuee"

    try:
        age = int(input(" Enter Age (0-120): ").strip())
    except ValueError:
        age = 30

    sex = input(" Enter Sex (M/F/O) [default M]: ").strip().upper() or "M"
    print(" Injury Severity Levels: none | minor | serious | critical")
    injury = input(" Enter Injury Severity: ").strip().lower() or "none"
    if injury not in ("none", "minor", "serious", "critical"):
        injury = "none"

    preg = False
    if sex == "F":
        preg_ans = input(" Is evacuee pregnant? (y/n) [default n]: ").strip().lower()
        preg = (preg_ans == "y")

    priority = calculate_triage_priority(age, injury, preg)
    p_names = {0: "Queue 0 (Critical Medical)", 1: "Queue 1 (Vulnerable Population)", 2: "Queue 2 (Standard Evacuee)"}

    print(f"\n [*] TRIAGE EVALUATION RESULT: Assigned to {p_names[priority]}")

    # Use default Kerala GPS coordinates for shelter matching
    lat, lon = 10.1076, 76.3516

    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO evacuees (name, age, sex, injury_severity, priority, latitude, longitude, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'QUEUED');
        """, (name, age, sex, injury, priority, lat, lon))
        evacuee_id = cur.lastrowid
    conn.close()

    task = Task(evacuee_id=evacuee_id, name=name, age=age, priority=priority, latitude=lat, longitude=lon)
    scheduler.submit_task(task)
    print(f" [OK] Evacuee #{evacuee_id} submitted to MLFQ Scheduler. Dispatching in background...\n")
    time.sleep(1)


def inspect_mlfq(scheduler: MLFQScheduler):
    """Prints live status of MLFQ Priority queues and dynamic aging metrics."""
    status = scheduler.get_queue_status()
    print("\n" + "=" * 60)
    print(" [*] OPERATING SYSTEM MLFQ QUEUE STATUS & AGING MONITOR")
    print("=" * 60)
    print(f" [Q0] Queue 0 (Critical Medical):     {status['Q0_Critical']} waiting")
    print(f" [Q1] Queue 1 (Vulnerable Groups):    {status['Q1_Vulnerable']} waiting")
    print(f" [Q2] Queue 2 (Standard Evacuees):    {status['Q2_Standard']} waiting")
    print("-" * 60)
    print(f" [AGING] Total Dynamic Aging Promotions: {status['Total_Promotions']}")
    print(f" [DONE]  Total Allocations Processed:    {status['Total_Processed']}")
    print("=" * 60)
    print(" [NOTE]: The background Aging Daemon checks Q2 every 2s.")
    print(" Any task waiting > 8s is promoted to Q1 to prevent starvation!\n")


def run_bankers_demo():
    """Runs a complete Dijkstra's Banker's algorithm safe sequence check."""
    banker = BankersAlgorithm()
    need = banker.get_need_matrix()

    print("\n" + "=" * 70)
    print(" [*] DIJKSTRA'S BANKER'S ALGORITHM (DEADLOCK AVOIDANCE)")
    print("=" * 70)
    print(" Resources Tracked: " + ", ".join(RESOURCE_NAMES))
    print(f" Available Vector (A): {banker.available}\n")

    print(f" {'Shelter':<22} | {'Max Claim (M)':<16} | {'Allocated (A)':<16} | {'Need (M-A)'}")
    print("-" * 70)
    for i in range(len(SHELTER_NAMES)):
        print(f" {SHELTER_NAMES[i]:<22} | {str(banker.max_claim[i]):<16} | {str(banker.allocated[i]):<16} | {str(need[i])}")
    print("-" * 70)

    is_safe, seq, trace = banker.is_safe_state()
    print("\n [*] STEP-BY-STEP SAFETY TRACE:")
    for step in trace:
        print("  " + step)

    if is_safe:
        print("\n [OK] RESULT: SYSTEM IS IN A SAFE STATE! No Deadlock.")
        print(" [*] Safe Execution Sequence: " + " -> ".join(seq))
    else:
        print("\n [WARN] RESULT: SYSTEM IS IN AN UNSAFE STATE! Deadlock possible.")
    print("=" * 70 + "\n")


def verify_cryptographic_audit():
    """Validates the continuous SHA-256 hash chain of the allocations table."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT allocation_id, evacuee_id, shelter_id, allocated_at, prev_hash, hash
    FROM allocations
    ORDER BY allocation_id ASC;
    """)
    records = cur.fetchall()
    conn.close()

    print("\n" + "=" * 75)
    print(" [*] CRYPTOGRAPHIC SHA-256 AUDIT CHAIN VERIFICATION")
    print("=" * 75)

    if not records:
        print(" (No allocation records found in ledger yet. Admit an evacuee first!)\n")
        return

    expected_prev = "GENESIS_BLOCK_00000000000000000000000000000000"
    broken = False

    for r in records:
        alloc_id = r["allocation_id"]
        actual_prev = r["prev_hash"]
        actual_hash = r["hash"]

        # Recalculate hash
        recalc = calculate_sha256(actual_prev, r["evacuee_id"], r["shelter_id"], r["allocated_at"])

        if actual_prev != expected_prev or recalc != actual_hash:
            print(f" [FAIL] TAMPERING DETECTED AT BLOCK #{alloc_id}!")
            print(f"    Expected Prev: {expected_prev}")
            print(f"    Actual Prev:   {actual_prev}")
            broken = True
            break
        else:
            print(f" [Block #{alloc_id:03d}] Valid: {actual_hash[:16]}... (Prev: {actual_prev[:8]}...)")

        expected_prev = actual_hash

    print("-" * 75)
    if not broken:
        print(f" [OK] AUDIT VERIFIED: All {len(records)} blocks in the cryptographic chain are 100% VALID!")
    print("=" * 75 + "\n")


def show_alerts():
    """Displays active alerts populated by SQL database triggers."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
    SELECT alert_id, alert_type, message, created_at
    FROM alert_queue
    ORDER BY alert_id DESC
    LIMIT 10;
    """)
    alerts = cur.fetchall()
    conn.close()

    print("\n" + "=" * 75)
    print(" [!] ACTIVE DATABASE TRIGGER ALERTS (Automated Event Queue)")
    print("=" * 75)
    if not alerts:
        print(" (No trigger alerts recorded yet. Reduce shelter beds to trigger 90% or Full alerts!)")
    else:
        for a in alerts:
            print(f" [{a['created_at']}] [{a['alert_type']}] {a['message']}")
    print("=" * 75 + "\n")


def test_sms_socket():
    """Simulates sending an offline SMS to the TCP Socket Daemon."""
    print("\n" + "-" * 55)
    print(" [*] SIMULATING OFFLINE EMERGENCY SMS OVER TCP (PORT 9999)")
    print("-" * 55)
    payload = "NAME:Deepak_Sharma,AGE:68,SEX:M,INJURY:serious,LAT:10.10,LON:76.35"
    print(f" Sending Raw Packet: '{payload}'")
    resp = send_test_sms(payload)
    print(f" Received Daemon Response: {resp}\n")


def interactive_menu():
    """Main CLI Menu Loop."""
    init_database()

    scheduler = MLFQScheduler()
    scheduler.start()

    sms_daemon = SMSSocketServer(scheduler)
    try:
        sms_daemon.start()
    except Exception as e:
        print(f" [Warning] SMS Daemon could not bind: {e}")

    try:
        while True:
            print_banner()
            print(" [1] Evacuee Intake & Medical Triage (P0 / P1 / P2 Scoring)")
            print(" [2] Shelter Directory & Real-Time Capacity (ASCII Progress Bars)")
            print(" [3] View Evacuees Registry")
            print(" [4] MLFQ Scheduler Queue Status & Aging Monitor")
            print(" [5] Banker's Algorithm Deadlock Check (Available/Max/Need Matrices)")
            print(" [6] Concurrency Load Stress Test (Pessimistic Locking Demo)")
            print(" [7] Verify Cryptographic SHA-256 Audit Chain")
            print(" [8] Send Test Offline SMS to TCP Socket Stream (Port 9999)")
            print(" [9] View Active Database Trigger Alerts (90% / Full / Stock)")
            print(" [0] Exit")
            print("=" * 80)

            choice = input(" Select an option (0-9): ").strip()

            if choice == "1":
                register_evacuee_interactive(scheduler)
            elif choice == "2":
                show_shelters()
            elif choice == "3":
                show_evacuees()
            elif choice == "4":
                inspect_mlfq(scheduler)
            elif choice == "5":
                run_bankers_demo()
            elif choice == "6":
                run_concurrency_stress_test(num_threads=50, initial_beds=5)
            elif choice == "7":
                verify_cryptographic_audit()
            elif choice == "8":
                test_sms_socket()
            elif choice == "9":
                show_alerts()
            elif choice == "0":
                print("\n [*] Shutting down CLI services cleanly. Goodbye!\n")
                break
            else:
                print("\n [!] Invalid option. Please enter a number between 0 and 9.\n")

            input(" Press [Enter] to return to menu...")
    finally:
        scheduler.stop()
        sms_daemon.stop()


def main():
    parser = argparse.ArgumentParser(description="OSDBMS Disaster Resource Allocation CLI Project")
    parser.add_argument("--shelters", action="store_true", help="Print shelter capacity list")
    parser.add_argument("--stress-test", action="store_true", dest="stress_test", help="Run 50-thread pessimistic lock concurrency test")
    parser.add_argument("--bankers", action="store_true", help="Run Dijkstra's Banker's deadlock safety algorithm")
    parser.add_argument("--verify-audit", action="store_true", dest="verify_audit", help="Verify SHA-256 cryptographic audit chain")
    parser.add_argument("--sms-test", action="store_true", dest="sms_test", help="Send a test offline SMS over TCP socket")

    args = parser.parse_args()

    # If flags were passed, run that specific task directly
    if args.shelters:
        init_database()
        show_shelters()
    elif args.stress_test:
        init_database()
        run_concurrency_stress_test()
    elif args.bankers:
        run_bankers_demo()
    elif args.verify_audit:
        init_database()
        verify_cryptographic_audit()
    elif args.sms_test:
        test_sms_socket()
    else:
        # Default: Launch interactive menu
        interactive_menu()


if __name__ == "__main__":
    main()
