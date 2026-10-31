# 🗄️ TriCoach AI — Database Schema Documentation

## 1. Overview
TriCoach AI uses a dual-backend storage model managed by `app/db.py`:
* **Default / Local / Test**: SQLite (`workouts.db` file or in-memory `:memory:`).
* **Cloud (Enterprise)**: Google Cloud Firestore (`(default)` database).

Both engines adhere to the identical schema, ensuring complete portability.

---

## 2. Table / Collection: `workouts`

Stores historical and active endurance workout sessions logged by athletes.

### Field Definitions

| Field Name | Type (SQLite) | Type (Firestore) | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `workout_id` | `TEXT PRIMARY KEY` | `string` (doc ID) | **Yes** | Unique collision-free workout identifier | `"workout-1793441880637-a1b2c3"` |
| `athlete_id` | `TEXT` | `string` | **Yes** | Identifier for the athlete (multi-tenancy) | `"athlete-01"` |
| `activity_type` | `TEXT` | `string` | **Yes** | Sport type: Run, Bike, Swim, Brick, Strength | `"Bike"` |
| `duration_minutes`| `INTEGER` | `integer` | **Yes** | Workout duration in minutes ($> 0$) | `75` |
| `distance_km` | `REAL` | `number` | **Yes** | Distance covered in kilometers ($\ge 0$) | `38.5` |
| `avg_heart_rate` | `INTEGER` | `integer` | **Yes** | Average heart rate in BPM ($30 \le \text{HR} \le 240$) | `142` |
| `intensity_zone` | `TEXT` | `string` | No | Heart rate training zone description | `"Zone 2 (Endurance)"` |
| `notes` | `TEXT` | `string` | No | Personal feedback, gear used, or pacing notes | `"Felt smooth, steady cadence."` |
| `date` | `TEXT` | `string` | **Yes** | UTC date string in `YYYY-MM-DD` format | `"2026-10-31"` |

---

## 3. SQLite Schema Definition (DDL)

```sql
CREATE TABLE IF NOT EXISTS workouts (
    workout_id TEXT PRIMARY KEY,
    athlete_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    distance_km REAL NOT NULL,
    avg_heart_rate INTEGER NOT NULL,
    intensity_zone TEXT,
    notes TEXT,
    date TEXT NOT NULL
);

-- Recommended Index for Multi-Tenant Querying
CREATE INDEX IF NOT EXISTS idx_workouts_athlete_date 
ON workouts (athlete_id, date DESC);
```

---

## 4. ID Generation Policy

To prevent primary key collisions when athletes log workouts or sync batch activities:
```python
workout_id = f"workout-{int(datetime.datetime.now().timestamp() * 1000)}-{uuid.uuid4().hex[:6]}"
```
* **Prefix**: `workout-`
* **Timestamp**: Millisecond UNIX timestamp providing natural chronological sorting.
* **Entropy**: 6-character random hexadecimal UUID slice preventing sub-millisecond race condition overwrites.

---

## 5. Seed Data

Sample initial records are provided in `seed_firestore.py` and can be seeded into SQLite using:
```python
from app.db import default_db

default_db.log_workout(
    activity_type="Run",
    duration_minutes=45,
    distance_km=8.5,
    avg_heart_rate=152,
    intensity_zone="Zone 3 (Tempo)",
    notes="Morning tempo run along the trail.",
    athlete_id="athlete-01",
    date_str="2026-09-22"
)
```
