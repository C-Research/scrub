## 1. Project Scaffold

- [x] 1.1 Create `pyproject.toml` with dependencies: `aiofiles`, `PyMuPDF`, `Pillow`, and dev deps
- [x] 1.2 Create package structure: `scrub/` with `__init__.py`, `cli.py`, `pipeline.py`, `converter.py`, `sanitize.py`, `fs.py`, `quarantine.py`, `log.py`, `clamav.py`
- [x] 1.3 Register `scrub` CLI entrypoint in `pyproject.toml`

## 2. Logging

- [x] 2.1 Implement `log.py`: structured log lines to file with timestamp, level, ARN, event (`START`/`SUCCESS`/`QUARANTINE`), and detail
- [x] 2.2 Ensure log file and parent directories are created on startup if absent

## 3. Filesystem I/O

- [x] 3.1 Implement `fs.py`: `walk_source(source_dir) -> AsyncIterator[Path]` using `os.scandir` in `run_in_executor`, yielding all files recursively
- [x] 3.2 Implement `validate_dirs(source, clean, quarantine)`: check source is readable, clean and quarantine are writable; raise fatal error if not
- [x] 3.3 Implement `derive_output_paths(source_dir, clean_dir, rel_path, page_count, is_xlsx) -> list[Path]`: build output paths preserving folder structure, zero-padded `page_NNN.png` / `sheet_NNN.png`
- [x] 3.4 Implement `write_png(path, data)` using aiofiles: create parent directories then write bytes
- [x] 3.5 Implement `write_quarantine_manifest(quarantine_dir, rel_path, manifest: dict)` using aiofiles: create parent directories then write JSON

## 4. Format Detection

- [x] 4.1 Implement magic-bytes format detection in `pipeline.py`: PDF, DOCX/XLSX/PPTX (ZIP-based), DOC/XLS/PPT (OLE), PNG, JPG, TIFF, BMP, GIF
- [x] 4.2 Implement pre-flight size check via `os.stat` before reading full file
- [x] 4.3 Return `UnsupportedFormat` quarantine for unrecognized magic bytes

## 5. Document Conversion (LibreOffice)

- [x] 5.1 Implement `converter.py`: `convert_to_pdf(input_path) -> Path` using `asyncio.create_subprocess_exec` with LibreOffice headless
- [x] 5.2 Pass fresh `--user-installation` temp dir to each LibreOffice invocation; clean up in `try/finally`
- [x] 5.3 Disable macros via LO security config; disable Java via `--nojava` flag
- [x] 5.4 For XLSX/XLS: pass `--infilter` export options to scale each sheet to fit one page
- [x] 5.5 Apply `asyncio.wait_for` timeout; SIGKILL on timeout; quarantine with `LibreOfficeTimeout`
- [x] 5.6 Apply `resource` module memory limit to LibreOffice subprocess; quarantine non-zero exits with `LibreOfficeError`

## 6. PDF Rasterization (PyMuPDF)

- [x] 6.1 Implement `rasterize_pdf(pdf_path) -> list[bytes]` in `converter.py`: open with `fitz`, iterate pages, return list of raw RGB pixel bytes per page
- [x] 6.2 Quarantine PDFs with zero pages with `EmptyDocument`
- [x] 6.3 Wrap fitz operations in try/except; quarantine with `PyMuPDFError` on exception

## 7. Image Sanitization (Pillow)

- [x] 7.1 Implement `sanitize.py`: `reencode_png(raw_rgb_bytes, width, height) -> bytes` using `Image.frombuffer()` → strip metadata → `Image.save()` to bytes buffer
- [x] 7.2 Implement `sanitize_image_input(path) -> bytes` for direct image inputs: open with Pillow, extract raw pixels, call `reencode_png`
- [x] 7.3 Wrap Pillow operations in try/except; quarantine with `ImageDecodeError` or `PillowEncodeError`
- [x] 7.4 Run Pillow re-encode via `asyncio.run_in_executor` (CPU-bound)

## 8. Quarantine

- [x] 8.1 Implement `quarantine.py`: `build_manifest(input_path, format_detected, error_type, error_detail, stack_trace, file_size_bytes, sha256, virus_name=None, scanned_file=None) -> dict`
- [x] 8.2 Compute SHA256 of raw input bytes immediately after reading source file
- [x] 8.3 Call `fs.write_quarantine_manifest()` to write JSON to quarantine directory mirroring source path
- [x] 8.4 Ensure no partial output PNGs are written to clean directory when a file is quarantined

## 9. ClamAV Integration

- [x] 9.1 Implement `clamav.py`: `wait_for_daemon(socket_path, timeout=60)` — poll Unix socket with exponential backoff; raise fatal error if daemon never responds
- [x] 9.2 Implement `scan_pngs(png_paths, socket_path, timeout=30) -> ScanResult` — invoke `clamdscan --no-summary --infected --socket=<path>` via `asyncio.create_subprocess_exec`; parse stdout for virus name and triggering file
- [x] 9.3 Return `ClamAVDetection` with `virus_name` and `scanned_file` on detection; return `ClamAVError` on non-zero exit, timeout, or socket failure

## 10. Pipeline Orchestration

- [x] 10.1 Implement `pipeline.py`: `process_file(rel_path, source_dir, clean_dir, quarantine_dir, socket_path, timeout, memory_limit)` wiring all stages together
- [x] 10.2 Route by detected format: image path skips LibreOffice and PyMuPDF, goes direct to Pillow
- [x] 10.3 After Pillow re-encode: call `scan_pngs()` on all output PNGs; quarantine immediately on any detection or scan error before any write to clean directory
- [x] 10.4 Implement `asyncio.Semaphore(workers)` in main loop; default `workers = os.cpu_count() * 2 - 1`

## 11. CLI

- [x] 11.1 Implement `cli.py` using `argparse`: parse `--source`, `--clean`, `--quarantine`, `--log`, `--workers`, `--timeout`, `--memory-limit`, `--clamav-socket` (default `/run/clamav/clamd.sock`)
- [x] 11.2 Call `fs.validate_dirs()` and `clamav.wait_for_daemon()` at startup; exit code 1 with fatal log if either fails
- [x] 11.3 Run `asyncio.run(main(...))` from CLI entrypoint
- [x] 11.4 Exit with code 0 if no quarantines, code 1 if any quarantines occurred

## 12. Docker & Deployment

- [x] 12.1 Write `Dockerfile` for scrub: base image (Ubuntu 22.04 slim), install LibreOffice, Python 3.11, system fonts, `clamdscan` CLI
- [x] 12.2 Disable LibreOffice Java and macro security in baked config
- [x] 12.3 Add `--no-new-privileges`, run as non-root user in `Dockerfile`
- [x] 12.4 Write `docker-compose.yml`: scrub service (`--runtime runsc --network none --cap-drop ALL --read-only --tmpfs /tmp`, bind mounts for `source:ro`, `clean`, `quarantine`, `logs`) + clamav service (`clamav/clamav`), shared `clamav-socket` volume, shared `clamav-sigs` named volume, aligned GID for socket access
- [x] 12.5 Add `healthcheck` to clamav service in docker-compose (poll clamd socket); scrub service `depends_on: clamav: condition: service_healthy`
