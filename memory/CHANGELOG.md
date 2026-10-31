# 📜 TriCoach AI — Changelog

All notable changes, architectural modifications, and testing milestones are documented in this file.

---

## [0.2.0] — 2026-10-31

### Added
* **Fitness & Nutrition Math Engine (`app/fitness_math.py`)**:
  * Mifflin-St Jeor equation for male and female Basal Metabolic Rate (BMR).
  * Total Daily Energy Expenditure (TDEE) with activity level multipliers (sedentary, light, moderate, very active, extra active).
  * Goal-based caloric adjustments (`fat_loss`, `aggressive_loss`, `maintenance`, `lean_bulk`, `endurance_fuel`) with an enforced safety floor of $\ge 1200\text{ kcal}$.
  * Macro breakdown: $1.8\text{ g/kg}$ protein, $25\%$ fat, balance carbs.
  * Karvonen 5-Zone Heart Rate calculator based on Heart Rate Reserve (HRR).
  * Weekly triathlon periodization template with consecutive-running fatigue protection.
* **Database Abstraction Layer (`app/db.py`)**:
  * Unified `WorkoutDatabase` class supporting local SQLite (`workouts.db` or `:memory:`) and Google Cloud Firestore.
  * Collision-free ID generation incorporating millisecond timestamp and random UUID slice (`workout-{timestamp}-{hex}`).
  * Multi-tenant athlete querying and workout deletion support.
* **Unified Web Server (`app/web_server.py`)**:
  * Single FastAPI ASGI process serving static assets (`/static`, `/`) and REST API endpoints (`/chat`, `/api/calories`, `/api/workouts`, `/feedback`, `/health`).
  * Direct response generation conforming to `frontend/static/index.html`'s A2UI parts format.
* **Automated Testing Framework (`tests/`)**:
  * **Unit Tests**: Calorie equations, TDEE, Karvonen zones, periodization rules, and boundary input validation (`test_calorie_calculations.py`, `test_workout_recommendations.py`, `test_input_validation.py`).
  * **API Tests**: Testing HTTP status codes (200, 400, 422), headers, and schemas (`test_chat_api.py`, `test_calorie_api.py`, `test_workout_api.py`).
  * **Integration Tests**: Data persistence, multi-athlete isolation, and cross-service workout logging/chat retrieval (`test_database_integration.py`, `test_system_flow.py`).
  * **Frontend Contract Tests**: Validating static HTML DOM elements, A2UI renderer hooks, and JSON serialization (`test_frontend_contracts.py`).
  * **Regression Suite**: Invariant protection for formulas and minimum thresholds (`test_regression_suite.py`).
  * **E2E Playwright Suite**: Browser automation tests simulating user workflow (`test_playwright_e2e.py`).
  * **Test Fixtures (`tests/conftest.py`)**: Built `DirectTestClient` to prevent AnyIO portal thread deadlocks on Windows and sandboxed test environments.
* **CI/CD Pipeline (`.github/workflows/ci.yml`)**:
  * Multi-job GitHub Actions workflow executing on push and PR.
  * Quality gate blocking production deployment if any test suite fails.
* **Persistent Context Management System**:
  * Added `AGENTS.md`, updated `GEMINI.md`, and created `docs/` and `memory/` directories.

### Changed
* Updated `pyproject.toml` to configure `asyncio_mode = "auto"` and registered `regression` and `e2e` pytest markers.
* Updated `app/__init__.py` to gracefully handle optional ADK dependencies during lightweight testing.
* Added `pytest.importorskip("google.adk")` and `pytest.importorskip("a2a")` to legacy integration tests to allow execution across diverse Python environments.

---

## [0.1.0] — 2026-09-24

### Initial Scaffolding
* Initial prototype created during Google Cloud hackathon with ADK Agent runtime.
* Hardcoded Qwiklabs project `qwiklabs-gcp-02-c57180f0ec07`.
* Standalone frontend proxy (`frontend/main.py`) connecting to remote Vertex AI Reasoning Engine.
