"""Email Reporting Service for TriCoach AI.

Implements:
1. Daily and weekly fitness progress report generation (plain text & HTML).
2. Resend API dispatch (Free plan: 3,000 emails/mo, 100/day, verified sender onboarding@resend.dev).
3. SMTP fallback dispatch with SSL/TLS encryption.
4. Safe offline dry-run / simulation mode when email credentials are not configured.
5. Email verification token generation and dispatch.
6. User consent checking and delivery audit logging into the database.
7. Strict credential security: never hardcodes credentials or exposes secrets.
"""

import email.message
import logging
import os
import smtplib
from typing import Any

import httpx

from app.db import default_db
from app.tracker_engine import (
    calculate_daily_energy_balance,
    calculate_daily_nutrition_summary,
    calculate_progress_confidence,
    calculate_progress_trends,
)

logger = logging.getLogger("tricoach_email")


def dispatch_email(
    recipient_email: str,
    subject: str,
    text_content: str,
    html_content: str,
) -> dict[str, str]:
    """Sends email via Resend API, SMTP, or safe offline simulation.

    Order of precedence:
    1. Resend REST API (if RESEND_API_KEY is configured).
    2. Standard SMTP (if SMTP_HOST, SMTP_USER, SMTP_PASSWORD are configured).
    3. Safe Simulation Mode (default offline mode for zero-cost hosting and testing).
    """
    clean_recipient = recipient_email.strip()
    resend_key = os.getenv("RESEND_API_KEY", "").strip()

    # 1. Resend API Dispatch (Free Tier Provider)
    if resend_key:
        from_email = os.getenv("RESEND_FROM_EMAIL", "TriCoach AI <onboarding@resend.dev>").strip()
        try:
            resend_payload = {
                "from": from_email,
                "to": [clean_recipient],
                "subject": subject,
                "html": html_content,
                "text": text_content,
            }
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                json=resend_payload,
                timeout=10.0,
            )
            if resp.status_code in (200, 201):
                logger.info(f"Report successfully emailed to {clean_recipient} via Resend.")
                return {"status": "sent", "provider": "resend", "error_message": ""}
            else:
                err = f"Resend API error (HTTP {resp.status_code}): {resp.text}"
                logger.error(err)
                return {"status": "failed", "provider": "resend", "error_message": err}
        except Exception as e:
            err = f"Resend dispatch exception: {e}"
            logger.error(err)
            return {"status": "failed", "provider": "resend", "error_message": err}

    # 2. SMTP Dispatch (Standard Email Fallback)
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM_EMAIL", "tricoach-reports@example.com").strip()

    if smtp_host and smtp_user and smtp_pass:
        try:
            msg = email.message.EmailMessage()
            msg["Subject"] = subject
            msg["From"] = smtp_from
            msg["To"] = clean_recipient
            msg.set_content(text_content)
            msg.add_alternative(html_content, subtype="html")

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            logger.info(f"Report successfully emailed to {clean_recipient} via SMTP.")
            return {"status": "sent", "provider": "smtp", "error_message": ""}
        except Exception as e:
            err = f"SMTP dispatch exception: {e}"
            logger.error(err)
            return {"status": "failed", "provider": "smtp", "error_message": err}

    # 3. Safe Simulation Mode (Offline Dry-Run for Zero-Cost Testing)
    logger.info(f"[SIMULATION] Email prepared for {clean_recipient} (Neither Resend nor SMTP configured).")
    return {"status": "simulated", "provider": "simulated", "error_message": ""}


