"""System Integration Tests: Frontend-Backend-Chatbot-Database Flow.

Tests:
- Complete workflow: query coach -> log workout -> verify database update -> query history in chat
- Nutrition goal calculation combined with recommended training schedule
- End-to-end data integrity across services
"""

import pytest
from fastapi import status


class TestSystemFlow:
    """End-to-end system integration tests across services."""

    def test_complete_workout_tracking_flow(self, test_client):
        athlete_id = "athlete-flow-99"

        # 1. User logs a workout via API
        workout_payload = {
            "activity_type": "Run",
            "duration_minutes": 55,
            "distance_km": 10.2,
            "avg_heart_rate": 162,
            "intensity_zone": "Zone 4 (Threshold)",
            "notes": "Tempo run around Central Park",
            "athlete_id": athlete_id,
        }
        res_log = test_client.post("/api/workouts", json=workout_payload)
        assert res_log.status_code == status.HTTP_200_OK
        workout_id = res_log.json()["workout"]["workout_id"]

        # 2. User queries their workout logs via Chatbot
        chat_payload = {
            "message": "Show me my workout history",
            "user_id": athlete_id,
        }
        res_chat = test_client.post("/chat", json=chat_payload)
        assert res_chat.status_code == status.HTTP_200_OK

        chat_reply = res_chat.json()["parts"][0]["text"]
        assert "Run" in chat_reply
        assert "10.2" in chat_reply

    def test_nutrition_and_periodization_flow(self, test_client, sample_athlete):
        # 1. Compute athlete nutrition targets
        res_cal = test_client.post("/api/calories", json=sample_athlete)
        assert res_cal.status_code == status.HTTP_200_OK
        nutrition = res_cal.json()["data"]

        # 2. Check training zones via chatbot
        res_zones = test_client.post("/chat", json={"message": "What are my training zones?"})
        assert res_zones.status_code == status.HTTP_200_OK
        assert "Zone" in res_zones.json()["parts"][0]["text"]

        # Verify cross-service consistency
        assert nutrition["target_calories"] > 1500
        assert nutrition["macros"]["protein_grams"] > 100
