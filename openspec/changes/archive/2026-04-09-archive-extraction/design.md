## Context

The pipeline currently walks the source directory and processes each file individually. Archives (`.zip`, `.rar`) are silently skipped because their extensions are not in `_SUPPORTED_EXTENSIONS`. Files inside those archives never reach the sanitization pipeline.

The source-read-only constraint in the existing filesystem-io spec is relaxed for this change: we write extracted members into the source directory before the walk begins. The existing pipeline then processes those files normally — no changes to the per-file processing path.

## Goals / Non-Goals

**Goals:**
- Extract `.zip` and `.rar` archives into the source directory before `walk_source` runs
- Skip members whose destination path already exists (dedup)
- Enforce path traversal and zip-bomb safety with configurable limits
- Make `_MAX_SIZE` overridable via env var alongside the new archive limits

**Non-Goals:**
- Recursive archive expansion (a zip inside a zip is extracted but not further expanded)
- Magic-byte-based archive detection (extension only: `.zip`, `.rar`)
- Modifying the per-file processing pipeline in any way
- Supporting other archive formats (tar, 7z, etc.)

## Decisions

### New `scrub/archive.py` module
The expansion logic lives in its own module rather than inside `fs.py` or `cli.py`. It has a single public function `expand_archives(source_dir, limits)`.

*Why:* `fs.py` owns async I/O; archive extraction is synchronous CPU-bound work with its own security concerns. Keeping it separate makes both modules easier to reason about and test.

### Called from `cli._run()`, synchronously before `walk_source`
`expand_archives` is called once after directory validation and ClamAV startup, before the async walk begins. It runs synchronously (blocking) in the main thread.

*Why:* The walk must see the extracted files. Running it before the walk is the simplest ordering guarantee. Since it's a one-time pre-processing pass (not per-file), blocking the event loop briefly is acceptable.

### Extension-only archive detection
Only `.zip` and `.rar` extensions trigger extraction. No magic byte check.

*Why:* Magic bytes are for adversarial-format detection on untrusted inputs entering the sanitization pipeline. Archive extraction is a pre-processing pass on operator-supplied files that were put in the source directory intentionally. Extension is the right signal here.

### Office ZIP disambiguation by extension
`.docx`, `.xlsx`, `.pptx` share the ZIP magic and a `.zip` extension is never an Office format. Extension check is sufficient: skip anything in `{".docx", ".xlsx", ".pptx"}`.

### One-level expansion, no recursion
Archives found by an initial `rglob` are collected into a list before any extraction begins. Extracted files are not re-scanned.

*Why:* Bounding expansion to one level is a simple, auditable safety property. A zip-inside-a-zip ends up as an unprocessed `.zip` in source_dir after extraction, which is then skipped by the pipeline — acceptable and logged.

### Configurable limits via env vars, shared with pipeline
`SCRUB_MAX_FILE_SIZE` (default 100 MB) replaces the hardcoded `_MAX_SIZE` in `pipeline.py` and also serves as the per-member size cap in archive extraction. Two additional archive-specific env vars control member count and total uncompressed bytes.

*Why:* Operators in different environments (testing vs. production) need to tune limits without rebuilding the image. Sharing `SCRUB_MAX_FILE_SIZE` between pipeline and archive extraction avoids a member being extracted but then immediately rejected by the pipeline size check.

### `rarfile.UNRAR_TOOL = "/usr/bin/unrar"` set explicitly
Hardcoded to the apt-installed path rather than relying on PATH lookup.

*Why:* The gVisor container has a minimal filesystem. Explicit path is more reliable and auditable in a security-sensitive context.

## Risks / Trade-offs

**Source directory mutation** → Operators who expect source to be untouched will see extracted files appear. Mitigated by: logging every extraction, clear documentation that archives are expanded in-place.

**Extraction before ClamAV** → Archive members are written to source_dir before scanning. They will be scanned as part of normal per-file processing. The risk is that extracted malware sits on disk briefly before the pipeline reaches it. Mitigated by: this is the same risk as any source file already in the directory; the gVisor sandbox limits what a file can do on disk.

**`unrar` binary dependency** → RAR extraction requires an external binary not under our control. Mitigated by: pinned to the Debian `unrar` apt package; if the binary is missing, `rarfile` raises a clear error that is caught and logged.

**Dedup by path only** → If a file with the same name but different content exists at the destination, it is treated as already-extracted and skipped. This is intentional (operator placed the file there), but could silently leave stale content if an archive is updated.

## Open Questions

- Should extracted archives themselves be deleted from source_dir after expansion, or left in place? Currently they remain and are logged as SKIPPED by the pipeline.
