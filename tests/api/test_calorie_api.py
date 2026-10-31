"""API Tests for Calorie & Nutrition Calculator Endpoints (/api/calories).

Tests:
- Valid calculation requests (male & female)
- Correct status codes (200 OK, 400 Bad Request, 422 Validation Error)
- Schema structure verification (status, data, bmr, tdee, macros)
- Boundary condition and edge case testing
"""

import pytest
from fastapi import status


class TestCalorieApi:
    """Tests for /api/calories endpoint."""

    def test_calculate_calories_success(self, test_client, sample_athlete):
        response = test_client.post("/api/calories", json=sample_athlete)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"
        res = data["data"]
        assert res["bmr"] > 1000
        assert res["tdee"] > res["bmr"]
        assert res["target_calories"] > 0
        assert "macros" in res
        assert res["macros"]["protein_grams"] > 0
        assert res["macros"]["carbs_grams"] > 0
        assert res["macros"]["fat_grams"] > 0

    def test_calculate_calories_female_fat_loss(self, test_client, sample_female_athlete):
        response = test_client.post("/api/calories", json=sample_female_athlete)
        assert response.status_code == status.HTTP_200_OK
        res = response.json()["data"]
        assert res["goal"] == "fat_loss"
        assert res["calorie_adjustment"] == -500

    def test_invalid_weight_returns_422(self, test_client):
        payload = {
            "weight_kg": 15.0,
            "height_cm": 175.0,
            "age": 25,
            "gender": "male",
            "activity_level": "moderate",
        }
        response = test_client.post("/api/calories", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_invalid_age_returns_422(self, test_client):
        payload = {
            "weight_kg": 70.0,
            "height_cm": 175.0,
            "age": 140,
            "gender": "male",
            "activity_level": "moderate",
        }
        response = test_client.post("/api/calories", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_unknown_activity_level_returns_400(self, test_client):
        payload = {
            "weight_kg": 70.0,
            "height_cm": 175.0,
            "age": 25,
            "gender": "male",
            "activity_level": "space_flight",
        }
        response = test_client.post("/api/calories", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unknown activity level" in response.json()["detail"]

    def test_unknown_goal_returns_400(self, test_client):
        payload = {
            "weight_kg": 70.0,
            "height_cm": 175.0,
            "age": 25,
            "gender": "male",
            "activity_level": "moderate",
            "goal": "be_invisible",
        }
        response = test_client.post("/api/calories", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unknown goal" in response.json()["detail"]
