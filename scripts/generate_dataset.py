"""
Synthetic dataset generator: Disaster Resource Allocation & Shelter Management.
Every number below is a stated ASSUMPTION for simulation, not an observed statistic.
Run: python generate_dataset.py   (fixed seed -> identical output every run)
"""
import csv, math, random, hashlib
from datetime import datetime, timedelta

SEED = 2026
random.seed(SEED)
OUT = "."
N_EVACUEES_TARGET = 20000
SHELTERS_PER_DISTRICT = 6

# District HQ coordinates (approximate, decimal degrees). coast: 'W' = sea to the west,
# 'E' = sea to the east, '' = inland. Used so jitter never pushes points into the sea.
DISTRICTS = {
 "Assam": [("Barpeta",26.32,91.00,""),("Cachar",24.83,92.78,""),("Dhemaji",27.48,94.58,""),
           ("Dhubri",26.02,89.98,""),("Kamrup Metropolitan",26.14,91.74,""),("Morigaon",26.25,92.34,""),("Nagaon",26.35,92.68,"")],
 "Bihar": [("Darbhanga",26.15,85.90,""),("Kishanganj",26.10,87.95,""),("Muzaffarpur",26.12,85.39,""),
           ("Patna",25.59,85.14,""),("Saharsa",25.88,86.60,""),("Supaul",26.12,86.60,"")],
 "Gujarat": [("Bharuch",21.71,72.98,"W"),("Jamnagar",22.47,70.06,"W"),("Junagadh",21.52,70.46,""),
           ("Kutch",23.25,69.67,""),("Morbi",22.82,70.84,""),("Surat",21.17,72.83,"W")],
 "Himachal Pradesh": [("Chamba",32.55,76.13,""),("Kinnaur",31.54,78.27,""),("Kullu",31.96,77.11,""),
           ("Lahaul and Spiti",32.57,77.03,""),("Mandi",31.71,76.93,""),("Shimla",31.10,77.17,"")],
 "Kerala": [("Alappuzha",9.50,76.34,"W"),("Ernakulam",9.98,76.30,"W"),("Idukki",9.85,76.97,""),
           ("Kottayam",9.59,76.52,""),("Kozhikode",11.26,75.78,"W"),("Pathanamthitta",9.26,76.79,""),
           ("Thrissur",10.53,76.21,"W"),("Wayanad",11.61,76.08,"")],
 "Maharashtra": [("Kolhapur",16.70,74.24,""),("Mumbai",19.08,72.88,"W"),("Raigad",18.64,72.87,"W"),
           ("Ratnagiri",16.99,73.31,"W"),("Sangli",16.85,74.58,""),("Thane",19.22,72.98,"W")],
 "Odisha": [("Balasore",21.49,86.93,"E"),("Bhadrak",21.06,86.50,""),("Ganjam",19.31,84.79,"E"),
           ("Jagatsinghpur",20.26,86.17,"E"),("Kendrapara",20.50,86.42,"E"),("Puri",19.81,85.83,"E")],
 "Tamil Nadu": [("Chennai",13.08,80.27,"E"),("Cuddalore",11.75,79.75,"E"),("Kanchipuram",12.83,79.70,""),
           ("Nagapattinam",10.77,79.84,"E"),("Thanjavur",10.79,79.14,""),("Tiruvallur",13.14,79.91,"")],
 "Uttarakhand": [("Chamoli",30.41,79.32,""),("Dehradun",30.32,78.03,""),("Nainital",29.38,79.46,""),
           ("Pithoragarh",29.58,80.22,""),("Rudraprayag",30.28,78.98,""),("Uttarkashi",30.73,78.45,"")],
 "West Bengal": [("Howrah",22.59,88.31,""),("Malda",25.01,88.14,""),("Murshidabad",24.10,88.25,""),
           ("North 24 Parganas",22.72,88.48,""),("South 24 Parganas",22.53,88.33,"")],
}
# One scenario event per state (assumed hazard profile, matching the original dataset's mapping)
EVENTS = {"Assam":("Flood","HIGH"),"Bihar":("Flood","EXTREME"),"Gujarat":("Earthquake","CRITICAL"),
  "Himachal Pradesh":("Landslide","HIGH"),"Kerala":("Flood","EXTREME"),"Maharashtra":("Urban Flood","HIGH"),
  "Odisha":("Cyclone","CRITICAL"),"Tamil Nadu":("Cyclone","HIGH"),"Uttarakhand":("Landslide","CRITICAL"),
  "West Bengal":("Cyclone","EXTREME")}
HILLY = {"Himachal Pradesh","Uttarakhand"}

