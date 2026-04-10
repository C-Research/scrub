## Why

Source files increasingly arrive as gzip-compressed archives (`.gz`, `.tar.gz`, `.tgz`) and plaintext CSV data exports, neither of which scrub currently handles. Expanding GZ support removes a gap in the archive pre-processing pass; adding CSV conversion closes a common data-pipeline format.

## What Changes

- Add `.gz` (single-file decompress), `.tar.gz`, and `.tgz` (multi-file tar extraction) to the archive pre-processing pass in `archive.py`, with the same size/count limits as zip/rar
- Add `.csv` as a supported input format: detected by extension (no reliable magic bytes), converted via LibreOffice Calc → PDF → rasterize, output named `sheet_NNN.png`
- Case-insensitive extension handling is already implemented — no change needed

## Capabilities

### New Capabilities

- `csv-conversion`: CSV files converted to PNGs via the LibreOffice document path, with extension-based format detection and `sheet_` output naming

### Modified Capabilities

- `archive-extraction`: extend pre-processing pass to support `.gz`, `.tar.gz`, and `.tgz` formats alongside existing `.zip` and `.rar`

## Impact

- **`scrub/archive.py`**: add `_expand_targz()` and `_expand_gz()` handlers; extend `expand_archives()` dispatch
- **`scrub/pipeline.py`**: add `.csv` to `_SUPPORTED_EXTENSIONS` and `_OFFICE_FORMATS`; add extension fallback in `detect_format()` for CSV; extend `is_xlsx` check to include `csv` for `sheet_` output naming
- **`scrub/converter.py`**: add `--infilter` for CSV in `_lo_cmd()`
- **No new dependencies**: `tarfile` and `gzip` are Python stdlib
- **README**: update supported formats list
