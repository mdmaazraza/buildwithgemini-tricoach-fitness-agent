"""Shared pytest fixtures and configuration for TriCoach AI test suite.
"""

import urllib.parse

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.db import WorkoutDatabase
from app.web_server import (
    CalorieRequest,
    ChatRequest,
    FeedbackRequest,
    WorkoutLogRequest,
    ProfileRequest,
    FoodEntryRequest,
    FoodUpdateRequest,
    NaturalFoodParseRequest,
    ActivityEntryRequest,
    BodyMeasurementRequest,
    EmailReportRequest,
    EmailSubscriptionRequest,
    EmailVerificationRequest,
    CronTriggerRequest,
    calculate_calories_endpoint,
    chat_endpoint,
    feedback_endpoint,
    health_check,
    list_workouts_endpoint,
    log_workout_endpoint,
    get_profile_endpoint,
    save_profile_endpoint,
    get_food_entries_endpoint,
    log_food_entry_endpoint,
    update_food_entry_endpoint,
    delete_food_entry_endpoint,
    parse_natural_food_endpoint,
    get_activities_endpoint,
    log_activity_endpoint,
    delete_activity_endpoint,
    get_measurements_endpoint,
    log_measurement_endpoint,
    delete_measurement_endpoint,
    get_daily_summary_endpoint,
    get_trends_endpoint,
    get_confidence_endpoint,
    send_email_report_endpoint,
    get_email_history_endpoint,
    get_email_subscription_endpoint,
    save_email_subscription_endpoint,
    verify_email_endpoint,
    cron_trigger_endpoint,
)


class MockResponse:
    """Simulates an HTTP response for synchronous test execution."""

    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data

    @property
    def text(self):
        import json
        return json.dumps(self._data)


