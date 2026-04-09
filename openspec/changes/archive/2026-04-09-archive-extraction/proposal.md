## Why

Source directories may contain zip or rar archives holding documents or images that need sanitization. Without archive extraction, those files are silently skipped, leaving unsanitized content in the pipeline's blind spot.

## What Changes

- New pre-processing pass runs before the main pipeline walk: expands `.zip` and `.rar` archives in-place into the source directory
- Members already present at their destination path are skipped (dedup by path)
- Path traversal, symlink, and zip-bomb protections enforced during extraction
- `_MAX_SIZE` in the pipeline is promoted from a hardcoded constant to an env-var-configurable limit
- Two new archive-specific limits, also env-var-configurable: max members per archive and max total uncompressed bytes per archive
- `unrar` added to the Docker image; `rarfile` added as a Python dependency
- Expanded archive count added to startup summary

## Capabilities

### New Capabilities
- `archive-extraction`: Pre-processing pass that expands `.zip` and `.rar` archives in the source directory before the pipeline walk, with dedup, path safety, and configurable bomb limits

### Modified Capabilities
- `cli`: New `SCRUB_MAX_FILE_SIZE`, `SCRUB_MAX_ARCHIVE_MEMBERS`, and `SCRUB_MAX_ARCHIVE_TOTAL_BYTES` env vars; expanded count in summary
- `filesystem-io`: `_MAX_SIZE` becomes a runtime-configurable value rather than a hardcoded constant

## Impact

- New file: `scrub/archive.py`
- Modified files: `scrub/cli.py`, `scrub/pipeline.py`, `scrub/log.py` (if new log event needed)
- New Python dependency: `rarfile`
- New system dependency: `unrar` (apt, `/usr/bin/unrar`)
- `Dockerfile` and `pyproject.toml` updated
