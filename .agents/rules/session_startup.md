---
description: Mandatory rules and protocol for starting any new AI conversation or resuming development on TriCoach AI.
trigger: always_on
---

# 🚀 AI Agent Session Startup Protocol

Every AI agent (Gemini, Claude, GPT, Antigravity, Cursor) MUST execute this 5-step checklist before making suggestions or writing code:

1. **Read Master Entry Point**:
   * Inspect `AGENTS.md` at the project root.
2. **Read Current State**:
   * Inspect `memory/CURRENT_STATUS.md` to identify active features, passing tests, and current branch state.
3. **Verify Reality Against Codebase**:
   * Do not hallucinate file contents or rely on outdated memory. Inspect actual files in `app/` and `tests/`.
4. **Respect Technical Decisions**:
   * Review `memory/TECHNICAL_DECISIONS.md` to understand why specific architectural choices were made (e.g. SQLite fallback, DirectTestClient, unified server mode).
5. **No Amnesia**:
   * Never ask the user to explain project architecture, existing features, or testing setup. All necessary context is documented within this repository.
