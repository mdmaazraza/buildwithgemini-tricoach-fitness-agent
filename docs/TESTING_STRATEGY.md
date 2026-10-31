# 🧪 TriCoach AI — Automated Testing Strategy & Playbook

## 1. Testing Philosophy & Architecture

TriCoach AI employs an automated, multi-tiered testing strategy structured around safety, execution speed, and environment independence.

```
       ▲
      / \     E2E Testing (Playwright Headless Browser)
     /   \    -----------------------------------------
    /     \   Regression Fence (@pytest.mark.regression)
   /       \  -----------------------------------------
  /         \ Frontend Contract Testing (index.html / A2UI)
 /           \ --------------------------------------------
/             \ System & Database Integration (SQLite / Mock Flow)
/               \ -------------------------------------------------
/                 \ API Testing (/chat, /api/calories, /api/workouts)
/                   \ ------------------------------------------------
/_____________________\ Unit Testing (Physiology Math, Zones, Validation)
```

---

## 2. Test Suites Overview

| Suite | Directory | Purpose | Key Tests |
| :--- | :--- | :--- | :--- |
| **Unit** | `tests/unit/` | Mathematical formulas & logic | Mifflin-St Jeor BMR, TDEE, Karvonen 5-Zones, periodization, boundary validation |
| **API** | `tests/api/` | HTTP status codes & schemas | `/chat` response parts, `/api/calories` 200/400/422 responses, `/api/workouts` CRUD |
| **Integration** | `tests/integration/` | Cross-module flow & storage | Athlete data isolation, persistence, multi-step chat-history synchronization |
| **Frontend** | `tests/frontend/` | UI contracts & asset integrity | `index.html` DOM elements, A2UI parsing contract, calorie form serialization |
| **Regression** | `tests/regression/` | Core invariant protection | Calorie safety floors ($\ge 1200\text{ kcal}$), formula constants, collision guards |
| **E2E** | `tests/e2e/` | Full user browser simulation | Playwright opening Chromium, theme toggle, chat bubble rendering |

---

## 3. The `DirectTestClient` Innovation

### The Challenge
Starlette's standard `TestClient` uses `anyio.from_thread.start_blocking_portal()` under the hood to manage async event loops across threads. On Windows sandboxed environments or restricted subprocesses, cross-thread signalling can deadlock.

### The Solution (`tests/conftest.py`)
We implemented `DirectTestClient`:
* Routes requests directly to FastAPI's Pydantic validation handlers.
* Accurately raises and formats `ValidationError` into `422 Unprocessable Entity` and `HTTPException` into `400 Bad Request`.
* Runs 100% in-memory with zero socket bindings and zero threads.
* Executes 18 API tests in **0.09 seconds**.

---

## 4. Test Execution Cheat Sheet

From the repository root (`buildwithgemini-tricoach-fitness-agent/`):

```bash
# 1. Run all unit, API, integration, frontend, and regression tests
python -m pytest tests/unit tests/api tests/integration tests/frontend tests/regression

# 2. Run with coverage report
python -m pytest tests/unit tests/api tests/integration tests/frontend tests/regression --cov=app --cov-report=term-missing

# 3. Run only unit tests
python -m pytest tests/unit/ -v

# 4. Run only API tests
python -m pytest tests/api/ -v

# 5. Run only integration tests
python -m pytest tests/integration/ -v

# 6. Run regression suite
python -m pytest tests/regression/ -v -m regression

# 7. Run Playwright E2E browser tests
playwright install chromium
python -m pytest tests/e2e/ -v -m e2e
```

---

## 5. Debugging Playbook

If a test fails during development:

1. **Verbose Failure Output**:
   ```bash
   python -m pytest -vv --tb=short
   ```
2. **Inspect Print Statements**:
   ```bash
   python -m pytest -s -k "test_name"
   ```
3. **Drop into Interactive Debugger on Failure**:
   ```bash
   python -m pytest --pdb
   ```
4. **Isolate Database State**:
   * Always use the `in_memory_db` fixture in new database tests to ensure each test runs on a clean SQLite database instance (`:memory:`).
