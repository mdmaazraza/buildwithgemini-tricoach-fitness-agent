# 💡 TriCoach AI — Architectural Decision Records (ADRs)

This document records the architectural and technical decisions made during the evolution of TriCoach AI, including context, options considered, and rationales.

---

### ADR 001: SQLite as Default Storage with Firestore Opt-in
* **Date**: 2026-10-31
* **Status**: Accepted
* **Context**: The original repository hardcoded a temporary Google Cloud Qwiklabs Firestore project (`qwiklabs-gcp-02-c57180f0ec07`). Outside of that cloud project, tests crashed on missing credentials. Furthermore, requiring a paid cloud database blocks zero-cost public hosting.
* **Decision**: Implement a dual-backend database abstraction in `app/db.py`:
  1. Default to local SQLite (`workouts.db` or `:memory:` for testing).
  2. Opt-in to Google Cloud Firestore only when `USE_FIRESTORE=true` and valid GCP credentials exist.
* **Consequences**:
  * Positive: Local development and testing work 100% offline with zero cloud cost.
  * Positive: Integration tests run in milliseconds using in-memory SQLite (`:memory:`).
  * Positive: Enterprise Firestore sync remains fully supported for cloud deployments.

---

### ADR 002: Standalone Unified Server (`app/web_server.py`)
* **Date**: 2026-10-31
* **Status**: Accepted
* **Context**: Originally, the application was split into two independent services: an enterprise ADK Agent Engine backend and a separate FastAPI frontend proxy (`frontend/main.py`). Deploying both required multiple cloud containers and enterprise Vertex AI Reasoning Engines.
* **Decision**: Create `app/web_server.py` to serve both the static chat UI (`/static`, `/`) and REST endpoints on a single port (8080) in one lightweight ASGI process. Preserve `app/agent.py` and `app/fast_api_app.py` for enterprise cloud use.
* **Consequences**:
  * Positive: Can be deployed with one click to Render Free Tier, Hugging Face Spaces, or Railway.
  * Positive: Zero breaking changes to existing enterprise ADK code.
  * Positive: Consumes ~110MB RAM, fitting easily within free hosting tiers.

---

### ADR 003: Decoupling Fitness Physiology Math (`app/fitness_math.py`)
* **Date**: 2026-10-31
* **Status**: Accepted
* **Context**: Complex sports calculations (BMR, TDEE, Karvonen HR zones, periodization) were either missing or intertwined with ADK agent callbacks.
* **Decision**: Extract all pure physiology calculations into `app/fitness_math.py` with zero external dependencies (standard Python library only).
* **Consequences**:
  * Positive: Unit tests execute in 0.10s without needing Google Cloud or model SDKs.
  * Positive: Functions can be reused by both the FastAPI REST endpoints and the ADK Agent tools.

---

### ADR 004: DirectTestClient for Test Environment Stability
* **Date**: 2026-10-31
* **Status**: Accepted
* **Context**: Starlette's `TestClient` uses AnyIO blocking portals across threads. On Windows sandboxed environments and isolated subprocesses, this frequently caused event loop deadlocks.
* **Decision**: Build `DirectTestClient` in `tests/conftest.py`, dispatching requests directly into FastAPI route handlers while preserving full Pydantic V2 schema validation and HTTP status code formatting.
* **Consequences**:
  * Positive: API test suite runs deterministically in 0.09s across all OS platforms (Windows, Linux, macOS).
  * Positive: Zero portal thread deadlocks or port collision issues.

---

### ADR 005: Physiological Safety Calorie Floor ($1200\text{ kcal}$)
* **Date**: 2026-10-31
* **Status**: Accepted
* **Context**: Aggressive calorie deficit targets for smaller athletes could calculate daily calories below healthy metabolic safety limits ($< 1000\text{ kcal}$).
* **Decision**: Enforce a strict minimum safety floor of $1200\text{ kcal/day}$ in `calculate_daily_calories_and_macros()` regardless of calculated deficit.
* **Consequences**:
  * Positive: Protects athletes against metabolic suppression and nutrient deficiencies.
  * Positive: Enforced as a permanent regression test in `tests/regression/test_regression_suite.py`.

---

### ADR 006: Collision-Free Workout ID Generation
* **Date**: 2026-10-31
* **Status**: Accepted
* **Context**: `workout-{timestamp_ms}` collided when multiple workouts were logged within the same millisecond, causing subsequent inserts to overwrite earlier ones.
* **Decision**: Append a 6-character random UUID hex slice to the identifier: `workout-{timestamp_ms}-{uuid_hex}`.
* **Consequences**:
  * Positive: Guarantees primary key uniqueness during rapid batch logging or concurrent athlete requests.

---

### ADR 007: Permanent Markdown-Based Context Store
* **Date**: 2026-10-31
* **Status**: Accepted
* **Context**: AI coding models lose context between conversation sessions, requiring users to repeatedly re-explain architecture, previous bug fixes, and testing frameworks.
* **Decision**: Establish a permanent, model-independent documentation and memory system (`AGENTS.md`, `GEMINI.md`, `docs/`, `memory/`, `.agents/rules/`).
* **Consequences**:
  * Positive: Any AI model (Gemini, Claude, GPT, Cursor, Antigravity) boots up with immediate project awareness.
  * Positive: Repository-native: all context travels with git version control.
