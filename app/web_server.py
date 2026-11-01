"""Unified Web Server & API for TriCoach AI.

Serves:
- Mobile-responsive frontend (static files & index.html)
- Chatbot API (/chat) supporting text & A2UI rich responses
- Calorie calculation API (/api/calories)
- Workout logging and listing APIs (/api/workouts)
- System health status (/health)
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import httpx
from pydantic import BaseModel, Field

load_dotenv()

try:
    from google import genai
    _HAS_GENAI = True
except ImportError:
    _HAS_GENAI = False

from app.db import default_db
from app.fitness_math import (
    calculate_daily_calories_and_macros,
)
from app.tracker_engine import (
    calculate_daily_nutrition_summary,
    calculate_daily_energy_balance,
    calculate_progress_trends,
    calculate_progress_confidence,
)
from app.email_service import (
    generate_progress_report_content,
    send_progress_email,
    send_verification_email,
)
from contextlib import asynccontextmanager

from app.scheduler import (
    dispatch_scheduled_reports,
    start_background_scheduler,
    stop_background_scheduler,
)

logger = logging.getLogger("tricoach_server")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes and tears down background scheduler."""
    if os.getenv("DISABLE_SCHEDULER", "").lower() != "true":
        start_background_scheduler(db=default_db)
    yield
    stop_background_scheduler()


app = FastAPI(
    title="TriCoach AI Web Server",
    description="Unified API & Web Host for TriCoach AI",
    version="1.1.0",
    lifespan=lifespan,
)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend" / "static"


# ---------------- Pydantic Request Models ----------------
class ChatRequest(BaseModel):
    message: str = Field(..., description="User message text")
    user_id: str | None = Field("athlete-01", description="Athlete / User Identifier")


class CalorieRequest(BaseModel):
    weight_kg: float = Field(..., gt=20, le=350, description="Weight in kg")
    height_cm: float = Field(..., gt=80, le=260, description="Height in cm")
    age: int = Field(..., ge=10, le=120, description="Age in years")
    gender: str = Field(..., description="'male' or 'female'")
    activity_level: str = Field(..., description="sedentary, light, moderate, very_active, extra_active")
    goal: str | None = Field("maintenance", description="fat_loss, maintenance, lean_bulk, endurance_fuel")


class WorkoutLogRequest(BaseModel):
    activity_type: str = Field(..., description="Run, Bike, Swim, Brick, Strength")
    duration_minutes: int = Field(..., gt=0, le=1440, description="Duration in minutes")
    distance_km: float = Field(..., ge=0, description="Distance in kilometers")
    avg_heart_rate: int = Field(..., gt=30, le=240, description="Average heart rate")
    intensity_zone: str = Field(..., description="Zone 1 to Zone 5 description")
    notes: str | None = Field("", description="Workout notes or athlete feedback")
    athlete_id: str | None = Field("athlete-01", description="Athlete identifier")


class FeedbackRequest(BaseModel):
    score: int = Field(..., ge=1, le=5)
    comment: str | None = Field("")


class ProfileRequest(BaseModel):
    athlete_id: str = Field("athlete-01", description="Athlete ID")
    age: int = Field(..., ge=10, le=120)
    height_cm: float = Field(..., ge=50, le=260)
    current_weight_kg: float = Field(..., ge=20, le=350)
    sex: str = Field(..., description="'male' or 'female'")
    activity_level: str = Field(..., description="sedentary, light, moderate, very_active, extra_active")
    goal: str = Field(..., description="fat_loss, muscle_gain, maintenance")
    target_weight_kg: float | None = Field(None)
    preferred_units: str = Field("metric", description="'metric' or 'imperial'")
    target_rate_change: float = Field(0.5, ge=0.1, le=2.0)


class FoodEntryRequest(BaseModel):
    athlete_id: str = Field("athlete-01")
    date: str = Field(..., description="YYYY-MM-DD")
    meal_type: str = Field(..., description="breakfast, lunch, dinner, snack, beverage")
    food_name: str = Field(..., min_length=1)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    calories: float = Field(..., ge=0)
    protein_g: float = Field(0.0, ge=0)
    carbs_g: float = Field(0.0, ge=0)
    fat_g: float = Field(0.0, ge=0)
    fiber_g: float = Field(0.0, ge=0)
    data_source: str = Field("manual")
    is_verified: bool = Field(False)


class FoodUpdateRequest(BaseModel):
    food_name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    meal_type: str | None = None
    is_verified: bool | None = None


class NaturalFoodParseRequest(BaseModel):
    text: str = Field(..., min_length=2, description="Natural language food description")
    meal_type: str = Field("lunch", description="Default meal type")