# facility type: (bed range, P(has_icu), P(wheelchair_accessible), P(has_medical_unit))
FACILITY = {
 "Govt Higher Secondary School":   ((150,500), 0.03, 0.45, 0.30),
 "Degree College":                 ((200,700), 0.05, 0.60, 0.40),
 "Indoor Stadium":                 ((500,1500),0.10, 0.80, 0.70),
 "Community Hall":                 ((100,350), 0.02, 0.50, 0.20),
 "Army Relief Camp":               ((300,1200),0.40, 0.55, 0.95),
 "Community Health Centre":        ((80,250),  0.55, 0.85, 1.00),
}
SEVERITY_INJURY = {  # P(none, minor, serious, critical) per severity  (assumption)
 "HIGH":(0.84,0.11,0.04,0.01),"CRITICAL":(0.78,0.14,0.06,0.02),"EXTREME":(0.74,0.16,0.07,0.03)}
EARTHQUAKE_INJURY = (0.66,0.20,0.10,0.04)
START = datetime(2026, 8, 1, 6, 0, 0)

FIRST_F = "Aarti Anjali Asha Bhavna Deepa Divya Farida Gita Jyoti Kavita Lakshmi Meena Nandini Neha Pooja Priya Radha Rekha Ritu Sakina Sangeeta Shabnam Sita Sunita Swati Usha Zainab Anita Kiran Parvati".split()
FIRST_M = "Abdul Ajay Amit Anil Arjun Ashok Deepak Gopal Harish Imran Jagdish Karan Manoj Mohan Mukesh Nitin Rahul Raju Ramesh Ravi Salim Sanjay Suresh Vijay Vinod Yusuf Joseph Thomas Gurpreet Bikash".split()
LAST = "Sharma Singh Kumar Yadav Das Nair Menon Patel Shah Rawat Negi Bisht Thakur Reddy Pillai Iyer Khan Ansari Mondal Ghosh Barman Bora Gogoi Sahu Mishra Patil Jadhav Pradhan Mohanty Kaur Joshi Chauhan Mathew Ali".split()

def jitter(lat, lon, max_km, coast):
    """Uniform point in a disc of radius max_km, kept on the landward side for coastal districts."""
    r = max_km * math.sqrt(random.random()); t = random.uniform(0, 2*math.pi)
    dlat = r*math.sin(t)/111.0; dlon = r*math.cos(t)/(111.0*math.cos(math.radians(lat)))
    if coast == "W": dlon = abs(dlon)
    if coast == "E": dlon = -abs(dlon)
    return round(lat+dlat, 5), round(lon+dlon, 5)

