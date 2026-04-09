---
name: ruff
description: Run ruff check and ruff format on the codebase. Use when you need to lint, find style issues, or auto-format Python files.
---

Run both ruff check and ruff format using uv:

1. `uv run ruff check .` — report any linting violations found
2. `uv run ruff format .` — format all files and report which files were changed

If `ruff check` finds violations, list them. If nothing needs fixing, say so.
