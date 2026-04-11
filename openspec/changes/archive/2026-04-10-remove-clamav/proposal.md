## Why

ClamAV scans the already-sanitized PNGs produced by the CDR pipeline — pure pixel data with all metadata stripped — and in practice never flags anything. The pixel-level re-encoding is the security guarantee; a signature scanner on the output adds no meaningful defense and imposes real cost (sidecar container, signature DB, daemon startup delay).

## What Changes

- Remove `scrub/clamav.py` entirely
- Remove `scan_dir` temp directory from `pipeline.py`; simplify all processing functions to remove the ClamAV scan step and scan path management
- Remove `quarantine_dir` parameter and `_quarantine` helper from `pipeline.py`; the quarantine result state is eliminated
- Remove `data/quarantine/` directory and `quarantine.py` module
- Remove `clamav` service, socket volume, and sig-DB volume from `docker-compose.yml` and `docker-compose.dev.yml`
- Remove daemon wait and quarantine tracking from `cli.py`
- Remove `CLAUDE.md` mention of `data/quarantine` in the setup mkdir command

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `clamav-scan`: Capability removed entirely — no scanning of output PNGs
- `quarantine`: Capability removed entirely — no quarantine path or manifests
- `filesystem-io`: `data/quarantine/` directory removed from output layout
- `cli`: Quarantine count tracking and daemon wait removed from startup and summary

## Impact

- Deleted files: `scrub/clamav.py`, `scrub/quarantine.py`
- Modified files: `scrub/pipeline.py`, `scrub/cli.py`, `docker-compose.yml`, `docker-compose.dev.yml`, `CLAUDE.md`
- Removed Docker volumes: `clamav-socket`, `clamav-sigs`, `clamav-logs`
- Tests referencing ClamAV or quarantine paths need updating
