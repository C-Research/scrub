## 1. GZ archive extraction (archive.py)

- [x] 1.1 Add `_expand_targz()` function: open with `tarfile.open(mode="r:gz")`, iterate members, apply path traversal check via `_safe_dest()`, skip symlinks (`info.issym()`), skip oversized members (`info.size > max_file_bytes`), enforce total bytes and member count limits, extract with `aiofiles`
- [x] 1.2 Add `_expand_gz()` function: decompress single file via `gzip.open()` reading in chunks, abort and discard if running total exceeds `max_file_bytes`, write output to archive path with `.gz` stripped using `aiofiles`
- [x] 1.3 Extend `expand_archives()` to collect `.gz`, `.tar.gz`, and `.tgz` files (use `name.endswith(".tar.gz")` and `name.endswith(".tgz")` before plain `.gz` fallback)
- [x] 1.4 Extend `expand_archives()` dispatch: route `.tar.gz`/`.tgz` to `_expand_targz()`, plain `.gz` to `_expand_gz()`

## 2. CSV pipeline support (pipeline.py)

- [x] 2.1 Add `.csv` to `_SUPPORTED_EXTENSIONS`
- [x] 2.2 Add `"csv"` to `_OFFICE_FORMATS`
- [x] 2.3 Add extension fallback in `detect_format()`: after the magic-byte loop, if no match and `ext == ".csv"` return `"csv"`
- [x] 2.4 Extend the `is_xlsx` check in `process_file()` to `fmt in ("xlsx", "xls", "csv")` so CSV output uses `sheet_` prefix

## 3. CSV LibreOffice infilter (converter.py)

- [x] 3.1 In `_lo_cmd()`, add `--infilter=Text - txt - csv (StarCalc)` when `fmt == "csv"`

## 4. README

- [x] 4.1 Add CSV, GZ, TAR.GZ, TGZ to the supported formats list

## 5. Verification

- [x] 5.1 Run `pytest` — confirm existing tests pass
- [ ] 5.2 Place a `.csv` file in `data/source/`, run pipeline, confirm `sheet_001.png` output
- [ ] 5.3 Place a `.tar.gz` archive containing a `.pdf` in `data/source/`, confirm members extracted and processed
- [ ] 5.4 Place a `report.pdf.gz` in `data/source/`, confirm `report.pdf` extracted and processed
