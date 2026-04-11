## 1. Delete dead modules

- [x] 1.1 Delete `scrub/clamav.py`
- [x] 1.2 Inline `sha256` and `build_manifest` from `scrub/quarantine.py` into `scrub/pipeline.py` (strip `virus_name` and `scanned_file` fields from the manifest dict); then delete `scrub/quarantine.py`

## 2. `scrub/pipeline.py` — remove ClamAV and quarantine

- [x] 2.1 Remove `import shutil`, `import tempfile` (both only used for `scan_dir`); remove `from . import ... quarantine ...` and `from .clamav import scan_pngs`
- [x] 2.2 Remove `quarantine_dir: Path` and `socket_path: str` parameters from `process_file`; update docstring return values to `'clean'` or `'error'` (drop `'quarantine'`)
- [x] 2.3 Remove `file_sha256 = quarantine.sha256(raw)` line; replace with `hashlib.sha256(raw).hexdigest()` inline in the `_error` helper (add `import hashlib` at the top)
- [x] 2.4 Remove `scan_dir = Path(tempfile.mkdtemp(...))` creation and `shutil.rmtree(scan_dir, ...)` cleanup from `process_file`; remove `scan_dir` argument from the three `_process_*` calls
- [x] 2.5 Remove the entire ClamAV scan block (scan_paths construction, `scan_pngs` call, ClamAV error/detection branches, `return "quarantine"`)
- [x] 2.6 Remove `scan_dir: Path` parameter from `_process_image`; return PNG bytes directly instead of writing to `scan_dir / "page_001.png"`; update call site in `process_file` to receive bytes
- [x] 2.7 Remove `scan_dir: Path` parameter from `_process_document`; return list of PNG bytes instead of writing pages to `scan_dir`; update call site in `process_file`
- [x] 2.8 Remove `scan_dir: Path` parameter from `_process_text_document`; return list of PNG bytes instead of writing pages to `scan_dir`; update call site in `process_file`
- [x] 2.9 Delete the `_quarantine` helper function entirely
- [x] 2.10 Update `_error` helper to use the inlined `build_manifest` dict (from task 1.2) and remove `virus_name`/`scanned_file` from the manifest

## 3. `scrub/cli.py` — remove ClamAV and quarantine

- [x] 3.1 Remove `from . import ... clamav ...` import
- [x] 3.2 Remove `_QUARANTINE = Path("/data/quarantine")` and `_SOCKET = "/run/clamav/clamd.sock"` constants
- [x] 3.3 Remove `quarantine=_QUARANTINE` and `socket=_SOCKET` from `log.startup(...)` call
- [x] 3.4 Remove `fs.validate_dirs(...)` call or update it to only validate `_SOURCE`, `_CLEAN`, `_ERRORS` (drop `_QUARANTINE`)
- [x] 3.5 Remove the ClamAV daemon wait block (`log.debug("[clamav]", ...)`, `await clamav.wait_for_daemon(...)`, `log.debug("[clamav]", "daemon ready")`)
- [x] 3.6 Remove `quarantine_count` variable, its `+= 1` branch, and its references in `log.summary(...)` and the exit code expression; update exit code to `1 if error_count else 0`
- [x] 3.7 Remove `quarantine_dir=_QUARANTINE` and `socket_path=_SOCKET` from the `process_file(...)` call

## 4. Docker configuration

- [x] 4.1 Remove the `clamav` service from `docker-compose.yml` (image, volumes, healthcheck, depends_on reference from `scrub` service)
- [x] 4.2 Remove `clamav-socket`, `clamav-sigs`, and `clamav-logs` volumes from `docker-compose.yml`
- [x] 4.3 Remove the `clamav-socket` volume mount from the `scrub` service in `docker-compose.yml`
- [x] 4.4 Apply the same removals to `docker-compose.dev.yml`
- [x] 4.5 Delete `docker/clamd.conf`

## 5. Configuration and docs

- [x] 5.1 Remove `data/quarantine` from the `mkdir -p` command in `CLAUDE.md`
- [x] 5.2 Remove `data/quarantine/` from the output layout description in `CLAUDE.md`
- [x] 5.3 Update `README.md`:
  - Line 3: remove "Output PNGs are scanned with ClamAV just to make sure everything is clean."
  - Line 12: remove `→ ClamAV scan` from pipeline description
  - Lines 26–27: remove the `--host-uds=open` bullet (solely about ClamAV socket forwarding)
  - Line 35: remove "ClamAV signature download happens at first run..." paragraph
  - Lines 42–44: remove `data/quarantine` and `data/clamav-socket` from the `mkdir -p` command; remove the `chmod 1777` line and its explanation
  - Lines 56–58: remove the "On first run, the ClamAV sidecar downloads..." paragraph
  - Line 67: remove `data/quarantine/` row from the output directory table
  - Lines 78–93: remove the entire "Quarantine manifests" section (heading, prose, JSON example)
  - Lines 96–110: remove `ClamAVDetection` and `ClamAVError` rows from the `error_type` table; rename section from "Quarantine manifests" context to "Error manifests" or similar
  - Lines 129–136: replace the EICAR/quarantine verification example with a simpler smoke test (e.g. process a plain image and check `data/clean/`)
  - Lines 148–171: replace the two-container architecture diagram with a single-container version (remove Unix socket and clamav container block)

## 6. Tests

- [x] 6.1 Remove `from scrub import quarantine as qmod` and `from scrub.clamav import ScanResult` imports from `tests/test_sanity.py`
- [x] 6.2 Remove the quarantine module test class (around line 171 in `test_sanity.py`)
- [x] 6.3 Remove `test_detection_goes_to_quarantine` and `test_clamav_error_goes_to_quarantine` test cases
- [x] 6.4 Remove `quarantine_dir=tmp_path / "quarantine"` and `socket_path=...` arguments from all remaining `process_file(...)` call sites in tests
- [x] 6.5 Remove quarantine-path assertions (e.g. `not list((tmp_path / "quarantine").rglob("*.json"))`) from remaining tests
