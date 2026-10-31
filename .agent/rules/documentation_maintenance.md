---
description: Mandatory rules for automatically updating project context and documentation after code changes.
trigger: always_on
---

# 📝 Automatic Context Maintenance Protocol

Whenever you perform meaningful code changes (feature additions, bug fixes, refactorings, or test additions):

1. **Update `memory/CHANGELOG.md`**:
   * Record what changed, why it changed, and affected modules.
2. **Update `memory/CURRENT_STATUS.md`**:
   * Refresh the active metrics (number of passing tests, test coverage %, current priority).
3. **Update `memory/COMPLETED_TASKS.md` or `memory/PENDING_TASKS.md`**:
   * Move completed backlog items to `COMPLETED_TASKS.md` with verification evidence.
4. **Update Technical Documentation if APIs or Schemas Changed**:
   * If an endpoint changed, update `docs/API_DOCUMENTATION.md`.
   * If a table or field changed, update `docs/DATABASE_SCHEMA.md`.
   * If a test suite was added, update `docs/TESTING_STRATEGY.md`.
5. **Never Record Unverified Facts**:
   * Only document features that have been implemented and verified with passing tests.
