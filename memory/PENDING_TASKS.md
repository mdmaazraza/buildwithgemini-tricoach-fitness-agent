# 📋 TriCoach AI — Pending Tasks & Roadmap

This document outlines the prioritized engineering backlog for upcoming development sessions.

---

## 🚀 Priority 1: Live Web Deployment (Zero-Cost Hosting)
* [ ] **Task 1.1**: Create `render.yaml` infrastructure-as-code file for 1-click deployment on Render.com free tier.
* [ ] **Task 1.2**: Update root `Dockerfile` to launch `app.web_server:app` directly on `PORT=8080`.
* [ ] **Task 1.3**: Configure public HTTPS link accessible on mobile phones and laptops (`https://tricoach-ai.onrender.com`).
* [ ] **Task 1.4**: Wire GitHub Actions auto-deploy hook for continuous deployment on `git push origin main`.

---

## 🏊 Priority 2: Advanced Swimming Math & Critical Swim Speed (CSS)
* [ ] **Task 2.1**: Implement CSS formula based on $400\text{m}$ and $200\text{m}$ time-trial benchmarks:
  $$\text{CSS (m/sec)} = \frac{400 - 200}{T_{400} - T_{200}}$$
* [ ] **Task 2.2**: Generate 5 swim training pace zones (per $100\text{m}$):
  * Zone 1: Recovery ($\text{CSS} + 10\text{s}$)
  * Zone 2: Aerobic Endurance ($\text{CSS} + 4-6\text{s}$)
  * Zone 3: Tempo / Threshold ($\text{CSS} \pm 2\text{s}$)
  * Zone 4: VO2 Max ($\text{CSS} - 3-5\text{s}$)
  * Zone 5: Sprint Speed ($\text{CSS} - 8-10\text{s}$)
* [ ] **Task 2.3**: Expose `/api/swimming/css` and add agent tool `calculate_critical_swim_speed`.
* [ ] **Task 2.4**: Add unit tests in `tests/unit/test_swimming_math.py`.

---

## 🚴 Priority 3: Cycling Power & Coggan 7-Zone FTP Engine
* [ ] **Task 3.1**: Implement Functional Threshold Power (FTP) calculator from a 20-minute ramp or steady test ($95\%$ of 20-min average watts).
* [ ] **Task 3.2**: Calculate the 7 Coggan Cycling Power Zones:
  * Zone 1: Active Recovery ($< 55\%$ FTP)
  * Zone 2: Endurance ($55-75\%$ FTP)
  * Zone 3: Tempo ($76-90\%$ FTP)
  * Zone 4: Sweet Spot & Lactate Threshold ($91-105\%$ FTP)
  * Zone 5: VO2 Max ($106-120\%$ FTP)
  * Zone 6: Anaerobic Capacity ($121-150\%$ FTP)
  * Zone 7: Neuromuscular Power ($> 150\%$ FTP)
* [ ] **Task 3.3**: Expose `/api/cycling/ftp` and agent tool `calculate_cycling_power_zones`.
* [ ] **Task 3.4**: Add unit tests in `tests/unit/test_cycling_math.py`.

---

## 📅 Priority 4: Multi-Week Periodized Training Plan Generator
* [ ] **Task 4.1**: Build a 12-week structured training schedule generator for Sprint and Olympic triathlons.
* [ ] **Task 4.2**: Implement 4 macrocycle blocks: Base Phase (Weeks 1-4), Build Phase (Weeks 5-8), Peak Phase (Weeks 9-10), Taper Phase (Weeks 11-12).
* [ ] **Task 4.3**: Emit plan using A2UI Cards & Columns for rich rendering in `frontend/static/index.html`.

---

## ⌚ Priority 5: Activity File Import (GPX & FIT)
* [ ] **Task 5.1**: Build a parser for GPX and FIT files to extract GPS track points, elevation gain, heart rate, and cadence.
* [ ] **Task 5.2**: Add upload modal/endpoint to log imported files directly into `WorkoutDatabase`.
* [ ] **Task 5.3**: Planned Strava OAuth2 sync tool.

---

## 👟 Priority 6: Gear & Equipment Mileage Tracker
* [ ] **Task 6.1**: Running shoe mileage tracker with automatic retirement alert at $500\text{ km}$.
* [ ] **Task 6.2**: Bike chain and tire wear maintenance notification schedule.
