## 1. `scrub/archive.py` — extraction target

- [x] 1.1 Add `_archive_stem(p: Path) -> str` helper: strips `.tar.gz` (7 chars), `.tgz` (4 chars), else returns `p.stem`
- [x] 1.2 Add `extracts_dir: Path` parameter to `expand_archives`; compute `dest_dir = extracts_dir / archive_path.relative_to(source_dir).parent / _archive_stem(archive_path)` for each archive and pass it to each `_expand_*` function
- [x] 1.3 Update `_expand_zip`, `_expand_rar`, `_expand_targz` signatures to accept `dest_dir: Path` instead of deriving it from `archive_path.parent`
- [x] 1.4 Update `_expand_gz` to accept `dest_dir: Path`; write output to `dest_dir / archive_path.stem` (no archive-stem subdirectory for single-file gz)

## 2. `scrub/archive.py` — first-member sentinel dedup

- [x] 2.1 In `expand_archives`, before calling `_expand_zip`/`_expand_rar`/`_expand_targz`/`_expand_gz`, implement the sentinel check: peek at the first member's relative path and check `source_dir / first_member_rel_path`; if it exists, log `ARCHIVE_SKIP "already in source"` and skip the archive
- [x] 2.2 For `.gz` (single-file), the sentinel check is: if `source_dir / archive_path.stem` exists, skip

## 3. `scrub/cli.py` — extracts directory

- [x] 3.1 Add `_EXTRACTS = Path("/data/extracts")` alongside the other fixed paths
- [x] 3.2 Pass `_EXTRACTS` to `archive.expand_archives` call
- [x] 3.3 Add `extracts=_EXTRACTS` to the `log.startup(...)` call
- [x] 3.4 Add `source_dir: Path` parameter to `_bounded`; pass it through to `process_file`
- [x] 3.5 After the `_SOURCE` walk, add a second walk over `_EXTRACTS` (skip if directory is empty or does not exist); enqueue tasks with `source_dir=_EXTRACTS`

## 4. Docker configuration

- [x] 4.1 Add `extracts` bind mount to `docker-compose.yml` (host: `./data/extracts`, container: `/data/extracts`)
- [x] 4.2 Add `extracts` bind mount to `docker-compose.dev.yml` with the same mapping
- [x] 4.3 Add `data/extracts` to the `mkdir -p` command in `CLAUDE.md` (local setup instructions)

## 5. Tests

- [x] 5.1 Test ZIP extraction: member lands in `extracts/<archive-stem>/` not in source
- [x] 5.2 Test mirrored structure: archive in subdirectory extracts to matching subdirectory in extracts
- [x] 5.3 Test `.gz` single-file extraction: output at `extracts/<stem>`, no extra subdirectory
- [x] 5.4 Test sentinel skip: first member exists in source → archive skipped, nothing written to extracts
- [x] 5.5 Test sentinel pass: first member absent from source → extraction proceeds to extracts
- [x] 5.6 Test extracts dedup: member already in extracts → member skipped on re-run
