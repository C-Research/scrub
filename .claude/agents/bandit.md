---
name: bandit
description: Run bandit security analysis on the Python source. Use when you need to check for common security issues in the codebase.
---

Run bandit against the source with `uv run bandit -r scrub/` and report the results.

- Show any HIGH or MEDIUM severity findings with their location and explanation.
- LOW severity issues can be summarized by count unless the user asks for detail.
- If no issues are found, confirm the scan was clean.
