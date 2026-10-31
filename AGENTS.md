# 🏊🚴🏃 TriCoach AI — Universal AI Agent Guidelines & Context

> **CRITICAL DIRECTIVE FOR ALL AI AGENTS (Gemini, Claude, GPT, Antigravity, Cursor, Copilot)**:
> You are working on **TriCoach AI**, a personal triathlon and fitness endurance coach web application.
> **DO NOT** ask the user to re-explain the architecture, tech stack, testing framework, or past decisions. Everything you need is persisted in this repository. Follow the **New Session Protocol** below immediately upon beginning any task.

---

## ⚡ Quick Project Orientation

| Attribute | Ground Truth Value |
| :--- | :--- |
| **Domain** | Triathlon & Endurance Coaching (Swim, Bike, Run, Nutrition, Training Zones) |
| **Backend** | Python 3.10+ / 3.11+, FastAPI, Pydantic V2, Uvicorn |
| **Storage** | SQLite (`workouts.db` or `:memory:`) with Firestore opt-in (`USE_FIRESTORE=true`) |
| **Frontend** | Responsive sports chat UI (`frontend/static/index.html`) + A2UI v0.8 renderer |
| **AI Models** | `gemini-flash-latest` (ADK), `gemini-3.1-flash-lite-image`, `gemini-omni-flash-preview` |
| **Server Modes** | **Mode 1**: Standalone Unified Server (`app/web_server.py`) on port 8080 (serves UI + API directly).<br/>**Mode 2**: Enterprise Agent Engine (`app/agent.py` + `app/fast_api_app.py` + A2A). |
| **Automated Tests** | 69 automated tests (Unit, API, Integration, Frontend, Regression, E2E Playwright) |
| **CI/CD** | GitHub Actions (`.github/workflows/ci.yml`) with automated Quality Gate deployment blocker |

---

## 🧭 Project Navigation Map

All project documentation and runtime memory are structured under:

```
buildwithgemini-tricoach-fitness-agent/
├── AGENTS.md                          # <-- YOU ARE HERE: Master Entry Point
├── GEMINI.md                          # Google Antigravity & Agent Engine Guidance
├── docs/
│   ├── PROJECT_OVERVIEW.md            # App mission, features, target athletes
│   ├── ARCHITECTURE.md                # System design, Dual-Mode server, A2UI dataflow
│   ├── DATABASE_SCHEMA.md             # SQLite & Firestore table structures
│   ├── API_DOCUMENTATION.md           # Endpoints (/chat, /calories, /workouts, /health)
│   ├── TESTING_STRATEGY.md            # Test pyramid, fixtures, execution commands
│   └── DEVELOPMENT_GUIDELINES.md      # Coding style, safety guardrails, git workflow
├── memory/
│   ├── CURRENT_STATUS.md              # 🔴 ACTIVE PROJECT STATE (Read First!)
│   ├── CHANGELOG.md                   # Chronological version & modification history
│   ├── COMPLETED_TASKS.md             # Verified implemented tasks
│   ├── PENDING_TASKS.md               # Prioritized engineering backlog
│   └── TECHNICAL_DECISIONS.md         # Architectural Decision Records (ADRs)
└── .agents/rules/                     # Machine-readable Antigravity / AI Rules
    ├── session_startup.md             # Step-by-step turn 1 initialization rules
    ├── code_standards.md              # Architectural invariants & coding rules
    └── documentation_maintenance.md   # Automatic memory update requirements
```

---

## 🚦 New Session Protocol (Execute on Turn 1)

Whenever you start a new conversation, change models, or receive a new request:

1. **Step 1: Read Active State**:
   * Inspect [`memory/CURRENT_STATUS.md`](file:///c:/Users/mdmaa/OneDrive/Desktop/AntigravityDev/buildwithgemini-tricoach-fitness-agent/memory/CURRENT_STATUS.md) to understand current features, test coverage, and active branch state.
2. **Step 2: Inspect Source Code as Source of Truth**:
   * Never guess module contents. Inspect files in `app/` and `tests/` before answering or writing code.
3. **Step 3: Check Technical Decisions**:
   * Consult [`memory/TECHNICAL_DECISIONS.md`](file:///c:/Users/mdmaa/OneDrive/Desktop/AntigravityDev/buildwithgemini-tricoach-fitness-agent/memory/TECHNICAL_DECISIONS.md) before proposing refactors (e.g. why SQLite fallback exists, why DirectTestClient is used for test isolation).
4. **Step 4: Run Tests on Code Changes**:
   * If modifying existing business logic, execute tests immediately:
     ```bash
     python -m pytest tests/unit tests/api tests/integration tests/frontend tests/regression
     ```
5. **Step 5: Maintain Context**:
   * After any meaningful modification, update `memory/CURRENT_STATUS.md` and `memory/CHANGELOG.md`.

---

## 🛡️ Non-Negotiable Core Invariants

1. **Do Not Break Tests**: The 69 existing tests must remain passing (`pytest` exit code 0).
2. **Do Not Break Backwards-Compatibility**:
   * `app/web_server.py` and `app/agent.py` coexist peacefully.
   * `index.html` expects `/chat` to return `{"parts": [{"kind": "text", ...}, {"kind": "a2ui", ...}]}`.
3. **No Hardcoded Credentials or Project IDs**:
   * Use `os.getenv("GOOGLE_CLOUD_PROJECT")`, `os.getenv("GEMINI_API_KEY")`, `os.getenv("USE_FIRESTORE")`.
4. **Preserve Human Code**:
   * Retain comments, docstrings, and existing license headers.
