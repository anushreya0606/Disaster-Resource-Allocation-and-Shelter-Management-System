/**
 * Disaster Resource Allocation & Shelter Management System
 * Frontend Client JavaScript & GIS Map Controller
 * Module Lead: Akanchha Singh (24012753)
 */
let map;
let shelterMarkers = [];
let spatialCircles = [];

document.addEventListener("DOMContentLoaded", () => {
    initLeafletMap();
    fetchShelters();
    fetchKeralaDataset();
    startPolling();
});

function initLeafletMap() {
    // Center map around Kerala / South India coordinates
    map = L.map('map').setView([10.1004, 76.3570], 9);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap contributors | Graphic Era OSDBMS Project'
    }).addTo(map);
}

async function fetchShelters() {
    try {
        const resp = await fetch('/api/shelters');
        const data = await resp.json();
        const shelters = data.shelters || [];
        
        document.getElementById('shelter-count-label').innerText = `${shelters.length} Active Indian Shelters`;
        
        // Populate Benchmark Select Dropdown
        const select = document.getElementById('benchmark-shelter-select');
        select.innerHTML = '';
        
        // Clear existing markers
        shelterMarkers.forEach(m => map.removeLayer(m));
        spatialCircles.forEach(c => map.removeLayer(c));
        shelterMarkers = [];
        spatialCircles = [];

        shelters.forEach(s => {
            // Add option to dropdown
            const opt = document.createElement('option');
            opt.value = s.shelter_id;
            opt.innerText = `${s.name} (${s.available_beds}/${s.total_beds} beds free)`;
            select.appendChild(opt);

            // Determine Marker Color based on Status
            let markerColor = 'green';
            if (s.status === 'CRITICAL_90' || s.occupancy_percent >= 90) markerColor = 'orange';
            if (s.status === 'FULL' || s.available_beds === 0) markerColor = 'red';

            const customIcon = L.divIcon({
                className: 'custom-div-icon',
                html: `<div style="background-color:${markerColor}; width:16px; height:16px; border-radius:50%; border:2px solid white; box-shadow:0 0 6px rgba(0,0,0,0.5);"></div>`,
                iconSize: [16, 16],
                iconAnchor: [8, 8]
            });

            const marker = L.marker([s.latitude, s.longitude], { icon: customIcon }).addTo(map);
            
            const popupContent = `
                <div style="font-family:sans-serif; font-size:0.85rem; color:#1e293b;">
                    <b style="color:#1e3a8a;">${s.name}</b><br/>
                    <b>District:</b> ${s.district}, ${s.state}<br/>
                    <b>Beds Free:</b> <span style="color:${markerColor === 'red' ? 'red' : 'green'}; font-weight:bold;">${s.available_beds} / ${s.total_beds}</span> (${s.occupancy_percent}% full)<br/>
                    <b>Oxygen Cylinders:</b> ${s.oxygen_cylinders}<br/>
                    <b>Food Units:</b> ${s.food_units}<br/>
                    <b>Contact:</b> ${s.contact_number || 'N/A'}<br/>
                    <button style="margin-top:6px; background:#2563eb; color:white; border:none; padding:4px 8px; border-radius:4px; cursor:pointer;" onclick="allocateDirectly(${s.shelter_id})">
                        Allocate Bed Now
                    </button>
                </div>
            `;
            marker.bindPopup(popupContent);
            shelterMarkers.push(marker);

            // Add 5km Spatial Proximity Buffer Radius Circle
            const circle = L.circle([s.latitude, s.longitude], {
                color: markerColor,
                fillColor: markerColor,
                fillOpacity: 0.08,
                radius: 5000 // 5km radius
            }).addTo(map);
            spatialCircles.push(circle);
        });
    } catch (err) {
        console.error("Error fetching shelters:", err);
    }
}

async function fetchKeralaDataset() {
    try {
        const resp = await fetch('/api/kerala_floods_data');
        const data = await resp.json();
        const records = data.kerala_floods_2018 || [];
        const tbody = document.querySelector('#kerala-dataset-table tbody');
        tbody.innerHTML = '';

        records.forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><b>${r.district}</b></td>
                <td>${r.rainfall_mm} mm</td>
                <td><span class="badge ${r.flood_severity === 'CRITICAL' || r.flood_severity === 'EXTREME' ? 'badge-full' : 'badge-critical'}">${r.flood_severity}</span></td>
                <td>${r.evacuated_population.toLocaleString()}</td>
                <td>${r.relief_camps_opened}</td>
                <td>${r.casualties}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error fetching Kerala dataset:", err);
    }
}

function startPolling() {
    setInterval(updateTelemetryAndQueue, 2000);
}

async function updateTelemetryAndQueue() {
    try {
        // 1. Fetch Telemetry
        const telResp = await fetch('/api/telemetry');
        const telData = await telResp.json();
        const tel = telData.telemetry || {};

        document.getElementById('stat-threads').innerText = tel.active_threads || 0;
        document.getElementById('stat-contentions').innerText = tel.mutex_contention_count || 0;
        document.getElementById('stat-wait').innerText = tel.avg_lock_wait_ms || '0.0';
        document.getElementById('stat-rps').innerText = tel.current_rps || '0.0';

        // 2. Fetch OS MLFQ Queue Snapshot
        const qResp = await fetch('/api/scheduler/queue');
        const qData = await qResp.json();

        document.getElementById('q0-count').innerText = qData.q0_count || 0;
        document.getElementById('q1-count').innerText = qData.q1_count || 0;
        document.getElementById('q2-count').innerText = qData.q2_count || 0;

        renderQueueList('q0-list', qData.active_processes.filter(p => p.priority === 0));
        renderQueueList('q1-list', qData.active_processes.filter(p => p.priority === 1));
        renderQueueList('q2-list', qData.active_processes.filter(p => p.priority === 2));
    } catch (err) {
        console.error("Telemetry update error:", err);
    }
}

