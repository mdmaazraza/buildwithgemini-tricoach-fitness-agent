"""Unit Tests for Input Validation and Error Handling.

Tests:
- Out of bound values for weight, height, age
- Invalid activity levels and unknown goal names
- Invalid workout durations, distances, and heart rates
- Meaningful error messages and exception types
"""

import pytest

from app.fitness_math import (
    calculate_bmr,
    calculate_daily_calories_and_macros,
    calculate_tdee,
)


class TestCalorieInputValidation:
    """Tests input validation on calorie & nutrition functions."""

    @pytest.mark.parametrize("invalid_weight", [-5, 0, 15, 400])
    def test_invalid_weight_raises_error(self, invalid_weight):
        with pytest.raises(ValueError, match="Invalid weight"):
            calculate_bmr(weight_kg=invalid_weight, height_cm=175, age=25, gender="male")

    @pytest.mark.parametrize("invalid_height", [-10, 50, 300])
    def test_invalid_height_raises_error(self, invalid_height):
        with pytest.raises(ValueError, match="Invalid height"):
            calculate_bmr(weight_kg=70, height_cm=invalid_height, age=25, gender="male")

    @pytest.mark.parametrize("invalid_age", [-1, 5, 130])
    def test_invalid_age_raises_error(self, invalid_age):
        with pytest.raises(ValueError, match="Invalid age"):
            calculate_bmr(weight_kg=70, height_cm=175, age=invalid_age, gender="male")

    def test_invalid_gender_raises_error(self):
        with pytest.raises(ValueError, match="Invalid gender"):
            calculate_bmr(weight_kg=70, height_cm=175, age=25, gender="other_species")

    def test_invalid_tdee_activity_raises_error(self):
        with pytest.raises(ValueError, match="Unknown activity level"):
            calculate_tdee(bmr=1500, activity_level="couch_potato")

    def test_invalid_goal_raises_error(self):
        with pytest.raises(ValueError, match="Unknown goal"):
            calculate_daily_calories_and_macros(
                weight_kg=70, height_cm=175, age=25, gender="male",
                activity_level="moderate", goal="superhuman"
            )


class TestWorkoutInputValidation:
    """Tests input validation for workout logging."""

    def test_negative_workout_duration_raises_error(self, in_memory_db):
        with pytest.raises(ValueError, match="Duration minutes must be positive"):
            in_memory_db.log_workout(
                activity_type="Run",
                duration_minutes=-30,
                distance_km=5.0,
                avg_heart_rate=150,
                intensity_zone="Zone 3",
                notes="",
            )

    def test_negative_distance_raises_error(self, in_memory_db):
        with pytest.raises(ValueError, match="Distance cannot be negative"):
            in_memory_db.log_workout(
                activity_type="Swim",
                duration_minutes=40,
                distance_km=-1.5,
                avg_heart_rate=140,
                intensity_zone="Zone 2",
                notes="",
            )

    @pytest.mark.parametrize("invalid_hr", [10, 260])
    def test_invalid_heart_rate_raises_error(self, in_memory_db, invalid_hr):
        with pytest.raises(ValueError, match="Invalid average heart rate"):
            in_memory_db.log_workout(
                activity_type="Bike",
                duration_minutes=60,
                distance_km=25.0,
                avg_heart_rate=invalid_hr,
                intensity_zone="Zone 2",
                notes="",
            )
