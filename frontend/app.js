"use strict";
/* Relief Shelter System - browser client. Plain JavaScript, no build step, works offline. */

const $ = s => document.querySelector(s);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const LEVEL = ["P0 Critical", "P1 Vulnerable", "P2 General"];
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } },
  del(k) { try { localStorage.removeItem(k); } catch (e) { } }
};
let session = store.get("session", null);
let page = "intake";
let gps = null;
const deviceId = store.get("deviceId", null) || (() => { const id = "dev-" + Math.random().toString(36).slice(2, 8); store.set("deviceId", id); return id; })();

function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("on"), 2800); }

/* ---------- API ---------- */
class ApiError extends Error { constructor(status, detail) { super(typeof detail === "string" ? detail : (detail && detail.message) || "Request failed"); this.status = status; this.detail = detail; } }
async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  if (session) headers.Authorization = "Bearer " + session.token;
  const res = await fetch(path, { method: opts.method || "GET", headers, body: opts.body ? JSON.stringify(opts.body) : undefined });
  let data = null; try { data = await res.json(); } catch (e) { }
  if (res.status === 401 && path !== "/api/auth/login") { signOut(true); throw new ApiError(401, "Sign in again"); }
  if (!res.ok) throw new ApiError(res.status, data && data.detail);
  return data;
}

/* ---------- theme ---------- */
function paintThemeBtn() { $("#themeBtn").textContent = document.documentElement.getAttribute("data-theme") === "dark" ? "Light theme" : "Dark theme"; }
$("#themeBtn").addEventListener("click", () => {
  const t = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", t); try { localStorage.setItem("theme", t); } catch (e) { } paintThemeBtn();
});

/* ---------- auth ---------- */
$("#loginForm").addEventListener("submit", async e => {
  e.preventDefault(); $("#loginErr").textContent = "";
  try {
    session = await api("/api/auth/login", { method: "POST", body: { username: $("#lu").value.trim(), password: $("#lp").value } });
    store.set("session", session); $("#lp").value = ""; start();
  } catch (err) { $("#loginErr").textContent = err instanceof ApiError ? err.message : "Cannot reach the server. Check the connection."; }
});
function signOut(expired) {
  if (!expired && session) api("/api/auth/logout", { method: "POST" }).catch(() => { });
  session = null; store.del("session");
  $("#app").hidden = true; $("#login").hidden = false;
  if (expired) $("#loginErr").textContent = "Your session ended. Sign in again.";
}
$("#logoutBtn").addEventListener("click", () => signOut(false));

