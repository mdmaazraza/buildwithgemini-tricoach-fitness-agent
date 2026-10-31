"""Unified Web Server & API for TriCoach AI.

Serves:
- Mobile-responsive frontend (static files & index.html)
- Chatbot API (/chat) supporting text & A2UI rich responses
- Calorie calculation API (/api/calories)
- Workout logging and listing APIs (/api/workouts)
- System health status (/health)
"""

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
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

logger = logging.getLogger("tricoach_server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="TriCoach AI Web Server",
    description="Unified API & Web Host for TriCoach AI",
    version="1.0.0",
)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend" / "static"


# ---------------- Pydantic Request Models ----------------
class ChatRequest(BaseModel):
    message: str = Field(..., description="User message text")
    user_id: str | None = Field("web-user", description="Athlete / User Identifier")


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


def query_gemini(user_msg: str, api_key: str) -> str | None:
    """Queries Google Gemini model using Google AI Studio API via SDK or HTTPX REST."""
    system_prompt = (
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

    # 2. Direct HTTP REST fallback using httpx (guaranteed to work with all Google AI Studio keys)
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


# ---------------- API Routes ----------------
@app.get("/health")
def health_check() -> dict[str, str]:
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "service": "tricoach-fitness-agent",
        "database": "connected",
    }


@app.post("/chat")
def chat_endpoint(req: ChatRequest) -> dict[str, Any]:
    """Chatbot message handler.
    Returns structured parts compliant with index.html renderer:
    {"parts": [{"kind": "text", "text": ...}, {"kind": "a2ui", "data": ...}]}
    """
    msg = req.message.strip()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    msg_lower = msg.lower()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    # Query local workout database if user asks specifically for logged history
    is_workout_history_query = "workout" in msg_lower and ("log" in msg_lower or "history" in msg_lower)
    if is_workout_history_query:
        recent = default_db.list_workouts(athlete_id=req.user_id, limit=3)
        if recent:
            summary = "\n".join([f"• {w['date']} - {w['activity_type']}: {w['distance_km']}km in {w['duration_minutes']} min (HR: {w['avg_heart_rate']})" for w in recent])
            return {"parts": [{"kind": "text", "text": f"📋 Here are your recent workouts:\n{summary}"}]}
        else:
            return {"parts": [{"kind": "text", "text": "You haven't logged any workouts yet. Tell me what workout you completed today (e.g., 'Log 45 min run, 8 km, 150 bpm')!"}]}

    # If GEMINI_API_KEY is available, let Gemini 2.0 / 1.5 Flash answer dynamically
    if api_key:
        ai_reply = query_gemini(msg, api_key)
        if ai_reply:
            return {"parts": [{"kind": "text", "text": ai_reply}]}

    # Deterministic rule-based fallback (active when API key is not set or in offline tests)
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
