## Context

The CDR pipeline converts every input file to pure RGB pixel PNGs via LibreOffice and Pillow. ClamAV currently scans these already-sanitized PNGs — after all metadata has been stripped and content re-encoded from raw pixels. In practice no quarantine events occur, which is expected: a signature scanner has nothing meaningful to match against inert pixel data.

The current implementation threads a `scan_dir` temp directory through every processing function in `pipeline.py`, creates and destroys it per file, and blocks startup waiting for the clamd daemon. Removing ClamAV eliminates this complexity and the Docker sidecar entirely.

## Goals / Non-Goals

**Goals:**
- Remove all ClamAV code, config, and Docker infrastructure
- Remove the quarantine output path (was solely for ClamAV detections)
- Simplify `pipeline.py` by eliminating `scan_dir` from all processing functions
- Simplify `cli.py` by removing daemon wait and quarantine tracking

**Non-Goals:**
- Changing the CDR pipeline itself (LibreOffice → PDF → PNG, Pillow re-encode)
- Modifying the error/failure path or error manifest format
- Adding any replacement scanning mechanism

## Decisions

### Remove `quarantine.py` and `data/quarantine/` entirely
The quarantine concept was exclusively tied to ClamAV. Errors (LibreOffice failures, decode errors, etc.) go to `data/errors/` and are handled by a separate error manifest path. With ClamAV gone, there is no quarantine path — the system produces clean output or errors.

**Alternative considered**: Keep quarantine as a concept for future use. Rejected — empty abstractions add noise and the error path already covers all failure cases.

### Delete `scrub/clamav.py` and `scrub/quarantine.py`
Both modules become dead code. Deleting them is cleaner than leaving them unused.

### Remove `scan_dir` from all processing functions
Currently every `_process_*` function in `pipeline.py` accepts a `scan_dir` parameter and writes PNGs there for scanning before copying to clean output. With ClamAV gone, pages can be returned as bytes and written directly to the output directory — no intermediate temp dir needed.

### Remove `--quarantine` CLI argument
The argument had no purpose beyond passing the quarantine path to the pipeline. With no quarantine path, it is removed. CLI becomes: `--source`, `--clean`, `--log`, `--workers`, `--timeout`.

### Remove `--clamav-socket` CLI argument and daemon wait
The startup `wait_for_daemon()` call was the primary cause of slow container cold-start. Removing it means workers start immediately.

## Risks / Trade-offs

**Loss of defense-in-depth** → The CDR pixel re-encoding is the security guarantee. ClamAV on the output provided no meaningful additional detection surface; the risk of removing it is negligible.

**Exit code change** → Previously exit code 1 meant "quarantine or error". After removal it means "error only". This is a minor behavioral change for any callers checking the exit code.

## Migration Plan

1. Remove `scrub/clamav.py`, `scrub/quarantine.py`
2. Simplify `pipeline.py`: remove `scan_dir` pattern, ClamAV scan block, `_quarantine` helper, quarantine-related imports
3. Update `cli.py`: remove daemon wait, `_QUARANTINE` path, quarantine count, `--quarantine`/`--clamav-socket` args
4. Update `docker-compose.yml` / `docker-compose.dev.yml`: remove clamav service and volumes
5. Update `CLAUDE.md`: remove `data/quarantine` from setup command
6. Update tests: remove ClamAV and quarantine test coverage
