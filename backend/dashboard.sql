-- Ishani: dashboard queries for disaster_management (SQLite)
-- Run after schema.sql and views.sql. Each SELECT is an independent dashboard panel.

-- 1. Overall operational summary: shelters, beds, evacuees, allocations, pending alerts.
SELECT
    (SELECT COUNT(*) FROM shelters) AS total_shelters,
    (SELECT COUNT(*) FROM shelters WHERE status NOT IN ('CLOSED')) AS operational_shelters,
    (SELECT COALESCE(SUM(total_beds), 0) FROM shelters WHERE status <> 'CLOSED') AS total_operational_beds,
    (SELECT COALESCE(SUM(total_beds - available_beds), 0) FROM shelters WHERE status <> 'CLOSED') AS occupied_operational_beds,
    (SELECT COALESCE(SUM(available_beds), 0) FROM shelters WHERE status <> 'CLOSED') AS available_operational_beds,
    (SELECT COUNT(*) FROM evacuees WHERE status = 'WAITING') AS waiting_evacuees,
    (SELECT COUNT(*) FROM evacuees WHERE status = 'ALLOCATED') AS allocated_evacuees,
    (SELECT COUNT(*) FROM allocations) AS total_allocation_records,
    (SELECT COUNT(*) FROM alert_queue WHERE status = 'PENDING') AS pending_alerts;

-- 2. Shelter capacity and resource status, most occupied first.
SELECT *
FROM vw_shelter_status
ORDER BY occupancy_percent DESC, available_beds ASC, shelter_name;

-- 3. Evacuee queue, medical critical and vulnerable cases first.
SELECT
    evacuee_id, full_name, age, gender, priority_label, medical_conditions,
    evacuee_status, registered_at, shelter_name, district, state
FROM vw_evacuee_status
WHERE evacuee_status IN ('WAITING', 'REDIRECTED')
ORDER BY triage_priority ASC, registered_at ASC;

-- 4. Shelter demand by district and state.
SELECT
    district,
    state,
    COUNT(*) AS evacuee_count,
    SUM(CASE WHEN status = 'WAITING' THEN 1 ELSE 0 END) AS waiting_count,
    SUM(CASE WHEN status = 'ALLOCATED' THEN 1 ELSE 0 END) AS allocated_count,
    SUM(CASE WHEN status = 'REDIRECTED' THEN 1 ELSE 0 END) AS redirected_count
FROM evacuees
GROUP BY district, state
ORDER BY waiting_count DESC, evacuee_count DESC, state, district;

-- 5. Allocation activity by shelter.
SELECT
    shelter_id,
    shelter_name,
    district,
    state,
    COUNT(*) AS allocation_count,
    COALESCE(SUM(allocated_beds), 0) AS beds_allocated,
    COALESCE(SUM(allocated_oxygen), 0) AS oxygen_allocated,
    COALESCE(SUM(allocated_food), 0) AS food_allocated,
    COALESCE(SUM(allocated_transport), 0) AS transport_allocated
FROM vw_allocation_history
GROUP BY shelter_id, shelter_name, district, state
ORDER BY allocation_count DESC, shelter_name;

-- 6. Recent allocation transactions (last 50).
SELECT *
FROM vw_allocation_history
ORDER BY allocated_at DESC, allocation_id DESC
LIMIT 50;

-- 7. Pending alerts, highest operational urgency first.
SELECT
    alert_id, shelter_id, shelter_name, district, state,
    alert_type, message, triggered_at
FROM vw_alert_status
WHERE alert_status = 'PENDING'
ORDER BY
    CASE alert_type
        WHEN 'CAPACITY_FULL' THEN 1
        WHEN 'OUT_OF_OXYGEN' THEN 2
        WHEN 'CAPACITY_90_PERCENT' THEN 3
        ELSE 4
    END,
    triggered_at ASC;

-- 8. Shelters needing attention: near-full, full, closed, or low resources.
SELECT
    shelter_id, shelter_name, district, state, shelter_status,
    occupancy_percent, available_beds, oxygen_cylinders, food_units,
    transport_units
FROM vw_shelter_status
WHERE shelter_status IN ('CRITICAL_90', 'FULL', 'CLOSED')
   OR oxygen_cylinders <= 0
   OR available_beds = 0
ORDER BY
    CASE shelter_status
        WHEN 'FULL' THEN 1
        WHEN 'CRITICAL_90' THEN 2
        WHEN 'CLOSED' THEN 3
        ELSE 4
    END,
    occupancy_percent DESC;

-- 9. Hourly allocation trend for the last 24 hours.
SELECT
    strftime('%Y-%m-%d %H:00:00', allocated_at) AS hour_bucket,
    COUNT(*) AS allocation_count,
    COALESCE(SUM(allocated_beds), 0) AS beds_allocated
FROM allocations
WHERE allocated_at >= datetime('now', '-24 hours')
GROUP BY hour_bucket
ORDER BY hour_bucket;

-- 10. System load-test and database telemetry trend.
SELECT
    logged_at,
    cpu_percent,
    active_threads,
    mutex_contention_count,
    avg_lock_wait_ms,
    load_test_rps
FROM telemetry_logs
ORDER BY logged_at DESC, log_id DESC
LIMIT 100;

-- 11. Load-test summary (null when no telemetry has been recorded).
SELECT
    COUNT(*) AS sample_count,
    ROUND(AVG(cpu_percent), 2) AS avg_cpu_percent,
    MAX(cpu_percent) AS max_cpu_percent,
    ROUND(AVG(active_threads), 2) AS avg_active_threads,
    MAX(mutex_contention_count) AS max_mutex_contention,
    ROUND(AVG(avg_lock_wait_ms), 2) AS avg_lock_wait_ms,
    ROUND(AVG(load_test_rps), 2) AS avg_load_test_rps,
    MAX(load_test_rps) AS peak_load_test_rps
FROM telemetry_logs;
