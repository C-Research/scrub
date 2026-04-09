## Why

Adversarial documents — PDF, Office formats, and images — require sanitization before any downstream use. By converting every file to plain PNG images, all active content (macros, scripts, embedded objects, exploit payloads) is stripped, leaving only the visual representation. This tool is designed for state-actor threat level where every input must be treated as weaponized.

## What Changes

- New Python CLI tool `scrub` that reads files from a mounted source directory and writes sanitized PNG images to a mounted clean directory
- Converts PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT via LibreOffice → PyMuPDF → Pillow pipeline
- Converts image inputs (PNG, JPG, TIFF, BMP, GIF) directly via Pillow re-encode (bypassing LibreOffice)
- Preserves source folder structure in output; each file becomes a subfolder of per-page/per-sheet PNGs
- Quarantines failures to a mounted quarantine directory as JSON manifests with SHA256 and full forensic context
- Runs entirely inside a single gVisor (runsc) Docker container on EC2 bare metal — no nested containers
- Scans all output PNGs with ClamAV (official `clamav/clamav` sidecar) before writing to clean directory; detections are quarantined

## Capabilities

### New Capabilities
- `document-conversion`: Convert office documents (PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT) to PNG images via LibreOffice headless → PyMuPDF → Pillow
- `image-sanitization`: Re-encode image inputs (PNG, JPG, TIFF, BMP, GIF) through Pillow from raw pixels, stripping all metadata
- `filesystem-io`: Async recursive directory walk of source folder, PNG write to clean directory, and quarantine manifest write; preserving folder structure via aiofiles
- `quarantine`: On any processing failure, write a JSON manifest to the quarantine directory with full forensic context (input path, SHA256, error details)
- `cli`: CLI entrypoint with configurable input/output buckets, worker count, timeout, memory limit, and log path
- `clamav-scan`: Post-conversion ClamAV scan of output PNGs via sidecar container before S3 upload; detections and scan errors quarantine the file

### Modified Capabilities

## Impact

- New standalone Python package with no existing codebase to modify
- Dependencies: `aiofiles`, `PyMuPDF`, `Pillow`, `LibreOffice` (system package in Docker image), `clamdscan` (CLI client in gVisor container)
- Deployment: two containers on EC2 — gVisor container (processing) + `clamav/clamav` sidecar (scanning); source, clean, and quarantine directories mounted from host
- gVisor container: no network egress; all I/O via mounted host volumes
- ClamAV sidecar: outbound network for `freshclam` signature updates only; communicates with gVisor container via Unix socket on shared volume
