# scrub

CDR (Content Disarm and Reconstruction) tool. Converts PDF, office documents and images to sanitized PNGs by re-encoding through a pixel-level pipeline. Every input is assumed adversarially crafted. Applies some TLC to your infected files telling malware:

So no, I don't want your number
No, I don't want to give you mine and
No, I don't want to meet you nowhere
No, I don't want none of your time

**Supported formats:** PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, CSV, PNG, JPG, TIFF, BMP, GIF, ZIP, RAR, GZ, TAR.GZ, TGZ

**Default pipeline:** archives expanded → file → magic-byte detection → LibreOffice → PDF → PyMuPDF → raw pixels → Pillow re-encode → clean PNG

**Text extraction pipeline** (`SCRUB_OUTPUT_MODE=text`): same input handling, but documents with a text layer are extracted directly to `.txt` instead of rasterized — skipping the OCR round-trip. Scanned PDFs and images fall back to PNG automatically.

## Requirements

- Docker Engine (from apt, not Snap)
- gVisor (`runsc`) — optional; provides kernel-level sandbox isolation (recommended for production)

## Setup

### 1. Install gVisor (recommended)

Follow the [gVisor installation docs](https://gvisor.dev/docs/user_guide/install/) to install `runsc` and register it with Docker.

One scrub-specific requirement when configuring the runtime in `daemon.json`:
- On bare metal with KVM available, use `runsc-kvm` (hardware virtualisation) rather than `runsc` (ptrace/systrap) — significantly faster for LibreOffice workloads.

Set `SCRUB_RUNTIME=runsc` (or `SCRUB_RUNTIME=runsc-kvm`) before running. Without it, the default `runc` runtime is used — useful for CI or machines without gVisor installed.

### 2. Build the image

```bash
docker compose build
```

## Running

### Prepare directories

```bash
mkdir -p data/source data/extracts data/clean data/errors data/logs
```

Place input files in `data/source/`. Source is mounted read-only — scrub never writes to it. ZIP, RAR, GZ, TAR.GZ, and TGZ archives are automatically expanded before processing — members are extracted into `data/extracts/` (mirroring the source subdirectory structure, scoped under the archive name). If the first member of an archive already exists in source, the archive is assumed already expanded and skipped.

### Start

```bash
# Default (runc — no gVisor):
docker compose up

# With gVisor (recommended for production):
SCRUB_RUNTIME=runsc docker compose up
```

### Output

| Directory | Contents |
|---|---|
| `data/source/` | Input files (read-only mount) |
| `data/extracts/` | Archive members extracted from source |
| `data/clean/` | Sanitized PNGs, subdirectory structure mirrored from source |
| `data/errors/` | JSON manifests for processing failures |
| `data/logs/` | Structured log file (`scrub.log`) |

Output filenames embed the original filename. In default PNG mode:

- `report.pdf` → `report.pdf.page_001.png`, `report.pdf.page_002.png`, …
- `budget.xlsx` → `budget.xlsx.sheet_001.png`, `budget.xlsx.sheet_002.png`, …
- `photo.png` → `photo.png.page_001.png`

In text mode (`SCRUB_OUTPUT_MODE=text`), documents with a text layer produce a single UTF-8 `.txt` file with pages separated by form-feed (`\f`). Documents without a text layer (scanned PDFs, images) still produce PNG:

- `report.pdf` → `report.pdf.txt` (text layer) or `report.pdf.page_001.png` (scanned)
- `budget.xlsx` → `budget.xlsx.txt`
- `photo.png` → `photo.png.page_001.png` (always PNG)

Files with existing clean output are skipped on re-runs — only new or previously unprocessed files are cleaned. With `SCRUB_SKIP_ERRORS=1`, files that already have an error manifest in `data/errors/` are also skipped.

### Error manifests

Files that fail processing have a JSON manifest written to `data/errors/` at the same relative path as the source file.

`error_type` values:

| Value | Meaning |
|---|---|
| `UnsupportedFormat` | Magic bytes don't match any supported format |
| `FileTooLarge` | Input exceeds `SCRUB_MAX_FILE_SIZE` (default 100 MB) |
| `LibreOfficeTimeout` | LibreOffice exceeded timeout (default 60s) |
| `LibreOfficeError` | LibreOffice non-zero exit |
| `PyMuPDFError` | PDF rasterisation failed |
| `EmptyDocument` | PDF produced zero pages |
| `ImageDecodeError` | Pillow couldn't decode the image |
| `PillowEncodeError` | Pillow couldn't re-encode to PNG |

## Tuning

Environment variables (set in shell before running, or edit `docker-compose.yml`):

| Variable | Default | Description |
|---|---|---|
| `SCRUB_RUNTIME` | `runc` | Docker runtime: `runc` (default) or `runsc`/`runsc-kvm` (gVisor) |
| `SCRUB_OUTPUT_MODE` | `png` | Output mode: `png` (rasterize) or `text` (extract text layer) |
| `SCRUB_WORKERS` | `ncpu*2-1` | Concurrent file workers |
| `SCRUB_TIMEOUT` | `60` | Per-file LibreOffice timeout (seconds) |
| `SCRUB_MAX_FILE_SIZE` | `100` | Per-file size limit (MB) |
| `SCRUB_MAX_ARCHIVE_MEMBERS` | `1000` | Max members extracted per archive |
| `SCRUB_MAX_ARCHIVE_TOTAL_MB` | `500` | Max total uncompressed size per archive (MB) |
| `SCRUB_SKIP_ERRORS` | `` | Set to `1`/`true`/`yes` to skip files with an existing error manifest |

```bash
SCRUB_RUNTIME=runsc SCRUB_WORKERS=4 SCRUB_TIMEOUT=120 docker compose up
```

## Verification

Smoke test — process a plain image and verify output lands in `data/clean/`:

```bash
cp tests/fixtures/eicar-adobe-acrobat-attachment.pdf data/source/
SCRUB_RUNTIME=runsc docker compose up --abort-on-container-exit
ls data/clean/
```

Verify gVisor is active:

```bash
# Should print "runsc" (or "runsc-kvm"), not "runc"
docker inspect scrub-scrub-1 --format '{{.HostConfig.Runtime}}'
```

## Architecture

```
┌───────────────────────────────────────────────────┐
│  scrub  [runtime: runsc-kvm]                      │
│  network_mode: none  |  read_only  |  cap_drop    │
│                                                   │
│  cli.py → archive.py (expand .zip/.rar)           │
│        → pipeline.py (per file)                   │
│    ├── already-clean / already-failed check (skip if exists)       │
│    ├── png mode (default)                         │
│    │     LibreOffice → PDF → PyMuPDF → Pillow     │
│    │     → clean PNG(s)                           │
│    └── text mode (SCRUB_OUTPUT_MODE=text)         │
│          PDF/office: PyMuPDF get_text()           │
│          → clean .txt  (or PNG fallback if        │
│            scanned / image input)                 │
└───────────────────────────────────────────────────┘
```

The `scrub` container has no network interface (`network_mode: none`). The gVisor sandbox means a LibreOffice or PyMuPDF exploit cannot reach the host kernel.
