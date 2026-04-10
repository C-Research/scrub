## Context

`archive.py` currently expands `.zip` and `.rar` archives before the file walk. `pipeline.py` routes files by magic bytes, with extension used only to disambiguate ZIP-based Office formats (`.docx`/`.xlsx`/`.pptx`) and OLE formats (`.doc`/`.xls`/`.ppt`). All supported formats have reliable magic byte signatures — CSV is the first exception.

## Goals / Non-Goals

**Goals:**
- Expand `.gz`, `.tar.gz`, and `.tgz` files in the archive pre-processing pass with the same safety limits as zip/rar
- Convert `.csv` files to PNGs via the existing LibreOffice → PDF → rasterize pipeline
- CSV output follows spreadsheet naming convention (`sheet_NNN.png`)

**Non-Goals:**
- `.bz2`, `.xz`, `.zst`, or other compression formats
- Nested GZ decompression (`.tar.gz` inside `.zip`, etc.) — same policy as existing nested archives: extract members, don't recurse into them
- CSV schema validation or content inspection beyond what LibreOffice's CDR conversion provides

## Decisions

### GZ: tarfile for .tar.gz/.tgz, gzip for plain .gz

**Chosen:** Python stdlib `tarfile` (with `mode="r:gz"`) for multi-member archives; `gzip.open()` for single-file `.gz`.

**Compound extension detection:** `Path("file.tar.gz").suffix == ".gz"` — the `.tar` is invisible to `suffix`. Detection uses `name.endswith(".tar.gz")` and `name.endswith(".tgz")` before the plain `.gz` fallback.

**Single `.gz` output path:** strip the `.gz` suffix — `report.pdf.gz` decompresses to `report.pdf` in the same directory. This is then picked up by the normal pipeline walk.

**Alternatives considered:**
- *`shutil.unpack_archive()`*: handles both cases but loses control over per-member size limits and path traversal checks. Rejected — safety guarantees are load-bearing.

### tarfile member safety: same checks as zip/rar

Path traversal, symlinks, per-member size, total bytes, member count — all enforced the same way as `_expand_zip`. `tarfile` exposes `TarInfo.issym()`, `TarInfo.name`, and `TarInfo.size`, giving equivalent introspection to `zipfile.ZipInfo`.

One difference: `tarfile` does not pre-report uncompressed sizes for streaming members (only for stored ones). `TarInfo.size` is populated for gzip-compressed tars. Enforcing `max_file_bytes` via `TarInfo.size` is sufficient.

### CSV: extension-only detection with LibreOffice conversion

**Why no magic bytes:** CSV is plain text with no header signature. Attempting heuristic detection (UTF-8 text + comma patterns) would be fragile and out of scope for a CDR tool. Extension-only is the correct policy.

**Detection flow change:** `detect_format()` currently returns `"unknown"` when no magic bytes match. A targeted fallback is added: if no magic matched AND `ext == ".csv"`, return `"csv"`. All other unknown-magic files still return `"unknown"` and are rejected.

**Conversion:** LibreOffice opens `.csv` natively via Calc with `--infilter="Text - txt - csv (StarCalc)"`. This forces the CSV import path rather than relying on extension-based auto-detect, which can behave differently across LibreOffice versions. Macro security level 4 is already set — this neutralizes CSV injection (DDE, `=CMD|...` formulas).

**Alternatives considered:**
- *Python csv + ReportLab/Pillow rendering*: full control but adds complexity and a rendering dependency. LibreOffice already in the image; consistency with the existing document path is better.
- *Treat CSV as plaintext via magic bytes*: no reliable signature exists.

### sheet_ prefix for CSV output

CSV goes through the LibreOffice Calc path (same as xlsx/xls). The `is_xlsx` flag in `process_file` controls `sheet_` vs `page_` naming. Extend the check to `fmt in ("xlsx", "xls", "csv")`.

## Risks / Trade-offs

- **`.csv.gz` files** → handled naturally: archive pass decompresses to `.csv`, pipeline pass converts it. No special casing needed.
- **LibreOffice CSV infilter string** → `"Text - txt - csv (StarCalc)"` is the documented LibreOffice filter name; if it varies across versions the conversion falls back to extension-based auto-detect (LibreOffice still opens the file, just without explicit filter). Mitigation: test on the pinned image version.
- **Malformed `.tar.gz`** → `tarfile.open()` raises on corrupt input; caught by the existing `except Exception` in `expand_archives()` and logged as `ARCHIVE_ERROR`.
- **Large single `.gz` with no size hint** → `gzip` doesn't report uncompressed size before reading. Enforce the limit by reading in chunks and aborting if the running total exceeds `max_file_bytes`.
