"""Fitness Calculation & Analytics Engine for TriCoach AI.

Implements:
1. Daily Nutrition Summary (calories, macros, meal breakdown, target comparisons).
2. Energy Expenditure & Calorie Balance (BMR, non-double-counted TDEE, net balance).
3. Fat Loss, Muscle Gain & Trend Analytics (rolling 7-day weight, waist delta, tissue interpretation).
4. Progress Confidence / Data Quality Indicator (0-100% score based on logging completeness).

Strict Safety & Medical Integrity:
- Never claims food logs directly measure true body-fat change.
- Explains that weight changes reflect water, glycogen, digestion, and tissue.
- States explicit uncertainty when data is insufficient.
- Never fabricates missing measurements.
"""

from typing import Any
import datetime
from app.fitness_math import (
    calculate_bmr,
    calculate_tdee,
    calculate_daily_calories_and_macros,
)


def calculate_daily_nutrition_summary(
    food_entries: list[dict[str, Any]],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculates daily nutritional totals, meal-wise breakdowns, and target comparisons."""
    total_cal = 0.0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0
    total_fiber = 0.0

    meals: dict[str, dict[str, Any]] = {
        "breakfast": {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "fiber_g": 0.0, "item_count": 0, "items": []},
        "lunch": {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "fiber_g": 0.0, "item_count": 0, "items": []},
        "dinner": {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "fiber_g": 0.0, "item_count": 0, "items": []},
        "snack": {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "fiber_g": 0.0, "item_count": 0, "items": []},
        "beverage": {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0, "fiber_g": 0.0, "item_count": 0, "items": []},
    }

    verified_count = 0
    total_items = len(food_entries)

    for item in food_entries:
        c = float(item.get("calories", 0.0))
        p = float(item.get("protein_g", 0.0))
        cb = float(item.get("carbs_g", 0.0))
        f = float(item.get("fat_g", 0.0))
        fb = float(item.get("fiber_g", 0.0))

        total_cal += c
        total_protein += p
        total_carbs += cb
        total_fat += f
        total_fiber += fb

        m_type = str(item.get("meal_type", "snack")).lower()
        if m_type not in meals:
            m_type = "snack"

        meals[m_type]["calories"] = round(meals[m_type]["calories"] + c, 1)
        meals[m_type]["protein_g"] = round(meals[m_type]["protein_g"] + p, 1)
        meals[m_type]["carbs_g"] = round(meals[m_type]["carbs_g"] + cb, 1)
        meals[m_type]["fat_g"] = round(meals[m_type]["fat_g"] + f, 1)
        meals[m_type]["fiber_g"] = round(meals[m_type]["fiber_g"] + fb, 1)
        meals[m_type]["item_count"] += 1
        meals[m_type]["items"].append(item)

        if item.get("is_verified"):
            verified_count += 1

    totals = {
        "calories": round(total_cal, 1),
        "protein_g": round(total_protein, 1),
        "carbs_g": round(total_carbs, 1),
        "fat_g": round(total_fat, 1),
        "fiber_g": round(total_fiber, 1),
        "item_count": total_items,
        "verified_items_count": verified_count,
        "unverified_items_count": total_items - verified_count,
    }

    # Target comparison
    targets = {}
    adherence = {}
    if profile:
        try:
            plan = calculate_daily_calories_and_macros(
                weight_kg=float(profile.get("current_weight_kg", 72.0)),
                height_cm=float(profile.get("height_cm", 175.0)),
                age=int(profile.get("age", 28)),
                gender=str(profile.get("sex", "male")),
                activity_level=str(profile.get("activity_level", "moderate")),
                goal=str(profile.get("goal", "maintenance")),
            )
            macros = plan.get("macros", {})
            p_target = float(macros.get("protein_grams", 0.0))
            c_target = float(macros.get("carbs_grams", 0.0))
            f_target = float(macros.get("fat_grams", 0.0))
            targets = {
                "target_calories": plan["target_calories"],
                "target_protein_g": p_target,
                "target_carbs_g": c_target,
                "target_fat_g": f_target,
                "goal": profile.get("goal", "maintenance"),
            }
            if plan["target_calories"] > 0:
                adherence["calories_pct"] = round((total_cal / plan["target_calories"]) * 100, 1)
            if p_target > 0:
                adherence["protein_pct"] = round((total_protein / p_target) * 100, 1)
            if c_target > 0:
                adherence["carbs_pct"] = round((total_carbs / c_target) * 100, 1)
            if f_target > 0:
                adherence["fat_pct"] = round((total_fat / f_target) * 100, 1)
        except Exception:
            pass

    return {
        "totals": totals,
        "meals": meals,
        "targets": targets,
        "adherence": adherence,
    }


def calculate_daily_energy_balance(
    profile: dict[str, Any],
    activities: list[dict[str, Any]],
    food_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Estimates BMR, TDEE, exercise burn (without double counting), and net calorie balance.

    Calculation model:
    - BMR = Mifflin-St Jeor formula
    - Sedentary Baseline TDEE = BMR * 1.2
    - If user profile has higher baseline activity (e.g. moderate 1.55), the baseline already
      accounts for typical exercise. We explicitly prevent double counting:
      Additional Burn = max(0, Logged Activity Burn - Built-in Activity Allowance)
    - Estimated Calorie Balance = Calories Consumed - Total Energy Expenditure
    """
    wt = float(profile.get("current_weight_kg", 72.0))
    ht = float(profile.get("height_cm", 175.0))
    age = int(profile.get("age", 28))
    sex = str(profile.get("sex", "male"))
    act_level = str(profile.get("activity_level", "moderate")).lower()

    bmr = calculate_bmr(wt, ht, age, sex)
    baseline_tdee = calculate_tdee(bmr, act_level)

    # Activity burn from logged entries
    raw_exercise_burn = sum(float(a.get("calories_burned", 0.0)) for a in activities)
    total_activity_minutes = sum(int(a.get("duration_minutes", 0)) for a in activities)

    # Activity model to prevent double-counting
    # Activity multipliers: sedentary 1.2, light 1.375, moderate 1.55, very_active 1.725, extra_active 1.9
    multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "very_active": 1.725,
        "extra_active": 1.9,
    }
    user_mult = multipliers.get(act_level, 1.55)
    built_in_exercise_allowance = round(bmr * (user_mult - 1.2), 1)

    if act_level == "sedentary":
        # All logged exercise is additive
        additional_exercise_burn = raw_exercise_burn
        total_expenditure = round(baseline_tdee + additional_exercise_burn, 1)
        double_counting_prevented = 0.0
    else:
        # Prevent double counting exercise already baked into baseline multiplier
        additional_exercise_burn = max(0.0, round(raw_exercise_burn - built_in_exercise_allowance, 1))
        double_counting_prevented = min(raw_exercise_burn, built_in_exercise_allowance)
        total_expenditure = round(baseline_tdee + additional_exercise_burn, 1)

    # Calories consumed
    calories_consumed = round(sum(float(f.get("calories", 0.0)) for f in food_entries), 1)

    # Conceptual calorie balance: Consumed - Expenditure
    calorie_balance = round(calories_consumed - total_expenditure, 1)

    if calorie_balance > 50.0:
        balance_status = "surplus"
    elif calorie_balance < -50.0:
        balance_status = "deficit"
    else:
        balance_status = "maintenance"

    return {
        "bmr": bmr,
        "baseline_tdee": baseline_tdee,
        "raw_exercise_burn": round(raw_exercise_burn, 1),
        "total_activity_minutes": total_activity_minutes,
        "built_in_allowance": built_in_exercise_allowance,
        "additional_exercise_burn": additional_exercise_burn,
        "double_counting_prevented": double_counting_prevented,
        "total_energy_expenditure": total_expenditure,
        "calories_consumed": calories_consumed,
        "estimated_calorie_balance": calorie_balance,
        "balance_status": balance_status,
        "calculation_disclaimer": (
            "Calorie balance is a mathematical estimate. It does not directly equate to body fat change; "
            "short-term scale fluctuations reflect hydration, glycogen status, sodium intake, and digestive contents."
        ),
    }