class DirectTestClient:
    """Deterministic, lightweight client executing FastAPI handlers without thread deadlock."""

    def get(self, url: str, params: dict | None = None) -> MockResponse:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        merged_params = {}
        if parsed.query:
            for k, v in urllib.parse.parse_qs(parsed.query).items():
                merged_params[k] = v[0] if len(v) == 1 else v
        if params:
            merged_params.update(params)

        if path == "/health":
            res = health_check()
            return MockResponse(200, res)
        elif path == "/api/workouts":
            athlete_id = merged_params.get("athlete_id", "athlete-01")
            limit = int(merged_params.get("limit", 10))
            res = list_workouts_endpoint(athlete_id=athlete_id, limit=limit)
            return MockResponse(200, res)
        elif path == "/api/profile":
            athlete_id = merged_params.get("athlete_id", "athlete-01")
            res = get_profile_endpoint(athlete_id=athlete_id)
            return MockResponse(200, res)
        elif path == "/api/food/entries":
            athlete_id = merged_params.get("athlete_id", "athlete-01")
            date = merged_params.get("date")
            start_date = merged_params.get("start_date")
            end_date = merged_params.get("end_date")
            res = get_food_entries_endpoint(athlete_id=athlete_id, date=date, start_date=start_date, end_date=end_date)
            return MockResponse(200, res)
        elif path == "/api/activities":
            athlete_id = merged_params.get("athlete_id", "athlete-01")
            date = merged_params.get("date")
            start_date = merged_params.get("start_date")
            end_date = merged_params.get("end_date")
            res = get_activities_endpoint(athlete_id=athlete_id, date=date, start_date=start_date, end_date=end_date)
            return MockResponse(200, res)
        elif path == "/api/measurements":
            athlete_id = merged_params.get("athlete_id", "athlete-01")
            start_date = merged_params.get("start_date")
            end_date = merged_params.get("end_date")
            limit = int(merged_params.get("limit", 100))
            res = get_measurements_endpoint(athlete_id=athlete_id, start_date=start_date, end_date=end_date, limit=limit)
            return MockResponse(200, res)
        elif path == "/api/analytics/daily-summary":
            athlete_id = merged_params.get("athlete_id", "athlete-01")
            date = merged_params.get("date")
            res = get_daily_summary_endpoint(athlete_id=athlete_id, date=date)
            return MockResponse(200, res)
        elif path == "/api/analytics/trends":
            athlete_id = merged_params.get("athlete_id", "athlete-01")
            days = int(merged_params.get("days", 30))
            res = get_trends_endpoint(athlete_id=athlete_id, days=days)
            return MockResponse(200, res)
        elif path == "/api/analytics/confidence":
            athlete_id = merged_params.get("athlete_id", "athlete-01")
            days = int(merged_params.get("days", 7))
            res = get_confidence_endpoint(athlete_id=athlete_id, days=days)
            return MockResponse(200, res)
        elif path == "/api/reports/email/history":
            athlete_id = merged_params.get("athlete_id", "athlete-01")
            limit = int(merged_params.get("limit", 20))
            res = get_email_history_endpoint(athlete_id=athlete_id, limit=limit)
            return MockResponse(200, res)
        elif path == "/api/reports/subscription":
            athlete_id = merged_params.get("athlete_id", "athlete-01")
            res = get_email_subscription_endpoint(athlete_id=athlete_id)
            return MockResponse(200, res)
        return MockResponse(404, {"detail": "Not found"})

    def post(self, url: str, json: dict | None = None) -> MockResponse:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        json = json or {}
        try:
            if path == "/chat":
                req = ChatRequest(**json)
                res = chat_endpoint(req)
                return MockResponse(200, res)
            elif path == "/api/calories":
                req = CalorieRequest(**json)
                res = calculate_calories_endpoint(req)
                return MockResponse(200, res)
            elif path == "/api/workouts":
                req = WorkoutLogRequest(**json)
                res = log_workout_endpoint(req)
                return MockResponse(200, res)
            elif path == "/feedback":
                req = FeedbackRequest(**json)
                res = feedback_endpoint(req)
                return MockResponse(200, res)
            elif path == "/api/profile":
                req = ProfileRequest(**json)
                res = save_profile_endpoint(req)
                return MockResponse(200, res)
            elif path == "/api/food/entries":
                req = FoodEntryRequest(**json)
                res = log_food_entry_endpoint(req)
                return MockResponse(200, res)
            elif path == "/api/food/parse-natural":
                req = NaturalFoodParseRequest(**json)
                res = parse_natural_food_endpoint(req)
                return MockResponse(200, res)
            elif path == "/api/activities":
                req = ActivityEntryRequest(**json)
                res = log_activity_endpoint(req)
                return MockResponse(200, res)
            elif path == "/api/measurements":
                req = BodyMeasurementRequest(**json)
                res = log_measurement_endpoint(req)
                return MockResponse(200, res)
            elif path == "/api/reports/email":
                req = EmailReportRequest(**json)
                res = send_email_report_endpoint(req)
                return MockResponse(200, res)
            elif path == "/api/reports/subscription":
                req = EmailSubscriptionRequest(**json)
                res = save_email_subscription_endpoint(req)
                return MockResponse(200, res)
            elif path == "/api/reports/verify":
                req = EmailVerificationRequest(**json)
                res = verify_email_endpoint(req)
                return MockResponse(200, res)
            elif path == "/api/reports/cron-trigger":
                req = CronTriggerRequest(**json)
                res = cron_trigger_endpoint(req)
                return MockResponse(200, res)
            return MockResponse(404, {"detail": "Not found"})
        except ValidationError as e:
            return MockResponse(422, {"detail": e.errors()})
        except HTTPException as e:
            return MockResponse(e.status_code, {"detail": e.detail})
        except Exception as e:
            return MockResponse(500, {"detail": str(e)})

    def put(self, url: str, json: dict | None = None) -> MockResponse:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        json = json or {}
        try:
            if path.startswith("/api/food/entries/"):
                entry_id = path.split("/")[-1]
                req = FoodUpdateRequest(**json)
                res = update_food_entry_endpoint(entry_id, req)
                return MockResponse(200, res)
            return MockResponse(404, {"detail": "Not found"})
        except ValidationError as e:
            return MockResponse(422, {"detail": e.errors()})
        except HTTPException as e:
            return MockResponse(e.status_code, {"detail": e.detail})
        except Exception as e:
            return MockResponse(500, {"detail": str(e)})

    def delete(self, url: str) -> MockResponse:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        try:
            if path.startswith("/api/food/entries/"):
                entry_id = path.split("/")[-1]
                res = delete_food_entry_endpoint(entry_id)
                return MockResponse(200, res)
            elif path.startswith("/api/activities/"):
                activity_id = path.split("/")[-1]
                res = delete_activity_endpoint(activity_id)
                return MockResponse(200, res)
            elif path.startswith("/api/measurements/"):
                measurement_id = path.split("/")[-1]
                res = delete_measurement_endpoint(measurement_id)
                return MockResponse(200, res)
            return MockResponse(404, {"detail": "Not found"})
        except HTTPException as e:
            return MockResponse(e.status_code, {"detail": e.detail})
        except Exception as e:
            return MockResponse(500, {"detail": str(e)})


@pytest.fixture
def test_client():
    """Provides a thread-safe test client for API and integration tests."""
    return DirectTestClient()


@pytest.fixture
def in_memory_db():
    """Provides an isolated in-memory SQLite database for test isolation."""
    db = WorkoutDatabase(db_path=":memory:")
    yield db
    db.clear()


@pytest.fixture
def sample_athlete():
    """Sample profile for a male endurance athlete."""
    return {
        "weight_kg": 72.5,
        "height_cm": 178.0,
        "age": 28,
        "gender": "male",
        "activity_level": "very_active",
        "goal": "endurance_fuel",
    }


@pytest.fixture
def sample_female_athlete():
    """Sample profile for a female endurance athlete."""
    return {
        "weight_kg": 58.0,
        "height_cm": 165.0,
        "age": 32,
        "gender": "female",
        "activity_level": "moderate",
        "goal": "fat_loss",
    }


@pytest.fixture
def sample_workout_payload():
    """Sample valid workout payload for logging tests."""
    return {
        "activity_type": "Bike",
        "duration_minutes": 75,
        "distance_km": 38.5,
        "avg_heart_rate": 142,
        "intensity_zone": "Zone 2 (Endurance)",
        "notes": "Steady aerobic cadence test along river trail.",
        "athlete_id": "athlete-test-01",
    }
