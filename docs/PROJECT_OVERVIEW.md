# 🏊🚴🏃 TriCoach AI — Project Overview

## 1. Mission & Vision
**TriCoach AI** is an intelligent endurance coaching application designed for multi-sport athletes (swimming, cycling, running, brick sessions, and strength training). It combines validated sports physiology calculations, conversational AI reasoning, interactive visual UI cards (A2UI), and durable workout logging into a responsive, mobile-first web interface.

---

## 2. Target Audience & Core Use Cases
* **Triathletes (Sprint, Olympic, 70.3 Half Ironman, 140.6 Full Ironman)**:
  * Computing personalized Karvonen heart rate zones for aerobic base building (Zone 2) vs threshold power (Zone 4).
  * Logging multisport workouts with distance, duration, cadence, and average heart rate.
  * Receiving periodized weekly training schedules that protect against consecutive-day running injuries.
* **Fitness Enthusiasts & Runners**:
  * Calculating exact Basal Metabolic Rate (BMR) and Total Daily Energy Expenditure (TDEE).
  * Dialing in daily macronutrient targets (endurance fuel, fat loss, maintenance, or lean muscle gain) with a safety calorie floor.
  * Checking outdoor weather and discovering nearby training facilities (gyms, pools, tracks, parks).

---

## 3. Technology Stack Breakdown

| Layer | Technologies | Role in System |
| :--- | :--- | :--- |
| **Frontend UI** | HTML5, CSS3 Variables, Vanilla JS (ES6+), Material Symbols | Mobile-responsive sports chat, dark/light theme, quick action chips |
| **Declarative UI** | Google A2UI (Catalog v0.8) | Renders rich cards, columns, rows, images, and text hints directly in chat |
| **Backend Framework** | FastAPI (ASGI), Pydantic V2, Uvicorn | High-performance API routing, input validation, request parsing |
| **AI Agent Logic** | Google ADK (`google-adk`), `google.genai` SDK | Multi-turn reasoning, tool execution, session persistence |
| **Models** | `gemini-flash-latest`, `gemini-3.1-flash-lite-image`, `gemini-omni-flash-preview` | Text conversation, motivational visual poster generation, workout motion clips |
| **Database & Cache** | SQLite (`workouts.db` or `:memory:`) + Google Cloud Firestore | Zero-cost local storage with enterprise cloud synchronization |
| **Testing Engine** | Pytest, pytest-cov, pytest-asyncio, Playwright | Unit, API, Integration, Frontend, Regression, and E2E automation |
| **CI/CD** | GitHub Actions (`.github/workflows/ci.yml`) | Automated linting, test suites, quality gate, and production deploy |

---

## 4. Key Functional Capabilities

1. **Fitness & Nutrition Math Engine (`app/fitness_math.py`)**:
   * Mifflin-St Jeor BMR equation for men and women.
   * TDEE multipliers from sedentary ($1.2$) to extra active ($1.9$).
   * Calorie target calculation with strict safety floor ($\ge 1200\text{ kcal}$).
   * Endurance macronutrient breakdown ($1.8\text{ g/kg}$ protein, $25\%$ fat, balance carbs).
   * Karvonen 5-Zone Heart Rate calculator based on Heart Rate Reserve (HRR).
   * Periodized workout recommendations based on athlete event and fatigue rules.
2. **Unified Web Server (`app/web_server.py`)**:
   * Serves static chat application and handles REST APIs on a single port.
   * Eliminates complex multi-container requirements for \$0 web hosting.
3. **Database Abstraction (`app/db.py`)**:
   * Supports local SQLite storage without requiring cloud billing.
   * Connects to Firestore automatically if `USE_FIRESTORE=true`.
   * High-frequency ID deduplication preventing collision on rapid workout logging.
4. **Automated Quality Gate**:
   * 69 tests running in ~1 second ensuring no regressions occur across updates.
