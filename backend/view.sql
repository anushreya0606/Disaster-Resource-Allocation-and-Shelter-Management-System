-- Ishani: reusable reporting views for disaster_management (SQLite)
-- Matches backend/schema.sql in the project brief.

-- Current shelter occupancy, capacity, and remaining resource stock.
CREATE VIEW IF NOT EXISTS vw_shelter_status AS
SELECT
    s.shelter_id,
    s.name AS shelter_name,
    s.district,
    s.state,
    s.status AS shelter_status,
    s.total_beds,
    s.available_beds,
    (s.total_beds - s.available_beds) AS occupied_beds,
    CASE WHEN s.total_beds > 0
         THEN ROUND(100.0 * (s.total_beds - s.available_beds) / s.total_beds, 2)
         ELSE 0 END AS occupancy_percent,
    s.oxygen_cylinders,
    s.food_units,
    s.transport_units,
    s.wheelchair_accessible,
    s.medical_facility,
    s.contact_number,
    s.latitude,
    s.longitude
FROM shelters AS s;

-- Evacuee queue enriched with assigned shelter details (if assigned).
CREATE VIEW IF NOT EXISTS vw_evacuee_status AS
SELECT
    e.evacuee_id,
    e.full_name,
    e.age,
    e.gender,
    e.triage_priority,
    CASE e.triage_priority
        WHEN 0 THEN 'MEDICAL_CRITICAL'
        WHEN 1 THEN 'VULNERABLE'
        WHEN 2 THEN 'GENERAL'
        ELSE 'UNSPECIFIED'
    END AS priority_label,
    e.medical_conditions,
    e.contact_phone,
    e.status AS evacuee_status,
    e.created_at AS registered_at,
    e.assigned_shelter_id AS shelter_id,
    s.name AS shelter_name,
    s.district,
    s.state
FROM evacuees AS e
LEFT JOIN shelters AS s
    ON s.shelter_id = e.assigned_shelter_id;

-- Allocation history with evacuee and shelter names.
CREATE VIEW IF NOT EXISTS vw_allocation_history AS
SELECT
    a.allocation_id,
    a.evacuee_id,
    e.full_name AS evacuee_name,
    e.triage_priority,
    a.shelter_id,
    s.name AS shelter_name,
    s.district,
    s.state,
    a.allocated_beds,
    a.allocated_oxygen,
    a.allocated_food,
    a.allocated_transport,
    a.allocated_at,
    a.transaction_hash
FROM allocations AS a
JOIN evacuees AS e ON e.evacuee_id = a.evacuee_id
JOIN shelters AS s ON s.shelter_id = a.shelter_id;

-- Active and historical alert queue entries with shelter context.
CREATE VIEW IF NOT EXISTS vw_alert_status AS
SELECT
    q.alert_id,
    q.shelter_id,
    s.name AS shelter_name,
    s.district,
    s.state,
    q.alert_type,
    q.message,
    q.status AS alert_status,
    q.triggered_at
FROM alert_queue AS q
JOIN shelters AS s ON s.shelter_id = q.shelter_id;