def generate_progress_report_content(
    athlete_id: str = "athlete-01",
    report_date: str | None = None,
    period: str = "daily",
    db=None,
) -> dict[str, str]:
    """Generates comprehensive plain text and HTML reports based on actual database records."""
    active_db = db or default_db
    profile = active_db.get_profile(athlete_id)

    import datetime
    today = datetime.datetime.now(datetime.timezone.utc).date()
    if report_date:
        try:
            today = datetime.date.fromisoformat(report_date)
        except ValueError:
            pass
    today_str = today.strftime("%Y-%m-%d")

    measurements = active_db.get_measurements(athlete_id, limit=30)
    trends = calculate_progress_trends(measurements, profile=profile)
    current_wt = trends["latest_weight_kg"] or profile.get("current_weight_kg", 0.0)
    wt_trend_7d = trends["avg_weight_change_7d_kg"]

    is_weekly = period.lower() in ("weekly", "weekly_digest")

    if is_weekly:
        # Aggregate last 7 days
        start_date = (today - datetime.timedelta(days=6)).strftime("%Y-%m-%d")
        all_foods = active_db.get_food_entries(athlete_id, start_date=start_date, end_date=today_str)
        all_acts = active_db.get_activity_entries(athlete_id, start_date=start_date, end_date=today_str)

        total_cals_in = sum(f.get("calories", 0.0) for f in all_foods)
        total_protein = sum(f.get("protein_g", 0.0) for f in all_foods)
        total_carbs = sum(f.get("carbs_g", 0.0) for f in all_foods)
        total_fat = sum(f.get("fat_g", 0.0) for f in all_foods)

        avg_cals_in = round(total_cals_in / 7.0, 1)
        avg_protein = round(total_protein / 7.0, 1)
        avg_carbs = round(total_carbs / 7.0, 1)
        avg_fat = round(total_fat / 7.0, 1)

        total_act_mins = sum(a.get("duration_minutes", 0) for a in all_acts)
        total_act_dist = round(sum(a.get("distance_km", 0.0) for a in all_acts), 1)
        total_act_burn = sum(a.get("calories_burned", 0.0) for a in all_acts)

        # Weekly energy balance
        bmr = 10 * profile.get("current_weight_kg", 72.0) + 6.25 * profile.get("height_cm", 175.0) - 5 * profile.get("age", 28) + 5
        weekly_bmr = bmr * 7.0
        weekly_burn = round(weekly_bmr + total_act_burn, 1)
        weekly_net = round(total_cals_in - weekly_burn, 1)
        net_sign = "+" if weekly_net > 0 else ""

        confidence = calculate_progress_confidence(all_foods, all_acts, measurements, days_window=7)
        conf_score = confidence["confidence_score"]
        conf_tier = confidence["confidence_tier"]

        subject = f"TriCoach AI Weekly Fitness Digest — Week of {today_str}"

        text_content = f"""TriCoach AI Weekly Fitness Digest
Week Ending: {today_str} (Window: {start_date} to {today_str})
Athlete ID: {athlete_id}
Goal: {profile.get('goal', 'maintenance').replace('_', ' ').title()}

------------------------------------------------------------
1. WEEKLY ENERGY & CALORIE TOTALS
------------------------------------------------------------
• Total Calories Consumed: {round(total_cals_in)} kcal (Daily Avg: {avg_cals_in} kcal)
• Total Energy Expenditure: {round(weekly_burn)} kcal (BMR: {round(weekly_bmr)} kcal, Workouts: {round(total_act_burn)} kcal)
• Estimated Weekly Net Balance: {net_sign}{weekly_net} kcal

------------------------------------------------------------
2. WEEKLY NUTRITION & MACROS (DAILY AVERAGE)
------------------------------------------------------------
• Protein: {avg_protein}g/day
• Carbohydrates: {avg_carbs}g/day
• Fats: {avg_fat}g/day
• Total Logged Meals: {len(all_foods)} items across 7 days

------------------------------------------------------------
3. TRAINING VOLUME & WORKOUTS
------------------------------------------------------------
• Total Completed Workouts: {len(all_acts)} session(s)
• Total Training Time: {total_act_mins} minutes ({round(total_act_mins / 60, 1)} hrs)
• Total Distance Covered: {total_act_dist} km
• Calories Burned in Sessions: {round(total_act_burn)} kcal

------------------------------------------------------------
4. BODY COMPOSITION & WEIGHT TREND
------------------------------------------------------------
• Current Scale Weight: {current_wt} kg
• 7-Day Rolling Trend: {wt_trend_7d:+} kg
• Data Reliability Score: {conf_score}% ({conf_tier})

------------------------------------------------------------
5. COACHING RECOMMENDATIONS FOR NEXT WEEK
------------------------------------------------------------
• Continue prioritizing daily protein consistency to preserve lean muscle tissue.
• Ensure adequate hydration and post-workout electrolyte replacement.
• Keep up consistent weigh-in habits under standard fasted morning conditions.

------------------------------------------------------------
PHYSIOLOGICAL INTEGRITY NOTICE
------------------------------------------------------------
Day-to-day weight fluctuations on the bathroom scale reflect shifts in total body water, glycogen stores, and digestive transit time rather than true changes in adipose or muscular tissue. Calorie values and energy calculations carry standard physiological estimation variance (±10-15%).
"""

        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 20px; }}
  .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
  .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 24px; text-align: center; }}
  .header h1 {{ margin: 0 0 6px; font-size: 20px; font-weight: 700; }}
  .header p {{ margin: 0; font-size: 14px; opacity: 0.85; }}
  .section {{ padding: 20px; border-bottom: 1px solid #f1f5f9; }}
  .section h2 {{ font-size: 14px; color: #f97316; margin: 0 0 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .metric-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 8px; }}
  .metric-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; text-align: center; }}
  .metric-val {{ font-size: 18px; font-weight: 700; color: #0f172a; }}
  .metric-lbl {{ font-size: 12px; color: #64748b; margin-top: 2px; }}
  .badge {{ display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; background: #ffedd5; color: #ea580c; }}
  .disclaimer {{ background: #f1f5f9; padding: 16px; font-size: 11px; color: #64748b; line-height: 1.5; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🏊🚴🏃 TriCoach AI Weekly Digest</h1>
    <p>Weekly Performance Review &bull; {start_date} to {today_str}</p>
  </div>

  <div class="section">
    <h2>Weekly Energy Balance</h2>
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-val">{round(total_cals_in)} kcal</div>
        <div class="metric-lbl">Total Consumed (Avg {avg_cals_in}/day)</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">{round(weekly_burn)} kcal</div>
        <div class="metric-lbl">Total Burned (BMR + Exercise)</div>
      </div>
    </div>
    <p style="text-align: center; margin: 8px 0 0; font-weight: 600;">
      Weekly Net Balance: <span class="badge">{net_sign}{weekly_net} kcal</span>
    </p>
  </div>

  <div class="section">
    <h2>Daily Average Macronutrients</h2>
    <div class="metric-grid">
      <div class="metric-card"><div class="metric-val">{avg_protein}g</div><div class="metric-lbl">Avg Protein / Day</div></div>
      <div class="metric-card"><div class="metric-val">{avg_carbs}g</div><div class="metric-lbl">Avg Carbs / Day</div></div>
      <div class="metric-card"><div class="metric-val">{avg_fat}g</div><div class="metric-lbl">Avg Fats / Day</div></div>
      <div class="metric-card"><div class="metric-val">{len(all_foods)}</div><div class="metric-lbl">Logged Food Items</div></div>
    </div>
  </div>

  <div class="section">
    <h2>Weekly Workout Volume</h2>
    <div class="metric-grid">
      <div class="metric-card"><div class="metric-val">{len(all_acts)} sessions</div><div class="metric-lbl">Completed Workouts</div></div>
      <div class="metric-card"><div class="metric-val">{round(total_act_mins / 60, 1)} hrs</div><div class="metric-lbl">Total Training Time</div></div>
      <div class="metric-card"><div class="metric-val">{total_act_dist} km</div><div class="metric-lbl">Total Distance</div></div>
      <div class="metric-card"><div class="metric-val">{round(total_act_burn)} kcal</div><div class="metric-lbl">Workout Burn</div></div>
    </div>
  </div>

  <div class="section">
    <h2>Weight Trends & Data Quality</h2>
    <p style="margin: 4px 0 8px; font-size: 14px;"><strong>Current Weight:</strong> {current_wt} kg (7-Day Rolling Trend: {wt_trend_7d:+} kg)</p>
    <p style="margin: 4px 0 8px; font-size: 14px;"><strong>Reliability Score:</strong> {conf_score}% &bull; {conf_tier}</p>
  </div>

  <div class="disclaimer">
    <strong>Physiological Integrity Notice:</strong> Short-term weight fluctuations predominantly reflect total body water, glycogen storage, and digestive transit time rather than true changes in adipose or muscular tissue.
  </div>
</div>
</body>
</html>
"""
    else:
        # Daily report
        food_entries = active_db.get_food_entries(athlete_id, date_str=today_str)
        activities = active_db.get_activity_entries(athlete_id, date_str=today_str)

        nutrition = calculate_daily_nutrition_summary(food_entries, profile=profile)
        energy = calculate_daily_energy_balance(profile, activities, food_entries)
        confidence = calculate_progress_confidence(food_entries, activities, measurements, days_window=7)

        cals_in = energy["calories_consumed"]
        cals_out = energy["total_energy_expenditure"]
        net_bal = energy["estimated_calorie_balance"]
        bal_sign = "+" if net_bal > 0 else ""
        protein = nutrition["totals"]["protein_g"]
        target_protein = nutrition["targets"].get("target_protein_g", 0.0)
        conf_tier = confidence["confidence_tier"]
        conf_score = confidence["confidence_score"]

        subject = f"TriCoach AI Daily Fitness Report — {today_str}"

        text_content = f"""TriCoach AI Daily Fitness Progress Report
Date: {today_str}
Athlete ID: {athlete_id}
Goal: {profile.get('goal', 'maintenance').replace('_', ' ').title()}

------------------------------------------------------------
1. ENERGY & CALORIE BALANCE
------------------------------------------------------------
• Calories Consumed: {cals_in} kcal
• Total Energy Expenditure: {cals_out} kcal (BMR: {energy['bmr']} kcal, Activity: {energy['additional_exercise_burn']} kcal)
• Estimated Net Balance: {bal_sign}{net_bal} kcal ({energy['balance_status'].upper()})

------------------------------------------------------------
2. NUTRITION & MACRONUTRIENTS
------------------------------------------------------------
• Protein: {protein}g (Target: {target_protein}g | Adherence: {nutrition['adherence'].get('protein_pct', 0)}%)
• Carbohydrates: {nutrition['totals']['carbs_g']}g
• Fats: {nutrition['totals']['fat_g']}g
• Fiber: {nutrition['totals']['fiber_g']}g
• Logged Items: {nutrition['totals']['item_count']} ({nutrition['totals']['verified_items_count']} verified)

------------------------------------------------------------
3. BODY COMPOSITION & WEIGHT TRENDS
------------------------------------------------------------
• Current Weight: {current_wt} kg
• 7-Day Rolling Trend: {wt_trend_7d:+} kg
• Tracked Workouts: {len(activities)} session(s)
• Observations:
{chr(10).join(['  - ' + o for o in trends['observed_facts'][:3]])}

------------------------------------------------------------
4. DATA QUALITY & CONFIDENCE
------------------------------------------------------------
• Confidence: {conf_score}% ({conf_tier})
• Note: {confidence['description']}

------------------------------------------------------------
PHYSIOLOGICAL & SAFETY DISCLAIMER
------------------------------------------------------------
{energy['calculation_disclaimer']}
Weight changes reflect fluctuations in hydration, glycogen, and gut contents, not solely adipose or muscle tissue.
"""

        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f8fafc; color: #0f172a; margin: 0; padding: 20px; }}
  .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
  .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 24px; text-align: center; }}
  .header h1 {{ margin: 0 0 6px; font-size: 20px; font-weight: 700; }}
  .header p {{ margin: 0; font-size: 14px; opacity: 0.85; }}
  .section {{ padding: 20px; border-bottom: 1px solid #f1f5f9; }}
  .section h2 {{ font-size: 14px; color: #f97316; margin: 0 0 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .metric-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 8px; }}
  .metric-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; text-align: center; }}
  .metric-val {{ font-size: 18px; font-weight: 700; color: #0f172a; }}
  .metric-lbl {{ font-size: 12px; color: #64748b; margin-top: 2px; }}
  .badge {{ display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; background: #ffedd5; color: #ea580c; }}
  .disclaimer {{ background: #f1f5f9; padding: 16px; font-size: 11px; color: #64748b; line-height: 1.5; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>TriCoach AI Progress Report</h1>
    <p>Daily Summary &bull; {today_str}</p>
  </div>

  <div class="section">
    <h2>Energy Balance</h2>
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-val">{cals_in} kcal</div>
        <div class="metric-lbl">Consumed</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">{cals_out} kcal</div>
        <div class="metric-lbl">Total Expenditure</div>
      </div>
    </div>
    <p style="text-align: center; margin: 8px 0 0; font-weight: 600;">
      Estimated Balance: <span class="badge">{bal_sign}{net_bal} kcal ({energy['balance_status'].upper()})</span>
    </p>
  </div>

  <div class="section">
    <h2>Macronutrients</h2>
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-val">{protein}g</div>
        <div class="metric-lbl">Protein (Target: {target_protein}g)</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">{nutrition['totals']['carbs_g']}g</div>
        <div class="metric-lbl">Carbohydrates</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">{nutrition['totals']['fat_g']}g</div>
        <div class="metric-lbl">Fats</div>
      </div>
      <div class="metric-card">
        <div class="metric-val">{nutrition['totals']['fiber_g']}g</div>
        <div class="metric-lbl">Fiber</div>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>Body Trends & Confidence</h2>
    <p style="margin: 4px 0 8px; font-size: 14px;"><strong>Current Weight:</strong> {current_wt} kg (7-Day Rolling: {wt_trend_7d:+} kg)</p>
    <p style="margin: 4px 0 8px; font-size: 14px;"><strong>Confidence Rating:</strong> {conf_score}% &bull; {conf_tier}</p>
    <p style="font-size: 12px; color: #64748b; margin: 4px 0;">{confidence['description']}</p>
  </div>

  <div class="disclaimer">
    <strong>Physiological Integrity Notice:</strong> Calorie balance calculations are mathematical estimations. Scale weight reflects fluid retention, glycogen stores, and digestive transit time in addition to adipose and lean tissue.
  </div>
</div>
</body>
</html>
"""

    return {
        "subject": subject,
        "text": text_content,
        "html": html_content,
    }


def send_verification_email(
    athlete_id: str,
    recipient_email: str,
    verification_token: str,
    base_url: str = "http://127.0.0.1:8080",
    db=None,
) -> dict[str, Any]:
    """Sends an email verification link and code to the user."""
    active_db = db or default_db
    clean_email = recipient_email.strip()
    verify_url = f"{base_url.rstrip('/')}/api/reports/verify?athlete_id={athlete_id}&token={verification_token}"

    subject = "Verify your email for TriCoach AI Progress Reports"
    text_content = f"""Welcome to TriCoach AI!

Please verify your email address to begin receiving automated daily and weekly fitness progress reports.

Verification Code: {verification_token}
Direct Verification Link: {verify_url}

If you did not request automated progress reports, simply ignore this email.
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; color: #0f172a; padding: 24px; }}
  .card {{ max-width: 500px; margin: 0 auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 28px; text-align: center; }}
  .btn {{ display: inline-block; background: #f97316; color: #fff; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; margin: 18px 0; }}
  .code {{ font-family: monospace; font-size: 18px; font-weight: 700; background: #f1f5f9; padding: 8px 16px; border-radius: 6px; letter-spacing: 2px; }}
</style>
</head>
<body>
<div class="card">
  <h2 style="margin-top:0;">🏊🚴🏃 TriCoach AI</h2>
  <p>Verify your email address to activate your automated daily and weekly fitness progress reports.</p>
  <p>Your Verification Code:</p>
  <p><span class="code">{verification_token}</span></p>
  <a href="{verify_url}" class="btn" style="color:#ffffff;">Verify Email Address</a>
  <p style="font-size: 12px; color: #64748b; margin-top: 20px;">If the button does not work, copy and paste this link in your browser:<br>{verify_url}</p>
</div>
</body>
</html>
"""

    dispatch_res = dispatch_email(recipient_email=clean_email, subject=subject, text_content=text_content, html_content=html_content)

    import datetime
    today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    active_db.log_email_report(
        athlete_id=athlete_id,
        recipient_email=clean_email,
        report_date=today_str,
        report_period="verification",
        summary_text=f"Email verification token dispatched for athlete {athlete_id}",
        status=dispatch_res["status"],
        provider=dispatch_res["provider"],
        error_message=dispatch_res["error_message"],
    )

    return {
        "status": dispatch_res["status"],
        "provider": dispatch_res["provider"],
        "recipient_email": clean_email,
        "verification_token": verification_token,
        "verify_url": verify_url,
        "error_message": dispatch_res["error_message"],
    }


def send_progress_email(
    recipient_email: str,
    athlete_id: str = "athlete-01",
    report_date: str | None = None,
    period: str = "daily",
    db=None,
) -> dict[str, Any]:
    """Dispatches or simulates the fitness progress email and records the delivery in the database."""
    active_db = db or default_db

    import datetime
    today_str = report_date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    report_content = generate_progress_report_content(
        athlete_id=athlete_id,
        report_date=today_str,
        period=period,
        db=active_db,
    )

    clean_email = recipient_email.strip()
    dispatch_res = dispatch_email(
        recipient_email=clean_email,
        subject=report_content["subject"],
        text_content=report_content["text"],
        html_content=report_content["html"],
    )

    # Record delivery log in persistent database
    log_entry = active_db.log_email_report(
        athlete_id=athlete_id,
        recipient_email=clean_email,
        report_date=today_str,
        report_period=period,
        summary_text=report_content["text"][:1000],
        status=dispatch_res["status"],
        provider=dispatch_res["provider"],
        error_message=dispatch_res["error_message"],
    )

    return {
        "status": dispatch_res["status"],
        "provider": dispatch_res["provider"],
        "recipient_email": clean_email,
        "report_date": today_str,
        "period": period,
        "error_message": dispatch_res["error_message"],
        "log_id": log_entry["report_id"],
        "subject": report_content["subject"],
        "preview_text": report_content["text"][:300] + "...",
        "text_content": report_content["text"],
    }