class ActivityEntryRequest(BaseModel):
    athlete_id: str = Field("athlete-01")
    date: str = Field(..., description="YYYY-MM-DD")
    activity_type: str = Field(..., min_length=1)
    duration_minutes: int = Field(..., gt=0)
    intensity: str = Field("moderate")
    distance_km: float = Field(0.0, ge=0)
    steps: int = Field(0, ge=0)
    calories_burned: float = Field(0.0, ge=0)
    strength_details_json: str = Field("[]")
    data_source: str = Field("manual")


class BodyMeasurementRequest(BaseModel):
    athlete_id: str = Field("athlete-01")
    date: str = Field(..., description="YYYY-MM-DD")
    weight_kg: float = Field(..., ge=20, le=350)
    waist_cm: float | None = Field(None, ge=30, le=250)
    body_fat_pct: float | None = Field(None, ge=2, le=70)
    measurement_method: str = Field("scale")
    notes: str = Field("")


class EmailReportRequest(BaseModel):
    recipient_email: str = Field(..., min_length=5)
    athlete_id: str = Field("athlete-01")
    report_date: str | None = None
    period: str = Field("daily", description="'daily' or 'weekly'")


class EmailSubscriptionRequest(BaseModel):
    athlete_id: str = Field("athlete-01")
    email: str = Field(..., min_length=5)
    report_frequency: str = Field("daily", description="'daily', 'weekly', 'both', or 'none'")
    user_consent: bool = Field(True, description="Explicit user consent to receive email reports")
    preferred_time_utc: str = Field("08:00")


class EmailVerificationRequest(BaseModel):
    athlete_id: str = Field("athlete-01")
    token: str = Field(..., min_length=1)


class CronTriggerRequest(BaseModel):
    period: str = Field("daily", description="'daily' or 'weekly'")
    secret: str | None = None
    force: bool = False


def query_gemini(user_msg: str, api_key: str, system_override: str | None = None) -> str | None:
    """Queries Google Gemini model using Google AI Studio API via SDK or HTTPX REST."""
    system_prompt = system_override or (
        "You are TriCoach AI, an elite, motivational endurance coach and sports nutrition expert. "
        "Specialize in triathlon (swimming, cycling, running), fitness, daily calories, food nutrition, and heart rate zones. "
        "Answer athlete questions directly, concisely, and supportively. "
        "When an athlete asks about food they have eaten (e.g. roti, curry, rice, chicken, eggs, pasta, shakes), estimate the total calories and "
        "macronutrients (protein, carbs, fat) clearly and provide practical fitness/recovery guidance."
    )
    full_prompt = f"{system_prompt}\n\nAthlete query: {user_msg}"
    candidate_models = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]

    # 1. Try google.genai SDK
    if _HAS_GENAI:
        for model_name in candidate_models:
            try:
                client = genai.Client(api_key=api_key)
                resp = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                )
                if resp and resp.text:
                    return resp.text.strip()
            except Exception as e:
                logger.warning(f"SDK Gemini call with {model_name} failed: {e}")

    # 2. Direct HTTP REST fallback using httpx
    for model_name in candidate_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": full_prompt}
                        ]
                    }
                ]
            }
            with httpx.Client(timeout=15.0) as http_client:
                r = http_client.post(url, json=payload)
                if r.status_code == 200:
                    data = r.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content_parts = candidates[0].get("content", {}).get("parts", [])
                        if content_parts and "text" in content_parts[0]:
                            return content_parts[0]["text"].strip()
                else:
                    logger.warning(f"HTTP Gemini call ({model_name}) status {r.status_code}: {r.text[:200]}")
        except Exception as e:
            logger.warning(f"HTTP Gemini call with {model_name} failed: {e}")

    return None


