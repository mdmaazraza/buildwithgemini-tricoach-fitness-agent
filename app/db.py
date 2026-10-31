"""Database abstraction layer for TriCoach AI.

Supports:
- SQLite (default for testing, local development, and zero-cost deployments)
- Google Cloud Firestore (when explicitly enabled with USE_FIRESTORE=true)
"""

import os
import sqlite3
import datetime
import uuid
from typing import List, Dict, Any, Optional

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

    def __init__(self, db_path: Optional[str] = None):
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
        """Creates workouts table in SQLite if it doesn't already exist."""
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
        # Auto-seed starter workouts for new production databases
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
        workout_id: Optional[str] = None,
        date_str: Optional[str] = None,
    ) -> Dict[str, Any]:
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

    def list_workouts(self, athlete_id: str = "athlete-01", limit: int = 10) -> List[Dict[str, Any]]:
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

    def get_workout_details(self, workout_id: str) -> Optional[Dict[str, Any]]:
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

    def clear(self):
        """Clears all records (primarily for test cleanup)."""
        if not self.use_firestore:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM workouts")
            conn.commit()
            if self._mem_conn is None:
                conn.close()


default_db = WorkoutDatabase()
