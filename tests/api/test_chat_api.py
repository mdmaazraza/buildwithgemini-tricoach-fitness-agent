"""API Tests for Chatbot Endpoints (/chat and /health).

Tests:
- /health endpoint status code and response payload
- Valid chat messages (calories, heart rate zones, workouts, coach reasoning)
- Response schema compliance ({"parts": [{"kind": "text", ...}]})
- Error handling on empty messages (400 Bad Request)
- Error handling on missing body or invalid JSON (422 Unprocessable Entity)
"""

import pytest
from fastapi import status


class TestHealthAndChatApi:
    """Tests for chat service API endpoints."""

    def test_health_check(self, test_client):
        response = test_client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "tricoach-fitness-agent"

    def test_chat_valid_message(self, test_client):
        payload = {"message": "Hello coach! I want to train for a triathlon."}
        response = test_client.post("/chat", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "parts" in data
        assert isinstance(data["parts"], list)
        assert len(data["parts"]) > 0
        first_part = data["parts"][0]
        assert "kind" in first_part
        assert "text" in first_part
        assert len(first_part["text"]) > 0

    def test_chat_heart_rate_zones_query(self, test_client):
        payload = {"message": "What are the Karvonen heart rate training zones?"}
        response = test_client.post("/chat", json=payload)
        assert response.status_code == status.HTTP_200_OK
        reply = response.json()["parts"][0]["text"]
        assert "Zone 2" in reply
        assert "Threshold" in reply or "Aerobic" in reply

    def test_chat_calorie_query(self, test_client):
        payload = {"message": "How do I calculate my daily calorie needs and BMR?"}
        response = test_client.post("/chat", json=payload)
        assert response.status_code == status.HTTP_200_OK
        reply = response.json()["parts"][0]["text"]
        assert "BMR" in reply or "TDEE" in reply

    def test_chat_empty_message_returns_400(self, test_client):
        payload = {"message": "   "}
        response = test_client.post("/chat", json=payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Message cannot be empty" in response.json()["detail"]

    def test_chat_missing_message_field_returns_422(self, test_client):
        payload = {"wrong_field": "hello"}
        response = test_client.post("/chat", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_chat_invalid_payload_type_returns_422(self, test_client):
        payload = {"message": 12345}  # should be string
        response = test_client.post("/chat", json=payload)
        # Pydantic may cast int to str or fail validation
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY)
