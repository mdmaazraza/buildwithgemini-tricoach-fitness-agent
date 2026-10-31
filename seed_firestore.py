import os
import time
from google.cloud import firestore

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-02-c57180f0ec07")

db = firestore.Client(project=PROJECT_ID, database="(default)")

SEED_WORKOUTS = [
    {
        "workout_id": "workout-101",
        "athlete_id": "athlete-01",
        "activity_type": "Run",
        "duration_minutes": 45,
        "distance_km": 8.5,
        "avg_heart_rate": 152,
        "intensity_zone": "Zone 3 (Tempo)",
        "notes": "Morning tempo run along the trail. Felt strong.",
        "date": "2026-09-22",
    },
    {
        "workout_id": "workout-102",
        "athlete_id": "athlete-01",
        "activity_type": "Bike",
        "duration_minutes": 90,
        "distance_km": 42.0,
        "avg_heart_rate": 138,
        "intensity_zone": "Zone 2 (Endurance)",
        "notes": "Long aerobic endurance ride. Kept cadence high.",
        "date": "2026-09-23",
    },
    {
        "workout_id": "workout-103",
        "athlete_id": "athlete-01",
        "activity_type": "Swim",
        "duration_minutes": 35,
        "distance_km": 1.8,
        "avg_heart_rate": 145,
        "intensity_zone": "Zone 3 (Threshold)",
        "notes": "Interval session: 10x100m on 1:40 rest.",
        "date": "2026-09-24",
    },
    {
        "workout_id": "workout-104",
        "athlete_id": "athlete-01",
        "activity_type": "Brick",
        "duration_minutes": 110,
        "distance_km": 35.0,
        "avg_heart_rate": 158,
        "intensity_zone": "Zone 4 (Race Pace)",
        "notes": "Olympic distance simulation brick workout (Bike + Run transition).",
        "date": "2026-09-24",
    },
]


def seed():
    for item in SEED_WORKOUTS:
        doc_ref = db.collection("workouts").document(item["workout_id"])
        doc_ref.set(item)
        print(f"Seeded workout: {item['workout_id']} - {item['activity_type']}")
        time.sleep(0.5)
    print("Firestore seeding complete!")


if __name__ == "__main__":
    seed()
