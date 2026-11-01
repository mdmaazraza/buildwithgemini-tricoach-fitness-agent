"""Unit Tests for Expanded Database Methods (app/db.py).

Tests:
1. User Profile CRUD & Input Validation.
2. Food Logging CRUD, Date Filtering & Updates.
3. Physical Activity Tracking CRUD & Strength Details.
4. Body Measurements CRUD & Automatic Profile Weight Sync.
5. Email Report Logging & Retrieval.
"""

import pytest
from app.db import WorkoutDatabase


@pytest.fixture
def test_db():
    """Provides a fresh isolated in-memory database."""
    db = WorkoutDatabase(db_path=":memory:")
    yield db
    db.clear()


class TestUserProfileCRUD:
    """Tests profile management."""

    def test_default_profile_creation(self, test_db):
        prof = test_db.get_profile("athlete-new")
        assert prof["athlete_id"] == "athlete-new"
        assert prof["current_weight_kg"] == 72.0
        assert prof["goal"] == "maintenance"

    def test_save_valid_profile(self, test_db):
        saved = test_db.save_profile(
            athlete_id="athlete-02",
            age=32,
            height_cm=182.5,
            current_weight_kg=78.0,
            sex="male",
            activity_level="very_active",
            goal="fat_loss",
            target_weight_kg=74.0,
        )
        assert saved["age"] == 32
        assert saved["current_weight_kg"] == 78.0
        assert saved["goal"] == "fat_loss"

        fetched = test_db.get_profile("athlete-02")
        assert fetched["current_weight_kg"] == 78.0

    @pytest.mark.parametrize("invalid_age", [5, 130])
    def test_invalid_age_raises_error(self, test_db, invalid_age):
        with pytest.raises(ValueError, match="Invalid age"):
            test_db.save_profile("ath", invalid_age, 175, 70, "male", "moderate", "maintenance")

    def test_invalid_sex_raises_error(self, test_db):
        with pytest.raises(ValueError, match="Invalid sex"):
            test_db.save_profile("ath", 30, 175, 70, "unknown", "moderate", "maintenance")

    def test_invalid_goal_raises_error(self, test_db):
        with pytest.raises(ValueError, match="Unknown goal"):
            test_db.save_profile("ath", 30, 175, 70, "male", "moderate", "super_powers")


class TestFoodTrackingCRUD:
    """Tests food logging and modifications."""

    def test_log_and_retrieve_food_entry(self, test_db):
        entry = test_db.log_food_entry(
            athlete_id="ath-food-01",
            date_str="2026-10-31",
            meal_type="breakfast",
            food_name="Boiled Eggs",
            quantity=2.0,
            unit="large",
            calories=144.0,
            protein_g=12.6,
            carbs_g=0.8,
            fat_g=9.8,
            fiber_g=0.0,
            is_verified=True,
        )
        assert entry["food_name"] == "Boiled Eggs"
        assert entry["calories"] == 144.0

        entries = test_db.get_food_entries(athlete_id="ath-food-01", date_str="2026-10-31")
        assert len(entries) == 1
        assert entries[0]["food_name"] == "Boiled Eggs"

    def test_food_input_validation(self, test_db):
        with pytest.raises(ValueError, match="Food name cannot be empty"):
            test_db.log_food_entry("ath", "2026-10-31", "lunch", "   ", 1.0, "bowl", 100)

        with pytest.raises(ValueError, match="Quantity must be positive"):
            test_db.log_food_entry("ath", "2026-10-31", "lunch", "Rice", -1.0, "bowl", 100)

        with pytest.raises(ValueError, match="Invalid meal type"):
            test_db.log_food_entry("ath", "2026-10-31", "midnight_craving", "Cookie", 1.0, "piece", 100)

    def test_update_and_delete_food_entry(self, test_db):
        entry = test_db.log_food_entry("ath-01", "2026-10-31", "dinner", "Pasta", 1.0, "plate", 450)
        e_id = entry["entry_id"]

        updated = test_db.update_food_entry(e_id, {"quantity": 2.0, "calories": 900.0})
        assert updated["quantity"] == 2.0
        assert updated["calories"] == 900.0

        deleted = test_db.delete_food_entry(e_id)
        assert deleted is True
        assert len(test_db.get_food_entries("ath-01", date_str="2026-10-31")) == 0


class TestActivityTrackingCRUD:
    """Tests activity logging and queries."""

    def test_log_cardio_and_strength_activities(self, test_db):
        act1 = test_db.log_activity_entry(
            athlete_id="ath-act",
            date_str="2026-10-31",
            activity_type="Run",
            duration_minutes=45,
            intensity="vigorous",
            distance_km=8.5,
            steps=7800,
            calories_burned=520.0,
        )
        assert act1["activity_type"] == "Run"
        assert act1["calories_burned"] == 520.0

        act2 = test_db.log_activity_entry(
            athlete_id="ath-act",
            date_str="2026-10-31",
            activity_type="Gym Strength",
            duration_minutes=50,
            intensity="moderate",
            calories_burned=280.0,
            strength_details_json='[{"exercise": "Deadlift", "sets": 4, "reps": 8, "weight_kg": 100}]',
        )
        assert "Deadlift" in act2["strength_details_json"]

        all_acts = test_db.get_activity_entries(athlete_id="ath-act", date_str="2026-10-31")
        assert len(all_acts) == 2


class TestBodyMeasurementsCRUD:
    """Tests body measurements and automatic profile weight sync."""

    def test_log_measurement_syncs_profile_weight(self, test_db):
        # Initial profile
        test_db.save_profile("ath-meas", 28, 175, 75.0, "male", "moderate", "fat_loss")
        assert test_db.get_profile("ath-meas")["current_weight_kg"] == 75.0

        # Log new measurement
        meas = test_db.log_measurement(
            athlete_id="ath-meas",
            date_str="2026-10-31",
            weight_kg=73.8,
            waist_cm=83.0,
            body_fat_pct=16.5,
            notes="Morning post-rest",
        )
        assert meas["weight_kg"] == 73.8

        # Profile weight should be updated to 73.8
        updated_prof = test_db.get_profile("ath-meas")
        assert updated_prof["current_weight_kg"] == 73.8

    def test_log_measurement_without_prior_profile_initializes_profile_weight(self, test_db):
        # Direct measurement without prior save_profile() call
        test_db.log_measurement("ath-newbie", "2026-11-01", weight_kg=78.4, waist_cm=85.0)
        prof = test_db.get_profile("ath-newbie")
        assert prof["current_weight_kg"] == 78.4

    def test_measurement_validation(self, test_db):
        with pytest.raises(ValueError, match="Invalid weight"):
            test_db.log_measurement("ath", "2026-10-31", 10.0)

        with pytest.raises(ValueError, match="Invalid waist"):
            test_db.log_measurement("ath", "2026-10-31", 70.0, waist_cm=15.0)


class TestEmailReportsCRUD:
    """Tests email report logging and retrieval."""

    def test_log_email_report(self, test_db):
        rep = test_db.log_email_report(
            athlete_id="ath-rep",
            recipient_email="user@example.com",
            report_date="2026-10-31",
            report_period="weekly",
            summary_text="Weekly summary: 500 kcal daily deficit, 3 workouts completed.",
            status="simulated",
        )
        assert rep["status"] == "simulated"

        reports = test_db.get_email_reports("ath-rep")
        assert len(reports) == 1
        assert reports[0]["recipient_email"] == "user@example.com"
