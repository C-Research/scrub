## Context

The archive-extraction change writes extracted members into `archive_path.parent` — directly inside the source directory. Source may be a read-only bind mount. Extraction must write elsewhere.

The pipeline currently walks only `_SOURCE`. With extraction going to a separate directory, the walk must cover both roots without changing per-file processing.

## Goals / Non-Goals

**Goals:**
- Redirect archive extraction from source into `/data/extracts`
- Mirror source structure in extracts, scoped under the archive stem
- Walk `extracts` as a second source root so extracted files reach the pipeline
- Add first-member sentinel check: if the first member exists in source, skip the archive

**Non-Goals:**
- Changing per-file processing logic
- Validating source for read-only access (operator responsibility)
- Supporting extraction into arbitrary user-configured paths

## Decisions

### Extraction target: `extracts_dir / rel_parent / archive_stem / member_path`

For an archive at `source/subdir/foo.zip` with member `docs/report.pdf`:
```
extracts/subdir/foo/docs/report.pdf
```
For a single-file `.gz` at `source/report.pdf.gz`:
```
extracts/report.pdf
```

*Why:* Scoping under the archive stem prevents member name collisions across archives in the same directory. Mirroring the source subdirectory makes the extracts tree auditable alongside source.

### `expand_archives` gains `extracts_dir` parameter; dest_dir computed by caller

`expand_archives` computes `dest_dir` for each archive:
```python
rel_parent = archive_path.relative_to(source_dir).parent
dest_dir = extracts_dir / rel_parent / _archive_stem(archive_path)
```
Each `_expand_*` function receives `dest_dir` rather than deriving it from `archive_path.parent`. `_safe_dest` is unchanged — it already takes `dest_dir` as its root.

*Why:* The extraction functions have no business knowing the directory layout policy. Computing `dest_dir` once in the caller and passing it in keeps the functions focused on format-specific logic.

### `_archive_stem` helper for multi-part extensions

A helper strips `.tar.gz` and `.tgz` as full suffixes before falling back to `Path.stem`:
```python
def _archive_stem(p: Path) -> str:
    name = p.name
    if name.endswith(".tar.gz"):
        return name[:-7]
    if name.endswith(".tgz"):
        return name[:-4]
    return p.stem
```

*Why:* `Path("foo.tar.gz").stem` gives `foo.tar`, not `foo`. The helper is a one-liner factored out to avoid repeating the suffix logic.

### First-member sentinel dedup check

Before extracting any member, peek at the first member's relative path and check `source_dir / first_member_rel_path`. If it exists, skip the entire archive with an `ARCHIVE_SKIP` log.

*Why:* Operators migrating from the old in-place extraction will have extracted members already sitting in source. Checking the first member is O(1) and avoids redundant extraction of archives that were already expanded. It also handles the common case of re-running scrub after a partial run where some archives were extracted to source by hand.

### Separate walk over `extracts`

`cli._run()` enqueues two walks: one over `_SOURCE`, one over `_EXTRACTS` (if the directory has content). `_bounded` gains a `source_dir` parameter so each file is resolved against its own root.

*Why:* The simplest approach that reuses all existing per-file processing. A unified walk helper would be marginally cleaner but adds indirection for no gain.

## Risks / Trade-offs

**Extracts not cleaned between runs** → If an archive is removed from source but its extracts remain, those files will be reprocessed on the next run. Mitigation: operator responsibility; scrub does not manage extracts lifecycle. Document clearly.

**First-member sentinel is a heuristic** → If the first member happens to exist in source for an unrelated reason, the archive is silently skipped. Mitigation: logged as `ARCHIVE_SKIP` with reason, so operators can audit.

**Two-root walk duplicates files if source and extracts overlap** → Possible if an operator manually copies extracted files to both. Mitigation: dedup is operator responsibility; scrub processes what it finds.
