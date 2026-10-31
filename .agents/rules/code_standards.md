---
description: Code standards, architecture invariants, and testing rules for TriCoach AI.
trigger: always_on
---

# 🛡️ Code Standards & Architecture Invariants

1. **Test Verification**:
   * All 69 existing tests must remain passing. Run the test suite after every code change:
     ```bash
     python -m pytest tests/unit tests/api tests/integration tests/frontend tests/regression
     ```
2. **Dual-Mode Architecture Preservation**:
   * Do not remove or break `app/web_server.py` or `app/agent.py`.
   * Keep pure math in `app/fitness_math.py` with zero heavy cloud dependencies.
   * Keep storage in `app/db.py` defaulting to SQLite (`workouts.db` or `:memory:`).
3. **Frontend Contract**:
   * The `/chat` endpoint must return `{"parts": [{"kind": "text", ...}, {"kind": "a2ui", ...}]}` so `frontend/static/index.html` continues to render correctly.
4. **Physiological Safety**:
   * Calorie calculations must enforce the $1200\text{ kcal}$ safety floor.
   * Periodization must protect against consecutive running days.
5. **No Credentials**:
   * Never commit API keys, service accounts, or secrets. Use environment variables.
