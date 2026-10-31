"""TriCoach AI - Fitness & Nutrition Math Engine.

Provides validated calculations for:
- Basal Metabolic Rate (BMR) via Mifflin-St Jeor formula
- Total Daily Energy Expenditure (TDEE) with activity multipliers
- Goal-based daily caloric and macronutrient targets
- Karvonen 5-Zone Heart Rate calculation
- Workout recommendation & periodization logic
"""

import json
from typing import Any

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,          # Little or no exercise
    "light": 1.375,            # Light exercise 1-3 days/week
    "moderate": 1.55,          # Moderate exercise 3-5 days/week
    "very_active": 1.725,      # Hard exercise 6-7 days/week
    "extra_active": 1.9,       # Very hard exercise, physical job or 2x training
}

GOAL_CALORIE_ADJUSTMENTS = {
    "fat_loss": -500,
    "aggressive_loss": -750,
    "maintenance": 0,
    "lean_bulk": 300,
    "endurance_fuel": 500,     # High-volume triathlon training fuel
}


def calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """Calculates Basal Metabolic Rate (BMR) using the Mifflin-St Jeor equation."""
    if not isinstance(weight_kg, (int, float)) or weight_kg <= 20 or weight_kg > 350:
        raise ValueError(f"Invalid weight: {weight_kg} kg. Must be between 20 and 350 kg.")
    if not isinstance(height_cm, (int, float)) or height_cm <= 80 or height_cm > 260:
        raise ValueError(f"Invalid height: {height_cm} cm. Must be between 80 and 260 cm.")
    if not isinstance(age, int) or age < 10 or age > 120:
        raise ValueError(f"Invalid age: {age}. Must be between 10 and 120 years.")

    gender_norm = str(gender).strip().lower()
    if gender_norm not in ("male", "female", "m", "f"):
        raise ValueError(f"Invalid gender: '{gender}'. Must be 'male' or 'female'.")

    base = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age)
    if gender_norm in ("male", "m"):
        return round(base + 5.0, 1)
    else:
        return round(base - 161.0, 1)


def calculate_tdee(bmr: float, activity_level: str) -> float:
    """Calculates Total Daily Energy Expenditure (TDEE)."""
    if bmr <= 0:
        raise ValueError(f"BMR must be positive. Received: {bmr}")

    level_norm = str(activity_level).strip().lower()
    if level_norm not in ACTIVITY_MULTIPLIERS:
        valid_keys = ", ".join(ACTIVITY_MULTIPLIERS.keys())
        raise ValueError(f"Unknown activity level: '{activity_level}'. Choose from: {valid_keys}")

    multiplier = ACTIVITY_MULTIPLIERS[level_norm]
    return round(bmr * multiplier, 1)


def calculate_daily_calories_and_macros(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    activity_level: str,
    goal: str = "maintenance",
) -> dict[str, Any]:
    """Calculates complete daily calorie requirements and macro breakdown."""
    goal_norm = str(goal).strip().lower()
    if goal_norm not in GOAL_CALORIE_ADJUSTMENTS:
        valid_goals = ", ".join(GOAL_CALORIE_ADJUSTMENTS.keys())
        raise ValueError(f"Unknown goal: '{goal}'. Choose from: {valid_goals}")

    bmr = calculate_bmr(weight_kg, height_cm, age, gender)
    tdee = calculate_tdee(bmr, activity_level)
    adjustment = GOAL_CALORIE_ADJUSTMENTS[goal_norm]
    target_calories = max(round(tdee + adjustment), 1200)

    protein_g = round(weight_kg * 1.8, 1)
    protein_kcal = protein_g * 4.0

    fat_kcal = target_calories * 0.25
    fat_g = round(fat_kcal / 9.0, 1)

    carbs_kcal = max(target_calories - (protein_kcal + fat_kcal), 0.0)
    carbs_g = round(carbs_kcal / 4.0, 1)

    return {
        "bmr": bmr,
        "tdee": tdee,
        "goal": goal_norm,
        "calorie_adjustment": adjustment,
        "target_calories": target_calories,
        "macros": {
            "protein_grams": protein_g,
            "protein_calories": round(protein_kcal, 1),
            "carbs_grams": carbs_g,
            "carbs_calories": round(carbs_kcal, 1),
            "fat_grams": fat_g,
            "fat_calories": round(fat_kcal, 1),
        },
    }