# ---------------- Helper Functions ----------------
def parse_natural_language_food(text: str, default_meal: str = "lunch", api_key: str | None = None) -> dict[str, Any]:
    """Converts natural language food descriptions into structured estimated food items.

    Strict Requirements:
    - Never saves automatically: returned for user review and confirmation.
    - Labels items as unverified estimates (data_source='ai_estimate', is_verified=False).
    - Identifies clarifying questions for ambiguous inputs.
    """
    items: list[dict[str, Any]] = []
    clarifications: list[str] = []

    # 1. Attempt Gemini structured parsing if API key is present
    if api_key:
        system_prompt = (
            "You are a sports nutrition parser. Convert natural language meal descriptions into a valid JSON list of items.\n"
            "Format: [{\"food_name\": string, \"quantity\": number, \"unit\": string, \"calories\": number, \"protein_g\": number, \"carbs_g\": number, \"fat_g\": number, \"fiber_g\": number, \"meal_type\": string}]\n"
            "Return ONLY raw JSON, no markdown, no explanations."
        )
        ai_resp = query_gemini(f"Meal description: {text}\nDefault meal type: {default_meal}", api_key, system_override=system_prompt)
        if ai_resp:
            try:
                clean_json = re.sub(r"^```[a-z]*\s*", "", ai_resp.strip(), flags=re.MULTILINE)
                clean_json = re.sub(r"```$", "", clean_json.strip(), flags=re.MULTILINE)
                parsed = json.loads(clean_json)
                if isinstance(parsed, list):
                    for p in parsed:
                        items.append({
                            "food_name": str(p.get("food_name", "Unknown Food")),
                            "quantity": float(p.get("quantity", 1.0)),
                            "unit": str(p.get("unit", "serving")),
                            "calories": float(p.get("calories", 100.0)),
                            "protein_g": float(p.get("protein_g", 0.0)),
                            "carbs_g": float(p.get("carbs_g", 0.0)),
                            "fat_g": float(p.get("fat_g", 0.0)),
                            "fiber_g": float(p.get("fiber_g", 0.0)),
                            "meal_type": str(p.get("meal_type", default_meal)).lower(),
                            "data_source": "ai_estimate",
                            "is_verified": False,
                        })
                    return {
                        "status": "success",
                        "items": items,
                        "clarifications_needed": clarifications,
                        "is_estimated": True,
                        "note": "Items are AI estimates based on standard nutritional data. Review and confirm before saving."
                    }
            except Exception as e:
                logger.warning(f"Natural language AI JSON parsing failed, using heuristic parser: {e}")

    # 2. Heuristic Food Knowledge Dictionary for robust offline / fallback parsing
    word_to_num = {
        "a": 1.0, "an": 1.0, "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0,
        "five": 5.0, "six": 6.0, "half": 0.5, "couple": 2.0, "several": 3.0,
    }

    food_db = [
        {"regex": r"(?:(\d+(?:\.\d+)?|\w+)\s+)?(?:boiled\s+)?eggs?", "name": "Boiled Eggs", "unit": "whole", "cal": 72.0, "p": 6.3, "c": 0.4, "f": 5.0, "fb": 0.0},
        {"regex": r"(?:(\d+(?:\.\d+)?|\w+)\s+)?(?:rotis?|chapatis?)", "name": "Roti", "unit": "piece", "cal": 80.0, "p": 3.0, "c": 16.0, "f": 0.5, "fb": 1.5},
        {"regex": r"(?:(\d+(?:\.\d+)?|\w+)\s+)?(?:bowls?\s+of\s+)?(?:chicken\s+curry|chicken)", "name": "Chicken Curry", "unit": "serving (150g)", "cal": 260.0, "p": 28.0, "c": 6.0, "f": 13.0, "fb": 1.0},
        {"regex": r"(?:(\d+(?:\.\d+)?|\w+)\s+)?(?:bowls?\s+of\s+)?(?:dal|lentils?|daal)", "name": "Lentil Dal", "unit": "bowl (200g)", "cal": 180.0, "p": 10.0, "c": 28.0, "f": 3.0, "fb": 6.0},
        {"regex": r"(?:(\d+(?:\.\d+)?|\w+)\s+)?(?:plates?\s+of\s+|bowls?\s+of\s+)?(?:rice|white\s+rice|brown\s+rice)", "name": "Cooked Rice", "unit": "bowl (150g)", "cal": 195.0, "p": 4.0, "c": 43.0, "f": 0.4, "fb": 0.5},
        {"regex": r"(?:(\d+(?:\.\d+)?|\w+)\s+)?(?:bowls?\s+of\s+)?(?:oats|oatmeal)", "name": "Oatmeal", "unit": "bowl (250g)", "cal": 210.0, "p": 6.0, "c": 38.0, "f": 4.0, "fb": 4.5},
        {"regex": r"(?:(\d+(?:\.\d+)?|\w+)\s+)?(?:cups?\s+of\s+)?(?:greek\s+)?yogurt", "name": "Greek Yogurt", "unit": "cup (150g)", "cal": 130.0, "p": 15.0, "c": 10.0, "f": 2.5, "fb": 0.0},
        {"regex": r"(?:(\d+(?:\.\d+)?|\w+)\s+)?bananas?", "name": "Banana", "unit": "medium", "cal": 105.0, "p": 1.3, "c": 27.0, "f": 0.3, "fb": 3.0},
        {"regex": r"(?:(\d+(?:\.\d+)?|\w+)\s+)?apples?", "name": "Apple", "unit": "medium", "cal": 95.0, "p": 0.5, "c": 25.0, "f": 0.3, "fb": 4.0},
        {"regex": r"(?:(\d+(?:\.\d+)?|\w+)\s+)?(?:protein\s+)?shakes?", "name": "Protein Shake", "unit": "scoop (30g)", "cal": 140.0, "p": 25.0, "c": 3.0, "f": 2.0, "fb": 1.0},
        {"regex": r"(?:(\d+(?:\.\d+)?|\w+)\s+)?slices?\s+of\s+bread|toast", "name": "Bread Toast", "unit": "slice", "cal": 75.0, "p": 2.5, "c": 14.0, "f": 1.0, "fb": 1.0},
    ]

    text_lower = text.lower()
    for item_spec in food_db:
        match = re.search(item_spec["regex"], text_lower)
        if match:
            raw_qty = match.group(1)
            qty = 1.0
            if raw_qty:
                raw_clean = raw_qty.strip().lower()
                if raw_clean in word_to_num:
                    qty = word_to_num[raw_clean]
                else:
                    try:
                        qty = float(raw_clean)
                    except ValueError:
                        qty = 1.0
            else:
                clarifications.append(f"Quantity was assumed to be 1 {item_spec['unit']} for {item_spec['name']}.")

            items.append({
                "food_name": item_spec["name"],
                "quantity": qty,
                "unit": item_spec["unit"],
                "calories": round(item_spec["cal"] * qty, 1),
                "protein_g": round(item_spec["p"] * qty, 1),
                "carbs_g": round(item_spec["c"] * qty, 1),
                "fat_g": round(item_spec["f"] * qty, 1),
                "fiber_g": round(item_spec["fb"] * qty, 1),
                "meal_type": default_meal.lower(),
                "data_source": "ai_estimate",
                "is_verified": False,
            })

    if not items:
        # Generic fallback
        items.append({
            "food_name": text.strip().title(),
            "quantity": 1.0,
            "unit": "serving",
            "calories": 250.0,
            "protein_g": 10.0,
            "carbs_g": 30.0,
            "fat_g": 8.0,
            "fiber_g": 2.0,
            "meal_type": default_meal.lower(),
            "data_source": "ai_estimate",
            "is_verified": False,
        })
        clarifications.append(f"Uncertain nutritional composition for '{text}'. Standard mixed meal estimate provided.")

    return {
        "status": "success",
        "items": items,
        "clarifications_needed": clarifications,
        "is_estimated": True,
        "note": "Items are structured estimates. Verify or adjust quantities before saving."
    }