/* ---------- navigation ---------- */
$("#tabs").addEventListener("click", e => {
  const b = e.target.closest("button[data-page]"); if (!b) return;
  page = b.dataset.page;
  document.querySelectorAll("#tabs button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll(".page").forEach(p => p.classList.toggle("on", p.id === "p-" + page));
  refresh();
});

/* ---------- connection + offline outbox ---------- */
function paintConn() {
  const on = navigator.onLine; $("#conn").textContent = on ? "Online" : "Offline"; $("#conn").classList.toggle("off", !on);
  const n = store.get("outbox", []).length;
  $("#pending").textContent = n ? `${n} not sent` : "";
  $("#outboxNote").textContent = n ? `${n} registrations are saved here and will be sent when the connection returns.` : "Nothing waiting. Registrations made without a connection are kept here until they can be sent.";
  $("#syncBtn").disabled = !n;
}
addEventListener("online", () => { paintConn(); syncOutbox(); });
addEventListener("offline", () => { paintConn(); toast("Offline. You can keep registering; records are saved on this device."); });

async function syncOutbox() {
  const box = store.get("outbox", []);
  if (!box.length || !navigator.onLine || !session) return;
  try {
    const res = await api("/api/intake/batch", { method: "POST", body: { records: box } });
    const done = new Set(res.results.map(r => r.client_request_id));
    store.set("outbox", store.get("outbox", []).filter(r => !done.has(r.client_request_id)));
    const placed = res.results.filter(r => r.ok && r.status === "ALLOCATED").length;
    const dups = res.results.filter(r => r.duplicate).length;
    toast(`Sent ${res.results.length}: ${placed} placed${dups ? `, ${dups} already registered` : ""}`);
  } catch (e) { /* still offline; try again later */ }
  paintConn();
}
$("#syncBtn").addEventListener("click", syncOutbox);

/* ---------- intake ---------- */
function readForm() {
  const d = $("#f-dist").value;
  const p = {
    full_name: $("#f-name").value.trim(), age: $("#f-age").value === "" ? null : +$("#f-age").value,
    sex: $("#f-sex").value, injury_severity: $("#f-inj").value, external_ref: $("#f-ref").value.trim() || null,
    needs_oxygen: $("#f-oxy").checked, pregnant: $("#f-preg").checked, uses_wheelchair: $("#f-wc").checked, unconscious: $("#f-unc").checked
  };
  if (d === "gps" && gps) { p.latitude = gps.lat; p.longitude = gps.lon; } else { p.district_id = +d; }
  return p;
}
// Same rules as backend/triage.py, so the volunteer sees the priority before submitting
function triage(p) {
  const c = [], v = [];
  if (p.unconscious) c.push("unconscious"); if (p.injury_severity === "critical") c.push("critical injury");
  if (p.injury_severity === "serious") c.push("serious injury"); if (p.needs_oxygen) c.push("needs oxygen");
  if (p.pregnant) v.push("pregnant"); if (p.age != null && p.age >= 60) v.push("aged 60 or over");
  if (p.age != null && p.age <= 5) v.push("child aged 5 or under"); if (p.uses_wheelchair) v.push("uses wheelchair");
  if (p.injury_severity === "minor") v.push("minor injury");
  if (c.length) return [0, c.concat(v)]; if (v.length) return [1, v]; return [2, []];
}
function paintTriage() {
  const [lvl, why] = triage(readForm());
  $("#triageNote").innerHTML = `Priority: <span class="p${lvl}">${LEVEL[lvl]}</span>${why.length ? " (" + esc(why.join(", ")) + ")" : ""}`;
}
$("#intakeForm").addEventListener("input", paintTriage);
$("#intakeForm").addEventListener("change", paintTriage);

$("#gpsBtn").addEventListener("click", () => {
  if (!navigator.geolocation) { toast("GPS is not available on this device"); return; }
  $("#gpsNote").textContent = "Reading GPS…";
  navigator.geolocation.getCurrentPosition(pos => {
    gps = { lat: +pos.coords.latitude.toFixed(5), lon: +pos.coords.longitude.toFixed(5) };
    let opt = $("#f-dist").querySelector('option[value="gps"]');
    if (!opt) { opt = new Option("My GPS position", "gps"); $("#f-dist").prepend(opt); }
    $("#f-dist").value = "gps"; $("#gpsNote").textContent = `GPS: ${gps.lat}, ${gps.lon}`;
  }, () => { $("#gpsNote").textContent = "Could not read GPS. Choose a district instead."; }, { timeout: 10000 });
});

$("#intakeForm").addEventListener("submit", async e => {
  e.preventDefault(); $("#intakeErr").textContent = "";
  const p = readForm();
  if (!p.full_name) { $("#intakeErr").textContent = "Enter the person's name."; $("#f-name").focus(); return; }
  if (p.age != null && (p.age < 0 || p.age > 120)) { $("#intakeErr").textContent = "Age must be between 0 and 120."; return; }
  if (p.pregnant && p.sex === "M") { $("#intakeErr").textContent = "Pregnant is ticked for a male record. Check the form."; return; }
  p.client_request_id = `${deviceId}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  $("#regBtn").disabled = true;
  try {
    if (!navigator.onLine) throw new TypeError("offline");
    const r = await api("/api/intake", { method: "POST", body: p });
    showResult(p, r); resetForm();
  } catch (err) {
    if (err instanceof ApiError) {
      $("#intakeErr").textContent = err.status === 409 ? `${err.message} (record ${err.detail.existing_id}).` : err.message;
    } else { // network failure: keep it on the device
      const box = store.get("outbox", []); box.push(p); store.set("outbox", box);
      const [lvl, why] = triage(p);
      $("#resultBox").innerHTML = `<h2>Saved on this device</h2><dl class="result">
        <dt>Person</dt><dd>${esc(p.full_name)}</dd><dt>Priority</dt><dd class="p${lvl}">${LEVEL[lvl]}</dd></dl>
        <p class="muted small">No connection. The shelter will be assigned when this record is sent.${lvl === 0 ? " This person needs medical care: contact the nearest medical team directly." : ""}</p>`;
      resetForm(); paintConn();
    }
  } finally { $("#regBtn").disabled = false; }
});
function resetForm() { const d = $("#f-dist").value; $("#intakeForm").reset(); $("#f-dist").value = d; paintTriage(); $("#f-name").focus(); }

function showResult(p, r) {
  const skipped = (r.skipped || []).map(s => `<li>Passed over ${esc(s.shelter_name)} (${s.km} km): ${esc(s.reasons.join(", "))}</li>`).join("");
  let body;
  if (r.status === "ALLOCATED") {
    const s = r.shelter || {};
    body = `<dt>Send to</dt><dd>${esc(s.shelter_name || r.shelter_name)}</dd>
      ${s.district ? `<dt>Location</dt><dd>${esc(s.district)}, ${esc(s.state)}${r.distance_km != null ? ` · ${r.distance_km} km away` : ""}</dd>` : ""}
      ${s.contact_helpline ? `<dt>Shelter helpline</dt><dd>${esc(s.contact_helpline)}</dd>` : ""}
      ${r.was_fallback ? `<dt>Note</dt><dd>The nearest shelter could not take this person, so the next suitable one was chosen.</dd>` : ""}`;
  } else if (r.status === "WAITING") {
    body = `<dt>Status</dt><dd>Waiting list</dd><dd class="muted small">${esc(r.message || "No suitable bed nearby.")} The person will be placed automatically when a bed opens.</dd>`;
  } else {
    body = `<dt>Status</dt><dd>${esc(r.status)}</dd><dd class="muted small">${esc(r.message || "")}</dd>`;
  }
  $("#resultBox").innerHTML = `<h2>Registered: ${esc(p.full_name)}</h2><dl class="result">
    <dt>Record number</dt><dd>${r.evacuee_id}</dd>
    <dt>Priority</dt><dd class="p${r.priority}">${LEVEL[r.priority]}${r.reasons && r.reasons.length ? ` (${esc(r.reasons.join(", "))})` : ""}</dd>
    ${body}</dl>${skipped ? `<ul>${skipped}</ul>` : ""}`;
}

async function loadDistricts() {
  let list = store.get("districts", []);
  try { list = await api("/api/districts"); store.set("districts", list); } catch (e) { }
  const sel = $("#f-dist"), keep = store.get("lastDistrict", null);
  sel.innerHTML = ""; const groups = {};
  list.forEach(d => { (groups[d.state] ||= []).push(d); });
  Object.keys(groups).forEach(st => {
    const g = document.createElement("optgroup"); g.label = st;
    groups[st].forEach(d => g.appendChild(new Option(d.district_name, d.district_id))); sel.appendChild(g);
  });
  if (keep) sel.value = keep;
  const states = Object.keys(groups);
  ["#s-state", "#b-state"].forEach(id => {
    const s = $(id), first = id === "#s-state" ? '<option value="">All states</option>' : "";
    s.innerHTML = first + states.map(x => `<option>${esc(x)}</option>`).join("");
  });
}
$("#f-dist").addEventListener("change", e => { if (e.target.value !== "gps") store.set("lastDistrict", e.target.value); });

/* ---------- tables ---------- */
function table(el, cols, data, empty) {
  if (!data.length) { el.innerHTML = `<tbody><tr><td class="muted">${empty}</td></tr></tbody>`; return; }
  el.innerHTML = `<thead><tr>${cols.map(c => `<th class="${c.cls || ""}">${c.h}</th>`).join("")}</tr></thead>
    <tbody>${data.map(r => `<tr>${cols.map(c => `<td class="${c.cls || ""}">${c.f(r)}</td>`).join("")}</tr>`).join("")}</tbody>`;
}
const occBar = o => `<span class="occ"><i><b class="${o >= 100 ? "full" : o >= 90 ? "hi" : ""}" style="width:${Math.min(100, o)}%"></b></i>${o.toFixed(1)}%</span>`;
const statusLabel = { OPEN: "Open", CRITICAL_90: "90%+", FULL: "Full", CLOSED: "Closed" };

async function loadShelters() {
  const [sum, list] = await Promise.all([api("/api/summary"),
    api(`/api/shelters?state_name=${encodeURIComponent($("#s-state").value)}&status=${$("#s-status").value}&q=${encodeURIComponent($("#s-q").value)}`)]);
  const s = sum.shelters;
  $("#stats").innerHTML = [["Shelters", s.shelters], ["Free beds", s.free_beds.toLocaleString()], ["Total beds", s.total_beds.toLocaleString()],
    ["Full", s.full], ["At 90% or more", s.critical], ["Placed people", (sum.evacuees.ALLOCATED || 0).toLocaleString()],
    ["Waiting", ((sum.evacuees.WAITING || 0) + (sum.evacuees.QUEUED || 0)).toLocaleString()]]
    .map(([k, v]) => `<div class="stat"><b>${v}</b><span>${k}</span></div>`).join("");
  table($("#s-table"), [
    { h: "Shelter", f: r => esc(r.shelter_name) }, { h: "District", f: r => esc(r.district_name) }, { h: "State", f: r => esc(r.state) },
    { h: "Free / total", cls: "num", f: r => `${r.available_beds} / ${r.total_beds}` }, { h: "Occupancy", f: r => occBar(r.occupancy) },
    { h: "Oxygen", cls: "num", f: r => r.oxygen }, { h: "ICU", f: r => r.has_icu ? "Yes" : "No" },
    { h: "Status", f: r => `<span class="st-${r.status}">${statusLabel[r.status]}</span>` }], list, "No shelters match these filters.");
}
["#s-state", "#s-status"].forEach(id => $(id).addEventListener("change", loadShelters));
let qTimer; $("#s-q").addEventListener("input", () => { clearTimeout(qTimer); qTimer = setTimeout(loadShelters, 300); });

async function loadPeople() {
  const list = await api(`/api/evacuees?status=${$("#e-status").value}&limit=200`);
  table($("#e-table"), [
    { h: "No.", cls: "num", f: r => r.evacuee_id }, { h: "Name", f: r => esc(r.full_name) }, { h: "Age", cls: "num", f: r => r.age ?? "" },
    { h: "Priority", f: r => `<span class="p${r.priority}">P${r.priority}</span>` }, { h: "Reason", f: r => esc(r.triage_reasons) },
    { h: "Status", f: r => esc(r.status) }, { h: "Shelter", f: r => esc(r.shelter_name || "") }, { h: "Source", f: r => esc(r.source) },
    { h: "", f: r => r.status === "ALLOCATED" ? `<button class="btn" data-discharge="${r.evacuee_id}">Discharge</button>` : "" }],
    list, "No people registered yet.");
}
$("#e-status").addEventListener("change", loadPeople);
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-discharge]"); if (!b) return;
  if (!confirm("Discharge this person and free their bed?")) return;
  try { await api(`/api/evacuees/${b.dataset.discharge}/discharge`, { method: "POST" }); toast("Discharged. The bed is free."); loadPeople(); }
  catch (err) { toast(err.message); }
});

async function loadQueue() {
  const q = await api("/api/queue"), s = q.stats;
  $("#q-note").textContent = `Workers always serve the highest level first. Anyone waiting more than ${s.age_after_s} s is moved up one level so no one is left behind.`;
  table($("#q-levels"), [{ h: "Level", f: r => `<span class="p${r.i}">${esc(r.name)}</span>` }, { h: "In queue", cls: "num", f: r => r.n }, { h: "Oldest wait", cls: "num", f: r => r.w + " s" }],
    s.level_names.map((name, i) => ({ i, name, n: s.levels[i], w: s.oldest_wait_s[i] })), "");
  $("#q-meta").textContent = `Buffer ${s.levels.reduce((a, b) => a + b, 0)} / ${s.capacity} · workers busy ${s.busy_workers} / ${s.workers} · processed ${s.processed} · promotions by aging ${s.promotions}`;
  table($("#q-waiting"), [{ h: "No.", cls: "num", f: r => r.evacuee_id }, { h: "Name", f: r => esc(r.full_name) },
    { h: "Priority", f: r => `<span class="p${r.priority}">P${r.priority}</span>` }, { h: "Reason", f: r => esc(r.triage_reasons) }, { h: "Registered", f: r => esc(r.created_at.replace("T", " ").slice(0, 19)) }],
    q.waiting, "No one is waiting for a bed.");
}
$("#retryBtn").addEventListener("click", async () => { const r = await api("/api/queue/retry", { method: "POST" }); toast(`Re-queued ${r.requeued} people`); loadQueue(); });

async function loadAlerts() {
  const list = await api("/api/alerts");
  $("#alertCount").textContent = list.length || "";
  table($("#a-table"), [{ h: "Time (UTC)", f: r => esc(r.created_at) }, { h: "Type", f: r => esc(r.alert_type.replace("_", " ")) },
    { h: "Message", f: r => esc(r.message) }, { h: "", f: r => session.role === "ADMIN" ? `<button class="btn" data-ack="${r.alert_id}">Acknowledge</button>` : "" }],
    list, "No open alerts.");
}
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-ack]"); if (!b) return;
  await api(`/api/alerts/${b.dataset.ack}/ack`, { method: "POST" }); loadAlerts();
});

/* ---------- Banker's ---------- */
async function loadBankers() {
  const st = $("#b-state").value; if (!st) return;
  const v = await api(`/api/bankers/${encodeURIComponent(st)}`);
  const names = Object.fromEntries(v.processes.map(p => [p.shelter_id, p.shelter_name]));
  $("#b-safe").innerHTML = `Depot stock: oxygen ${v.available[0]}, stretchers ${v.available[1]}, generators ${v.available[2]}.<br>` +
    (v.safe ? `<span class="ok">Safe state.</span> <span class="small muted">Safe order: ${v.safe_sequence.map(id => "#" + id).join(" → ")}</span>` : `<span class="bad">Unsafe state.</span>`);
  const v3 = a => a.join(" / ");
  table($("#b-table"), [{ h: "Shelter", f: r => `#${r.shelter_id} ${esc(r.shelter_name)}` }, { h: "Max (O₂ / stretcher / generator)", f: r => v3(r.max) },
    { h: "On loan", f: r => v3(r.allocated) }, { h: "Still may need", f: r => v3(r.need) }], v.processes, "No shelters in this state have declared claims.");
  const sel = $("#b-shelter"), keep = sel.value;
  sel.innerHTML = v.processes.map(p => `<option value="${p.shelter_id}">#${p.shelter_id} ${esc(p.shelter_name)}</option>`).join("");
  if (names[keep]) sel.value = keep;
}
$("#b-state").addEventListener("change", loadBankers);
async function bankersAction(kind) {
  const body = { shelter_id: +$("#b-shelter").value, amounts: { oxygen_cylinder: +$("#b-o2").value, stretcher: +$("#b-st").value, generator: +$("#b-gen").value } };
  try {
    const r = await api(`/api/bankers/${kind}`, { method: "POST", body });
    $("#b-msg").innerHTML = kind === "request" ? `<span class="${r.granted ? "ok" : "bad"}">${esc(r.reason)}</span>` : `<span class="ok">Returned to the depot.</span>`;
    loadBankers();
  } catch (err) { $("#b-msg").innerHTML = `<span class="bad">${esc(err.message)}</span>`; }
}
$("#b-form").addEventListener("submit", e => { e.preventDefault(); bankersAction("request"); });
$("#b-return").addEventListener("click", () => bankersAction("release"));

