# 💻 TriCoach AI — Development & Contribution Guidelines

## 1. Coding Standards & Conventions

### Language & Formatting
* **Python Target**: Python 3.10+ / 3.11+.
* **Linter & Formatter**: Ruff (`ruff check app/ tests/`).
* **Line Length**: Max 88 characters.
* **Docstrings**: Google-style docstrings for all functions, classes, and tools.
* **Type Annotations**: Mandatory type hints on all function parameters and returns (`from typing import Optional, List, Dict, Any`).

---

## 2. Architecture Principles

1. **Dual-Mode Compatibility**:
   * Never write code that strictly depends on Vertex AI credentials without providing a local / mock / SQLite fallback.
   * Business math belongs in `app/fitness_math.py`, completely decoupled from agent framework wrappers.
2. **Deterministic Fallbacks**:
   * If an external API (Open-Meteo, Google Maps, Gemini) is unreachable, tools must return meaningful, structured error messages instead of raising uncaught exceptions that crash the server.
3. **Frontend Contract Preservation**:
   * Any change to `/chat` must return `{"parts": [...]}` so `frontend/static/index.html` renders without breakage.

---

## 3. How to Implement a New Triathlon Calculation

Follow this step-by-step checklist:

1. **Step 1: Implement Pure Math in `app/fitness_math.py`**:
   * Write a pure Python function with strict physiological input validation:
   ```python
   def calculate_css_pace(time_400m_seconds: float, time_200m_seconds: float) -> Dict[str, Any]:
       if time_400m_seconds <= time_200m_seconds:
           raise ValueError("400m time must be greater than 200m time.")
       # Critical Swim Speed calculation...
   ```
2. **Step 2: Add Unit Tests in `tests/unit/`**:
   * Test normal cases, boundary values, and error exceptions (`pytest.raises(ValueError)`).
3. **Step 3: Expose via API in `app/web_server.py`**:
   * Add request model and endpoint route (`/api/swimming/css`).
4. **Step 4: Expose to Agent as a Tool in `app/agent.py`**:
   * Add the tool function to `root_agent.tools`.
5. **Step 5: Run Automated Tests**:
   ```bash
   python -m pytest tests/unit tests/api tests/integration
   ```

---

## 4. Security & Environment Configuration

* **Never Hardcode Secrets**: Never commit API keys, Google Cloud service account keys, or private tokens.
* **Environment Variables**:
  * `GEMINI_API_KEY`: Google AI Studio API key (free tier).
  * `GOOGLE_CLOUD_PROJECT`: Optional GCP Project ID for Vertex AI.
  * `USE_FIRESTORE`: Set to `"true"` to enable cloud Firestore sync; defaults to `"false"` (SQLite).
  * `GOOGLE_MAPS_API_KEY`: Optional key for Geocoding and Places API.

---

## 5. Git Commit & Documentation Workflow

* Use conventional commit messages:
  * `feat: add critical swim speed (CSS) calculator`
  * `fix: prevent millisecond workout id collision`
  * `test: add regression test for calorie floor`
  * `docs: update API documentation for css endpoint`
* **Maintain Context**: Always update `memory/CURRENT_STATUS.md` and `memory/CHANGELOG.md` upon completing work.