# ---------------- API Routes ----------------
@app.get("/health")
def health_check() -> dict[str, str]:
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "service": "tricoach-fitness-agent",
        "database": "connected",
    }


# ---------------- Profile Endpoints ----------------
@app.get("/api/profile")
def get_profile_endpoint(athlete_id: str = "athlete-01") -> dict[str, Any]:
    """Retrieves user fitness profile."""
    profile = default_db.get_profile(athlete_id)
    return {"status": "success", "profile": profile}


@app.post("/api/profile")
def save_profile_endpoint(req: ProfileRequest) -> dict[str, Any]:
    """Saves or updates user fitness profile."""
    try:
        profile = default_db.save_profile(
            athlete_id=req.athlete_id,
            age=req.age,
            height_cm=req.height_cm,
            current_weight_kg=req.current_weight_kg,
            sex=req.sex,
            activity_level=req.activity_level,
            goal=req.goal,
            target_weight_kg=req.target_weight_kg,
            preferred_units=req.preferred_units,
            target_rate_change=req.target_rate_change,
        )
        return {"status": "success", "profile": profile}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


# ---------------- Daily Food Tracking Endpoints ----------------
@app.get("/api/food/entries")
def get_food_entries_endpoint(
    athlete_id: str = "athlete-01",
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Retrieves logged food entries."""
    entries = default_db.get_food_entries(athlete_id=athlete_id, date_str=date, start_date=start_date, end_date=end_date)
    return {"status": "success", "count": len(entries), "entries": entries}


@app.post("/api/food/entries")
def log_food_entry_endpoint(req: FoodEntryRequest) -> dict[str, Any]:
    """Logs a food consumption record."""
    try:
        entry = default_db.log_food_entry(
            athlete_id=req.athlete_id,
            date_str=req.date,
            meal_type=req.meal_type,
            food_name=req.food_name,
            quantity=req.quantity,
            unit=req.unit,
            calories=req.calories,
            protein_g=req.protein_g,
            carbs_g=req.carbs_g,
            fat_g=req.fat_g,
            fiber_g=req.fiber_g,
            data_source=req.data_source,
            is_verified=req.is_verified,
        )
        return {"status": "success", "entry": entry}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@app.put("/api/food/entries/{entry_id}")
def update_food_entry_endpoint(entry_id: str, req: FoodUpdateRequest) -> dict[str, Any]:
    """Updates quantity or nutritional macros of an existing food entry."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = default_db.update_food_entry(entry_id, updates)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Food entry '{entry_id}' not found.")
    return {"status": "success", "entry": updated}


