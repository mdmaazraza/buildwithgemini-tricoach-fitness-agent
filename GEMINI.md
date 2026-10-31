# 🏊🚴🏃 TriCoach AI — Gemini & Antigravity Coding Agent Guide

> **Context Pointer**: Refer to [`AGENTS.md`](./AGENTS.md) and [`memory/CURRENT_STATUS.md`](./memory/CURRENT_STATUS.md) for current application state, test metrics, and operational invariants.

---

## ⚡ Antigravity & Gemini Rules

When operating as an agent within Google Antigravity or using Gemini models:

1. **Session Bootstrapping**:
   * Always read [`memory/CURRENT_STATUS.md`](./memory/CURRENT_STATUS.md) on Turn 1 to understand the current build status and test results.
   * Verify facts against the actual codebase (`app/fitness_math.py`, `app/web_server.py`, `app/db.py`, `tests/`).
2. **Execution Modes**:
   * **Standalone Unified Server** (Recommended for local dev & free web hosting):
     ```bash
     python -m uvicorn app.web_server:app --host 0.0.0.0 --port 8080 --reload
     ```
   * **Enterprise ADK Server** (When running in Google Cloud Vertex AI / agents-cli):
     ```bash
     python -m uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8000
     ```
3. **Testing Discipline**:
   * Always verify code changes with the automated test suite before declaring completion:
     ```bash
     python -m pytest tests/unit tests/api tests/integration tests/frontend tests/regression
     ```
4. **Context Maintenance**:
   * When you complete an implementation or fix a bug, record your work in [`memory/CHANGELOG.md`](./memory/CHANGELOG.md) and update [`memory/CURRENT_STATUS.md`](./memory/CURRENT_STATUS.md).

---

## 🛠️ CLI Development Commands

| Command | Purpose |
| :--- | :--- |
| `python -m pytest tests/unit tests/api tests/integration` | Fast local test execution |
| `python -m pytest --cov=app --cov-report=term-missing` | Generate test coverage report |
| `python -m pytest tests/regression/ -m regression` | Run regression guardrails |
| `python -m pytest tests/e2e/ -m e2e` | Run Playwright browser simulation |
| `python -m uvicorn app.web_server:app --port 8080` | Launch unified web app |
| `ruff check app/ tests/` | Code linting and style validation |
| `agents-cli playground` | Interactive local ADK testing |
| `agents-cli deploy` | Enterprise deployment to Vertex AI Reasoning Engine |

---

## 🛡️ Operational Guidelines

- **Code Preservation**: Only modify code directly targeted by user requests. Preserve all existing mathematical constants, test fixtures, and fallback modes.
- **Model Invariants**: Keep root model default to `gemini-flash-latest` in `app/agent.py`. Do not alter model names unless explicitly requested.
- **Zero-Cost Protection**: Default database is SQLite (`workouts.db`); do not require mandatory GCP Firestore or Cloud Storage credentials unless `USE_FIRESTORE=true`.
