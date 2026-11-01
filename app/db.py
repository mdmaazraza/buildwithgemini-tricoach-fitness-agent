"""Database abstraction layer for TriCoach AI.

Supports:
- SQLite (default for testing, local development, and zero-cost deployments)
- Google Cloud Firestore (when explicitly enabled with USE_FIRESTORE=true)
"""

import datetime
import os
import sqlite3
import uuid
from typing import Any

_use_firestore = False
_firestore_client = None

# Only attempt Firestore if explicitly opted-in via USE_FIRESTORE=true
if os.getenv("USE_FIRESTORE", "false").lower() == "true":
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if project_id:
        try:
            from google.cloud import firestore
            _firestore_client = firestore.Client(project=project_id, database="(default)")
            _use_firestore = True
        except Exception:
            _use_firestore = False


class WorkoutDatabase:
    """Workout database interface supporting SQLite and Firestore."""

    def __init__(self, db_path: str | None = None):
        """Initializes database. If db_path is ':memory:', keeps a persistent connection for in-memory testing."""
        self.db_path = db_path or os.getenv("SQLITE_DB_PATH", "workouts.db")
        self.use_firestore = _use_firestore and (self.db_path != ":memory:")
        self._mem_conn = None
        if not self.use_firestore:
            if self.db_path == ":memory:":
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._init_sqlite()

    def _get_connection(self):
        if self._mem_conn is not None:
            return self._mem_conn
        return sqlite3.connect(self.db_path)

    def _init_sqlite(self):
        """Creates workouts, profiles, food entries, activities, measurements, and email tables in SQLite."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
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
            )
        """)

        # User Fitness Profiles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                athlete_id TEXT PRIMARY KEY,
                age INTEGER NOT NULL DEFAULT 28,
                height_cm REAL NOT NULL DEFAULT 175.0,
                current_weight_kg REAL NOT NULL DEFAULT 72.0,
                sex TEXT NOT NULL DEFAULT 'male',
                activity_level TEXT NOT NULL DEFAULT 'moderate',
                goal TEXT NOT NULL DEFAULT 'maintenance',
                target_weight_kg REAL DEFAULT 70.0,
                preferred_units TEXT NOT NULL DEFAULT 'metric',
                target_rate_change REAL DEFAULT 0.5,
                updated_at TEXT NOT NULL
            )
        """)

        # Daily Food Entries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS food_entries (
                entry_id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                date TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                food_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                calories REAL NOT NULL,
                protein_g REAL NOT NULL DEFAULT 0.0,
                carbs_g REAL NOT NULL DEFAULT 0.0,
                fat_g REAL NOT NULL DEFAULT 0.0,
                fiber_g REAL NOT NULL DEFAULT 0.0,
                data_source TEXT NOT NULL DEFAULT 'manual',
                is_verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # Daily Physical Activities
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_entries (
                activity_id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                date TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                intensity TEXT NOT NULL DEFAULT 'moderate',
                distance_km REAL DEFAULT 0.0,
                steps INTEGER DEFAULT 0,
                calories_burned REAL NOT NULL DEFAULT 0.0,
                strength_details_json TEXT DEFAULT '{}',
                data_source TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL
            )
        """)

        # Daily Body Measurements
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS body_measurements (
                measurement_id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                date TEXT NOT NULL,
                weight_kg REAL NOT NULL,
                waist_cm REAL,
                body_fat_pct REAL,
                measurement_method TEXT DEFAULT 'scale',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        # Email Delivery Reports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_reports (
                report_id TEXT PRIMARY KEY,
                athlete_id TEXT NOT NULL,
                recipient_email TEXT NOT NULL,
                report_date TEXT NOT NULL,
                report_period TEXT NOT NULL,
                summary_text TEXT NOT NULL,
                status TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'simulated',
                error_message TEXT DEFAULT '',
                sent_at TEXT NOT NULL
            )
        """)

        # Backward compatibility: ensure provider column exists in email_reports
        try:
            cursor.execute("ALTER TABLE email_reports ADD COLUMN provider TEXT NOT NULL DEFAULT 'simulated'")
        except sqlite3.OperationalError:
            pass  # column already exists

        # Email Subscriptions & User Consent
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_subscriptions (
                athlete_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                is_verified INTEGER NOT NULL DEFAULT 0,
                verification_token TEXT NOT NULL,
                user_consent INTEGER NOT NULL DEFAULT 0,
                consent_timestamp TEXT,
                report_frequency TEXT NOT NULL DEFAULT 'daily',
                preferred_time_utc TEXT NOT NULL DEFAULT '08:00',
                updated_at TEXT NOT NULL,
                last_sent_at TEXT
            )
        """)

        # Auto-seed starter workouts and demo data for new non-memory databases
        cursor.execute("SELECT COUNT(*) FROM workouts")
        if cursor.fetchone()[0] == 0 and self.db_path != ":memory:":
            starter_workouts = [
                ("workout-seed-101", "athlete-01", "Run", 45, 8.5, 152, "Zone 3 (Tempo)", "Morning tempo run along the trail.", "2026-10-28"),
                ("workout-seed-102", "athlete-01", "Bike", 90, 42.0, 138, "Zone 2 (Endurance)", "Aerobic endurance ride. Kept heart rate steady.", "2026-10-29"),
                ("workout-seed-103", "athlete-01", "Swim", 35, 1.8, 145, "Zone 3 (Threshold)", "Technique focus with 10x100m intervals.", "2026-10-30"),
                ("workout-seed-104", "athlete-01", "Brick", 110, 35.0, 158, "Zone 4 (Race Pace)", "Olympic distance simulation (Bike + Run transition).", "2026-10-31"),
            ]
            cursor.executemany("""
                INSERT OR IGNORE INTO workouts
                (workout_id, athlete_id, activity_type, duration_minutes, distance_km, avg_heart_rate, intensity_zone, notes, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, starter_workouts)

            # Seed default profile for athlete-01
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            cursor.execute("""
                INSERT OR IGNORE INTO user_profiles
                (athlete_id, age, height_cm, current_weight_kg, sex, activity_level, goal, target_weight_kg, preferred_units, target_rate_change, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ("athlete-01", 28, 178.0, 74.5, "male", "moderate", "fat_loss", 71.0, "metric", 0.5, now_iso))

            # Seed sample food entries for yesterday and today
            today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
            starter_food = [
                ("food-seed-01", "athlete-01", today_str, "breakfast", "Boiled Eggs", 2.0, "large", 144.0, 12.6, 0.8, 9.8, 0.0, "verified_db", 1, now_iso),
                ("food-seed-02", "athlete-01", today_str, "breakfast", "Oatmeal with Almond Milk", 1.0, "bowl (250g)", 210.0, 6.0, 38.0, 4.0, 4.5, "verified_db", 1, now_iso),
                ("food-seed-03", "athlete-01", today_str, "lunch", "Grilled Chicken Breast with Brown Rice", 1.0, "plate (350g)", 480.0, 42.0, 52.0, 8.5, 3.5, "verified_db", 1, now_iso),
                ("food-seed-04", "athlete-01", today_str, "snack", "Greek Yogurt with Berries", 1.0, "cup (150g)", 130.0, 15.0, 12.0, 2.0, 2.0, "verified_db", 1, now_iso),
            ]
            cursor.executemany("""
                INSERT OR IGNORE INTO food_entries
                (entry_id, athlete_id, date, meal_type, food_name, quantity, unit, calories, protein_g, carbs_g, fat_g, fiber_g, data_source, is_verified, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, starter_food)

            # Seed sample body measurements
            starter_measurements = [
                ("meas-seed-01", "athlete-01", "2026-10-25", 75.2, 84.5, 17.5, "scale", "Initial baseline check", now_iso),
                ("meas-seed-02", "athlete-01", "2026-10-27", 74.9, 84.2, 17.3, "scale", "Morning post-run weigh in", now_iso),
                ("meas-seed-03", "athlete-01", "2026-10-29", 74.6, 83.8, 17.1, "scale", "Rest day morning weigh in", now_iso),
                ("meas-seed-04", "athlete-01", today_str, 74.3, 83.5, 16.9, "scale", "Weekly progress check", now_iso),
            ]
            cursor.executemany("""
                INSERT OR IGNORE INTO body_measurements
                (measurement_id, athlete_id, date, weight_kg, waist_cm, body_fat_pct, measurement_method, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, starter_measurements)

        conn.commit()
        if self._mem_conn is None:
            conn.close()

    def log_workout(
        self,
        activity_type: str,
        duration_minutes: int,
        distance_km: float,
        avg_heart_rate: int,
        intensity_zone: str,
        notes: str,
        athlete_id: str = "athlete-01",
        workout_id: str | None = None,
        date_str: str | None = None,
    ) -> dict[str, Any]:
        """Logs a workout and returns the recorded dictionary."""
        if not workout_id:
            workout_id = f"workout-{int(datetime.datetime.now().timestamp() * 1000)}-{uuid.uuid4().hex[:6]}"
        if not date_str:
            date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

        # Validate inputs
        if duration_minutes <= 0:
            raise ValueError(f"Duration minutes must be positive. Received {duration_minutes}")
        if distance_km < 0:
            raise ValueError(f"Distance cannot be negative. Received {distance_km}")
        if avg_heart_rate <= 30 or avg_heart_rate > 240:
            raise ValueError(f"Invalid average heart rate: {avg_heart_rate}. Must be between 30 and 240 bpm.")

        doc_data = {
            "workout_id": workout_id,
            "athlete_id": athlete_id,
            "activity_type": activity_type,
            "duration_minutes": int(duration_minutes),
            "distance_km": float(distance_km),
            "avg_heart_rate": int(avg_heart_rate),
            "intensity_zone": intensity_zone,
            "notes": notes,
            "date": date_str,
        }

        if self.use_firestore and _firestore_client:
            _firestore_client.collection("workouts").document(workout_id).set(doc_data)
        else:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO workouts
                (workout_id, athlete_id, activity_type, duration_minutes, distance_km, avg_heart_rate, intensity_zone, notes, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                workout_id, athlete_id, activity_type, duration_minutes,
                distance_km, avg_heart_rate, intensity_zone, notes, date_str
            ))
            conn.commit()
            if self._mem_conn is None:
                conn.close()

        return doc_data

    def list_workouts(self, athlete_id: str = "athlete-01", limit: int = 10) -> list[dict[str, Any]]:
        """Retrieves workout logs for an athlete."""
        if limit <= 0:
            return []

        if self.use_firestore and _firestore_client:
            query = _firestore_client.collection("workouts").where("athlete_id", "==", athlete_id).limit(limit)
            return [doc.to_dict() for doc in query.stream()]
        else:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT workout_id, athlete_id, activity_type, duration_minutes, distance_km, avg_heart_rate, intensity_zone, notes, date
                FROM workouts
                WHERE athlete_id = ?
                ORDER BY date DESC
                LIMIT ?
            """, (athlete_id, limit))
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            if self._mem_conn is None:
                conn.close()
            return results

    def get_workout_details(self, workout_id: str) -> dict[str, Any] | None:
        """Retrieves details of a specific workout log."""
        if self.use_firestore and _firestore_client:
            doc = _firestore_client.collection("workouts").document(workout_id).get()
            return doc.to_dict() if doc.exists else None
        else:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT workout_id, athlete_id, activity_type, duration_minutes, distance_km, avg_heart_rate, intensity_zone, notes, date
                FROM workouts
                WHERE workout_id = ?
            """, (workout_id,))
            row = cursor.fetchone()
            result = dict(row) if row else None
            if self._mem_conn is None:
                conn.close()
            return result

    def delete_workout(self, workout_id: str) -> bool:
        """Deletes a workout by ID."""
        if self.use_firestore and _firestore_client:
            _firestore_client.collection("workouts").document(workout_id).delete()
            return True
        else:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM workouts WHERE workout_id = ?", (workout_id,))
            conn.commit()
            count = cursor.rowcount
            if self._mem_conn is None:
                conn.close()
            return count > 0

    # ---------------- User Profile Methods ----------------
    def get_profile(self, athlete_id: str = "athlete-01") -> dict[str, Any]:
        """Retrieves user fitness profile or creates/returns default profile."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_profiles WHERE athlete_id = ?", (athlete_id,))
        row = cursor.fetchone()
        if row:
            res = dict(row)
        else:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            # If measurements already exist for this athlete, use the latest logged weight
            cursor.execute("SELECT weight_kg FROM body_measurements WHERE athlete_id = ? ORDER BY date DESC, created_at DESC LIMIT 1", (athlete_id,))
            meas_row = cursor.fetchone()
            starting_wt = float(meas_row[0]) if meas_row else 72.0

            res = {
                "athlete_id": athlete_id,
                "age": 28,
                "height_cm": 175.0,
                "current_weight_kg": starting_wt,
                "sex": "male",
                "activity_level": "moderate",
                "goal": "maintenance",
                "target_weight_kg": starting_wt,
                "preferred_units": "metric",
                "target_rate_change": 0.5,
                "updated_at": now_iso,
            }
            cursor.execute("""
                INSERT OR REPLACE INTO user_profiles
                (athlete_id, age, height_cm, current_weight_kg, sex, activity_level, goal, target_weight_kg, preferred_units, target_rate_change, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                res["athlete_id"], res["age"], res["height_cm"], res["current_weight_kg"],
                res["sex"], res["activity_level"], res["goal"], res["target_weight_kg"],
                res["preferred_units"], res["target_rate_change"], res["updated_at"]
            ))
            conn.commit()

        if self._mem_conn is None:
            conn.close()
        return res

    def save_profile(
        self,
        athlete_id: str,
        age: int,
        height_cm: float,
        current_weight_kg: float,
        sex: str,
        activity_level: str,
        goal: str,
        target_weight_kg: float | None = None,
        preferred_units: str = "metric",
        target_rate_change: float = 0.5,
    ) -> dict[str, Any]:
        """Saves or updates user fitness profile with strict validation."""
        if age < 10 or age > 120:
            raise ValueError(f"Invalid age: {age}. Must be between 10 and 120.")
        if height_cm < 50.0 or height_cm > 260.0:
            raise ValueError(f"Invalid height: {height_cm}. Must be between 50 and 260 cm.")
        if current_weight_kg < 20.0 or current_weight_kg > 350.0:
            raise ValueError(f"Invalid weight: {current_weight_kg}. Must be between 20 and 350 kg.")
        sex_clean = sex.strip().lower()
        if sex_clean not in ("male", "female"):
            raise ValueError(f"Invalid sex: {sex}. Must be 'male' or 'female'.")

        valid_activities = ("sedentary", "light", "moderate", "very_active", "extra_active")
        if activity_level.lower() not in valid_activities:
            raise ValueError(f"Unknown activity level: {activity_level}. Choose from {valid_activities}.")

        valid_goals = ("fat_loss", "muscle_gain", "maintenance", "aggressive_loss", "lean_bulk", "endurance_fuel")
        if goal.lower() not in valid_goals:
            raise ValueError(f"Unknown goal: {goal}. Choose from {valid_goals}.")

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        target_wt = float(target_weight_kg) if target_weight_kg is not None else float(current_weight_kg)

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO user_profiles
            (athlete_id, age, height_cm, current_weight_kg, sex, activity_level, goal, target_weight_kg, preferred_units, target_rate_change, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            athlete_id, int(age), float(height_cm), float(current_weight_kg),
            sex_clean, activity_level.lower(), goal.lower(), target_wt,
            preferred_units, float(target_rate_change), now_iso
        ))
        conn.commit()
        if self._mem_conn is None:
            conn.close()

        return {
            "athlete_id": athlete_id,
            "age": int(age),
            "height_cm": float(height_cm),
            "current_weight_kg": float(current_weight_kg),
            "sex": sex_clean,
            "activity_level": activity_level.lower(),
            "goal": goal.lower(),
            "target_weight_kg": target_wt,
            "preferred_units": preferred_units,
            "target_rate_change": float(target_rate_change),
            "updated_at": now_iso,
        }

    # ---------------- Food Tracking Methods ----------------
    def log_food_entry(
        self,
        athlete_id: str,
        date_str: str,
        meal_type: str,
        food_name: str,
        quantity: float,
        unit: str,
        calories: float,
        protein_g: float = 0.0,
        carbs_g: float = 0.0,
        fat_g: float = 0.0,
        fiber_g: float = 0.0,
        data_source: str = "manual",
        is_verified: bool = False,
        entry_id: str | None = None,
    ) -> dict[str, Any]:
        """Logs a single food or beverage consumption record."""
        if not food_name.strip():
            raise ValueError("Food name cannot be empty.")
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive. Received {quantity}.")
        if calories < 0:
            raise ValueError("Calories cannot be negative.")

        meal_clean = meal_type.strip().lower()
        valid_meals = ("breakfast", "lunch", "dinner", "snack", "snacks", "beverage", "beverages")
        if meal_clean not in valid_meals:
            raise ValueError(f"Invalid meal type: '{meal_type}'. Choose from {valid_meals}.")
        if meal_clean == "snacks":
            meal_clean = "snack"
        elif meal_clean == "beverages":
            meal_clean = "beverage"

        if not entry_id:
            entry_id = f"food-{int(datetime.datetime.now().timestamp() * 1000)}-{uuid.uuid4().hex[:6]}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        doc_data = {
            "entry_id": entry_id,
            "athlete_id": athlete_id,
            "date": date_str,
            "meal_type": meal_clean,
            "food_name": food_name.strip(),
            "quantity": float(quantity),
            "unit": unit.strip(),
            "calories": round(float(calories), 1),
            "protein_g": round(float(protein_g), 1),
            "carbs_g": round(float(carbs_g), 1),
            "fat_g": round(float(fat_g), 1),
            "fiber_g": round(float(fiber_g), 1),
            "data_source": data_source,
            "is_verified": 1 if is_verified else 0,
            "created_at": now_iso,
        }

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO food_entries
            (entry_id, athlete_id, date, meal_type, food_name, quantity, unit, calories, protein_g, carbs_g, fat_g, fiber_g, data_source, is_verified, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_data["entry_id"], doc_data["athlete_id"], doc_data["date"], doc_data["meal_type"],
            doc_data["food_name"], doc_data["quantity"], doc_data["unit"], doc_data["calories"],
            doc_data["protein_g"], doc_data["carbs_g"], doc_data["fat_g"], doc_data["fiber_g"],
            doc_data["data_source"], doc_data["is_verified"], doc_data["created_at"]
        ))
        conn.commit()
        if self._mem_conn is None:
            conn.close()

        return doc_data

    def get_food_entries(
        self,
        athlete_id: str = "athlete-01",
        date_str: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves food logs for an athlete, filtered by date or date range."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if date_str:
            cursor.execute("""
                SELECT * FROM food_entries
                WHERE athlete_id = ? AND date = ?
                ORDER BY created_at ASC
            """, (athlete_id, date_str))
        elif start_date and end_date:
            cursor.execute("""
                SELECT * FROM food_entries
                WHERE athlete_id = ? AND date >= ? AND date <= ?
                ORDER BY date ASC, created_at ASC
            """, (athlete_id, start_date, end_date))
        else:
            cursor.execute("""
                SELECT * FROM food_entries
                WHERE athlete_id = ?
                ORDER BY date DESC, created_at DESC
                LIMIT 100
            """, (athlete_id,))

        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        if self._mem_conn is None:
            conn.close()
        return results

    def update_food_entry(self, entry_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Updates nutritional fields of an existing food entry."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM food_entries WHERE entry_id = ?", (entry_id,))
        row = cursor.fetchone()
        if not row:
            if self._mem_conn is None:
                conn.close()
            return None

        current = dict(row)
        for key in ("food_name", "quantity", "unit", "calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "meal_type", "is_verified"):
            if key in updates:
                current[key] = updates[key]

        cursor.execute("""
            UPDATE food_entries
            SET food_name = ?, quantity = ?, unit = ?, calories = ?, protein_g = ?, carbs_g = ?, fat_g = ?, fiber_g = ?, meal_type = ?, is_verified = ?
            WHERE entry_id = ?
        """, (
            current["food_name"], float(current["quantity"]), current["unit"], float(current["calories"]),
            float(current["protein_g"]), float(current["carbs_g"]), float(current["fat_g"]), float(current["fiber_g"]),
            current["meal_type"], 1 if current["is_verified"] else 0, entry_id
        ))
        conn.commit()
        if self._mem_conn is None:
            conn.close()
        return current

    def delete_food_entry(self, entry_id: str) -> bool:
        """Deletes a food entry by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM food_entries WHERE entry_id = ?", (entry_id,))
        conn.commit()
        count = cursor.rowcount
        if self._mem_conn is None:
            conn.close()
        return count > 0

    # ---------------- Physical Activity Tracking Methods ----------------
    def log_activity_entry(
        self,
        athlete_id: str,
        date_str: str,
        activity_type: str,
        duration_minutes: int,
        intensity: str = "moderate",
        distance_km: float = 0.0,
        steps: int = 0,
        calories_burned: float = 0.0,
        strength_details_json: str = "[]",
        data_source: str = "manual",
        activity_id: str | None = None,
    ) -> dict[str, Any]:
        """Logs physical activity or strength workout."""
        if duration_minutes <= 0:
            raise ValueError(f"Duration minutes must be positive. Received {duration_minutes}.")
        if calories_burned < 0:
            raise ValueError("Calories burned cannot be negative.")

        if not activity_id:
            activity_id = f"act-{int(datetime.datetime.now().timestamp() * 1000)}-{uuid.uuid4().hex[:6]}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        doc_data = {
            "activity_id": activity_id,
            "athlete_id": athlete_id,
            "date": date_str,
            "activity_type": activity_type.strip(),
            "duration_minutes": int(duration_minutes),
            "intensity": intensity.strip().lower(),
            "distance_km": round(float(distance_km), 2),
            "steps": int(steps),
            "calories_burned": round(float(calories_burned), 1),
            "strength_details_json": strength_details_json,
            "data_source": data_source,
            "created_at": now_iso,
        }

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO activity_entries
            (activity_id, athlete_id, date, activity_type, duration_minutes, intensity, distance_km, steps, calories_burned, strength_details_json, data_source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_data["activity_id"], doc_data["athlete_id"], doc_data["date"], doc_data["activity_type"],
            doc_data["duration_minutes"], doc_data["intensity"], doc_data["distance_km"], doc_data["steps"],
            doc_data["calories_burned"], doc_data["strength_details_json"], doc_data["data_source"], doc_data["created_at"]
        ))
        conn.commit()
        if self._mem_conn is None:
            conn.close()

        return doc_data

    def get_activity_entries(
        self,
        athlete_id: str = "athlete-01",
        date_str: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves physical activity records for an athlete."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if date_str:
            cursor.execute("""
                SELECT * FROM activity_entries
                WHERE athlete_id = ? AND date = ?
                ORDER BY created_at ASC
            """, (athlete_id, date_str))
        elif start_date and end_date:
            cursor.execute("""
                SELECT * FROM activity_entries
                WHERE athlete_id = ? AND date >= ? AND date <= ?
                ORDER BY date ASC, created_at ASC
            """, (athlete_id, start_date, end_date))
        else:
            cursor.execute("""
                SELECT * FROM activity_entries
                WHERE athlete_id = ?
                ORDER BY date DESC, created_at DESC
                LIMIT 100
            """, (athlete_id,))

        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        if self._mem_conn is None:
            conn.close()
        return results

    def delete_activity_entry(self, activity_id: str) -> bool:
        """Deletes an activity entry by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM activity_entries WHERE activity_id = ?", (activity_id,))
        conn.commit()
        count = cursor.rowcount
        if self._mem_conn is None:
            conn.close()
        return count > 0

    # ---------------- Body Measurements Methods ----------------
    def log_measurement(
        self,
        athlete_id: str,
        date_str: str,
        weight_kg: float,
        waist_cm: float | None = None,
        body_fat_pct: float | None = None,
        measurement_method: str = "scale",
        notes: str = "",
        measurement_id: str | None = None,
    ) -> dict[str, Any]:
        """Logs a daily body measurement and keeps profile weight synced."""
        if weight_kg < 20.0 or weight_kg > 350.0:
            raise ValueError(f"Invalid weight: {weight_kg}. Must be between 20 and 350 kg.")
        if waist_cm is not None and (waist_cm < 30.0 or waist_cm > 250.0):
            raise ValueError(f"Invalid waist circumference: {waist_cm}. Must be between 30 and 250 cm.")
        if body_fat_pct is not None and (body_fat_pct < 2.0 or body_fat_pct > 70.0):
            raise ValueError(f"Invalid body fat percentage: {body_fat_pct}. Must be between 2 and 70%.")

        if not measurement_id:
            measurement_id = f"meas-{int(datetime.datetime.now().timestamp() * 1000)}-{uuid.uuid4().hex[:6]}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        doc_data = {
            "measurement_id": measurement_id,
            "athlete_id": athlete_id,
            "date": date_str,
            "weight_kg": round(float(weight_kg), 2),
            "waist_cm": round(float(waist_cm), 1) if waist_cm is not None else None,
            "body_fat_pct": round(float(body_fat_pct), 1) if body_fat_pct is not None else None,
            "measurement_method": measurement_method,
            "notes": notes.strip(),
            "created_at": now_iso,
        }

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO body_measurements
            (measurement_id, athlete_id, date, weight_kg, waist_cm, body_fat_pct, measurement_method, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_data["measurement_id"], doc_data["athlete_id"], doc_data["date"], doc_data["weight_kg"],
            doc_data["waist_cm"], doc_data["body_fat_pct"], doc_data["measurement_method"], doc_data["notes"],
            doc_data["created_at"]
        ))

        # Keep current profile weight synced to newest measurement
        cursor.execute("SELECT athlete_id FROM user_profiles WHERE athlete_id = ?", (athlete_id,))
        if cursor.fetchone():
            cursor.execute("""
                UPDATE user_profiles
                SET current_weight_kg = ?, updated_at = ?
                WHERE athlete_id = ?
            """, (doc_data["weight_kg"], now_iso, athlete_id))
        else:
            cursor.execute("""
                INSERT INTO user_profiles
                (athlete_id, age, height_cm, current_weight_kg, sex, activity_level, goal, target_weight_kg, preferred_units, target_rate_change, updated_at)
                VALUES (?, 28, 175.0, ?, 'male', 'moderate', 'maintenance', ?, 'metric', 0.5, ?)
            """, (athlete_id, doc_data["weight_kg"], doc_data["weight_kg"], now_iso))

        conn.commit()
        if self._mem_conn is None:
            conn.close()

        return doc_data

    def get_measurements(
        self,
        athlete_id: str = "athlete-01",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieves historical body measurements ordered chronologically."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if start_date and end_date:
            cursor.execute("""
                SELECT * FROM body_measurements
                WHERE athlete_id = ? AND date >= ? AND date <= ?
                ORDER BY date ASC
                LIMIT ?
            """, (athlete_id, start_date, end_date, limit))
        else:
            cursor.execute("""
                SELECT * FROM body_measurements
                WHERE athlete_id = ?
                ORDER BY date ASC
                LIMIT ?
            """, (athlete_id, limit))

        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        if self._mem_conn is None:
            conn.close()
        return results

    def delete_measurement(self, measurement_id: str) -> bool:
        """Deletes a body measurement by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM body_measurements WHERE measurement_id = ?", (measurement_id,))
        conn.commit()
        count = cursor.rowcount
        if self._mem_conn is None:
            conn.close()
        return count > 0

    # ---------------- Email Report Tracking Methods ----------------
    def log_email_report(
        self,
        athlete_id: str,
        recipient_email: str,
        report_date: str,
        report_period: str,
        summary_text: str,
        status: str,
        provider: str = "simulated",
        error_message: str = "",
        report_id: str | None = None,
    ) -> dict[str, Any]:
        """Logs an email report dispatch record."""
        if not report_id:
            report_id = f"email-{int(datetime.datetime.now().timestamp() * 1000)}-{uuid.uuid4().hex[:6]}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        doc_data = {
            "report_id": report_id,
            "athlete_id": athlete_id,
            "recipient_email": recipient_email.strip(),
            "report_date": report_date,
            "report_period": report_period,
            "summary_text": summary_text,
            "status": status,
            "provider": provider,
            "error_message": error_message,
            "sent_at": now_iso,
        }

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO email_reports
            (report_id, athlete_id, recipient_email, report_date, report_period, summary_text, status, provider, error_message, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_data["report_id"], doc_data["athlete_id"], doc_data["recipient_email"], doc_data["report_date"],
            doc_data["report_period"], doc_data["summary_text"], doc_data["status"], doc_data["provider"], doc_data["error_message"], doc_data["sent_at"]
        ))
        conn.commit()
        if self._mem_conn is None:
            conn.close()

        return doc_data

    def get_email_reports(self, athlete_id: str = "athlete-01", limit: int = 20) -> list[dict[str, Any]]:
        """Retrieves email delivery logs for an athlete."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM email_reports
            WHERE athlete_id = ?
            ORDER BY sent_at DESC
            LIMIT ?
        """, (athlete_id, limit))
        rows = cursor.fetchall()
        results = [dict(row) for row in rows]
        if self._mem_conn is None:
            conn.close()
        return results

    # ---------------- Email Subscription & Consent Methods ----------------
    def get_email_subscription(self, athlete_id: str = "athlete-01") -> dict[str, Any] | None:
        """Retrieves user's email subscription and verification state."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_subscriptions WHERE athlete_id = ?", (athlete_id,))
        row = cursor.fetchone()
        if self._mem_conn is None:
            conn.close()
        if not row:
            return None
        d = dict(row)
        d["is_verified"] = bool(d["is_verified"])
        d["user_consent"] = bool(d["user_consent"])
        return d

    def save_email_subscription(
        self,
        athlete_id: str,
        email: str,
        report_frequency: str = "daily",
        user_consent: bool = True,
        preferred_time_utc: str = "08:00",
    ) -> dict[str, Any]:
        """Saves or updates email subscription preferences, issuing a verification token."""
        clean_email = email.strip().lower()
        if not clean_email or "@" not in clean_email or "." not in clean_email:
            raise ValueError(f"Invalid email address '{email}'.")

        allowed_freq = ("daily", "weekly", "both", "none")
        if report_frequency.lower() not in allowed_freq:
            raise ValueError(f"Invalid report frequency '{report_frequency}'. Must be one of: {allowed_freq}")

        existing = self.get_email_subscription(athlete_id)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # If email changed or not yet verified, generate a new token
        if existing and existing.get("email") == clean_email:
            verification_token = existing["verification_token"]
            is_verified = 1 if existing["is_verified"] else 0
        else:
            verification_token = uuid.uuid4().hex[:12]
            is_verified = 0

        consent_int = 1 if user_consent else 0
        consent_ts = now_iso if user_consent else (existing["consent_timestamp"] if existing else None)

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO email_subscriptions
            (athlete_id, email, is_verified, verification_token, user_consent, consent_timestamp, report_frequency, preferred_time_utc, updated_at, last_sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            athlete_id, clean_email, is_verified, verification_token, consent_int,
            consent_ts, report_frequency.lower(), preferred_time_utc, now_iso,
            existing.get("last_sent_at") if existing else None
        ))
        conn.commit()
        if self._mem_conn is None:
            conn.close()

        return {
            "athlete_id": athlete_id,
            "email": clean_email,
            "is_verified": bool(is_verified),
            "verification_token": verification_token,
            "user_consent": bool(consent_int),
            "consent_timestamp": consent_ts,
            "report_frequency": report_frequency.lower(),
            "preferred_time_utc": preferred_time_utc,
            "updated_at": now_iso,
        }

    def verify_email_subscription(self, athlete_id: str, token: str) -> bool:
        """Verifies email address using the supplied token."""
        sub = self.get_email_subscription(athlete_id)
        if not sub:
            return False
        if sub["verification_token"] != token.strip():
            return False

        conn = self._get_connection()
        cursor = conn.cursor()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("""
            UPDATE email_subscriptions
            SET is_verified = 1, updated_at = ?
            WHERE athlete_id = ?
        """, (now_iso, athlete_id))
        conn.commit()
        if self._mem_conn is None:
            conn.close()
        return True

    def get_active_subscribers(self, frequency: str = "daily") -> list[dict[str, Any]]:
        """Returns all verified athletes who gave consent and want the specified report frequency."""
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM email_subscriptions
            WHERE is_verified = 1
              AND user_consent = 1
              AND (report_frequency = ? OR report_frequency = 'both')
        """, (frequency.lower(),))
        rows = cursor.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["is_verified"] = bool(d["is_verified"])
            d["user_consent"] = bool(d["user_consent"])
            results.append(d)
        if self._mem_conn is None:
            conn.close()
        return results

    def update_subscriber_last_sent(self, athlete_id: str, sent_at: str | None = None):
        """Updates last sent timestamp for a subscriber."""
        ts = sent_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE email_subscriptions
            SET last_sent_at = ?
            WHERE athlete_id = ?
        """, (ts, athlete_id))
        conn.commit()
        if self._mem_conn is None:
            conn.close()

    def clear(self):
        """Clears all records (primarily for test cleanup)."""
        if not self.use_firestore:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM workouts")
            cursor.execute("DELETE FROM user_profiles")
            cursor.execute("DELETE FROM food_entries")
            cursor.execute("DELETE FROM activity_entries")
            cursor.execute("DELETE FROM body_measurements")
            cursor.execute("DELETE FROM email_reports")
            cursor.execute("DELETE FROM email_subscriptions")
            conn.commit()
            if self._mem_conn is None:
                conn.close()


default_db = WorkoutDatabase()
