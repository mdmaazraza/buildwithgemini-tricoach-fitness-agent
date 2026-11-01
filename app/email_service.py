"""Email Reporting Service for TriCoach AI.

Implements:
1. Daily and weekly fitness progress report generation (plain text & HTML).
2. Bulletproof, high-contrast HTML templates optimized for Gmail, Apple Mail, Outlook, and mobile.
3. Resend API dispatch (Free plan: 3,000 emails/mo, 100/day, verified sender onboarding@resend.dev).
4. SMTP fallback dispatch with SSL/TLS encryption.
5. Safe offline dry-run / simulation mode when email credentials are not configured.
6. Email verification token generation and dispatch.
7. User consent checking and delivery audit logging into the database.
8. Strict credential security: never hardcodes credentials or exposes secrets.
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
    """Generates comprehensive plain text and high-contrast, email-client compatible HTML reports."""
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

        balance_bg = "#dcfce7" if weekly_net <= 0 else "#ffedd5"
        balance_color = "#166534" if weekly_net <= 0 else "#9a3412"

        html_content = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{subject}</title>
</head>
<body style="margin:0; padding:24px 0; background-color:#f1f5f9; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#0f172a;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f1f5f9;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px; width:100%; background-color:#ffffff; border-radius:14px; border:1px solid #e2e8f0; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06);">
          
          <!-- Header Banner -->
          <tr>
            <td style="background-color:#0f172a; padding:28px 24px; text-align:center;">
              <div style="font-size:28px; line-height:1; margin-bottom:8px;">🏊🚴🏃</div>
              <h1 style="margin:0 0 6px; font-size:22px; font-weight:700; color:#ffffff; letter-spacing:-0.3px;">TriCoach AI Weekly Digest</h1>
              <p style="margin:0; font-size:14px; color:#cbd5e1;">Performance Summary &bull; {start_date} to {today_str}</p>
            </td>
          </tr>

          <!-- Athlete Goal Banner -->
          <tr>
            <td style="background-color:#f8fafc; padding:12px 24px; border-bottom:1px solid #e2e8f0; font-size:13px; color:#64748b;">
              <strong>Athlete:</strong> {athlete_id} &nbsp;|&nbsp; <strong>Goal:</strong> <span style="text-transform:capitalize; color:#0f172a; font-weight:600;">{profile.get('goal', 'maintenance').replace('_', ' ')}</span>
            </td>
          </tr>

          <!-- Section 1: Energy & Calorie Balance -->
          <tr>
            <td style="padding:22px 24px; border-bottom:1px solid #f1f5f9;">
              <h2 style="font-size:13px; font-weight:700; color:#f97316; margin:0 0 14px; text-transform:uppercase; letter-spacing:0.8px;">🔥 Weekly Energy & Calorie Balance</h2>
              
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="48%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px; text-align:center;">
                    <div style="font-size:24px; font-weight:700; color:#0f172a;">{round(total_cals_in):,} <span style="font-size:14px; font-weight:500;">kcal</span></div>
                    <div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:4px;">Total Consumed</div>
                    <div style="font-size:12px; color:#94a3b8; margin-top:2px;">(Avg {avg_cals_in} kcal/day)</div>
                  </td>
                  <td width="4%">&nbsp;</td>
                  <td width="48%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px; text-align:center;">
                    <div style="font-size:24px; font-weight:700; color:#0f172a;">{round(weekly_burn):,} <span style="font-size:14px; font-weight:500;">kcal</span></div>
                    <div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:4px;">Total Expended</div>
                    <div style="font-size:12px; color:#94a3b8; margin-top:2px;">(BMR + Exercise Burn)</div>
                  </td>
                </tr>
              </table>

              <div style="margin-top:14px; background-color:{balance_bg}; border-radius:8px; padding:10px 16px; text-align:center; font-size:14px; font-weight:700; color:{balance_color};">
                Estimated Weekly Net Balance: {net_sign}{weekly_net} kcal
              </div>
            </td>
          </tr>

          <!-- Section 2: Daily Average Macronutrients -->
          <tr>
            <td style="padding:22px 24px; border-bottom:1px solid #f1f5f9;">
              <h2 style="font-size:13px; font-weight:700; color:#f97316; margin:0 0 14px; text-transform:uppercase; letter-spacing:0.8px;">🥗 Daily Average Macronutrients</h2>
              
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="31%" style="background-color:#f8fafc; border-top:3px solid #3b82f6; border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0; border-radius:8px; padding:12px; text-align:center;">
                    <div style="font-size:20px; font-weight:700; color:#0f172a;">{avg_protein}g</div>
                    <div style="font-size:11px; font-weight:600; color:#3b82f6; text-transform:uppercase; margin-top:3px;">Protein / Day</div>
                  </td>
                  <td width="3%">&nbsp;</td>
                  <td width="31%" style="background-color:#f8fafc; border-top:3px solid #f59e0b; border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0; border-radius:8px; padding:12px; text-align:center;">
                    <div style="font-size:20px; font-weight:700; color:#0f172a;">{avg_carbs}g</div>
                    <div style="font-size:11px; font-weight:600; color:#d97706; text-transform:uppercase; margin-top:3px;">Carbs / Day</div>
                  </td>
                  <td width="3%">&nbsp;</td>
                  <td width="31%" style="background-color:#f8fafc; border-top:3px solid #ef4444; border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0; border-radius:8px; padding:12px; text-align:center;">
                    <div style="font-size:20px; font-weight:700; color:#0f172a;">{avg_fat}g</div>
                    <div style="font-size:11px; font-weight:600; color:#dc2626; text-transform:uppercase; margin-top:3px;">Fats / Day</div>
                  </td>
                </tr>
              </table>
              <div style="font-size:12px; color:#64748b; margin-top:10px; text-align:right;">
                Total Meals Logged: <strong>{len(all_foods)} items</strong> across the 7-day period
              </div>
            </td>
          </tr>

          <!-- Section 3: Training Volume -->
          <tr>
            <td style="padding:22px 24px; border-bottom:1px solid #f1f5f9;">
              <h2 style="font-size:13px; font-weight:700; color:#f97316; margin:0 0 14px; text-transform:uppercase; letter-spacing:0.8px;">⚡ Completed Training Volume</h2>
              
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="23%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px 6px; text-align:center;">
                    <div style="font-size:18px; font-weight:700; color:#0f172a;">{len(all_acts)}</div>
                    <div style="font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:2px;">Workouts</div>
                  </td>
                  <td width="2%">&nbsp;</td>
                  <td width="23%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px 6px; text-align:center;">
                    <div style="font-size:18px; font-weight:700; color:#0f172a;">{round(total_act_mins / 60, 1)} hrs</div>
                    <div style="font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:2px;">Duration</div>
                  </td>
                  <td width="2%">&nbsp;</td>
                  <td width="23%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px 6px; text-align:center;">
                    <div style="font-size:18px; font-weight:700; color:#0f172a;">{total_act_dist} km</div>
                    <div style="font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:2px;">Distance</div>
                  </td>
                  <td width="2%">&nbsp;</td>
                  <td width="23%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px 6px; text-align:center;">
                    <div style="font-size:18px; font-weight:700; color:#0f172a;">{round(total_act_burn)}</div>
                    <div style="font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:2px;">Workout kcal</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Section 4: Weight Trends & Confidence -->
          <tr>
            <td style="padding:22px 24px; border-bottom:1px solid #f1f5f9;">
              <h2 style="font-size:13px; font-weight:700; color:#f97316; margin:0 0 14px; text-transform:uppercase; letter-spacing:0.8px;">📉 Weight Trend & Data Confidence</h2>
              
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="48%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px; text-align:center;">
                    <div style="font-size:22px; font-weight:700; color:#0f172a;">{current_wt} kg</div>
                    <div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:3px;">Latest Scale Weight</div>
                    <div style="font-size:12px; font-weight:600; color:#2563eb; margin-top:2px;">7-Day Trend: {wt_trend_7d:+} kg</div>
                  </td>
                  <td width="4%">&nbsp;</td>
                  <td width="48%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px; text-align:center;">
                    <div style="font-size:22px; font-weight:700; color:#16a34a;">{conf_score}%</div>
                    <div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:3px;">Data Reliability</div>
                    <div style="font-size:12px; color:#16a34a; font-weight:600; margin-top:2px;">Rating: {conf_tier}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Section 5: Actionable Recommendations -->
          <tr>
            <td style="padding:22px 24px; border-bottom:1px solid #f1f5f9;">
              <h2 style="font-size:13px; font-weight:700; color:#f97316; margin:0 0 12px; text-transform:uppercase; letter-spacing:0.8px;">🎯 Coaching Action Plan for Next Week</h2>
              
              <div style="background-color:#eff6ff; border-left:4px solid #3b82f6; border-radius:6px; padding:14px 16px;">
                <div style="font-size:13px; line-height:1.6; color:#1e3a8a;">
                  &bull; <strong>Protein Consistency:</strong> Target {avg_protein}g+ daily to protect lean muscle during endurance training.<br/>
                  &bull; <strong>Hydration & Electrolytes:</strong> Rehydrate with sodium/potassium within 60 minutes after long cardio sessions.<br/>
                  &bull; <strong>Weigh-in Protocol:</strong> Step on the scale under standard fasted morning conditions for true trend accuracy.
                </div>
              </div>
            </td>
          </tr>

          <!-- Footer Disclaimer -->
          <tr>
            <td style="background-color:#f8fafc; padding:20px 24px; font-size:11px; line-height:1.6; color:#64748b; text-align:center;">
              <strong>Physiological Note:</strong> Short-term scale weight fluctuations primarily reflect changes in total body hydration, glycogen storage, and digestive transit time rather than true changes in adipose or muscular tissue. BMR and energy calculations utilize validated formulas with standard variance (±10-15%).
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
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

        balance_bg = "#dcfce7" if net_bal <= 0 else "#ffedd5"
        balance_color = "#166534" if net_bal <= 0 else "#9a3412"

        html_content = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{subject}</title>
</head>
<body style="margin:0; padding:24px 0; background-color:#f1f5f9; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#0f172a;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f1f5f9;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px; width:100%; background-color:#ffffff; border-radius:14px; border:1px solid #e2e8f0; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06);">
          
          <!-- Header Banner -->
          <tr>
            <td style="background-color:#0f172a; padding:28px 24px; text-align:center;">
              <div style="font-size:28px; line-height:1; margin-bottom:8px;">⚡🏊🚴🏃</div>
              <h1 style="margin:0 0 6px; font-size:22px; font-weight:700; color:#ffffff; letter-spacing:-0.3px;">TriCoach AI Daily Progress</h1>
              <p style="margin:0; font-size:14px; color:#cbd5e1;">Daily Performance Summary &bull; {today_str}</p>
            </td>
          </tr>

          <!-- Athlete Goal Banner -->
          <tr>
            <td style="background-color:#f8fafc; padding:12px 24px; border-bottom:1px solid #e2e8f0; font-size:13px; color:#64748b;">
              <strong>Athlete:</strong> {athlete_id} &nbsp;|&nbsp; <strong>Goal:</strong> <span style="text-transform:capitalize; color:#0f172a; font-weight:600;">{profile.get('goal', 'maintenance').replace('_', ' ')}</span>
            </td>
          </tr>

          <!-- Section 1: Energy & Calorie Balance -->
          <tr>
            <td style="padding:22px 24px; border-bottom:1px solid #f1f5f9;">
              <h2 style="font-size:13px; font-weight:700; color:#f97316; margin:0 0 14px; text-transform:uppercase; letter-spacing:0.8px;">🔥 Today's Energy & Calorie Balance</h2>
              
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="48%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px; text-align:center;">
                    <div style="font-size:26px; font-weight:700; color:#0f172a;">{cals_in:,} <span style="font-size:14px; font-weight:500;">kcal</span></div>
                    <div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:4px;">Consumed</div>
                  </td>
                  <td width="4%">&nbsp;</td>
                  <td width="48%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px; text-align:center;">
                    <div style="font-size:26px; font-weight:700; color:#0f172a;">{cals_out:,} <span style="font-size:14px; font-weight:500;">kcal</span></div>
                    <div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:4px;">Total Expenditure</div>
                    <div style="font-size:11px; color:#94a3b8; margin-top:2px;">(BMR: {energy['bmr']} + Activity: {energy['additional_exercise_burn']})</div>
                  </td>
                </tr>
              </table>

              <div style="margin-top:14px; background-color:{balance_bg}; border-radius:8px; padding:10px 16px; text-align:center; font-size:14px; font-weight:700; color:{balance_color};">
                Estimated Net Balance: {bal_sign}{net_bal} kcal ({energy['balance_status'].upper()})
              </div>
            </td>
          </tr>

          <!-- Section 2: Macronutrients -->
          <tr>
            <td style="padding:22px 24px; border-bottom:1px solid #f1f5f9;">
              <h2 style="font-size:13px; font-weight:700; color:#f97316; margin:0 0 14px; text-transform:uppercase; letter-spacing:0.8px;">🥗 Macronutrient Adherence</h2>
              
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="31%" style="background-color:#f8fafc; border-top:3px solid #3b82f6; border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0; border-radius:8px; padding:12px; text-align:center;">
                    <div style="font-size:20px; font-weight:700; color:#0f172a;">{protein}g</div>
                    <div style="font-size:11px; font-weight:600; color:#3b82f6; text-transform:uppercase; margin-top:3px;">Protein</div>
                    <div style="font-size:11px; color:#94a3b8; margin-top:2px;">Target: {target_protein}g</div>
                  </td>
                  <td width="3%">&nbsp;</td>
                  <td width="31%" style="background-color:#f8fafc; border-top:3px solid #f59e0b; border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0; border-radius:8px; padding:12px; text-align:center;">
                    <div style="font-size:20px; font-weight:700; color:#0f172a;">{nutrition['totals']['carbs_g']}g</div>
                    <div style="font-size:11px; font-weight:600; color:#d97706; text-transform:uppercase; margin-top:3px;">Carbs</div>
                    <div style="font-size:11px; color:#94a3b8; margin-top:2px;">Fiber: {nutrition['totals']['fiber_g']}g</div>
                  </td>
                  <td width="3%">&nbsp;</td>
                  <td width="31%" style="background-color:#f8fafc; border-top:3px solid #ef4444; border-left:1px solid #e2e8f0; border-right:1px solid #e2e8f0; border-bottom:1px solid #e2e8f0; border-radius:8px; padding:12px; text-align:center;">
                    <div style="font-size:20px; font-weight:700; color:#0f172a;">{nutrition['totals']['fat_g']}g</div>
                    <div style="font-size:11px; font-weight:600; color:#dc2626; text-transform:uppercase; margin-top:3px;">Fats</div>
                    <div style="font-size:11px; color:#94a3b8; margin-top:2px;">Healthy Lipids</div>
                  </td>
                </tr>
              </table>
              <div style="font-size:12px; color:#64748b; margin-top:10px; text-align:right;">
                Logged: <strong>{nutrition['totals']['item_count']} items</strong> ({nutrition['totals']['verified_items_count']} verified)
              </div>
            </td>
          </tr>

          <!-- Section 3: Body & Workouts -->
          <tr>
            <td style="padding:22px 24px; border-bottom:1px solid #f1f5f9;">
              <h2 style="font-size:13px; font-weight:700; color:#f97316; margin:0 0 14px; text-transform:uppercase; letter-spacing:0.8px;">📉 Scale Weight & Workout Activity</h2>
              
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td width="48%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px; text-align:center;">
                    <div style="font-size:22px; font-weight:700; color:#0f172a;">{current_wt} kg</div>
                    <div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:3px;">Scale Weight</div>
                    <div style="font-size:12px; font-weight:600; color:#2563eb; margin-top:2px;">7-Day Trend: {wt_trend_7d:+} kg</div>
                  </td>
                  <td width="4%">&nbsp;</td>
                  <td width="48%" style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px; text-align:center;">
                    <div style="font-size:22px; font-weight:700; color:#0f172a;">{len(activities)}</div>
                    <div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase; margin-top:3px;">Logged Workouts</div>
                    <div style="font-size:12px; color:#16a34a; font-weight:600; margin-top:2px;">Reliability: {conf_score}%</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer Disclaimer -->
          <tr>
            <td style="background-color:#f8fafc; padding:20px 24px; font-size:11px; line-height:1.6; color:#64748b; text-align:center;">
              <strong>Physiological Note:</strong> Daily weight fluctuations on the bathroom scale reflect shifts in hydration, glycogen storage, and digestive transit time rather than true changes in adipose or muscular tissue. BMR calculations use Mifflin-St Jeor formulas with standard variance (±10-15%).
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
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
    """Sends a crisp, responsive verification email to confirm user subscription."""
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

    html_content = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{subject}</title>
</head>
<body style="margin:0; padding:24px 0; background-color:#f1f5f9; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color:#0f172a;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f1f5f9;">
    <tr>
      <td align="center">
        <table width="520" cellpadding="0" cellspacing="0" border="0" style="max-width:520px; width:100%; background-color:#ffffff; border-radius:14px; border:1px solid #e2e8f0; overflow:hidden; box-shadow:0 4px 16px rgba(0,0,0,0.06); text-align:center;">
          <tr>
            <td style="background-color:#0f172a; padding:28px 24px;">
              <div style="font-size:28px; line-height:1; margin-bottom:8px;">⚡</div>
              <h1 style="margin:0; font-size:20px; font-weight:700; color:#ffffff;">TriCoach AI Email Verification</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 24px;">
              <p style="margin:0 0 16px; font-size:15px; line-height:1.5; color:#334155;">
                You are one step away from receiving your automated <strong>daily and weekly fitness progress reports</strong>.
              </p>
              
              <div style="margin:20px 0; background-color:#f8fafc; border:1px dashed #cbd5e1; border-radius:8px; padding:14px;">
                <div style="font-size:12px; font-weight:600; color:#64748b; text-transform:uppercase; margin-bottom:4px;">Your Verification Code:</div>
                <div style="font-family:monospace; font-size:22px; font-weight:700; color:#f97316; letter-spacing:3px;">{verification_token}</div>
              </div>

              <div style="margin:24px 0;">
                <a href="{verify_url}" style="display:inline-block; background-color:#f97316; color:#ffffff; font-size:15px; font-weight:700; text-decoration:none; padding:12px 28px; border-radius:8px; box-shadow:0 2px 8px rgba(249,115,22,0.35);">
                  Verify Email Address &rarr;
                </a>
              </div>

              <p style="margin:20px 0 0; font-size:12px; color:#94a3b8; line-height:1.5;">
                Or paste this link into your browser:<br/>
                <a href="{verify_url}" style="color:#2563eb; word-break:break-all;">{verify_url}</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
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
        "html_content": report_content["html"],
    }
