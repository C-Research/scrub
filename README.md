# scrub

CDR (Content Disarm and Reconstruction) tool. Converts PDF, office documents and images to sanitized PNGs by re-encoding through a pixel-level pipeline. Every input is assumed adversarially crafted. Output PNGs are scanned with ClamAV just to make sure everything is clean. Applies some TLC to your infected files telling malware:

So no, I don't want your number
No, I don't want to give you mine and
No, I don't want to meet you nowhere
No, I don't want none of your time

**Supported formats:** PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, CSV, PNG, JPG, TIFF, BMP, GIF, ZIP, RAR, GZ, TAR.GZ, TGZ

**Pipeline:** archives expanded → file → magic-byte detection → LibreOffice → PDF → PyMuPDF → raw pixels → Pillow re-encode → ClamAV scan → clean PNG

## Requirements

- Docker Engine (from apt, not Snap)
- gVisor (`runsc`) — provides kernel-level sandbox isolation

## Setup

### 1. Install gVisor

Follow the [gVisor installation docs](https://gvisor.dev/docs/user_guide/install/) to install `runsc` and register it with Docker.

Two scrub-specific requirements when configuring the runtime in `daemon.json`:
- `--host-uds=open` is required. The ClamAV socket directory must be a **bind mount** (not a named Docker volume) — see `docker-compose.yml`. gVisor's gofer proxy resolves host paths for bind mounts, which is what lets `--host-uds=open` forward the `connect()` syscall to the real host-side socket. Named volumes go through a different gofer code path that doesn't support the `ConnectAt` RPC, so the socket file is visible inside the sandbox but connections fail.
- On bare metal with KVM available, use `runsc-kvm` (hardware virtualisation) rather than `runsc` (ptrace/systrap) — significantly faster for LibreOffice workloads. Change the `runtime:` line in `docker-compose.yml` if KVM isn't available.

### 2. Build the image

```bash
docker compose build
```

ClamAV signature download happens at first run, not at build time.

## Running

### Prepare directories

```bash
mkdir -p data/source data/clean data/quarantine data/logs data/clamav-socket
chmod 1777 data/clamav-socket
```

The `chmod 1777` on `data/clamav-socket` is required: the ClamAV container runs as UID 100 (clamav user) and needs write access to create the socket file. The sticky bit prevents other processes from deleting the socket.

Place input files in `data/source/`. Subdirectory structure is preserved in output. ZIP and RAR archives are automatically expanded before processing — members are extracted alongside the archive in the source directory.

### Start

```bash
docker compose up
```

On first run, the ClamAV sidecar downloads virus signatures (~300 MB) before `scrub` starts processing. This takes 1–3 minutes. Subsequent runs use the cached `clamav-sigs` volume and start in seconds.

`scrub` waits for ClamAV to be healthy before processing any files (`depends_on: condition: service_healthy`).

### Output

| Directory | Contents |
|---|---|
| `data/clean/` | Sanitized PNGs, subdirectory structure mirrored from source |
| `data/quarantine/` | JSON manifests for rejected files |
| `data/logs/` | Structured log file (`scrub.log`) |

Each input file produces one PNG per page (documents) or one PNG (images). Output filenames embed the original filename:

- `report.pdf` → `report.pdf.page_001.png`, `report.pdf.page_002.png`, …
- `budget.xlsx` → `budget.xlsx.sheet_001.png`, `budget.xlsx.sheet_002.png`, …
- `photo.png` → `photo.png.page_001.png`

Files with existing clean output are skipped on re-runs — only new or previously unprocessed files are cleaned.

### Quarantine manifests

Files that cannot be safely converted are quarantined — never written to the clean directory. A JSON manifest is written to `data/quarantine/` at the same relative path as the source file:

```json
{
  "input_path": "invoices/q1.xlsx",
  "format_detected": "xlsx",
  "error_type": "ClamAVDetection",
  "error_detail": "Virus detected",
  "virus_name": "Win.Exploit.CVE-2024-1234",
  "scanned_file": "page_001.png",
  "file_size_bytes": 204800,
  "sha256": "a3f2...",
  "timestamp": "2026-04-09T14:23:01Z"
}
```

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
| `ClamAVDetection` | ClamAV found a threat |
| `ClamAVError` | ClamAV scan failed (treated as detection) |

## Tuning

Environment variables (set in shell before `docker compose up`, or edit `docker-compose.yml`):

| Variable | Default | Description |
|---|---|---|
| `SCRUB_WORKERS` | `ncpu*2-1` | Concurrent file workers |
| `SCRUB_TIMEOUT` | `60` | Per-file LibreOffice timeout (seconds) |
| `SCRUB_MAX_FILE_SIZE` | `100` | Per-file size limit (MB) |
| `SCRUB_MAX_ARCHIVE_MEMBERS` | `1000` | Max members extracted per archive |
| `SCRUB_MAX_ARCHIVE_TOTAL_MB` | `500` | Max total uncompressed size per archive (MB) |

```bash
SCRUB_WORKERS=4 SCRUB_TIMEOUT=120 docker compose up
```

## Verification

Smoke test with an EICAR test file (detects as virus, should produce a quarantine manifest, not crash):

```bash
# Download a benign EICAR Word macro test doc
cp eicar-standard-antivirus-test-files/eicar-word-macro-cmd-echo.doc data/source/
docker compose up --abort-on-container-exit
cat data/quarantine/eicar-word-macro-cmd-echo.doc.json
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
│    ├── Pillow (pixel re-encode → PNG)             │
│    └── clamdscan --stream (scan before write)     │
│                    │                              │
└────────────────────┼──────────────────────────────┘
                     │ Unix socket
              /run/clamav/clamd.sock
         (shared Docker volume: clamav-socket)
                     │
┌────────────────────┼─────────────────────────────┐
│  clamav  [runtime: runc]                         │
│  clamd + freshclam                               │
└──────────────────────────────────────────────────┘
```

The `scrub` container has no network interface (`network_mode: none`). ClamAV communication is entirely via Unix socket on a shared volume. The gVisor sandbox means a LibreOffice or PyMuPDF exploit cannot reach the host kernel.
