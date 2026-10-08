import json
import os
import sys

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import init_db, get_db_connection

def seed_database():
    print("Initializing Database Schema...")
    init_db()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Seed Shelters
    with open("data/india_shelters_sample.json", "r", encoding="utf-8") as f:
        shelters_data = json.load(f)
        
    cursor.execute("DELETE FROM shelters;")
    for s in shelters_data:
        cursor.execute("""
            INSERT INTO shelters (name, district, state, latitude, longitude, total_beds, available_beds, oxygen_cylinders, food_units, transport_units, wheelchair_accessible, medical_facility, contact_number, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            s["name"], s["district"], s["state"], s["latitude"], s["longitude"],
            s["total_beds"], s["available_beds"], s["oxygen_cylinders"], s["food_units"],
            s["transport_units"], 1 if s["wheelchair_accessible"] else 0,
            1 if s["medical_facility"] else 0, s["contact_number"], s["status"]
        ))
        
    print(f"Successfully seeded {len(shelters_data)} Indian emergency shelters.")

    # 2. Seed Initial Evacuees (Triage Queue)
    cursor.execute("DELETE FROM evacuees;")
    sample_evacuees = [
        ("Rahul Sharma", 28, "MALE", 0, "Severe Leg Fracture & Hemorrhage", 10.12, 76.34),
        ("Kavita Nair", 68, "FEMALE", 1, "Asthma & High Blood Pressure", 9.50, 76.35),
        ("Ananya Das", 32, "FEMALE", 1, "Pregnancy (8th Month)", 10.51, 76.22),
        ("Vikram Singh", 45, "MALE", 2, "General Evacuee", 9.27, 76.79),
        ("Meera Patel", 72, "FEMALE", 1, "Diabetic & Wheelchair User", 10.09, 77.06),
        ("Suresh Kumar", 54, "MALE", 2, "General Evacuee", 11.61, 76.08)
    ]
    for name, age, gender, priority, medical, lat, lon in sample_evacuees:
        cursor.execute("""
            INSERT INTO evacuees (full_name, age, gender, triage_priority, medical_conditions, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, age, gender, priority, medical, lat, lon))
        
    print(f"Successfully seeded {len(sample_evacuees)} initial triage evacuees.")
    
    conn.commit()
    conn.close()
    print("Database seeding completed successfully!")

if __name__ == '__main__':
    seed_database()
