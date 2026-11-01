"""Unit Tests for Fitness Calculation & Analytics Engine (app/tracker_engine.py).

Tests:
1. Daily Nutrition Summary (calories, macros, meal grouping, adherence).
2. Energy Expenditure & Calorie Balance (Mifflin BMR, double-counting prevention, net balance).
3. Fat Loss, Muscle Gain & Rolling Trends (7-day average, waist deltas, explicit uncertainties).
4. Progress Confidence / Data Quality Indicator (0-100% scoring).
"""

from app.tracker_engine import (
    calculate_daily_nutrition_summary,
    calculate_daily_energy_balance,
    calculate_progress_trends,
    calculate_progress_confidence,
)


class TestDailyNutritionSummary:
    """Tests daily food aggregation and meal-wise breakdowns."""

    def test_nutrition_summary_aggregation(self):
        sample_food = [
            {"meal_type": "breakfast", "food_name": "Eggs", "calories": 140.0, "protein_g": 12.0, "carbs_g": 1.0, "fat_g": 10.0, "fiber_g": 0.0, "is_verified": 1},
            {"meal_type": "breakfast", "food_name": "Oatmeal", "calories": 200.0, "protein_g": 6.0, "carbs_g": 35.0, "fat_g": 4.0, "fiber_g": 4.0, "is_verified": 1},
            {"meal_type": "lunch", "food_name": "Chicken Breast", "calories": 300.0, "protein_g": 35.0, "carbs_g": 0.0, "fat_g": 6.0, "fiber_g": 0.0, "is_verified": 0},
            {"meal_type": "dinner", "food_name": "Salmon Salad", "calories": 450.0, "protein_g": 30.0, "carbs_g": 15.0, "fat_g": 20.0, "fiber_g": 5.0, "is_verified": 1},
            {"meal_type": "snack", "food_name": "Almonds", "calories": 160.0, "protein_g": 6.0, "carbs_g": 6.0, "fat_g": 14.0, "fiber_g": 3.0, "is_verified": 0},
        ]
        summary = calculate_daily_nutrition_summary(sample_food)
        totals = summary["totals"]
        assert totals["calories"] == 1250.0
        assert totals["protein_g"] == 89.0
        assert totals["carbs_g"] == 57.0
        assert totals["fat_g"] == 54.0
        assert totals["fiber_g"] == 12.0
        assert totals["verified_items_count"] == 3
        assert totals["unverified_items_count"] == 2

        # Verify meal breakdown
        meals = summary["meals"]
        assert meals["breakfast"]["calories"] == 340.0
        assert meals["breakfast"]["protein_g"] == 18.0
        assert meals["lunch"]["calories"] == 300.0
        assert meals["dinner"]["calories"] == 450.0
        assert meals["snack"]["calories"] == 160.0

    def test_nutrition_summary_with_profile_targets(self):
        sample_food = [
            {"meal_type": "lunch", "food_name": "Rice & Lentils", "calories": 600.0, "protein_g": 22.0, "carbs_g": 90.0, "fat_g": 12.0, "fiber_g": 8.0, "is_verified": 1},
        ]
        profile = {
            "current_weight_kg": 70.0,
            "height_cm": 175.0,
            "age": 25,
            "sex": "male",
            "activity_level": "moderate",
            "goal": "maintenance",
        }
        summary = calculate_daily_nutrition_summary(sample_food, profile=profile)
        assert "target_calories" in summary["targets"]
        assert summary["targets"]["target_calories"] > 0
        assert "calories_pct" in summary["adherence"]
        assert summary["adherence"]["calories_pct"] > 0

    def test_empty_food_summary(self):
        summary = calculate_daily_nutrition_summary([])
        assert summary["totals"]["calories"] == 0.0
        assert summary["totals"]["protein_g"] == 0.0
        assert summary["totals"]["item_count"] == 0


