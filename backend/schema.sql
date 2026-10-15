-- Normalised (3NF) schema. available_beds is a counter kept on the shelter row so a single
-- guarded UPDATE can claim a bed; integrity_report() cross-checks it against allocations.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  user_id       INTEGER PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE,
  full_name     TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('ADMIN','VOLUNTEER','SYSTEM')),
  password_hash TEXT NOT NULL,
  salt          TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
  token      TEXT PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS disaster_events (
  event_id      INTEGER PRIMARY KEY,
  event_name    TEXT NOT NULL,
  disaster_type TEXT NOT NULL,
  severity      TEXT NOT NULL,
  state         TEXT NOT NULL,
  start_time    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS districts (
  district_id   INTEGER PRIMARY KEY,
  district_name TEXT NOT NULL,
  state         TEXT NOT NULL,
  hq_latitude   REAL NOT NULL,
  hq_longitude  REAL NOT NULL,
  hilly_terrain INTEGER NOT NULL DEFAULT 0,
  UNIQUE (district_name, state)
);

CREATE TABLE IF NOT EXISTS shelters (
  shelter_id        INTEGER PRIMARY KEY,
  shelter_name      TEXT NOT NULL,
  facility_type     TEXT NOT NULL,
  district_id       INTEGER NOT NULL REFERENCES districts(district_id),
  latitude          REAL NOT NULL,
  longitude         REAL NOT NULL,
  total_beds        INTEGER NOT NULL CHECK (total_beds > 0),
  initial_occupied  INTEGER NOT NULL CHECK (initial_occupied >= 0),
  available_beds    INTEGER NOT NULL,
  has_icu           INTEGER NOT NULL DEFAULT 0,
  has_medical_unit  INTEGER NOT NULL DEFAULT 0,
  wheelchair_ok     INTEGER NOT NULL DEFAULT 0,
  contact_helpline  TEXT,
  status            TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CRITICAL_90','FULL','CLOSED')),
  CHECK (available_beds BETWEEN 0 AND total_beds)          -- last line of defence against overbooking
);
CREATE INDEX IF NOT EXISTS idx_shelters_district ON shelters(district_id);

CREATE TABLE IF NOT EXISTS shelter_inventory (
  shelter_id          INTEGER NOT NULL REFERENCES shelters(shelter_id),
  resource            TEXT NOT NULL,
  unit                TEXT NOT NULL,
  quantity            INTEGER NOT NULL CHECK (quantity >= 0),
  low_stock_threshold INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (shelter_id, resource)
);

CREATE TABLE IF NOT EXISTS evacuees (
  evacuee_id        INTEGER PRIMARY KEY,
  client_request_id TEXT UNIQUE,            -- idempotency key from the device (offline sync safe)
  external_ref      TEXT UNIQUE,            -- ID card / dataset id; blocks duplicate check-ins
  full_name         TEXT NOT NULL,
  age               INTEGER CHECK (age BETWEEN 0 AND 120),
  sex               TEXT CHECK (sex IN ('F','M','O')),
  pregnant          INTEGER NOT NULL DEFAULT 0,
  injury_severity   TEXT NOT NULL CHECK (injury_severity IN ('none','minor','serious','critical')),
  unconscious       INTEGER NOT NULL DEFAULT 0,
  needs_oxygen      INTEGER NOT NULL DEFAULT 0,
  uses_wheelchair   INTEGER NOT NULL DEFAULT 0,
  latitude          REAL NOT NULL,
  longitude         REAL NOT NULL,
  priority          INTEGER NOT NULL CHECK (priority IN (0,1,2)),
  triage_reasons    TEXT NOT NULL DEFAULT '',
  status            TEXT NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','ALLOCATED','WAITING','DISCHARGED')),
  shelter_id        INTEGER REFERENCES shelters(shelter_id),
  registered_by     INTEGER REFERENCES users(user_id),
  source            TEXT NOT NULL DEFAULT 'WEB',
  created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now')),
  allocated_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_evacuees_status ON evacuees(status);
CREATE INDEX IF NOT EXISTS idx_evacuees_name ON evacuees(full_name, age);

CREATE TABLE IF NOT EXISTS allocations (
  allocation_id  INTEGER PRIMARY KEY,
  evacuee_id     INTEGER NOT NULL REFERENCES evacuees(evacuee_id),
  shelter_id     INTEGER NOT NULL REFERENCES shelters(shelter_id),
  action         TEXT NOT NULL CHECK (action IN ('ALLOCATE','DISCHARGE')),
  distance_km    REAL,
  was_fallback   INTEGER NOT NULL DEFAULT 0,
  priority       INTEGER,
  queue_wait_ms  REAL,
  created_at     TEXT NOT NULL,
  prev_hash      TEXT NOT NULL,
  hash           TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS alert_queue (
  alert_id     INTEGER PRIMARY KEY,
  shelter_id   INTEGER REFERENCES shelters(shelter_id),
  alert_type   TEXT NOT NULL,
  message      TEXT NOT NULL,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  acknowledged INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS telemetry_logs (
  log_id            INTEGER PRIMARY KEY,
  ts                TEXT NOT NULL DEFAULT (datetime('now')),
  active_threads    INTEGER,
  queue_p0          INTEGER, queue_p1 INTEGER, queue_p2 INTEGER,
  promotions        INTEGER,
  lock_wait_avg_ms  REAL, lock_wait_max_ms REAL,
  allocations       INTEGER
);

-- Banker's algorithm: reusable equipment loaned from each state depot to shelters
CREATE TABLE IF NOT EXISTS depot_stock (
  state     TEXT NOT NULL,
  resource  TEXT NOT NULL,
  available INTEGER NOT NULL CHECK (available >= 0),
  PRIMARY KEY (state, resource)
);
CREATE TABLE IF NOT EXISTS resupply_claims (
  shelter_id INTEGER NOT NULL REFERENCES shelters(shelter_id),
  resource   TEXT NOT NULL,
  max_claim  INTEGER NOT NULL CHECK (max_claim >= 0),
  allocated  INTEGER NOT NULL CHECK (allocated >= 0),
  PRIMARY KEY (shelter_id, resource),
  CHECK (allocated <= max_claim)
);

-- ---------- Active triggers: capacity alerts and status ----------
CREATE TRIGGER IF NOT EXISTS trg_capacity_90
AFTER UPDATE OF available_beds ON shelters
WHEN (NEW.total_beds - NEW.available_beds) * 10 >= NEW.total_beds * 9
 AND (OLD.total_beds - OLD.available_beds) * 10 <  OLD.total_beds * 9
 AND NEW.available_beds > 0
BEGIN
  INSERT INTO alert_queue (shelter_id, alert_type, message)
  VALUES (NEW.shelter_id, 'CAPACITY_90', NEW.shelter_name || ' has reached 90% occupancy');
  UPDATE shelters SET status = 'CRITICAL_90' WHERE shelter_id = NEW.shelter_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_capacity_full
AFTER UPDATE OF available_beds ON shelters
WHEN NEW.available_beds = 0 AND OLD.available_beds > 0
BEGIN
  INSERT INTO alert_queue (shelter_id, alert_type, message)
  VALUES (NEW.shelter_id, 'FULL', NEW.shelter_name || ' is full; new arrivals are routed elsewhere');
  UPDATE shelters SET status = 'FULL' WHERE shelter_id = NEW.shelter_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_capacity_reopen
AFTER UPDATE OF available_beds ON shelters
WHEN NEW.available_beds > OLD.available_beds AND NEW.status <> 'CLOSED'
BEGIN
  UPDATE shelters SET status =
    CASE WHEN (NEW.total_beds - NEW.available_beds) * 10 >= NEW.total_beds * 9 THEN 'CRITICAL_90' ELSE 'OPEN' END
  WHERE shelter_id = NEW.shelter_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_low_stock
AFTER UPDATE OF quantity ON shelter_inventory
WHEN NEW.quantity < NEW.low_stock_threshold AND OLD.quantity >= OLD.low_stock_threshold
BEGIN
  INSERT INTO alert_queue (shelter_id, alert_type, message)
  VALUES (NEW.shelter_id, 'LOW_STOCK',
          'Low ' || replace(NEW.resource, '_', ' ') || ': ' || NEW.quantity || ' ' || NEW.unit || ' left');
END;
