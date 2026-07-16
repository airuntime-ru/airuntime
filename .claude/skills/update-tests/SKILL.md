---
name: update-tests
description: Run the backend test suite with coverage, then fix failing tests and add tests for new business logic based on recent changes. Use before merging/deploying a non-trivial backend change, or when asked to "update tests" / "fix the test suite" / "run the testing workflow".
---

# Update tests (coverage-driven)

Full background: [docs/testing-workflow.md](../../../docs/testing-workflow.md). This skill
operationalizes that doc for an AI session - follow these steps in order.

## Steps

1. **Find what changed.** Run `git log --stat -20` (or, if given a specific range/PR, diff
   against that base) to see which files and commits are in scope. Read the actual diffs for
   the changed files, not just the file list.

2. **Run the suite with coverage.**
   ```bash
   ./scripts/test_coverage.sh
   ```
   This needs a Postgres + Redis reachable at `DATABASE_URL`/`REDIS_URL` (see `tests/conftest.py`
   for defaults) - if none is running, start throwaway containers on non-default ports, run
   `alembic upgrade head` from `backend/`, point the env vars at them, and tear them down after.

3. **Fix every failure first**, before adding anything new. For each failure, decide:
   - **Stale test**: the code's behavior changed on purpose (new response shape, new
     architecture for a flow, a renamed function) and the test still asserts the old shape.
     Update the test to match current, intended behavior - read the surrounding code to confirm
     the new behavior is actually intended, not itself a bug.
   - **Real bug**: the test's expectation was correct and the code regressed. Fix the code, not
     the test.
   Never blanket-relax an assertion just to make it pass - understand why it broke.

4. **Look at the coverage report's missing-lines output** for files touched by the diff. For
   each gap that represents real business logic (a branch, a validation rule, a new endpoint's
   error path) rather than boilerplate, consider adding a test.

5. **Apply the test-quality rules** before writing anything:
   - Cover business logic and main scenarios - not getters/framework behavior/trivial
     pass-through.
   - Don't add near-duplicate tests that would all fail for the same underlying bug - one
     well-chosen test beats five.
   - Reuse existing fixtures/fakes/helpers (`tests/conftest.py`'s `client`/`db` fixtures, the
     fake Docker client pattern in `tests/test_deployment_adapter.py`/
     `tests/test_project_services.py`) instead of inventing new patterns for the same thing.

6. **Re-run `./scripts/test_coverage.sh`** to confirm everything is green, then run
   `ruff check backend/src agents tests scripts admin` and `ruff format --check` on the files
   you touched (pre-existing lint debt elsewhere in the repo is not yours to fix here).

7. Report back concisely: what was fixed and why (stale test vs. real bug, one line each), what
   new tests were added and what business logic they cover, and the final pass/fail count.
