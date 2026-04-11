## Why

Source directories may be mounted read-only, making the current in-place archive extraction (which writes extracted members back into source) fail at runtime. A dedicated `extracts` directory gives archives a writable landing zone without touching source.

## What Changes

- New `/data/extracts` directory added alongside `source`, `clean`, `quarantine`, and `errors`
- Archive extraction writes members into `extracts` instead of the source directory, mirroring source structure and scoping under the archive stem
- Pipeline walks `extracts` as a second source root after `source`
- Dedup check: if the first member of an archive already exists in `source`, the archive is skipped entirely (assumed already extracted)
- `docker-compose.yml` (and dev variant) gains an `extracts` bind mount

## Capabilities

### New Capabilities
- `extracts-dir`: The `/data/extracts` directory as the extraction target for archive members, with source-mirrored structure scoped under each archive's stem

### Modified Capabilities
- `archive-extraction`: Extraction target changes from source directory (in-place) to `extracts`; dedup sentinel check added (first member in source → skip archive)
- `filesystem-io`: Pipeline walks both `source` and `extracts`; source is now strictly read-only (no writes by any pass)

## Impact

- Modified files: `scrub/archive.py`, `scrub/cli.py`
- Modified config: `docker-compose.yml`, `docker-compose.dev.yml`
- Modified specs: `openspec/specs/archive-extraction/spec.md`, `openspec/specs/filesystem-io/spec.md`