@app.delete("/api/food/entries/{entry_id}")
def delete_food_entry_endpoint(entry_id: str) -> dict[str, Any]:
    """Deletes a food entry."""
    deleted = default_db.delete_food_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Food entry '{entry_id}' not found.")
    return {"status": "success", "deleted": True}


@app.post("/api/food/parse-natural")
def parse_natural_food_endpoint(req: NaturalFoodParseRequest) -> dict[str, Any]:
    """Parses natural language meal text into structured estimated items with uncertainty tags."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    return parse_natural_language_food(req.text, default_meal=req.meal_type or "lunch", api_key=api_key or None)


# ---------------- Activity Tracking Endpoints ----------------
@app.get("/api/activities")
def get_activities_endpoint(
    athlete_id: str = "athlete-01",
    date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Retrieves physical activity logs."""
    acts = default_db.get_activity_entries(athlete_id=athlete_id, date_str=date, start_date=start_date, end_date=end_date)
    return {"status": "success", "count": len(acts), "activities": acts}


@app.post("/api/activities")
def log_activity_endpoint(req: ActivityEntryRequest) -> dict[str, Any]:
    """Logs physical activity or strength session."""
    try:
        act = default_db.log_activity_entry(
            athlete_id=req.athlete_id,
            date_str=req.date,
            activity_type=req.activity_type,
            duration_minutes=req.duration_minutes,
            intensity=req.intensity,
            distance_km=req.distance_km,
            steps=req.steps,
            calories_burned=req.calories_burned,
            strength_details_json=req.strength_details_json,
            data_source=req.data_source,
        )
        return {"status": "success", "activity": act}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@app.delete("/api/activities/{activity_id}")
