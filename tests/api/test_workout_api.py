"""API Tests for Workout Logging & History Endpoints (/api/workouts and /feedback).

Tests:
- Successful workout logging (Run, Bike, Swim)
- Retrieval of logged workouts
- Input validation (duration > 0, realistic heart rate)
- User feedback submission
"""

from fastapi import status


class TestWorkoutApi:
    """Tests for workout logging and history endpoints."""

    def test_log_workout_success(self, test_client, sample_workout_payload):
        response = test_client.post("/api/workouts", json=sample_workout_payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"
        record = data["workout"]
        assert record["activity_type"] == sample_workout_payload["activity_type"]
        assert record["duration_minutes"] == sample_workout_payload["duration_minutes"]
        assert record["distance_km"] == sample_workout_payload["distance_km"]
        assert "workout_id" in record

    def test_list_workouts_success(self, test_client, sample_workout_payload):
        # Log first
        test_client.post("/api/workouts", json=sample_workout_payload)

        # Retrieve
        response = test_client.get(
            f"/api/workouts?athlete_id={sample_workout_payload['athlete_id']}&limit=5"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] >= 1
        assert len(data["workouts"]) >= 1

    def test_log_workout_negative_duration_returns_422(self, test_client):
        payload = {
            "activity_type": "Run",
            "duration_minutes": -45,  # Invalid
            "distance_km": 5.0,
            "avg_heart_rate": 150,
            "intensity_zone": "Zone 2",
        }
        response = test_client.post("/api/workouts", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_log_workout_extreme_heart_rate_returns_422(self, test_client):
        payload = {
            "activity_type": "Run",
            "duration_minutes": 45,
            "distance_km": 5.0,
            "avg_heart_rate": 280,  # Extreme / invalid
            "intensity_zone": "Zone 5",
        }
        response = test_client.post("/api/workouts", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_submit_feedback_success(self, test_client):
        payload = {"score": 5, "comment": "Excellent workout recommendation!"}
        response = test_client.post("/feedback", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "received"
        assert data["feedback"]["score"] == 5
