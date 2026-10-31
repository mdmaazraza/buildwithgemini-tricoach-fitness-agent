"""Unit Tests for Calorie & Nutrition Calculations.

Tests:
- BMR Mifflin-St Jeor formula (male & female)
- TDEE multipliers
- Daily calorie targets by fitness goal
- Macronutrient distribution (protein, fat, carbs)
- Minimum calorie floor enforcement
"""

import pytest
from app.fitness_math import (
    calculate_bmr,
    calculate_tdee,
    calculate_daily_calories_and_macros,
)


class TestBMRCalculations:
    """Tests for Basal Metabolic Rate calculation."""

    def test_bmr_male_calculation(self):
        # Male: 10 * 75kg + 6.25 * 180cm - 5 * 30 + 5
        # 750 + 1125 - 150 + 5 = 1730 kcal
        bmr = calculate_bmr(weight_kg=75.0, height_cm=180.0, age=30, gender="male")
        assert bmr == 1730.0

    def test_bmr_female_calculation(self):
        # Female: 10 * 60kg + 6.25 * 165cm - 5 * 25 - 161
        # 600 + 1031.25 - 125 - 161 = 1345.25 -> 1345.3 kcal
        bmr = calculate_bmr(weight_kg=60.0, height_cm=165.0, age=25, gender="female")
        assert bmr == 1345.2 or bmr == 1345.3

    def test_bmr_gender_normalization(self):
        bmr_m = calculate_bmr(weight_kg=70, height_cm=175, age=25, gender="M")
        bmr_male = calculate_bmr(weight_kg=70, height_cm=175, age=25, gender="Male")
        assert bmr_m == bmr_male

        bmr_f = calculate_bmr(weight_kg=55, height_cm=160, age=25, gender="f")
        bmr_female = calculate_bmr(weight_kg=55, height_cm=160, age=25, gender="Female")
        assert bmr_f == bmr_female


class TestTDEECalculations:
    """Tests for Total Daily Energy Expenditure calculation."""

    @pytest.mark.parametrize(
        "level,multiplier",
        [
            ("sedentary", 1.2),
            ("light", 1.375),
            ("moderate", 1.55),
            ("very_active", 1.725),
            ("extra_active", 1.9),
        ],
    )
    def test_tdee_multipliers(self, level, multiplier):
        bmr = 1600.0
        expected = round(bmr * multiplier, 1)
        assert calculate_tdee(bmr, level) == expected

    def test_tdee_case_insensitivity(self):
        assert calculate_tdee(1500.0, "MODERATE") == calculate_tdee(1500.0, "moderate")


class TestDailyCaloriesAndMacros:
    """Tests for complete daily nutrition targets and macronutrient distributions."""

    def test_maintenance_calories(self, sample_athlete):
        res = calculate_daily_calories_and_macros(**sample_athlete)
        assert res["goal"] == "endurance_fuel"
        assert res["target_calories"] == round(res["tdee"] + 500)
        assert res["macros"]["protein_grams"] == round(72.5 * 1.8, 1)
        assert res["macros"]["fat_grams"] > 0
        assert res["macros"]["carbs_grams"] > 0

    def test_fat_loss_calorie_reduction(self, sample_female_athlete):
        res = calculate_daily_calories_and_macros(**sample_female_athlete)
        assert res["goal"] == "fat_loss"
        assert res["calorie_adjustment"] == -500
        assert res["target_calories"] == round(res["tdee"] - 500)

    def test_minimum_calorie_floor(self):
        # Very low weight/height should not drop below safety floor of 1200 kcal
        res = calculate_daily_calories_and_macros(
            weight_kg=40.0,
            height_cm=140.0,
            age=60,
            gender="female",
            activity_level="sedentary",
            goal="aggressive_loss",
        )
        assert res["target_calories"] >= 1200
