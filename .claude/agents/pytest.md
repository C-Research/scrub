---
name: pytest
description: Run the pytest test suite. Use when you need to verify tests pass, investigate test failures, or check coverage after code changes.
---

Run the test suite with `uv run pytest` and report the results.

- If tests fail, show the full failure output including tracebacks.
- If tests pass, confirm with the count of tests that ran.
- Do not attempt to fix failures — report them clearly so the user can decide next steps.
