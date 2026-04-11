# scrub

CDR (Content Disarm and Reconstruction) tool. Converts PDF, office documents and images to sanitized PNGs by re-encoding through a pixel-level pipeline. Every input is assumed adversarially crafted. Applies some TLC to your infected files telling malware:

So no, I don't want your number
No, I don't want to give you mine and
No, I don't want to meet you nowhere
No, I don't want none of your time

**Supported formats:** PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, CSV, PNG, JPG, TIFF, BMP, GIF, ZIP, RAR, GZ, TAR.GZ, TGZ

**Pipeline:** archives expanded → file → magic-byte detection → LibreOffice → PDF → PyMuPDF → raw pixels → Pillow re-encode → clean PNG

## Requirements

- Docker Engine (from apt, not Snap)
- gVisor (`runsc`) — provides kernel-level sandbox isolation

## Setup

### 1. Install gVisor

Follow the [gVisor installation docs](https://gvisor.dev/docs/user_guide/install/) to install `runsc` and register it with Docker.

One scrub-specific requirement when configuring the runtime in `daemon.json`:
- On bare metal with KVM available, use `runsc-kvm` (hardware virtualisation) rather than `runsc` (ptrace/systrap) — significantly faster for LibreOffice workloads. Change the `runtime:` line in `docker-compose.yml` if KVM isn't available.

### 2. Build the image

`docker-compose.yml` is the base config (volumes, caps, network isolation). `docker-compose.runsc.yml` overlays the gVisor runtime — omit it to run under the default `runc` (useful for CI or machines without gVisor installed).

```bash
docker compose -f docker-compose.yml -f docker-compose.runsc.yml build
```

## Running

### Prepare directories

```bash
mkdir -p data/source data/extracts data/clean data/errors data/logs
```

Place input files in `data/source/`. Source is mounted read-only — scrub never writes to it. ZIP, RAR, GZ, TAR.GZ, and TGZ archives are automatically expanded before processing — members are extracted into `data/extracts/` (mirroring the source subdirectory structure, scoped under the archive name). If the first member of an archive already exists in source, the archive is assumed already expanded and skipped.

### Start

```bash
docker compose -f docker-compose.yml -f docker-compose.runsc.yml up
```

### Output

| Directory | Contents |
|---|---|
| `data/source/` | Input files (read-only mount) |
| `data/extracts/` | Archive members extracted from source |
| `data/clean/` | Sanitized PNGs, subdirectory structure mirrored from source |
| `data/errors/` | JSON manifests for processing failures |
| `data/logs/` | Structured log file (`scrub.log`) |

Each input file produces one PNG per page (documents) or one PNG (images). Output filenames embed the original filename:

- `report.pdf` → `report.pdf.page_001.png`, `report.pdf.page_002.png`, …
- `budget.xlsx` → `budget.xlsx.sheet_001.png`, `budget.xlsx.sheet_002.png`, …
- `photo.png` → `photo.png.page_001.png`

Files with existing clean output are skipped on re-runs — only new or previously unprocessed files are cleaned.

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
| `SCRUB_WORKERS` | `ncpu*2-1` | Concurrent file workers |
| `SCRUB_TIMEOUT` | `60` | Per-file LibreOffice timeout (seconds) |
| `SCRUB_MAX_FILE_SIZE` | `100` | Per-file size limit (MB) |
| `SCRUB_MAX_ARCHIVE_MEMBERS` | `1000` | Max members extracted per archive |
| `SCRUB_MAX_ARCHIVE_TOTAL_MB` | `500` | Max total uncompressed size per archive (MB) |

```bash
SCRUB_WORKERS=4 SCRUB_TIMEOUT=120 docker compose -f docker-compose.yml -f docker-compose.runsc.yml up
```

## Verification

Smoke test — process a plain image and verify output lands in `data/clean/`:

```bash
cp tests/fixtures/eicar-adobe-acrobat-attachment.pdf data/source/
docker compose -f docker-compose.yml -f docker-compose.runsc.yml up --abort-on-container-exit
ls data/clean/
```

Verify gVisor is active:

```bash
# Should print "runsc" not "runc"
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
│    ├── already-clean check (skip if exists)       │
│    ├── LibreOffice (subprocess, per file)         │
│    ├── PyMuPDF (rasterise PDF)                    │
│    └── Pillow (pixel re-encode → PNG)             │
└───────────────────────────────────────────────────┘
```

The `scrub` container has no network interface (`network_mode: none`). The gVisor sandbox means a LibreOffice or PyMuPDF exploit cannot reach the host kernel.