function renderQueueList(elementId, processes) {
    const container = document.getElementById(elementId);
    container.innerHTML = '';
    if (processes.length === 0) {
        container.innerHTML = '<div style="font-size:0.75rem; color:var(--text-muted); margin-top:4px;">No active processes</div>';
        return;
    }
    processes.forEach(p => {
        const pill = document.createElement('div');
        pill.className = 'evacuee-pill';
        pill.innerHTML = `
            <div>
                <b>${p.name}</b> (Age: ${p.age_years})<br/>
                <span style="font-size:0.75rem; color:var(--text-muted);">${p.medical_notes || 'General Evacuee'}</span>
            </div>
            <div style="text-align:right;">
                <span class="badge ${p.aging_boosted ? 'badge-critical' : 'badge-open'}">${p.aging_boosted ? 'AGED PROMOTED' : 'WAIT ' + p.wait_time_sec + 's'}</span>
            </div>
        `;
        container.appendChild(pill);
    });
}

async function handleEvacueeRegistration(event) {
    event.preventDefault();
    const payload = {
        full_name: document.getElementById('reg-name').value,
        age: parseInt(document.getElementById('reg-age').value),
        gender: 'UNSPECIFIED',
        triage_priority: parseInt(document.getElementById('reg-priority').value),
        medical_conditions: document.getElementById('reg-medical').value || "None",
        latitude: parseFloat(document.getElementById('reg-lat').value),
        longitude: parseFloat(document.getElementById('reg-lon').value)
    };

    try {
        const resp = await fetch('/api/evacuees/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const res = await resp.json();
        if (res.success) {
            alert(`✅ Evacuee Registered & Enqueued into OS Scheduler! (ID: ${res.evacuee_id})`);
            document.getElementById('reg-name').value = '';
            document.getElementById('reg-medical').value = '';
            fetchShelters();
        }
    } catch (err) {
        alert("Registration error: " + err);
    }
}

async function runConcurrencyBenchmark() {
    const shelterId = parseInt(document.getElementById('benchmark-shelter-select').value);
    const threads = parseInt(document.getElementById('benchmark-threads-input').value);
    const box = document.getElementById('benchmark-result-box');

    box.style.display = 'block';
    box.innerHTML = `<span style="color:var(--accent-amber);">⌛ Running multi-threaded benchmark with ${threads} parallel threads...</span>`;

    try {
        const resp = await fetch('/api/benchmark/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ shelter_id: shelterId, num_concurrent_requests: threads })
        });
        const res = await resp.json();

        box.innerHTML = `
            <b style="color:var(--accent-green); font-size:1rem;">✅ Concurrency Surge Test Complete</b><br/><br/>
            <b>Target Shelter:</b> ${res.shelter_name}<br/>
            <b>Concurrent Threads Fired:</b> ${res.concurrent_threads}<br/>
            <b>Initial Beds:</b> ${res.initial_beds} &rarr; <b>Final Beds:</b> ${res.final_beds}<br/>
            <b>Successful Allocations:</b> ${res.successful_allocations}<br/>
            <b>Pessimistic Lock Rejections (Capacity Exceeded):</b> ${res.failed_allocations}<br/>
            <b>Throughput:</b> ${res.throughput_requests_per_sec} requests/sec<br/>
            <b>Zero Overbooking Integrity Verified:</b> <span style="color:var(--accent-green); font-weight:bold;">${res.zero_overbooking_verified ? 'PASSED (0 OVERBOOKINGS)' : 'FAILED'}</span>
        `;
        fetchShelters();
    } catch (err) {
        box.innerHTML = `<span style="color:var(--accent-red);">Benchmark failed: ${err}</span>`;
    }
}

async function sendOfflineSMSIPC() {
    const raw = document.getElementById('sms-raw-input').value;
    const ackBox = document.getElementById('sms-ack-box');
    ackBox.innerText = 'Transmitting raw stream to OS Socket Daemon...';

    try {
        const resp = await fetch('/api/ipc/send_sms', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ raw_payload: raw })
        });
        const res = await resp.json();
        if (res.success) {
            ackBox.innerText = `✅ Socket ACK Received: "${res.socket_ack}". Parsed into DB & Allocated Bed!`;
            fetchShelters();
        } else {
            ackBox.innerText = `❌ IPC Error: ${res.error}`;
        }
    } catch (err) {
        ackBox.innerText = `❌ Network Error: ${err}`;
    }
}

async function allocateDirectly(shelterId) {
    try {
        const resp = await fetch('/api/allocate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ evacuee_id: 1, shelter_id: shelterId, beds: 1 })
        });
        const res = await resp.json();
        if (res.success) {
            alert(`✅ Bed allocated at ${res.shelter_name}! Remaining: ${res.remaining_beds}. SHA-256 TX: ${res.transaction_hash.substring(0, 16)}...`);
            fetchShelters();
        } else {
            alert(`❌ Allocation failed: ${res.error}`);
        }
    } catch (err) {
        alert("Error: " + err);
    }
}
