## 1. Dependencies

- [x] 1.1 Add `weasyprint` and `defusedxml` to `pyproject.toml` dependencies
- [x] 1.2 Add weasyprint system packages to Dockerfile (Pango, fontconfig, cairo, gdk-pixbuf)
- [x] 1.3 Verify weasyprint renders a basic HTML document to PDF inside the Docker build

## 2. Text Renderer (converter.py)

- [x] 2.1 Add `_block_external_fetches(url)` url_fetcher that raises for any non-`data:` URL
- [x] 2.2 Add `_txt_to_html(text: str) -> str` — escapes and wraps in `<pre style="font-family:monospace">`
- [x] 2.3 Add `_csv_to_html(raw: bytes) -> str` — parses with `csv.reader`, HTML-escapes all cells, emits `<table>`
- [x] 2.4 Add `_xml_to_text(raw: bytes) -> str` — parses with `defusedxml`, calls `itertext()`, joins with newlines; falls back to raw decode on parse failure
- [x] 2.5 Add `text_to_pdf(raw: bytes, fmt: str) -> Path` — dispatches to the above helpers, calls weasyprint with `_block_external_fetches`, writes temp PDF, returns path (caller deletes)

## 3. Format Detection (pipeline.py)

- [x] 3.1 Add `_sniff_text_format(header: bytes, ext: str) -> str | None` — strips BOM, checks for `<?xml`, checks for HTML markers, falls back to extension for `txt`/`csv`; returns format string or `None`
- [x] 3.2 Integrate `_sniff_text_format` into `detect_format()` after magic byte check
- [x] 3.3 Add `.txt`, `.html`, `.htm`, `.xml` to `_SUPPORTED_EXTENSIONS`
- [x] 3.4 Add `_TEXT_FORMATS = {"txt", "html", "htm", "xml", "csv"}` set; remove `"csv"` from `_OFFICE_FORMATS`

## 4. Pipeline Routing (pipeline.py)

- [x] 4.1 Add `_process_text_document(raw, fmt, scan_dir, timeout)` — calls `text_to_pdf()`, then existing `rasterize_pdf()`, then re-encode loop (mirrors `_process_document` structure)
- [x] 4.2 Add routing branch in `process_file()`: `elif fmt in _TEXT_FORMATS: pages = await _process_text_document(...)`
- [x] 4.3 Ensure CSV `is_xlsx` flag is `False` and output uses `sheet_` naming via existing `fs.derive_output_paths` logic

## 5. Tests

- [x] 5.1 Add fixture files: `tests/fixtures/sample.txt`, `tests/fixtures/sample.html`, `tests/fixtures/sample.xml`, `tests/fixtures/sample.csv`
- [x] 5.2 Add `TestDetectFormat` cases for `.txt`, `.html`, `.htm`, `.xml`, BOM-prefixed XML and HTML, HTML content sniff overriding `.txt` extension
- [x] 5.3 Add unit tests for `_block_external_fetches` (raises on http URL, passes data URI)
- [x] 5.4 Add unit tests for `_csv_to_html` (formula injection escaping, HTML injection escaping)
- [x] 5.5 Add unit tests for `_xml_to_text` (text extraction, malformed XML fallback, XXE input)
- [x] 5.6 Add integration test: each of the four formats produces at least one valid PNG output