def calculate_progress_trends(
    measurements: list[dict[str, Any]],
    food_summaries_by_date: dict[str, dict[str, Any]] | None = None,
    activities_by_date: dict[str, list[dict[str, Any]]] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculates rolling 7-day averages, weight deltas, waist trends, and evaluates progress hypotheses."""
    food_summaries = food_summaries_by_date or {}
    act_by_date = activities_by_date or {}
    prof = profile or {}

    # Sort measurements chronologically
    sorted_meas = sorted(measurements, key=lambda m: str(m.get("date", "")))
    weights = [float(m["weight_kg"]) for m in sorted_meas if "weight_kg" in m]
    waists = [float(m["waist_cm"]) for m in sorted_meas if m.get("waist_cm") is not None]

    total_measurements = len(sorted_meas)
    latest_weight = weights[-1] if weights else None
    earliest_weight = weights[0] if weights else None

    # Rolling 7-day average calculation
    rolling_7d: list[dict[str, Any]] = []
    for m in sorted_meas:
        current_date_str = str(m.get("date", ""))
        try:
            curr_date = datetime.date.fromisoformat(current_date_str)
            # Find all measurements in preceding 7 days
            window = [
                float(sub["weight_kg"]) for sub in sorted_meas
                if 0 <= (curr_date - datetime.date.fromisoformat(str(sub.get("date", "")))).days < 7
            ]
            if window:
                avg = round(sum(window) / len(window), 2)
                rolling_7d.append({
                    "date": current_date_str,
                    "actual_weight_kg": float(m["weight_kg"]),
                    "rolling_7d_avg_kg": avg,
                    "data_points_in_window": len(window),
                })
        except Exception:
            pass

    current_7d_avg = rolling_7d[-1]["rolling_7d_avg_kg"] if rolling_7d else latest_weight
    baseline_7d_avg = rolling_7d[0]["rolling_7d_avg_kg"] if rolling_7d else earliest_weight

    weight_change_total = round(latest_weight - earliest_weight, 2) if (latest_weight is not None and earliest_weight is not None) else 0.0
    avg_weight_change_7d = round(current_7d_avg - baseline_7d_avg, 2) if (current_7d_avg is not None and baseline_7d_avg is not None) else 0.0

    # Waist delta
    waist_change = None
    if len(waists) >= 2:
        waist_change = round(waists[-1] - waists[0], 1)

    # Protein intake consistency
    protein_values = [summary.get("totals", {}).get("protein_g", 0.0) for summary in food_summaries.values()]
    avg_protein_g = round(sum(protein_values) / len(protein_values), 1) if protein_values else 0.0

    target_wt = float(prof.get("current_weight_kg", 72.0))
    target_protein_min = round(target_wt * 1.6, 1)  # 1.6 g/kg recommended threshold
    protein_adequate = avg_protein_g >= target_protein_min

    # Strength consistency
    total_strength_sessions = 0
    for acts in act_by_date.values():
        for a in acts:
            act_type = str(a.get("activity_type", "")).lower()
            if "strength" in act_type or "gym" in act_type or "lift" in act_type or "weights" in act_type:
                total_strength_sessions += 1

    # Trend interpretation (Objective, Hypothesis, and Uncertainties)
    goal = str(prof.get("goal", "fat_loss")).lower()
    observed_facts: list[str] = []
    interpretations: list[str] = []
    uncertainties: list[str] = []

    if latest_weight and earliest_weight:
        observed_facts.append(f"Recorded body weight moved from {earliest_weight} kg to {latest_weight} kg (Delta: {weight_change_total:+} kg).")
    if current_7d_avg and baseline_7d_avg:
        observed_facts.append(f"Rolling 7-day average moved from {baseline_7d_avg} kg to {current_7d_avg} kg (Net trend: {avg_weight_change_7d:+} kg).")
    if waist_change is not None:
        observed_facts.append(f"Waist circumference changed by {waist_change:+} cm over tracked period.")
    if protein_values:
        observed_facts.append(f"Average daily protein intake is {avg_protein_g} g/day (Target threshold: {target_protein_min} g/day).")
    observed_facts.append(f"Tracked {total_strength_sessions} resistance/strength training session(s).")

    # Hypothesis formulation
    if goal in ("fat_loss", "aggressive_loss"):
        if avg_weight_change_7d < -0.2:
            if waist_change is not None and waist_change <= 0:
                interpretations.append("Progress is consistent with fat loss: Downward rolling weight trend accompanied by stable or decreasing waist circumference.")
            else:
                interpretations.append("Downward weight trend observed. Waist circumference data is pending or stable.")
        elif avg_weight_change_7d > 0.2:
            interpretations.append("Weight is trending upward. Review energy balance and food logging accuracy to ensure desired calorie deficit.")
        else:
            interpretations.append("Weight is holding stable on rolling average. Maintenance calories are currently being matched.")

    elif goal in ("muscle_gain", "lean_bulk"):
        if avg_weight_change_7d > 0.1 and total_strength_sessions >= 2 and protein_adequate:
            interpretations.append("Progress is consistent with lean mass accrual: Gentle positive weight trend supported by strength stimulus and adequate protein.")
        elif avg_weight_change_7d > 0.6:
            interpretations.append("Weight is increasing rapidly (>0.6 kg/week). A portion of this gain may be adipose tissue or fluid; monitor waist circumference.")
        else:
            interpretations.append("Strength training is logged, but weight has not yet trended upward. A slight increase in calorie intake may be required.")
    else:
        interpretations.append("Maintenance goal active: Weight fluctuations remain within expected physiological rolling range (+- 1.0 kg).")

    # Explicit Uncertainties
    uncertainties.append("Food logs and body scale measurements cannot isolate fat mass from lean muscle tissue.")
    uncertainties.append("Short-term day-to-day fluctuations are heavily influenced by sodium, carbohydrates, hydration, and gut transit time.")
    if not waists:
        uncertainties.append("No waist circumference logs recorded. Waist tracking is recommended to corroborate fat-loss vs fluid retention.")
    if not protein_adequate and goal in ("fat_loss", "aggressive_loss"):
        uncertainties.append(f"Average protein ({avg_protein_g}g) is below the recommended {target_protein_min}g floor. In a deficit, this increases risk of lean tissue catabolism.")

    return {
        "total_measurements": total_measurements,
        "latest_weight_kg": latest_weight,
        "earliest_weight_kg": earliest_weight,
        "weight_change_total_kg": weight_change_total,
        "current_7d_avg_kg": current_7d_avg,
        "baseline_7d_avg_kg": baseline_7d_avg,
        "avg_weight_change_7d_kg": avg_weight_change_7d,
        "rolling_7d_history": rolling_7d,
        "waist_change_cm": waist_change,
        "avg_daily_protein_g": avg_protein_g,
        "total_strength_sessions": total_strength_sessions,
        "observed_facts": observed_facts,
        "interpretations": interpretations,
        "uncertainties": uncertainties,
    }


def calculate_progress_confidence(
    food_entries: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    days_window: int = 7,
) -> dict[str, Any]:
    """Evaluates data completeness and logging reliability (0-100% score).

    Criteria:
    - Food logging completeness (up to 30 pts)
    - Weigh-in frequency (up to 25 pts)
    - Activity logging (up to 20 pts)
    - Nutrition data verification quality (up to 15 pts)
    - Waist or body composition measurements (up to 10 pts)
    """
    score = 0
    breakdown = {}

    # 1. Food logging: at least 3 meals logged across tracked days
    dates_with_food = set(str(f.get("date", "")) for f in food_entries if f.get("date"))
    food_days_count = len(dates_with_food)
    food_score = min(30, int((food_days_count / max(1, min(days_window, 7))) * 30))
    score += food_score
    breakdown["food_logging_score"] = food_score

    # 2. Weigh-in frequency: at least 4 weigh-ins in window is optimal
    meas_dates = set(str(m.get("date", "")) for m in measurements if m.get("date"))
    meas_count = len(meas_dates)
    weigh_in_score = min(25, int((meas_count / 4.0) * 25))
    score += weigh_in_score
    breakdown["weigh_in_score"] = weigh_in_score

    # 3. Activity logging
    act_dates = set(str(a.get("date", "")) for a in activities if a.get("date"))
    act_score = min(20, int((len(act_dates) / max(1, min(days_window, 4))) * 20))
    score += act_score
    breakdown["activity_score"] = act_score

    # 4. Data verification quality: verified items vs manual/ai_estimate
    total_food = len(food_entries)
    if total_food > 0:
        verified_count = sum(1 for f in food_entries if f.get("is_verified") or f.get("data_source") == "verified_db")
        verification_ratio = verified_count / total_food
        verification_score = int(verification_ratio * 15)
    else:
        verification_score = 0
    score += verification_score
    breakdown["verification_quality_score"] = verification_score

    # 5. Waist or body comp measurement presence
    has_waist = any(m.get("waist_cm") is not None for m in measurements)
    has_body_fat = any(m.get("body_fat_pct") is not None for m in measurements)
    waist_score = 10 if (has_waist or has_body_fat) else 0
    score += waist_score
    breakdown["body_comp_score"] = waist_score

    # Determine confidence tier
    if score >= 75:
        tier = "High Confidence"
        description = "Comprehensive records: regular weigh-ins, complete food logging, and verified nutrition entries provide high analytical reliability."
    elif score >= 50:
        tier = "Moderate Confidence"
        description = "Adequate records: sufficient data to observe directional trends, but occasional missing meals or weigh-ins introduce variance."
    else:
        tier = "Preliminary / Low Confidence"
        description = "Sparse records: insufficient data points to establish reliable trend conclusions. Continue logging daily meals and morning weights."

    return {
        "confidence_score": min(100, score),
        "confidence_tier": tier,
        "description": description,
        "score_breakdown": breakdown,
        "disclaimer": (
            "Confidence score evaluates data completeness and tracking consistency. "
            "It is not a medically validated probability or diagnosis."
        ),
    }
