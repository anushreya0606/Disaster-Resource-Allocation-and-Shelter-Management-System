-- Disaster Resource Allocation & Shelter Management System (OSDBMS PBL)
-- Schema Definition with Triggers, Stored Procedures, and Indexes

-- 1. Shelters Table
CREATE TABLE IF NOT EXISTS shelters (
    shelter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    district TEXT NOT NULL,
    state TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    total_beds INTEGER NOT NULL,
    available_beds INTEGER NOT NULL,
    oxygen_cylinders INTEGER DEFAULT 0,
    food_units INTEGER DEFAULT 0,
    transport_units INTEGER DEFAULT 0,
    wheelchair_accessible BOOLEAN DEFAULT 0,
    medical_facility BOOLEAN DEFAULT 1,
    contact_number TEXT,
    status TEXT DEFAULT 'OPEN', -- OPEN, CRITICAL_90, FULL, CLOSED
    version INTEGER DEFAULT 1, -- Optimistic Locking version
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Fast Spatial & Capacity Queries
CREATE INDEX IF NOT EXISTS idx_shelters_district ON shelters(district);
CREATE INDEX IF NOT EXISTS idx_shelters_status ON shelters(status);
CREATE INDEX IF NOT EXISTS idx_shelters_coords ON shelters(latitude, longitude);

-- 2. Evacuees Table (Triage Queue Entities)
CREATE TABLE IF NOT EXISTS evacuees (
    evacuee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL,
    triage_priority INTEGER NOT NULL, -- 0: Medical Critical, 1: Vulnerable (Elderly/Pregnant), 2: General
    medical_conditions TEXT,
    contact_phone TEXT,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    assigned_shelter_id INTEGER,
    status TEXT DEFAULT 'WAITING', -- WAITING, ALLOCATED, REDIRECTED, CANCELLED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(assigned_shelter_id) REFERENCES shelters(shelter_id)
);

CREATE INDEX IF NOT EXISTS idx_evacuees_triage ON evacuees(triage_priority, status);

-- 3. Allocations Log Table (ACID Transaction Audit Trail)
CREATE TABLE IF NOT EXISTS allocations (
    allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    evacuee_id INTEGER NOT NULL,
    shelter_id INTEGER NOT NULL,
    allocated_beds INTEGER DEFAULT 1,
    allocated_oxygen INTEGER DEFAULT 0,
    allocated_food INTEGER DEFAULT 0,
    allocated_transport INTEGER DEFAULT 0,
    allocated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    transaction_hash TEXT NOT NULL, -- Cryptographic SHA-256 Hash Chain
    FOREIGN KEY(evacuee_id) REFERENCES evacuees(evacuee_id),
    FOREIGN KEY(shelter_id) REFERENCES shelters(shelter_id)
);

-- 4. Alert Queue Table (Active DB Trigger Target)
CREATE TABLE IF NOT EXISTS alert_queue (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    shelter_id INTEGER NOT NULL,
    alert_type TEXT NOT NULL, -- CAPACITY_90_PERCENT, CAPACITY_FULL, OUT_OF_OXYGEN
    message TEXT NOT NULL,
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'PENDING',
    FOREIGN KEY(shelter_id) REFERENCES shelters(shelter_id)
);

-- 5. Telemetry Logs Table (OS System Performance Collector)
CREATE TABLE IF NOT EXISTS telemetry_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cpu_percent REAL,
    active_threads INTEGER,
    mutex_contention_count INTEGER,
    avg_lock_wait_ms REAL,
    load_test_rps REAL,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DB Active Trigger 1: Threshold Warning Trigger (Fires when shelter capacity reaches 90% or 100%)
CREATE TRIGGER IF NOT EXISTS trg_shelter_capacity_alert
AFTER UPDATE OF available_beds ON shelters
FOR EACH ROW
WHEN (NEW.available_beds <= (NEW.total_beds * 0.10)) AND (OLD.available_beds > (NEW.total_beds * 0.10))
BEGIN
    INSERT INTO alert_queue (shelter_id, alert_type, message)
    VALUES (
        NEW.shelter_id,
        CASE WHEN NEW.available_beds = 0 THEN 'CAPACITY_FULL' ELSE 'CAPACITY_90_PERCENT' END,
        'WARNING: Shelter ' || NEW.name || ' has reached critical occupancy (' || NEW.available_beds || '/' || NEW.total_beds || ' beds remaining).'
    );
    
    UPDATE shelters SET status = CASE WHEN NEW.available_beds = 0 THEN 'FULL' ELSE 'CRITICAL_90' END
    WHERE shelter_id = NEW.shelter_id;
END;
