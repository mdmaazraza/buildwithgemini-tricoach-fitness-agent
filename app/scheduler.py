"""Server-Side Background Scheduler for TriCoach AI Email Reports.

Implements:
1. Continuous background worker running as a daemon thread inside the server process.
2. Independent execution: continues running and dispatching reports when users close their browser.
3. Automated daily & weekly report triggers based on subscriber preferences and explicit consent.
4. Programmatic cron webhook endpoint trigger for free cloud hosting platforms (e.g. Render.com free tier).
5. Safe error isolation: individual delivery failures never crash the scheduler loop.
"""

import datetime
import logging
import threading
import time
from typing import Any

from app.db import default_db
from app.email_service import send_progress_email

logger = logging.getLogger("tricoach_scheduler")

_scheduler_thread = None
_stop_event = threading.Event()


def dispatch_scheduled_reports(
    period: str = "daily",
    db=None,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Dispatches scheduled daily or weekly reports to all verified, consented subscribers."""
    active_db = db or default_db
    frequency_key = "weekly" if period.lower() in ("weekly", "weekly_digest") else "daily"

    subscribers = active_db.get_active_subscribers(frequency=frequency_key)
    results = []

    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    for sub in subscribers:
        ath_id = sub["athlete_id"]
        email = sub["email"]
        last_sent = sub.get("last_sent_at")

        # Prevent duplicate sends on the same day unless forced
        if not force and last_sent and last_sent.startswith(today_str):
            logger.info(f"Skipping {frequency_key} report for {ath_id} ({email}): already sent today.")
            continue

        try:
            dispatch_result = send_progress_email(
                recipient_email=email,
                athlete_id=ath_id,
                report_date=today_str,
                period=period,
                db=active_db,
            )
            active_db.update_subscriber_last_sent(ath_id)
            results.append(dispatch_result)
            logger.info(f"Dispatched {frequency_key} report to {email} (status: {dispatch_result['status']}).")
        except Exception as e:
            logger.error(f"Failed to dispatch {frequency_key} report to {email}: {e}")
            results.append({
                "athlete_id": ath_id,
                "recipient_email": email,
                "status": "failed",
                "error_message": str(e),
            })

    return results


def _scheduler_loop(db=None, poll_interval_seconds: int = 60):
    """Background daemon loop checking time and dispatching reports."""
    logger.info("TriCoach AI background email scheduler started.")

    while not _stop_event.is_set():
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            # Default scheduled trigger time: 08:00 UTC (morning report)
            is_dispatch_time = now_utc.hour == 8 and now_utc.minute == 0

            if is_dispatch_time:
                # 1. Daily reports
                dispatch_scheduled_reports(period="daily", db=db)

                # 2. Weekly reports on Sundays (weekday 6)
                if now_utc.weekday() == 6:
                    dispatch_scheduled_reports(period="weekly", db=db)

                # Sleep slightly over 60 seconds to avoid double-triggering in the same minute
                time.sleep(65)
                continue
        except Exception as e:
            logger.error(f"Error in background scheduler loop: {e}")

        _stop_event.wait(timeout=poll_interval_seconds)


def start_background_scheduler(db=None) -> threading.Thread:
    """Launches the server-side scheduler as a daemon thread."""
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return _scheduler_thread

    _stop_event.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(db,),
        daemon=True,
        name="TriCoachEmailScheduler",
    )
    _scheduler_thread.start()
    logger.info("TriCoach background email scheduler thread spawned.")
    return _scheduler_thread


def stop_background_scheduler():
    """Stops the scheduler thread cleanly (used in teardown/tests)."""
    _stop_event.set()
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=2.0)
    _scheduler_thread = None