def delete_activity_endpoint(activity_id: str) -> dict[str, Any]:
    """Deletes an activity entry."""
    deleted = default_db.delete_activity_entry(activity_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Activity '{activity_id}' not found.")
    return {"status": "success", "deleted": True}


# ---------------- Body Measurements Endpoints ----------------
@app.get("/api/measurements")
def get_measurements_endpoint(
    athlete_id: str = "athlete-01",
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Retrieves historical body measurements."""
    meas = default_db.get_measurements(athlete_id=athlete_id, start_date=start_date, end_date=end_date, limit=limit)
    return {"status": "success", "count": len(meas), "measurements": meas}


@app.post("/api/measurements")
def log_measurement_endpoint(req: BodyMeasurementRequest) -> dict[str, Any]:
    """Logs a body measurement and keeps current weight synced."""
    try:
        meas = default_db.log_measurement(
            athlete_id=req.athlete_id,
            date_str=req.date,
            weight_kg=req.weight_kg,
            waist_cm=req.waist_cm,
            body_fat_pct=req.body_fat_pct,
            measurement_method=req.measurement_method,
            notes=req.notes,
        )
        return {"status": "success", "measurement": meas}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@app.delete("/api/measurements/{measurement_id}")
def delete_measurement_endpoint(measurement_id: str) -> dict[str, Any]:
    """Deletes a body measurement record."""
    deleted = default_db.delete_measurement(measurement_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Measurement '{measurement_id}' not found.")
    return {"status": "success", "deleted": True}


# ---------------- Analytics & Progress Endpoints ----------------
@app.get("/api/analytics/daily-summary")
def get_daily_summary_endpoint(athlete_id: str = "athlete-01", date: str | None = None) -> dict[str, Any]:
    """Calculates daily nutritional totals, meal-wise breakdown, and energy balance for a specific date."""
    import datetime
    date_str = date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    profile = default_db.get_profile(athlete_id)
    food_entries = default_db.get_food_entries(athlete_id, date_str=date_str)
    activities = default_db.get_activity_entries(athlete_id, date_str=date_str)

    nutrition = calculate_daily_nutrition_summary(food_entries, profile=profile)
    energy = calculate_daily_energy_balance(profile, activities, food_entries)

    return {
        "status": "success",
        "date": date_str,
        "athlete_id": athlete_id,
        "nutrition": nutrition,
        "energy_balance": energy,
    }


@app.get("/api/analytics/trends")
def get_trends_endpoint(athlete_id: str = "athlete-01", days: int = 30) -> dict[str, Any]:
    """Calculates rolling 7-day weight trends, waist deltas, and progress interpretations."""
    profile = default_db.get_profile(athlete_id)
    measurements = default_db.get_measurements(athlete_id, limit=days)

    # Fetch recent food summaries and activities
    food_entries = default_db.get_food_entries(athlete_id)
    food_by_date: dict[str, list[dict[str, Any]]] = {}
    for f in food_entries:
        d = str(f.get("date", ""))
        food_by_date.setdefault(d, []).append(f)
    food_summaries = {d: calculate_daily_nutrition_summary(items, profile=profile) for d, items in food_by_date.items()}

    activities = default_db.get_activity_entries(athlete_id)
    act_by_date: dict[str, list[dict[str, Any]]] = {}
    for a in activities:
        d = str(a.get("date", ""))
        act_by_date.setdefault(d, []).append(a)

    trends = calculate_progress_trends(measurements, food_summaries_by_date=food_summaries, activities_by_date=act_by_date, profile=profile)
    return {"status": "success", "athlete_id": athlete_id, "trends": trends}


@app.get("/api/analytics/confidence")
def get_confidence_endpoint(athlete_id: str = "athlete-01", days: int = 7) -> dict[str, Any]:
    """Calculates data completeness and logging reliability score (0-100%)."""
    food = default_db.get_food_entries(athlete_id)
    acts = default_db.get_activity_entries(athlete_id)
    meas = default_db.get_measurements(athlete_id, limit=days)
    conf = calculate_progress_confidence(food, acts, meas, days_window=days)
    return {"status": "success", "athlete_id": athlete_id, "confidence": conf}


# ---------------- Email Progress Reports Endpoints ----------------
@app.post("/api/reports/email")
def send_email_report_endpoint(req: EmailReportRequest) -> dict[str, Any]:
    """Generates progress report, dispatches via SMTP (or safe simulation), and logs in DB."""
    result = send_progress_email(
        recipient_email=req.recipient_email,
        athlete_id=req.athlete_id,
        report_date=req.report_date,
        period=req.period,
        db=default_db,
    )
    return {"status": "success", "report": result}


@app.get("/api/reports/email/history")
def get_email_history_endpoint(athlete_id: str = "athlete-01", limit: int = 20) -> dict[str, Any]:
    """Retrieves email delivery logs for an athlete."""
    history = default_db.get_email_reports(athlete_id=athlete_id, limit=limit)
    return {"status": "success", "count": len(history), "history": history}


@app.get("/api/reports/subscription")
def get_email_subscription_endpoint(athlete_id: str = "athlete-01") -> dict[str, Any]:
    """Retrieves email subscription preferences and verification status."""
    sub = default_db.get_email_subscription(athlete_id)
    return {"status": "success", "athlete_id": athlete_id, "subscription": sub}


@app.post("/api/reports/subscription")
def save_email_subscription_endpoint(req: EmailSubscriptionRequest) -> dict[str, Any]:
    """Saves email subscription, records user consent, and dispatches a verification email."""
    try:
        sub = default_db.save_email_subscription(
            athlete_id=req.athlete_id,
            email=req.email,
            report_frequency=req.report_frequency,
            user_consent=req.user_consent,
            preferred_time_utc=req.preferred_time_utc,
        )
        verification_dispatch = None
        if not sub["is_verified"] and sub["user_consent"]:
            verification_dispatch = send_verification_email(
                athlete_id=req.athlete_id,
                recipient_email=req.email,
                verification_token=sub["verification_token"],
                db=default_db,
            )
        return {"status": "success", "subscription": sub, "verification": verification_dispatch}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@app.post("/api/reports/verify")
def verify_email_endpoint(req: EmailVerificationRequest) -> dict[str, Any]:
    """Verifies user email address using the supplied token."""
    verified = default_db.verify_email_subscription(athlete_id=req.athlete_id, token=req.token)
    if not verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token or athlete ID.")
    return {"status": "success", "athlete_id": req.athlete_id, "verified": True}


@app.get("/api/reports/verify")
def verify_email_link_endpoint(athlete_id: str, token: str) -> HTMLResponse:
    """Direct one-click email verification via browser link."""
    verified = default_db.verify_email_subscription(athlete_id=athlete_id, token=token)
    if verified:
        return HTMLResponse(
            "<html><body style='font-family:system-ui,sans-serif;text-align:center;padding:50px;background:#f8fafc;'>"
            "<div style='max-width:500px;margin:0 auto;background:#fff;padding:30px;border-radius:12px;border:1px solid #e2e8f0;'>"
            "<h1 style='color:#16a34a;margin-top:0;'>✅ Email Verified Successfully!</h1>"
            "<p>Your email address is now verified. You will receive automated TriCoach AI fitness reports according to your schedule.</p>"
            "<a href='/' style='display:inline-block;background:#f97316;color:#fff;padding:10px 20px;text-decoration:none;border-radius:8px;font-weight:600;'>Return to TriCoach AI</a>"
            "</div></body></html>"
        )
    return HTMLResponse(
        "<html><body style='font-family:system-ui,sans-serif;text-align:center;padding:50px;background:#f8fafc;'>"
        "<div style='max-width:500px;margin:0 auto;background:#fff;padding:30px;border-radius:12px;border:1px solid #e2e8f0;'>"
        "<h1 style='color:#dc2626;margin-top:0;'>❌ Verification Failed</h1>"
        "<p>The verification code is invalid, expired, or already used.</p>"
        "<a href='/' style='display:inline-block;background:#f97316;color:#fff;padding:10px 20px;text-decoration:none;border-radius:8px;font-weight:600;'>Return to TriCoach AI</a>"
        "</div></body></html>",
        status_code=400,
    )


@app.post("/api/reports/cron-trigger")
def cron_trigger_endpoint(req: CronTriggerRequest) -> dict[str, Any]:
    """Cron webhook endpoint for external schedulers (e.g. GitHub Actions, cron-job.org, Render cron)."""
    expected_secret = os.getenv("CRON_SECRET", "").strip()
    if expected_secret and (not req.secret or req.secret.strip() != expected_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cron authorization secret.")

    results = dispatch_scheduled_reports(period=req.period, db=default_db, force=req.force)
    return {
        "status": "success",
        "period": req.period,
        "dispatched_count": len(results),
        "results": results,
    }


# ---------------- Grounded Chatbot API ----------------
@app.post("/chat")
def chat_endpoint(req: ChatRequest) -> dict[str, Any]:
    """Chatbot message handler grounded in the athlete's actual stored fitness records."""
    msg = req.message.strip()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    msg_lower = msg.lower()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    athlete_id = req.user_id or "athlete-01"

    # Query local workout database if user asks specifically for logged history
    is_workout_history_query = "workout" in msg_lower and ("log" in msg_lower or "history" in msg_lower)
    if is_workout_history_query:
        recent = default_db.list_workouts(athlete_id=athlete_id, limit=3)
        if recent:
            summary = "\n".join([f"• {w['date']} - {w['activity_type']}: {w['distance_km']}km in {w['duration_minutes']} min (HR: {w['avg_heart_rate']})" for w in recent])
            return {"parts": [{"kind": "text", "text": f"📋 Here are your recent workouts:\n{summary}"}]}
        else:
            return {"parts": [{"kind": "text", "text": "You haven't logged any workouts yet. Tell me what workout you completed today (e.g., 'Log 45 min run, 8 km, 150 bpm')!"}]}

    # Grounding check: Did user ask about their current/historical records, calories, protein, deficit, or weight?
    is_stats_query = any(k in msg_lower for k in [
        "how many calories", "how much protein", "my deficit", "my calorie", "my weight",
        "my progress", "average weight", "did i consume", "did i eat", "meeting my protein",
        "trend", "my summary", "my journal", "my macros"
    ])

    if is_stats_query:
        import datetime
        today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        prof = default_db.get_profile(athlete_id)
        food_today = default_db.get_food_entries(athlete_id, date_str=today_str)
        acts_today = default_db.get_activity_entries(athlete_id, date_str=today_str)
        meas = default_db.get_measurements(athlete_id, limit=14)

        nutrition = calculate_daily_nutrition_summary(food_today, profile=prof)
        energy = calculate_daily_energy_balance(prof, acts_today, food_today)
        trends = calculate_progress_trends(meas, profile=prof)

        grounded_context = (
            f"ACTUAL STORED FITNESS DATABASE FOR ATHLETE '{athlete_id}' (Date: {today_str}):\n"
            f"- Profile: Age {prof['age']}, Height {prof['height_cm']}cm, Current Weight {prof['current_weight_kg']}kg, Goal: {prof['goal']}\n"
            f"- Today's Food Consumed: {energy['calories_consumed']} kcal (Protein: {nutrition['totals']['protein_g']}g, Carbs: {nutrition['totals']['carbs_g']}g, Fat: {nutrition['totals']['fat_g']}g)\n"
            f"- Today's Nutrition Targets: {nutrition['targets'].get('target_calories', 2000)} kcal, Protein: {nutrition['targets'].get('target_protein_g', 120)}g\n"
            f"- Today's Energy Expenditure: {energy['total_energy_expenditure']} kcal (BMR: {energy['bmr']} kcal, Activity: {energy['additional_exercise_burn']} kcal)\n"
            f"- Today's Net Calorie Balance: {energy['estimated_calorie_balance']:+} kcal ({energy['balance_status']})\n"
            f"- Recent Weight Trend: Baseline 7d Avg: {trends['baseline_7d_avg_kg']} kg -> Current 7d Avg: {trends['current_7d_avg_kg']} kg (Net Change: {trends['avg_weight_change_7d_kg']:+} kg)\n"
            f"- Workouts Logged Today: {len(acts_today)} session(s)\n"
        )

        if api_key:
            system_prompt = (
                "You are TriCoach AI, an elite endurance coach and nutritionist. "
                "The user is asking about their own fitness data. "
                "Base your answer STRICTLY on the actual database records provided below. "
                "Do not hallucinate or make up missing numbers. State actual values directly and concisely.\n\n"
                f"{grounded_context}"
            )
            ai_reply = query_gemini(msg, api_key, system_override=system_prompt)
            if ai_reply:
                return {"parts": [{"kind": "text", "text": ai_reply}]}

        # Deterministic grounded fallback response
        reply = (
            f"📊 **Your Stored Fitness Summary for Today ({today_str}):**\n\n"
            f"• **Calories Consumed**: {energy['calories_consumed']} kcal / {nutrition['targets'].get('target_calories', 'N/A')} kcal target\n"
            f"• **Protein**: {nutrition['totals']['protein_g']}g / {nutrition['targets'].get('target_protein_g', 'N/A')}g target\n"
            f"• **Total Expenditure**: {energy['total_energy_expenditure']} kcal\n"
            f"• **Estimated Calorie Balance**: {energy['estimated_calorie_balance']:+} kcal ({energy['balance_status'].upper()})\n"
            f"• **7-Day Weight Trend**: {trends['avg_weight_change_7d_kg']:+} kg (Current: {trends['latest_weight_kg'] or prof['current_weight_kg']} kg)\n\n"
            "All metrics are permanently recorded in your application database."
        )
        return {"parts": [{"kind": "text", "text": reply}]}

    # Standard general queries
    if api_key:
        ai_reply = query_gemini(msg, api_key)
        if ai_reply:
            return {"parts": [{"kind": "text", "text": ai_reply}]}

    # Deterministic rule-based fallback
    parts = []
    if "calorie" in msg_lower or "bmr" in msg_lower or "tdee" in msg_lower:
        parts.append({
            "kind": "text",
            "text": "🏊🚴🏃 I can calculate your exact BMR, TDEE, and daily endurance macronutrient targets! Send your weight, height, age, gender, and activity level, or call /api/calories directly."
        })
    elif "zone" in msg_lower or "heart rate" in msg_lower:
        parts.append({
            "kind": "text",
            "text": "❤️ Karvonen Training Zones: Zone 1 (Recovery 50-60%), Zone 2 (Aerobic Base 60-70%), Zone 3 (Tempo 70-80%), Zone 4 (Threshold 80-90%), Zone 5 (Anaerobic / VO2 Max 90-100%)."
        })
    else:
        parts.append({
            "kind": "text",
            "text": (
                f"Coach TriCoach here! I received: '{msg}'.\n\n"
                "💡 **Note**: To enable full dynamic AI reasoning and food calorie estimation, "
                "ensure `GEMINI_API_KEY` is added to your Render Environment Variables!"
            )
        })

    return {"parts": parts}


@app.post("/api/calories")
def calculate_calories_endpoint(req: CalorieRequest) -> dict[str, Any]:
    """Calculates BMR, TDEE, target calories, and macro breakdown."""
    try:
        result = calculate_daily_calories_and_macros(
            weight_kg=req.weight_kg,
            height_cm=req.height_cm,
            age=req.age,
            gender=req.gender,
            activity_level=req.activity_level,
            goal=req.goal,
        )
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@app.post("/api/workouts")
def log_workout_endpoint(req: WorkoutLogRequest) -> dict[str, Any]:
    """Logs a new workout."""
    try:
        record = default_db.log_workout(
            activity_type=req.activity_type,
            duration_minutes=req.duration_minutes,
            distance_km=req.distance_km,
            avg_heart_rate=req.avg_heart_rate,
            intensity_zone=req.intensity_zone,
            notes=req.notes or "",
            athlete_id=req.athlete_id or "athlete-01",
        )
        return {"status": "success", "workout": record}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@app.get("/api/workouts")
def list_workouts_endpoint(athlete_id: str = "athlete-01", limit: int = 10) -> dict[str, Any]:
    """Retrieves workout history for an athlete."""
    workouts = default_db.list_workouts(athlete_id=athlete_id, limit=limit)
    return {"status": "success", "count": len(workouts), "workouts": workouts}


@app.post("/feedback")
def feedback_endpoint(req: FeedbackRequest) -> dict[str, Any]:
    """Records user feedback."""
    return {"status": "received", "feedback": req.model_dump()}


# ---------------- Frontend Static Mount ----------------
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(STATIC_DIR / "index.html")
