"""Unit Tests for Workout Recommendation Logic and Training Zones.

Tests:
- Day-by-day triathlon workout periodization
- Level-specific volume adjustments (beginner vs advanced)
- Consecutive high-impact collision avoidance (Run -> Swim recovery)
- Karvonen 5-Zone calculation logic
"""

import pytest
import json
from app.fitness_math import recommend_workout, calculate_training_zones


class TestWorkoutRecommendations:
    """Tests for periodized triathlon workout recommendation logic."""

    def test_monday_recovery_swim(self):
        rec = recommend_workout(fitness_level="beginner", target_event="sprint", day_of_week="Monday")
        assert rec["activity_type"] == "Swim"
        assert rec["duration_minutes"] == 35
        assert "Zone 2" in rec["intensity_zone"]

    def test_saturday_brick_for_endurance_events(self):
        rec = recommend_workout(fitness_level="intermediate", target_event="olympic", day_of_week="Saturday")
        assert rec["activity_type"] == "Brick"
        assert rec["duration_minutes"] == 120

    def test_volume_scaling_by_experience(self):
        beg = recommend_workout(fitness_level="beginner", target_event="sprint", day_of_week="Sunday")
        adv = recommend_workout(fitness_level="advanced", target_event="sprint", day_of_week="Sunday")
        assert beg["duration_minutes"] < adv["duration_minutes"]

    def test_consecutive_run_avoidance(self):
        rec = recommend_workout(
            fitness_level="intermediate",
            target_event="olympic",
            day_of_week="Sunday",
            previous_activity="run",
        )
        assert rec["activity_type"] == "Swim"
        assert "recovery" in rec["description"].lower()


class TestKarvonenTrainingZones:
    """Tests for 5-Zone Karvonen heart rate calculation."""

    def test_karvonen_zones_calculation(self):
        raw = calculate_training_zones(max_heart_rate=190, resting_heart_rate=60)
        data = json.loads(raw)

        assert data["max_heart_rate"] == 190
        assert data["resting_heart_rate"] == 60
        assert data["heart_rate_reserve"] == 130

        zones = data["training_zones"]
        assert "Zone 1 (Active Recovery)" in zones
        assert "Zone 2 (Endurance / Aerobic)" in zones
        assert "Zone 3 (Tempo / Aerobic Power)" in zones
        assert "Zone 4 (Lactate Threshold)" in zones
        assert "Zone 5 (Anaerobic / VO2 Max)" in zones

    def test_karvonen_zones_boundary(self):
        raw = calculate_training_zones(max_heart_rate=180, resting_heart_rate=50)
        data = json.loads(raw)
        assert "115 - 128 BPM" in data["training_zones"]["Zone 1 (Active Recovery)"]
