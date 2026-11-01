"""Unit and integration tests for the Email Reporting System.

Verifies:
1. Resend API dispatch handling and mock API integration.
2. Safe simulation fallback when credentials are not configured.
3. Weekly digest and daily summary calculation and formatting.
4. Email subscription, user consent, verification token generation and verification.
5. Scheduled background report dispatch logic.
"""

from unittest.mock import MagicMock, patch

from app.db import WorkoutDatabase
from app.email_service import (
    dispatch_email,
    generate_progress_report_content,
    send_progress_email,
    send_verification_email,
)
from app.scheduler import dispatch_scheduled_reports


class TestResendAndEmailDispatch:
    """Tests for Resend API dispatch, SMTP fallback, and simulated delivery."""

    def test_simulated_dispatch_when_no_credentials(self, monkeypatch):
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        monkeypatch.delenv("SMTP_HOST", raising=False)

        res = dispatch_email(
            recipient_email="athlete@example.com",
            subject="Test Subject",
            text_content="Test body",
            html_content="<p>Test body</p>",
        )
        assert res["status"] == "simulated"
        assert res["provider"] == "simulated"
        assert res["error_message"] == ""

    def test_resend_api_dispatch_success(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key_12345")
        monkeypatch.setenv("RESEND_FROM_EMAIL", "TriCoach AI <onboarding@resend.dev>")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "resend_msg_abc123"}

        with patch("httpx.post", return_value=mock_resp) as mock_post:
            res = dispatch_email(
                recipient_email="user@example.com",
                subject="Daily Progress",
                text_content="Body text",
                html_content="<p>Body html</p>",
            )
            assert res["status"] == "sent"
            assert res["provider"] == "resend"
            assert res["error_message"] == ""

            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0] == "https://api.resend.com/emails"
            assert kwargs["headers"]["Authorization"] == "Bearer re_test_key_12345"
            assert kwargs["json"]["to"] == ["user@example.com"]
            assert kwargs["json"]["from"] == "TriCoach AI <onboarding@resend.dev>"

    def test_resend_api_dispatch_failure_handling(self, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "re_test_key_12345")

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "Forbidden: sender domain not verified"

        with patch("httpx.post", return_value=mock_resp):
            res = dispatch_email(
                recipient_email="user@example.com",
                subject="Daily Progress",
                text_content="Body text",
                html_content="<p>Body html</p>",
            )
            assert res["status"] == "failed"
            assert res["provider"] == "resend"
            assert "403" in res["error_message"]


class TestEmailReportContentGeneration:
    """Verifies that daily and weekly reports contain all required nutritional, workout, and weight data."""

    def test_daily_report_generation(self):
        db = WorkoutDatabase(db_path=":memory:")
        ath_id = "ath-rep-daily"

        db.save_profile(athlete_id=ath_id, age=30, height_cm=180.0, current_weight_kg=75.0, sex="male", activity_level="moderate", goal="fat_loss")
        db.log_food_entry(athlete_id=ath_id, date_str="2026-11-01", meal_type="breakfast", food_name="Oatmeal", quantity=1, unit="bowl", calories=300, protein_g=12, carbs_g=50, fat_g=5)
        db.log_activity_entry(athlete_id=ath_id, date_str="2026-11-01", activity_type="Run", duration_minutes=40, calories_burned=400)
        db.log_measurement(athlete_id=ath_id, date_str="2026-11-01", weight_kg=75.0)

        report = generate_progress_report_content(athlete_id=ath_id, report_date="2026-11-01", period="daily", db=db)
        assert "Daily Fitness Report" in report["subject"]
        assert "Calories Consumed: 300.0 kcal" in report["text"]
        assert "Protein: 12.0g" in report["text"]
        assert "Current Weight: 75.0 kg" in report["text"]
        assert "Tracked Workouts: 1 session(s)" in report["text"]

    def test_weekly_digest_aggregation(self):
        db = WorkoutDatabase(db_path=":memory:")
        ath_id = "ath-rep-weekly"

        db.save_profile(athlete_id=ath_id, age=28, height_cm=175.0, current_weight_kg=70.0, sex="male", activity_level="moderate", goal="maintenance")

        # Log meals and activities over 3 days
        dates = ["2026-10-27", "2026-10-29", "2026-10-31"]
        for d in dates:
            db.log_food_entry(athlete_id=ath_id, date_str=d, meal_type="lunch", food_name="Chicken & Rice", quantity=1, unit="plate", calories=600, protein_g=40, carbs_g=70, fat_g=15)
            db.log_activity_entry(athlete_id=ath_id, date_str=d, activity_type="Bike", duration_minutes=60, distance_km=25.0, calories_burned=500)

        report = generate_progress_report_content(athlete_id=ath_id, report_date="2026-11-01", period="weekly", db=db)
        assert "Weekly Fitness Digest" in report["subject"]
        assert "Total Calories Consumed: 1800 kcal" in report["text"]
        assert "Total Completed Workouts: 3 session(s)" in report["text"]
        assert "Total Distance Covered: 75.0 km" in report["text"]
        assert "Total Training Time: 180 minutes" in report["text"]


