## 1. Dependencies

- [x] 1.1 Add `rarfile` to `dependencies` in `pyproject.toml`
- [x] 1.2 Add `unrar` to the `apt-get install` block in `Dockerfile`

## 2. Configurable limits

- [x] 2.1 Replace hardcoded `_MAX_SIZE = 100 * 1024 * 1024` in `pipeline.py` with a module-level value read from `SCRUB_MAX_FILE_SIZE` env var (default 100 MB) using the existing `_optional_int` pattern
- [x] 2.2 Add `SCRUB_MAX_ARCHIVE_MEMBERS` and `SCRUB_MAX_ARCHIVE_TOTAL_BYTES` env var reads in `cli._run()` and pass them to `expand_archives`

## 3. `scrub/archive.py` — new module

- [x] 3.1 Implement `expand_archives(source_dir, max_file_bytes, max_members, max_total_bytes) -> int` — returns count of archives expanded
- [x] 3.2 Collect all `.zip` / `.rar` paths via `rglob` upfront (excluding `.docx`, `.xlsx`, `.pptx`), then expand in one pass
- [x] 3.3 Implement ZIP extraction: set `rarfile.UNRAR_TOOL = "/usr/bin/unrar"`; for each member validate path (no `..`, no absolute, resolves within parent dir, not a symlink), check member size ≤ `max_file_bytes`, accumulate total bytes, enforce `max_members`; skip if destination exists; extract
- [x] 3.4 Implement RAR extraction with the same safety checks as ZIP
- [x] 3.5 Log a warning for each skipped member (path traversal, symlink, oversized) and when a per-archive limit aborts remaining members

## 4. `scrub/cli.py` — integration

- [x] 4.1 Call `archive.expand_archives(...)` after `clamav.wait_for_daemon` and before the `walk_source` loop
- [x] 4.2 Add `expanded` count to the `log.summary(...)` call

## 5. `scrub/log.py` — summary update

- [x] 5.1 Add `expanded` parameter to `log.summary` and include it in the summary log line

## 6. Tests

- [x] 6.1 Test ZIP extraction: members land in source dir alongside archive
- [x] 6.2 Test dedup: member skipped when destination already exists
- [x] 6.3 Test path traversal rejection: `..` and absolute paths skipped
- [x] 6.4 Test symlink skipped
- [x] 6.5 Test per-member size limit: oversized member skipped, others extracted
- [x] 6.6 Test member count limit: extraction aborts after `max_members`
- [x] 6.7 Test total bytes limit: extraction aborts when cumulative size exceeded
- [x] 6.8 Test Office ZIP skipped: `.docx` not treated as archive
- [x] 6.9 Test one-level only: inner zip extracted but not expanded
