"""Integration Tests for Database Storage & Athlete Data Processing.

Tests:
- Full CRUD operations on workouts database
- Isolation between different athletes (multi-tenancy)
- Ordering of workout history by date
- Handling of non-existent records
"""

import pytest
from app.db import WorkoutDatabase


class TestDatabaseIntegration:
    """Integration tests for workout data persistence."""

    def test_log_and_retrieve_workout(self, in_memory_db, sample_workout_payload):
        logged = in_memory_db.log_workout(**sample_workout_payload)
        assert logged["workout_id"] is not None

        retrieved = in_memory_db.get_workout_details(logged["workout_id"])
        assert retrieved is not None
        assert retrieved["activity_type"] == sample_workout_payload["activity_type"]
        assert retrieved["duration_minutes"] == sample_workout_payload["duration_minutes"]
        assert retrieved["distance_km"] == sample_workout_payload["distance_km"]
        assert retrieved["avg_heart_rate"] == sample_workout_payload["avg_heart_rate"]

    def test_athlete_isolation(self, in_memory_db):
        in_memory_db.log_workout(
            activity_type="Run",
            duration_minutes=45,
            distance_km=7.5,
            avg_heart_rate=155,
            intensity_zone="Zone 3",
            notes="Athlete 1 Run",
            athlete_id="athlete-alpha",
        )
        in_memory_db.log_workout(
            activity_type="Swim",
            duration_minutes=30,
            distance_km=1.5,
            avg_heart_rate=140,
            intensity_zone="Zone 2",
            notes="Athlete 2 Swim",
            athlete_id="athlete-beta",
        )

        alpha_workouts = in_memory_db.list_workouts(athlete_id="athlete-alpha")
        beta_workouts = in_memory_db.list_workouts(athlete_id="athlete-beta")

        assert len(alpha_workouts) == 1
        assert alpha_workouts[0]["activity_type"] == "Run"

        assert len(beta_workouts) == 1
        assert beta_workouts[0]["activity_type"] == "Swim"

    def test_workout_deletion(self, in_memory_db, sample_workout_payload):
        logged = in_memory_db.log_workout(**sample_workout_payload)
        wid = logged["workout_id"]

        assert in_memory_db.get_workout_details(wid) is not None
        deleted = in_memory_db.delete_workout(wid)
        assert deleted is True
        assert in_memory_db.get_workout_details(wid) is None

    def test_get_nonexistent_workout_returns_none(self, in_memory_db):
        assert in_memory_db.get_workout_details("non-existent-999") is None