def write(name, header, rows):
    with open(f"{OUT}/{name}", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print(f"{name}: {len(rows)} rows")

# ---------- disaster_events, districts ----------
events, districts, ev_of_state = [], [], {}
did = 0
for i, (state, (dtype, sev)) in enumerate(EVENTS.items(), 1):
    start = START + timedelta(days=random.randint(0, 40), hours=random.randint(0, 23))
    events.append([i, f"{state} {dtype} 2026 (simulated)", dtype, sev, state, start.isoformat(timespec="seconds")])
    ev_of_state[state] = (i, sev, dtype, start)
dist_rows = {}
for state, ds in DISTRICTS.items():
    for name, lat, lon, coast in ds:
        did += 1
        districts.append([did, name, state, lat, lon, coast or "INLAND", "YES" if state in HILLY else "NO"])
        dist_rows[did] = (name, state, lat, lon, coast)
write("disaster_events.csv", ["event_id","event_name","disaster_type","severity","state","start_time"], events)
write("districts.csv", ["district_id","district_name","state","hq_latitude","hq_longitude","coast_side","hilly_terrain"], districts)

# ---------- shelters + inventory ----------
shelters, inventory = [], []
sid = 0
for d_id, (dname, state, lat, lon, coast) in dist_rows.items():
    radius = 12 if state in HILLY else 20
    for k in range(SHELTERS_PER_DISTRICT):
        sid += 1
        ftype = random.choice(list(FACILITY))
        (blo, bhi), p_icu, p_wc, p_med = FACILITY[ftype]
        beds = random.randint(blo, bhi)
        icu = random.random() < p_icu
        med = icu or random.random() < p_med
        slat, slon = jitter(lat, lon, radius, coast if coast else "")
        pre = int(beds * random.uniform(0.40, 0.95))          # occupied before the simulation starts
        phone = f"+91-00000-{sid:05d}"  # deliberately fake, cannot dial a real person
        shelters.append([sid, f"{dname} {ftype} #{k+1}", ftype, d_id, slat, slon, beds, pre,
                         "YES" if icu else "NO", "YES" if med else "NO",
                         "YES" if random.random() < p_wc else "NO", phone, "OPEN"])
        o2 = random.randint(10, 60) if icu else (random.randint(2, 15) if med else 0)
        res = [("oxygen_cylinder","units",o2,max(2,o2//5)),
               ("food","kg",beds*random.randint(3,8),beds),
               ("drinking_water","litres",beds*random.randint(6,15),beds*3),
               ("blanket","units",int(beds*random.uniform(0.6,1.2)),beds//4),
               ("medical_kit","units",random.randint(5,40) if med else random.randint(0,5),3)]
        for r, unit, q, th in res:
            inventory.append([sid, r, unit, q, th])
write("shelters.csv", ["shelter_id","shelter_name","facility_type","district_id","latitude","longitude",
      "total_beds","occupied_at_start","has_icu","has_medical_unit","wheelchair_accessible","contact_helpline","status"], shelters)
write("shelter_inventory.csv", ["shelter_id","resource","unit","quantity","low_stock_threshold"], inventory)

# ---------- volunteers ----------
volunteers = []
vols_by_district = {}
vid = 0
for d_id in dist_rows:
    for _ in range(4):
        vid += 1
        sex = random.choice("FM")
        nm = f"{random.choice(FIRST_F if sex=='F' else FIRST_M)} {random.choice(LAST)}"
        volunteers.append([vid, nm, d_id, f"dev-{vid:04d}"])
        vols_by_district.setdefault(d_id, []).append(vid)
write("volunteers.csv", ["volunteer_id","volunteer_name","district_id","device_id"], volunteers)

# ---------- households, evacuees, arrivals ----------
def sample_age():
    b = random.choices([(0,5),(6,17),(18,44),(45,59),(60,90)], weights=[9,23,42,15,11])[0]  # assumption
    return random.randint(*b)

evacuees, arrivals = [], []
eid = hid = aid = 0
# uneven demand: a few hotspot districts get far more arrivals than local free beds (forces fallback routing)
weights = {d: random.lognormvariate(0, 1.0) for d in dist_rows}
wsum = sum(weights.values())
for d_id, (dname, state, lat, lon, coast) in dist_rows.items():
    per_district = int(N_EVACUEES_TARGET * weights[d_id] / wsum)
    ev_id, sev, dtype, start = ev_of_state[state]
    probs = EARTHQUAKE_INJURY if dtype == "Earthquake" else SEVERITY_INJURY[sev]
    count = 0
    while count < per_district:
        hid += 1
        size = random.choices([1,2,3,4,5,6], weights=[10,18,22,25,15,10])[0]
        hlat, hlon = jitter(lat, lon, 10 if state in HILLY else 25, coast if coast else "")
        # arrival surge: exponential decay, mean ~10 h, capped at 72 h
        t = start + timedelta(minutes=min(72*60, random.expovariate(1/600)))
        vol = random.choice(vols_by_district[d_id])
        last = random.choice(LAST)
        for m in range(size):
            eid += 1; count += 1
            age = sample_age() if m else random.randint(20, 75)   # first member is an adult
            sex = random.choice("FM")
            pregnant = sex == "F" and 18 <= age <= 45 and random.random() < 0.05
            injury = random.choices(["none","minor","serious","critical"], weights=probs)[0]
            unconscious = injury == "critical" and random.random() < 0.30
            p_o2 = {"none":0.005,"minor":0.01,"serious":0.15,"critical":0.55}[injury] + (0.02 if age >= 60 else 0)
            needs_o2 = random.random() < p_o2
            wheelchair = random.random() < (0.08 if age >= 70 else 0.01)
            chronic = random.random() < (0.25 if age >= 60 else 0.05)
            first = random.choice(FIRST_F if sex == "F" else FIRST_M)
            elat, elon = jitter(hlat, hlon, 0.3, "")
            evacuees.append([eid, hid, f"{first} {last}", age, sex, "YES" if pregnant else "NO", injury,
                             "YES" if unconscious else "NO", "YES" if needs_o2 else "NO",
                             "YES" if wheelchair else "NO", "YES" if chronic else "NO",
                             elat, elon, d_id, ev_id])
            at = t + timedelta(seconds=random.randint(0, 120))
            aid += 1
            arrivals.append([aid, eid, vol, f"dev-{vol:04d}", at.isoformat(timespec="seconds"), "NO"])
            # ~1% duplicate submissions: same person, another volunteer, within 3 minutes (for dedup tests)
            if random.random() < 0.01:
                other = random.choice(vols_by_district[d_id])
                aid += 1
                arrivals.append([aid, eid, other, f"dev-{other:04d}",
                                 (at + timedelta(seconds=random.randint(5, 180))).isoformat(timespec="seconds"), "YES"])
arrivals.sort(key=lambda r: r[4])
for i, r in enumerate(arrivals, 1): r[0] = i
write("evacuees.csv", ["evacuee_id","household_id","full_name","age","sex","pregnant","injury_severity",
      "unconscious","needs_oxygen","uses_wheelchair","chronic_condition","latitude","longitude","district_id","event_id"], evacuees)
write("arrival_events.csv", ["arrival_id","evacuee_id","volunteer_id","device_id","submitted_at","is_duplicate_submission"], arrivals)
