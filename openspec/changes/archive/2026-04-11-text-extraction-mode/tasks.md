## 1. Env var and mode wiring

- [x] 1.1 Add `SCRUB_OUTPUT_MODE` parsing to `cli.py` alongside existing `_env_int` helpers — accept `png`/`text`, exit 1 on unknown value
- [x] 1.2 Thread `output_mode` through to `process_file` in `pipeline.py` (pass as a parameter, not a global)

## 2. Text extraction in converter.py

- [x] 2.1 Add `extract_text_from_pdf(pdf_path: Path) -> list[str]` to `converter.py` using PyMuPDF `page.get_text()` — returns one string per page
- [x] 2.2 Add scanned detection logic: count total non-whitespace chars across all pages; return `None` (signals fallback to PNG) if below 50
- [x] 2.3 Add `is_spreadsheet_fmt(fmt: str) -> bool` helper to distinguish page vs sheet structure in TXT output

## 3. TXT output in fs.py

- [x] 3.1 Rename `write_json` → `write_txt(out_path, text: str)` async function in `fs.py` (UTF-8 plain text)
- [x] 3.2 Rename `derive_json_output_path` → `derive_txt_output_path` in `fs.py` — returns `<rel_path>.txt`

## 4. Pipeline routing for text mode

- [x] 4.1 In `pipeline.py`, add `_process_document_text` async function: calls existing `convert_to_pdf` → `extract_text_from_pdf`; returns `list[str]` or raises `ConversionError`
- [x] 4.2 In `pipeline.py`, add `_process_pdf_text` async function: calls `extract_text_from_pdf` directly (no LO); returns `list[str]` or `None` (scanned fallback)
- [x] 4.3 In `process_file`, branch on `output_mode`: text mode routes documents/PDFs to new text functions; images always take rasterize path; scanned PDFs fall back to rasterize path
- [x] 4.4 Join extracted pages with `\f` separator and write via `fs.write_txt`

## 5. Already-clean sentinel update

- [x] 5.1 Update the `already_clean` check in `pipeline.py` to detect `.txt` output in text mode (look for `<rel_path>.txt` in clean dir) — already done using `derive_txt_output_path`

## 6. Tests

- [x] 6.1 Unit test `extract_text_from_pdf` with a known text-layer PDF fixture — assert per-page strings returned
- [x] 6.2 Unit test scanned detection — fixture with no text layer should return `None`
- [x] 6.3 Integration test: DOCX in text mode produces `.txt` (skip if LO unavailable)
- [x] 6.4 Integration test: XLSX in text mode produces `.txt` (skip if LO unavailable)
- [x] 6.5 Integration test: image (JPG) in text mode produces `.png` fallback
- [x] 6.6 Test `SCRUB_OUTPUT_MODE=invalid` exits with code 1
- [x] 6.7 Test `SCRUB_OUTPUT_MODE` unset defaults to PNG mode (existing tests continue to pass)

## 7. Text format coverage in text mode

- [x] 7.1 Restructure routing in `pipeline.py`: check `output_mode == "text"` before `fmt in _TEXT_FORMATS` so text mode applies to all non-image formats
- [x] 7.2 Add `extract_plain_text(raw: bytes, fmt: str) -> str` to `converter.py`: passthrough decode for `txt`/`csv`; HTMLParser tag-strip with script/style suppression for `html`/`htm`; itertext extraction for `xml`
- [x] 7.3 Wire `extract_plain_text` into the text mode `_TEXT_FORMATS` branch in `pipeline.py`, writing output via `fs.write_txt`
- [x] 7.4 Test: TXT file in text mode produces `.txt` passthrough (content preserved)
- [x] 7.5 Test: CSV file in text mode produces `.txt` passthrough (content preserved)
- [x] 7.6 Test: HTML file in text mode produces `.txt` with tags stripped and `<script>`/`<style>` bodies excluded
- [x] 7.7 Test: XML file in text mode produces `.txt` with element text extracted
- [x] 7.8 Test: HTML/TXT/CSV/XML files in PNG mode still produce PNG output via WeasyPrint (regression)