/* ---------- audit + system ---------- */
async function loadAudit() {
  const list = await api("/api/audit?limit=100");
  table($("#au-table"), [{ h: "No.", cls: "num", f: r => r.allocation_id }, { h: "Action", f: r => r.action === "ALLOCATE" ? "Allocated" : "Discharged" },
    { h: "Person", f: r => esc(r.full_name) }, { h: "Shelter", f: r => esc(r.shelter_name) }, { h: "km", cls: "num", f: r => r.distance_km ?? "" },
    { h: "Fallback", f: r => r.was_fallback ? "Yes" : "" }, { h: "Hash", f: r => `<span class="mono" title="${r.hash}">${r.hash.slice(0, 16)}…</span>` }],
    list, "No allocations yet.");
}
$("#verifyBtn").addEventListener("click", async () => {
  const v = await api("/api/audit/verify");
  $("#verifyMsg").innerHTML = v.valid ? `<span class="ok">Chain intact.</span> ${v.checked} records checked.` : `<span class="bad">Chain broken at record ${v.broken_at}.</span> That record or an earlier one was changed.`;
});
$("#integrityBtn").addEventListener("click", async () => {
  const r = await api("/api/integrity");
  $("#verifyMsg").innerHTML = r.overbooked || r.counter_mismatches ? `<span class="bad">${r.overbooked} overbooked shelters, ${r.counter_mismatches} counter mismatches.</span>` : `<span class="ok">No overbooking.</span> ${r.shelters_checked} shelters checked.`;
});
async function loadSystem() {
  const list = await api("/api/telemetry?limit=40");
  table($("#t-table"), [{ h: "Time (UTC)", f: r => esc(r.ts) }, { h: "Threads", cls: "num", f: r => r.active_threads },
    { h: "P0 / P1 / P2 queued", f: r => `${r.queue_p0} / ${r.queue_p1} / ${r.queue_p2}` }, { h: "Promotions", cls: "num", f: r => r.promotions },
    { h: "Lock wait avg (ms)", cls: "num", f: r => r.lock_wait_avg_ms }, { h: "Lock wait max (ms)", cls: "num", f: r => r.lock_wait_max_ms },
    { h: "Allocations", cls: "num", f: r => r.allocations }], list, "No telemetry yet. Rows appear every few seconds.");
}

/* ---------- refresh loop ---------- */
const loaders = { shelters: loadShelters, people: loadPeople, queue: loadQueue, alerts: loadAlerts, resources: loadBankers, audit: loadAudit, system: loadSystem };
async function refresh() {
  try { if (loaders[page]) await loaders[page](); if (page !== "alerts" && navigator.onLine) { const a = await api("/api/alerts"); $("#alertCount").textContent = a.length || ""; } }
  catch (e) { if (!(e instanceof ApiError)) { /* offline: keep what is on screen */ } else toast(e.message); }
}
setInterval(() => { if (session && page !== "intake" && page !== "resources" && !document.hidden) refresh(); }, 5000);
setInterval(() => { if (session) syncOutbox(); }, 15000);

async function start() {
  $("#login").hidden = true; $("#app").hidden = false;
  document.body.classList.toggle("is-admin", session.role === "ADMIN");
  $("#who").textContent = `${session.full_name} (${session.role.toLowerCase()})`;
  paintThemeBtn(); paintConn(); paintTriage();
  await loadDistricts(); paintTriage(); refresh(); syncOutbox();
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => { });
paintThemeBtn();
if (session) start(); else $("#login").hidden = false;
