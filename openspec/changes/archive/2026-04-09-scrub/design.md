## Context

`scrub` is a greenfield CDR (Content Disarm and Reconstruction) tool built for state-actor threat level. Every input file is assumed to be adversarially crafted. The tool runs as a single gVisor-sandboxed Docker container on EC2, reads files from a host-mounted source directory, converts them to sanitized PNG images, and writes clean output and quarantine manifests to separate host-mounted directories. There is no existing codebase.

Key constraint: the gVisor runtime is the primary isolation boundary. LibreOffice runs as a subprocess within the same container — there are no nested containers. This means LibreOffice process isolation relies on OS-level resource limits and timeouts rather than container boundaries.

## Goals / Non-Goals

**Goals:**
- Sanitize office documents and images by converting to PNG via a pixel-level re-encode
- Support PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT, PNG, JPG, TIFF, BMP, GIF
- Preserve source folder structure in clean output directory
- Quarantine failures with forensic manifests (input path, SHA256, error details)
- Async I/O throughout (aiofiles)
- Concurrency capped at `ncpu*2-1` concurrent file workers

**Non-Goals:**
- OCR or text extraction
- Document fidelity beyond visual representation
- Real-time/streaming processing
- Support for formats beyond the listed set
- Output formats other than PNG

## Decisions

### D1: Single gVisor container (no per-file Docker containers)

**Decision**: Run the orchestrator and LibreOffice in the same gVisor container. Spawn LibreOffice as subprocesses per file.

**Alternatives considered**:
- *Per-file Docker containers*: Maximum isolation but requires Docker-in-gVisor which is complex and slow. Adds 300-500ms overhead per file.
- *Single container, no gVisor*: Insufficient for threat level. A LibreOffice RCE could escape to the host kernel.

**Rationale**: gVisor's kernel interposition protects the host regardless of whether LibreOffice is in a sub-container. Per-file subprocess isolation with ulimits + timeouts is sufficient within gVisor. Simpler deployment, faster per-file processing.

---

### D2: LibreOffice → PDF → PyMuPDF pipeline for office formats

**Decision**: Convert DOCX/DOC/XLSX/XLS/PPTX/PPT to PDF via LibreOffice headless, then rasterize with PyMuPDF.

**Alternatives considered**:
- *python-docx + manual rendering*: Incomplete, poor fidelity for complex documents.
- *PyMuPDF direct for DOCX*: PyMuPDF can open DOCX but quality is worse than LO.
- *WeasyPrint / other*: HTML-intermediate path, loses fidelity and adds attack surface.

**Rationale**: LibreOffice is the gold standard for Office format rendering. PyMuPDF is fast and has a minimal attack surface for the PDF-to-pixels step.

---

### D3: Pillow re-encode from raw pixels (not file copy)

**Decision**: Never pass container-produced image bytes directly to S3. Always: PyMuPDF pixmap → raw RGB bytes → Pillow `Image.frombuffer()` → `Image.save()` clean PNG.

**Alternatives considered**:
- *Pass PyMuPDF PNG bytes directly*: Fast but a crafted document could produce a weaponized PNG that exploits downstream image viewers.

**Rationale**: Re-encoding from pixel data is the CDR guarantee. The output PNG is constructed from scratch, not passed through. This is non-negotiable at state-actor level.

---

### D4: Fresh LibreOffice user profile per subprocess invocation

**Decision**: Each LibreOffice subprocess gets a fresh `--user-installation` pointing to a `mkdtemp()` directory, cleaned up after the subprocess exits.

**Alternatives considered**:
- *Shared profile*: A sophisticated exploit could poison the LO profile on file N and activate on file N+1.

**Rationale**: Profile poisoning is a real cross-file attack vector. Per-invocation profiles eliminate it at the cost of ~50ms startup overhead.

---

### D5: XLSX sheet-per-page via LibreOffice export filter options

**Decision**: Use LO's `--infilter` with `Calc MS Excel 2007 XML` and export options to scale each sheet to fit exactly one page (`PageScale=1` + `FitWidth=1` + `FitHeight=1`).

**Alternatives considered**:
- *Default LO PDF export*: Paginates based on print area, not sheet boundaries. A sheet wider than one page would produce multiple pages, breaking the "one image per sheet" contract.
- *openpyxl + custom render*: Incomplete rendering, not CDR-safe.

**Rationale**: LO export filter options give exact control over sheet-to-page mapping without macros.

---

### D6: aiofiles for all filesystem I/O

**Decision**: Use `aiofiles` for reading source files and writing output PNGs and quarantine manifests. Directory walking uses `os.scandir` wrapped in `run_in_executor`.

**Alternatives considered**:
- *Synchronous file I/O*: Blocks the event loop during reads/writes; unacceptable with `ncpu*2-1` concurrent workers.
- *asyncio streams*: Lower-level than needed; aiofiles wraps standard file operations cleanly.

