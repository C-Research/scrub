# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

`scrub` is a Content Disarm and Reconstruction (CDR) tool. It converts potentially malicious office documents and images into sanitized PNGs through pixel-level re-encoding — every input is treated as adversarially crafted. It runs in a hardened Docker container with gVisor kernel-level sandbox isolation.

Supported formats: PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, PNG, JPG, TIFF, BMP, GIF

## Commands

```bash
# Run tests
pytest
pytest tests/test_sanity.py::TestDetectFormat   # single test class
pytest tests/test_sanity.py::TestDetectFormat::test_pdf  # single test

# Lint / format
ruff check scrub/ tests/
ruff format scrub/ tests/

# Security scan
bandit scrub/

# Build and run (Docker)
docker compose build
mkdir -p data/source data/extracts data/clean data/errors data/logs
SCRUB_RUNTIME=runsc docker compose up

# Local dev install
pip install -e ".[dev]"
```

Environment variables: `SCRUB_RUNTIME` (default: `runc`; set to `runsc`/`runsc-kvm` for gVisor), `SCRUB_WORKERS` (default: CPU×2−1), `SCRUB_TIMEOUT` (LibreOffice timeout in seconds, default 60), `SCRUB_MAX_PAGES` (max PDF pages before `FileTooLarge`, default 500), `SCRUB_MAX_PAGE_PIXELS` (max pixels per rasterized page, default 50000000 ≈ 7000×7000).

## Architecture

The pipeline runs fully async (`asyncio`) with a worker semaphore to cap concurrency.

```
Input file
  → magic-byte format detection (pipeline.py)
  → image path: sanitize.py (Pillow RGB decode → PNG re-encode)
  → document path: converter.py (LibreOffice → PDF, PyMuPDF rasterize → RGB pixels) → sanitize.py
  → clean PNG(s) written to output dir  OR  JSON manifest to errors
```

**Key modules:**

| Module | Role |
|---|---|
| `cli.py` | Entry point, async worker loop, semaphore, directory validation |
| `pipeline.py` | Orchestration: routes by format, calls converter/sanitize, emits decisions |
| `converter.py` | LibreOffice subprocess (macro security level 4) → PDF; PyMuPDF rasterization at 150 dpi RGB |
| `sanitize.py` | Pillow: decode raw bytes to RGB, re-encode to PNG (strips all metadata) |
| `fs.py` | Async file I/O (aiofiles), directory walk, output path derivation |
| `log.py` | Structured logging with semantic labels: START, SUCCESS, ERROR, SKIPPED |

**Output layout** (mirrors source subdirectory structure):
- `data/clean/` — sanitized PNGs (`page_001.png`, `page_002.png`, … / `sheet_001.png`, …)
- `data/errors/` — JSON manifests for processing failures
- `data/logs/scrub.log` — structured event log

**Error types** used throughout the codebase: `UnsupportedFormat`, `FileTooLarge`, `LibreOfficeTimeout`, `LibreOfficeError`, `PyMuPDFError`, `EmptyDocument`, `ImageDecodeError`, `PillowEncodeError`.

## Testing

Tests live in `tests/` with real fixture files in `tests/fixtures/` (EICAR test files, macro-laden Office docs) for format detection. pytest-asyncio is configured in auto mode.