class TestSubscriptionVerificationAndScheduler:
    """Verifies user consent, token verification, and server-side scheduled dispatch."""

    def test_subscription_creation_and_consent(self):
        db = WorkoutDatabase(db_path=":memory:")
        ath_id = "ath-sub-01"

        sub = db.save_email_subscription(
            athlete_id=ath_id,
            email="athlete@example.com",
            report_frequency="both",
            user_consent=True,
        )
        assert sub["email"] == "athlete@example.com"
        assert sub["user_consent"] is True
        assert sub["is_verified"] is False
        assert len(sub["verification_token"]) >= 8

        # Unverified subscriber should not be in active subscribers list
        active = db.get_active_subscribers(frequency="daily")
        assert not any(s["athlete_id"] == ath_id for s in active)

    def test_verification_token_lifecycle(self):
        db = WorkoutDatabase(db_path=":memory:")
        ath_id = "ath-sub-02"

        sub = db.save_email_subscription(
            athlete_id=ath_id,
            email="athlete@example.com",
            report_frequency="daily",
            user_consent=True,
        )
        token = sub["verification_token"]

        # Incorrect token fails
        assert db.verify_email_subscription(ath_id, "wrong_token") is False

        # Correct token succeeds
        assert db.verify_email_subscription(ath_id, token) is True

        # Now active
        active = db.get_active_subscribers(frequency="daily")
        assert any(s["athlete_id"] == ath_id for s in active)

    def test_send_verification_email(self):
        db = WorkoutDatabase(db_path=":memory:")
        ath_id = "ath-verif-test"

        res = send_verification_email(
            athlete_id=ath_id,
            recipient_email="verify@example.com",
            verification_token="token_abc_123",
            base_url="http://localhost:8080",
            db=db,
        )
        assert res["status"] in ("sent", "simulated")
        assert res["verification_token"] == "token_abc_123"
        assert "token=token_abc_123" in res["verify_url"]

        # Check DB audit log
        logs = db.get_email_reports(ath_id)
        assert len(logs) >= 1
        assert logs[0]["report_period"] == "verification"

    def test_dispatch_scheduled_reports(self):
        db = WorkoutDatabase(db_path=":memory:")
        ath_id = "ath-sched-01"

        db.save_profile(athlete_id=ath_id, age=25, height_cm=170.0, current_weight_kg=65.0, sex="female", activity_level="light", goal="fat_loss")
        sub = db.save_email_subscription(
            athlete_id=ath_id,
            email="sched@example.com",
            report_frequency="daily",
            user_consent=True,
        )
        db.verify_email_subscription(ath_id, sub["verification_token"])

        dispatched = dispatch_scheduled_reports(period="daily", db=db, force=True)
        assert len(dispatched) >= 1
        assert dispatched[0]["recipient_email"] == "sched@example.com"
        assert dispatched[0]["status"] in ("sent", "simulated")

        # Verify DB audit log
        reports = db.get_email_reports(ath_id)
        assert any(r["report_period"] == "daily" for r in reports)