**Rationale**: aiofiles keeps all I/O non-blocking. Source, clean, and quarantine directories are host paths mounted into the container — no network I/O required, no external dependencies beyond the standard Python ecosystem.

---

### D8: ClamAV sidecar via Unix socket on shared volume

**Decision**: Run the official `clamav/clamav` Docker image as a sidecar container. The gVisor container communicates with it via a Unix socket on a shared Docker volume. ClamAV scans each output PNG before it is uploaded to S3. Any detection or scan error quarantines the file (security-first; no whitelisting).

**Alternatives considered**:
- *ClamAV inside the gVisor container*: Simpler deployment but conflates conversion and scanning concerns; larger image; ClamAV signature updates require rebuilding the gVisor image.
- *TCP between containers on docker network*: Requires the gVisor container to have a network interface. Unix socket over shared volume works with `--network none` on the gVisor container.
- *clamscan per file*: Loads the ~300MB signature DB on every invocation (~1-2s overhead). With `ncpu*2-1` workers all scanning concurrently, a persistent `clamd` daemon is significantly faster.
- *Post-write filesystem scan*: Scans after writing to clean directory, meaning a detection requires deleting already-written files. Pre-write is strictly safer and simpler.

**Rationale**: Sidecar separation allows independent image updates and freshclam scheduling. The gVisor container retains `--network none`. Unix socket communication requires no network interface on the gVisor container. `clamd` daemon keeps signatures in memory, handling concurrent scan requests efficiently. Security-first means `ClamAVError` (daemon unavailable, socket timeout) also quarantines — a scan that cannot complete is treated as a detection.

---

### D7: SHA256 computed on raw input bytes before conversion

**Decision**: Hash the input file bytes immediately after download, before any processing. Store in quarantine manifest and log.

**Rationale**: Allows correlation against threat intel feeds. Hash must be of the original, not any intermediate form.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| LibreOffice CVE exploitation within gVisor | gVisor kernel interposition; per-process ulimits; timeout kills hung processes |
| Pillow CVE on image inputs (TIFF, BMP especially) | Images go directly to Pillow without LO; Pillow runs in-process — consider wrapping in subprocess with resource limits if threat model demands |
| LO hangs on malformed XLSX (infinite loop in parser) | `asyncio.wait_for` with configurable timeout (default 60s); SIGKILL on timeout |
| Zip bomb / decompression bomb (DOCX/XLSX are ZIP) | Pre-flight file size check before download; LO memory limit via ulimit |
| gVisor systrap mode on non-metal EC2 | ~2x slower; acceptable for throughput. Recommend bare metal for production |
| LibreOffice profile dir not cleaned up on crash | Use `try/finally` around subprocess; temp dir cleanup always runs |
| Large spreadsheet → many PDF pages → many PNGs | No per-document page cap currently; acceptable given one-image-per-sheet contract |
| Host volume permissions prevent writes to clean/quarantine dirs | Validate write access to all three directories at startup before processing any files |
| ClamAV daemon not ready at startup | Orchestrator polls clamd socket with backoff before starting workers; fail fast if daemon never responds |
| ClamAV false positive on clean PNG | Security-first: quarantine the file; no whitelisting. Acceptable false positive rate is low for re-encoded PNGs |
| freshclam blocked / signatures stale | ClamAV sidecar has outbound network; monitor freshclam logs; alert on signature age |
| Unix socket permission mismatch between containers | Run both containers with same GID for socket access; configure in docker-compose |

## Migration Plan

1. Build and push scrub Docker image with gVisor runtime configured
2. Launch EC2 instance with gVisor and Docker installed; prepare host directories: `source/`, `clean/`, `quarantine/`, `logs/`
3. Create named Docker volume `clamav-socket` for Unix socket; create named volume `clamav-sigs` for signature persistence
4. Start ClamAV sidecar: `docker run -d --name clamav -v clamav-socket:/run/clamav -v clamav-sigs:/var/lib/clamav clamav/clamav`
5. Run scrub container via docker-compose, mounting host directories read/write:
   ```
   -v /host/source:/data/source:ro
   -v /host/clean:/data/clean
   -v /host/quarantine:/data/quarantine
   -v /host/logs:/var/log/scrub
   -v clamav-socket:/run/clamav:ro
   ```

Rollback: container is stateless; stop the container. Source directory is read-only mount; no input data is modified.

A `docker-compose.yml` documents the full service definition including shared volumes and GID alignment.

Rollback: container is stateless; simply stop the container. Input S3 bucket is read-only; no input data is modified.

## Open Questions

- Should image inputs (PNG/JPG/TIFF/BMP/GIF) also be wrapped in a subprocess with resource limits, or is in-process Pillow acceptable? Currently in-process for simplicity, but a crafted TIFF could exploit Pillow.
- Should there be a per-document page count cap (e.g., refuse documents claiming >1000 pages)?
- What DPI for rasterization? 150dpi is screen-readable; 300dpi is print-quality. Affects output file size and processing time significantly.