class TestEnergyExpenditureAndBalance:
    """Tests BMR, TDEE, double counting elimination, and net calorie balance."""

    def test_sedentary_additive_exercise_model(self):
        profile = {
            "current_weight_kg": 80.0,
            "height_cm": 180.0,
            "age": 30,
            "sex": "male",
            "activity_level": "sedentary",
        }
        activities = [
            {"activity_type": "Run", "duration_minutes": 45, "calories_burned": 450.0},
        ]
        food = [
            {"calories": 2000.0},
        ]
        res = calculate_daily_energy_balance(profile, activities, food)
        # BMR for 80kg, 180cm, 30yo male = 10*80 + 6.25*180 - 5*30 + 5 = 800 + 1125 - 150 + 5 = 1780
        # Sedentary TDEE = 1780 * 1.2 = 2136.0
        # Total expenditure = 2136 + 450 = 2586.0
        # Calorie balance = 2000 - 2586 = -586.0 (deficit)
        assert res["bmr"] == 1780.0
        assert res["baseline_tdee"] == 2136.0
        assert res["total_energy_expenditure"] == 2586.0
        assert res["estimated_calorie_balance"] == -586.0
        assert res["balance_status"] == "deficit"
        assert res["double_counting_prevented"] == 0.0

    def test_moderate_activity_prevents_double_counting(self):
        profile = {
            "current_weight_kg": 75.0,
            "height_cm": 175.0,
            "age": 28,
            "sex": "male",
            "activity_level": "moderate",  # 1.55 multiplier
        }
        # 400 kcal logged activity
        activities = [
            {"activity_type": "Bike", "duration_minutes": 40, "calories_burned": 400.0},
        ]
        food = [
            {"calories": 2800.0},
        ]
        res = calculate_daily_energy_balance(profile, activities, food)
        # BMR = 10*75 + 6.25*175 - 5*28 + 5 = 750 + 1093.75 - 140 + 5 = 1708.8
        # Built-in allowance = 1708.8 * (1.55 - 1.2) = 1708.8 * 0.35 = 598.1 kcal
        # Logged burn (400) <= allowance (598.1), so additional burn is 0, prevented is 400
        assert res["double_counting_prevented"] == 400.0
        assert res["additional_exercise_burn"] == 0.0
        assert res["total_energy_expenditure"] == res["baseline_tdee"]
        assert "Calorie balance is a mathematical estimate" in res["calculation_disclaimer"]


class TestProgressTrendsAndAnalytics:
    """Tests 7-day rolling weight, waist change, and progress hypotheses."""

    def test_rolling_7day_average_and_fat_loss_hypothesis(self):
        measurements = [
            {"date": "2026-10-20", "weight_kg": 80.0, "waist_cm": 90.0},
            {"date": "2026-10-21", "weight_kg": 79.8, "waist_cm": 90.0},
            {"date": "2026-10-22", "weight_kg": 79.5, "waist_cm": 89.5},
            {"date": "2026-10-23", "weight_kg": 79.3, "waist_cm": 89.5},
            {"date": "2026-10-24", "weight_kg": 79.1, "waist_cm": 89.0},
            {"date": "2026-10-25", "weight_kg": 79.0, "waist_cm": 89.0},
            {"date": "2026-10-26", "weight_kg": 78.8, "waist_cm": 88.5},
        ]
        profile = {"goal": "fat_loss", "current_weight_kg": 78.8}
        trends = calculate_progress_trends(measurements, profile=profile)

        assert trends["total_measurements"] == 7
        assert trends["latest_weight_kg"] == 78.8
        assert trends["earliest_weight_kg"] == 80.0
        assert trends["weight_change_total_kg"] == -1.2
        assert trends["waist_change_cm"] == -1.5
        assert len(trends["rolling_7d_history"]) == 7

        # Check interpretations and explicit uncertainties
        interp_text = " ".join(trends["interpretations"])
        assert "consistent with fat loss" in interp_text.lower()
        uncertainty_text = " ".join(trends["uncertainties"])
        assert "cannot isolate fat mass from lean muscle tissue" in uncertainty_text


class TestProgressConfidence:
    """Tests data quality / progress confidence scoring."""

    def test_high_confidence_with_full_records(self):
        food = [
            {"date": f"2026-10-{i}", "meal_type": "lunch", "is_verified": 1}
            for i in range(20, 27)
        ]
        activities = [
            {"date": f"2026-10-{i}", "duration_minutes": 30}
            for i in range(20, 25)
        ]
        measurements = [
            {"date": f"2026-10-{i}", "weight_kg": 75.0, "waist_cm": 82.0}
            for i in range(20, 25)
        ]
        conf = calculate_progress_confidence(food, activities, measurements, days_window=7)
        assert conf["confidence_score"] >= 75
        assert conf["confidence_tier"] == "High Confidence"
        assert "Confidence score evaluates data completeness" in conf["disclaimer"]

    def test_low_confidence_with_sparse_records(self):
        food = [{"date": "2026-10-26", "is_verified": 0}]
        activities = []
        measurements = []
        conf = calculate_progress_confidence(food, activities, measurements, days_window=7)
        assert conf["confidence_score"] < 50
        assert conf["confidence_tier"] == "Preliminary / Low Confidence"
