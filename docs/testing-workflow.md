# Testing workflow: coverage-driven test maintenance

Run this after any non-trivial change, before merging/deploying. Goal: catch regressions the
change introduced, and keep the test suite covering real business logic instead of decaying
alongside the code.

## 1. Run tests with coverage

```bash
./scripts/test_coverage.sh
```

This runs the full suite (`tests/`) with coverage measured over `backend/src`, prints a
per-file missing-lines summary in the terminal, and writes a browsable report to
`htmlcov/index.html`. Fix any failures before moving on - don't layer new tests on top of a
red suite.

## 2. Hand a fresh AI session the diff + coverage gaps

Coverage percentage alone is a bad signal in isolation - what matters is whether the *lines
that changed* are exercised. In a new session (fresh context avoids the implementer's own
blind spots about what they just wrote), give the agent:

- The output of `git log --stat <last-reviewed-commit>..HEAD` (or the PR diff) so it knows
  exactly what changed.
- The coverage report's missing-lines output (terminal summary is usually enough; point to
  `htmlcov/` for detail on specific files).

Ask it to:
1. Fix any tests that fail against the new code (decide per-failure whether the *test* is
   stale relative to an intentional behavior change, or the *code* has a real bug - don't
   reflexively update assertions to match broken output).
2. Add tests only for genuinely new business logic surfaced in the diff - see the rules below
   for what's worth covering.

The `Explore` step this needs (locating relevant existing tests, fixtures, and patterns to
follow) is exactly what a coding agent should do before writing anything - point it at
`tests/` and let it find the existing fixture/fake patterns (e.g. `tests/conftest.py`'s
`client`/`db` fixtures, the fake Docker client pattern in `tests/test_deployment_adapter.py`)
rather than inventing new ones.

## 3. Test-quality rules

- **Cover business logic and main scenarios** - the actual decision points and branches a real
  user's request would hit (a new endpoint's happy path + its realistic failure modes, a state
  machine transition, a validation rule with teeth).
- **Don't test the obvious** - getters/setters, framework behavior (e.g. "FastAPI returns 404
  for an unknown route"), or trivial pass-through code. A test that would never fail for any
  bug worth catching is noise, not coverage.
- **No test-count padding** - one well-chosen test with a couple of meaningful assertions beats
  five near-duplicate tests that vary one irrelevant input. If two tests would fail for exactly
  the same underlying bug, keep one.
- Prefer extending an existing test file's patterns (fixtures, fake clients, helper functions)
  over introducing a new convention for the same thing.

## Why this exists

The test suite drifts out of sync with the code by default - a behavior change (new response
shape, a redesigned control-flow path) doesn't update the tests that assert on the old shape,
and new business logic doesn't get a test unless someone deliberately adds one. Coverage numbers
by themselves don't catch this (a stale test can still "cover" a line while asserting the wrong
thing about it) - the fix is a habitual diff-plus-coverage review, not a coverage percentage
gate.