def calculate_training_zones(max_heart_rate: int, resting_heart_rate: int = 60) -> str:
    """Calculates personalized 5-Zone heart rate training ranges using the Karvonen formula."""
    try:
        hrr = max_heart_rate - resting_heart_rate
        zones = {
            "Zone 1 (Active Recovery)": f"{int(resting_heart_rate + 0.50 * hrr)} - {int(resting_heart_rate + 0.60 * hrr)} BPM",
            "Zone 2 (Endurance / Aerobic)": f"{int(resting_heart_rate + 0.60 * hrr) + 1} - {int(resting_heart_rate + 0.70 * hrr)} BPM",
            "Zone 3 (Tempo / Aerobic Power)": f"{int(resting_heart_rate + 0.70 * hrr) + 1} - {int(resting_heart_rate + 0.80 * hrr)} BPM",
            "Zone 4 (Lactate Threshold)": f"{int(resting_heart_rate + 0.80 * hrr) + 1} - {int(resting_heart_rate + 0.90 * hrr)} BPM",
            "Zone 5 (Anaerobic / VO2 Max)": f"{int(resting_heart_rate + 0.90 * hrr) + 1} - {max_heart_rate} BPM",
        }
        result = {
            "max_heart_rate": max_heart_rate,
            "resting_heart_rate": resting_heart_rate,
            "heart_rate_reserve": hrr,
            "training_zones": zones,
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error calculating training zones: {e!s}"


def recommend_workout(
    fitness_level: str,
    target_event: str,
    day_of_week: str,
    previous_activity: str | None = None,
) -> dict[str, Any]:
    """Generates structured workout recommendations based on triathlon periodization rules."""
    valid_levels = ("beginner", "intermediate", "advanced")
    valid_events = ("sprint", "olympic", "70.3", "ironman", "general_fitness")
    days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

    level = str(fitness_level).strip().lower()
    event = str(target_event).strip().lower()
    day = str(day_of_week).strip().lower()

    if level not in valid_levels:
        raise ValueError(f"Invalid fitness level: '{fitness_level}'. Choose: {', '.join(valid_levels)}")
    if event not in valid_events:
        raise ValueError(f"Invalid target event: '{target_event}'. Choose: {', '.join(valid_events)}")
    if day not in days:
        raise ValueError(f"Invalid day: '{day_of_week}'. Choose valid day of week.")

    schedule = {
        "monday": {
            "activity_type": "Swim",
            "duration_minutes": 35 if level == "beginner" else 50,
            "intensity_zone": "Zone 2 (Endurance)",
            "description": "Technique focus with drill sets and easy aerobic swimming.",
        },
        "tuesday": {
            "activity_type": "Bike",
            "duration_minutes": 45 if level == "beginner" else 75,
            "intensity_zone": "Zone 3 (Tempo)",
            "description": "Cadence build-ups and progressive aerobic power intervals.",
        },
        "wednesday": {
            "activity_type": "Run",
            "duration_minutes": 30 if level == "beginner" else 50,
            "intensity_zone": "Zone 4 (Threshold)",
            "description": "Warm-up followed by 4x4-minute threshold pace with 90s jog recovery.",
        },
        "thursday": {
            "activity_type": "Swim",
            "duration_minutes": 40 if level == "beginner" else 60,
            "intensity_zone": "Zone 2 (Aerobic)",
            "description": "Continuous endurance intervals (e.g. 5x200m steady with pull buoy).",
        },
        "friday": {
            "activity_type": "Strength / Mobility",
            "duration_minutes": 30,
            "intensity_zone": "Zone 1 (Active Recovery)",
            "description": "Core stability, hip flexor mobility, and rotator cuff resistance work.",
        },
        "saturday": {
            "activity_type": "Brick" if event in ("olympic", "70.3", "ironman") else "Bike",
            "duration_minutes": 60 if level == "beginner" else 120,
            "intensity_zone": "Zone 2 (Endurance)",
            "description": "Long steady bike ride immediately followed by a 15-minute transition run.",
        },
        "sunday": {
            "activity_type": "Run",
            "duration_minutes": 45 if level == "beginner" else 90,
            "intensity_zone": "Zone 2 (Long Slow Distance)",
            "description": "Conversational pace long aerobic run building endurance resilience.",
        },
    }

    rec = schedule[day].copy()
    rec["fitness_level"] = level
    rec["target_event"] = event
    rec["day_of_week"] = day.capitalize()

    if previous_activity and previous_activity.strip().lower() == "run" and rec["activity_type"] == "Run":
        rec["activity_type"] = "Swim"
        rec["intensity_zone"] = "Zone 1 (Active Recovery)"
        rec["description"] = "Shifted to recovery swim to prevent overuse impact from consecutive running days."

    return rec
