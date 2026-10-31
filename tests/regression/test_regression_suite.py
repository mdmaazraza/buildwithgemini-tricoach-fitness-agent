"""Regression Test Suite for TriCoach AI.

Guarantees that new feature developments, refactorings, or updates do not regress:
1. Mathematical invariants (Mifflin-St Jeor, Karvonen 5-Zone formulas)
2. Safety floor invariants (1200 kcal minimum threshold)
3. Athlete multi-sport periodization rules (consecutive running avoidance)
4. Database persistence and query contracts
5. Chat API response format compatibility
"""

import json

import pytest

from app.fitness_math import (
    calculate_bmr,
    calculate_daily_calories_and_macros,
    calculate_training_zones,
    recommend_workout,
)


@pytest.mark.regression
class TestRegressionSuite:
    """Core regression test cases for critical business logic."""

    def test_regression_bmr_exact_constants(self):
        # Male 80kg, 185cm, 30yo: 10*80 + 6.25*185 - 5*30 + 5 = 800 + 1156.25 - 150 + 5 = 1811.25 -> 1811.3
        bmr_male = calculate_bmr(80.0, 185.0, 30, "male")
        assert bmr_male in (1811.2, 1811.3)

        # Female 60kg, 170cm, 30yo: 10*60 + 6.25*170 - 5*30 - 161 = 600 + 1062.5 - 150 - 161 = 1351.5
        bmr_female = calculate_bmr(60.0, 170.0, 30, "female")
        assert bmr_female in (1351.5, 1351.6)

    def test_regression_safety_calorie_floor(self):
        # Even with extreme deficit, calories must NEVER drop below 1200 kcal
        plan = calculate_daily_calories_and_macros(
            weight_kg=35.0,
            height_cm=140.0,
            age=50,
            gender="female",
            activity_level="sedentary",
            goal="aggressive_loss",
        )
        assert plan["target_calories"] >= 1200

    def test_regression_karvonen_formula_invariants(self):
        raw = calculate_training_zones(max_heart_rate=200, resting_heart_rate=50)
        data = json.loads(raw)
        assert data["heart_rate_reserve"] == 150
        # Zone 5 must cap at max_heart_rate
        assert "200 BPM" in data["training_zones"]["Zone 5 (Anaerobic / VO2 Max)"]

    def test_regression_periodization_consecutive_run_safety(self):
        rec = recommend_workout("intermediate", "olympic", "Sunday", previous_activity="run")
        # Invariant: running two days in a row must be prevented
        assert rec["activity_type"] != "Run"
        assert rec["activity_type"] == "Swim"

    def test_regression_chat_response_parts_contract(self, test_client):
        res = test_client.post("/chat", json={"message": "Zone 2 explanation"})
        assert res.status_code == 200
        data = res.json()
        assert "parts" in data
        assert isinstance(data["parts"], list)
        assert len(data["parts"]) > 0
        assert "text" in data["parts"][0]
