"""Shared pytest fixtures and configuration for TriCoach AI test suite.
"""

import urllib.parse
import pytest
from pydantic import ValidationError
from fastapi import HTTPException

from app.web_server import (
    app,
    health_check,
    chat_endpoint,
    calculate_calories_endpoint,
    log_workout_endpoint,
    list_workouts_endpoint,
    feedback_endpoint,
    ChatRequest,
    CalorieRequest,
    WorkoutLogRequest,
    FeedbackRequest,
)
from app.db import WorkoutDatabase


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

    def get(self, url: str, params: dict = None) -> MockResponse:
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
        return MockResponse(404, {"detail": "Not found"})

    def post(self, url: str, json: dict = None) -> MockResponse:
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
            return MockResponse(404, {"detail": "Not found"})
        except ValidationError as e:
            return MockResponse(422, {"detail": e.errors()})
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
