"""API Tests for Fitness Tracker Endpoints (Profile, Food, Activities, Measurements, Analytics, Email, Grounded Chat).
"""

from fastapi import status


class TestTrackerApi:
    """Tests for enhanced fitness tracking and analytics API endpoints."""

    def test_get_and_save_profile(self, test_client):
        # 1. Fetch default profile
        res_get = test_client.get("/api/profile?athlete_id=ath-api-01")
        assert res_get.status_code == status.HTTP_200_OK
        prof = res_get.json()["profile"]
        assert prof["athlete_id"] == "ath-api-01"

        # 2. Update profile
        payload = {
            "athlete_id": "ath-api-01",
            "age": 30,
            "height_cm": 180.0,
            "current_weight_kg": 76.5,
            "sex": "male",
            "activity_level": "very_active",
            "goal": "fat_loss",
            "target_weight_kg": 72.0,
            "preferred_units": "metric",
            "target_rate_change": 0.5,
        }
        res_post = test_client.post("/api/profile", json=payload)
        assert res_post.status_code == status.HTTP_200_OK
        updated = res_post.json()["profile"]
        assert updated["current_weight_kg"] == 76.5
        assert updated["goal"] == "fat_loss"

    def test_food_lifecycle_and_natural_parser(self, test_client):
        # 1. Natural language parse test
        parse_req = {
            "text": "I ate 2 boiled eggs and 1 bowl of oatmeal",
            "meal_type": "breakfast",
        }
        res_parse = test_client.post("/api/food/parse-natural", json=parse_req)
        assert res_parse.status_code == status.HTTP_200_OK
        data = res_parse.json()
        assert len(data["items"]) >= 2
        assert any("egg" in item["food_name"].lower() for item in data["items"])
        assert data["is_estimated"] is True

        # 2. Log food item
        food_req = {
            "athlete_id": "ath-food-api",
            "date": "2026-10-31",
            "meal_type": "breakfast",
            "food_name": "Greek Yogurt",
            "quantity": 1.0,
            "unit": "cup",
            "calories": 130.0,
            "protein_g": 15.0,
            "carbs_g": 8.0,
            "fat_g": 2.0,
            "fiber_g": 0.0,
            "data_source": "verified_db",
            "is_verified": True,
        }
        res_log = test_client.post("/api/food/entries", json=food_req)
        assert res_log.status_code == status.HTTP_200_OK
        entry = res_log.json()["entry"]
        entry_id = entry["entry_id"]

        # 3. Retrieve entries
        res_list = test_client.get("/api/food/entries?athlete_id=ath-food-api&date=2026-10-31")
        assert res_list.status_code == status.HTTP_200_OK
        assert res_list.json()["count"] >= 1

        # 4. Update entry
        res_update = test_client.put(f"/api/food/entries/{entry_id}", json={"quantity": 2.0, "calories": 260.0})
        assert res_update.status_code == status.HTTP_200_OK
        assert res_update.json()["entry"]["calories"] == 260.0

        # 5. Delete entry
        res_del = test_client.delete(f"/api/food/entries/{entry_id}")
        assert res_del.status_code == status.HTTP_200_OK
        assert res_del.json()["deleted"] is True

    def test_activity_lifecycle(self, test_client):
        act_req = {
            "athlete_id": "ath-act-api",
            "date": "2026-10-31",
            "activity_type": "Running",
            "duration_minutes": 50,
            "intensity": "vigorous",
            "distance_km": 10.0,
            "steps": 9200,
            "calories_burned": 650.0,
            "data_source": "manual",
        }
        res_post = test_client.post("/api/activities", json=act_req)
        assert res_post.status_code == status.HTTP_200_OK
        act_id = res_post.json()["activity"]["activity_id"]

        res_list = test_client.get("/api/activities?athlete_id=ath-act-api&date=2026-10-31")
        assert res_list.status_code == status.HTTP_200_OK
        assert res_list.json()["count"] >= 1

        res_del = test_client.delete(f"/api/activities/{act_id}")
        assert res_del.status_code == status.HTTP_200_OK
        assert res_del.json()["deleted"] is True

    def test_measurement_lifecycle_and_weight_sync(self, test_client):
        meas_req = {
            "athlete_id": "ath-sync-test",
            "date": "2026-10-31",
            "weight_kg": 73.2,
            "waist_cm": 82.5,
            "body_fat_pct": 16.0,
            "measurement_method": "scale",
            "notes": "Morning check",
        }
        res_post = test_client.post("/api/measurements", json=meas_req)
        assert res_post.status_code == status.HTTP_200_OK
        meas_id = res_post.json()["measurement"]["measurement_id"]

        # Confirm profile was synced
        prof = test_client.get("/api/profile?athlete_id=ath-sync-test").json()["profile"]
        assert prof["current_weight_kg"] == 73.2

        res_del = test_client.delete(f"/api/measurements/{meas_id}")
        assert res_del.status_code == status.HTTP_200_OK

    def test_analytics_endpoints(self, test_client):
        # 1. Daily summary
        res_summary = test_client.get("/api/analytics/daily-summary?athlete_id=athlete-01")
        assert res_summary.status_code == status.HTTP_200_OK
        sum_data = res_summary.json()
        assert "nutrition" in sum_data
        assert "energy_balance" in sum_data
        assert "estimated_calorie_balance" in sum_data["energy_balance"]

        # 2. Trends
        res_trends = test_client.get("/api/analytics/trends?athlete_id=athlete-01&days=30")
        assert res_trends.status_code == status.HTTP_200_OK
        trends_data = res_trends.json()["trends"]
        assert "rolling_7d_history" in trends_data
        assert "uncertainties" in trends_data

        # 3. Confidence
        res_conf = test_client.get("/api/analytics/confidence?athlete_id=athlete-01&days=7")
        assert res_conf.status_code == status.HTTP_200_OK
        conf_data = res_conf.json()["confidence"]
        assert "confidence_score" in conf_data
        assert "confidence_tier" in conf_data

    def test_email_report_simulation_and_history(self, test_client):
        email_req = {
            "recipient_email": "runner@example.com",
            "athlete_id": "athlete-01",
            "period": "daily",
        }
        res_send = test_client.post("/api/reports/email", json=email_req)
        assert res_send.status_code == status.HTTP_200_OK
        rep = res_send.json()["report"]
        assert rep["status"] in ("simulated", "sent")
        assert "TriCoach AI" in rep["subject"]

        res_hist = test_client.get("/api/reports/email/history?athlete_id=athlete-01")
        assert res_hist.status_code == status.HTTP_200_OK
        assert res_hist.json()["count"] >= 1

    def test_grounded_chat_pulls_database_nutrition(self, test_client):
        # Query chatbot about consumed calories
        chat_req = {
            "message": "How many calories did I consume today and what is my calorie balance?",
            "user_id": "athlete-01",
        }
        res_chat = test_client.post("/chat", json=chat_req)
        assert res_chat.status_code == status.HTTP_200_OK
        reply = res_chat.json()["parts"][0]["text"]
        # Grounded response must include calorie / balance information from the stored records
        assert "calorie" in reply.lower() or "balance" in reply.lower()
