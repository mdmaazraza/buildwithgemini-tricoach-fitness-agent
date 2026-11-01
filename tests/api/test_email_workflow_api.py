"""API tests for the Email Subscription, Verification, and Scheduled Cron endpoints.
"""

import uuid
from fastapi import status


class TestEmailWorkflowApi:
    """Verifies REST endpoints for subscription, verification, and cron triggers."""

    def test_subscription_creation_and_retrieval(self, test_client):
        ath_id = f"ath-sub-{uuid.uuid4().hex[:6]}"

        # 1. Initially no subscription
        res = test_client.get(f"/api/reports/subscription?athlete_id={ath_id}")
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["subscription"] is None

        # 2. Save subscription
        payload = {
            "athlete_id": ath_id,
            "email": f"{ath_id}@example.com",
            "report_frequency": "both",
            "user_consent": True,
            "preferred_time_utc": "08:00",
        }
        res_post = test_client.post("/api/reports/subscription", json=payload)
        assert res_post.status_code == status.HTTP_200_OK
        sub = res_post.json()["subscription"]
        assert sub["email"] == f"{ath_id}@example.com"
        assert sub["is_verified"] is False
        assert sub["user_consent"] is True
        token = sub["verification_token"]

        # 3. Retrieve saved subscription
        res_get = test_client.get(f"/api/reports/subscription?athlete_id={ath_id}")
        assert res_get.status_code == status.HTTP_200_OK
        assert res_get.json()["subscription"]["email"] == f"{ath_id}@example.com"

        # 4. Verify with wrong token fails
        res_bad_verify = test_client.post("/api/reports/verify", json={"athlete_id": ath_id, "token": "invalid_token"})
        assert res_bad_verify.status_code == status.HTTP_400_BAD_REQUEST

        # 5. Verify with correct token succeeds
        res_good_verify = test_client.post("/api/reports/verify", json={"athlete_id": ath_id, "token": token})
        assert res_good_verify.status_code == status.HTTP_200_OK
        assert res_good_verify.json()["verified"] is True

        # 6. Retrieve again and verify active state
        res_verified = test_client.get(f"/api/reports/subscription?athlete_id={ath_id}")
        assert res_verified.json()["subscription"]["is_verified"] is True

    def test_cron_trigger_endpoint(self, test_client, monkeypatch):
        # 1. Setup verified subscriber
        ath_id = f"ath-cron-{uuid.uuid4().hex[:6]}"
        sub_payload = {
            "athlete_id": ath_id,
            "email": f"{ath_id}@example.com",
            "report_frequency": "daily",
            "user_consent": True,
        }
        res_sub = test_client.post("/api/reports/subscription", json=sub_payload)
        token = res_sub.json()["subscription"]["verification_token"]
        test_client.post("/api/reports/verify", json={"athlete_id": ath_id, "token": token})

        # 2. Trigger daily cron without secret when CRON_SECRET is unset
        monkeypatch.delenv("CRON_SECRET", raising=False)
        res_cron = test_client.post("/api/reports/cron-trigger", json={"period": "daily", "force": True})
        assert res_cron.status_code == status.HTTP_200_OK
        assert res_cron.json()["dispatched_count"] >= 1

        # 3. Test secret authorization when CRON_SECRET is configured
        monkeypatch.setenv("CRON_SECRET", "super_secret_cron_123")
        res_unauth = test_client.post("/api/reports/cron-trigger", json={"period": "daily", "secret": "wrong_secret", "force": True})
        assert res_unauth.status_code == status.HTTP_401_UNAUTHORIZED

        res_auth = test_client.post("/api/reports/cron-trigger", json={"period": "daily", "secret": "super_secret_cron_123", "force": True})
        assert res_auth.status_code == status.HTTP_200_OK
