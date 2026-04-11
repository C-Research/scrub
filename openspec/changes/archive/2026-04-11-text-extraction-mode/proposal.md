## Why

Scrub currently rasterizes all documents to PNG regardless of whether they contain extractable text, forcing users to run OCR on pixel output that was never needed. Documents with text layers can be extracted directly — producing smaller, higher-quality, machine-readable output without the rasterize→OCR round-trip.

## What Changes

- Add `SCRUB_OUTPUT_MODE` env var (`png` default, `text` opt-in)
- In `text` mode: office documents (DOCX/DOC/XLSX/XLS/PPTX/PPT) are converted to plain text via LibreOffice `--convert-to txt`
- In `text` mode: PDFs with a text layer are extracted via PyMuPDF `page.get_text()` directly, skipping LibreOffice
- In `text` mode: plain text formats (TXT, CSV) are passed through directly as decoded UTF-8 — no transformation needed
- In `text` mode: HTML/HTM files have tags stripped and `<script>`/`<style>` content excluded, producing clean indexable text
- In `text` mode: XML files have element text extracted via tree iteration (reusing existing logic), skipping WeasyPrint
- In `text` mode: scanned PDFs (no text layer) and pure images fall back to the existing rasterize-to-PNG path
- Text output is written as UTF-8 `.txt` to the clean directory
- CDR guarantees are preserved: plain text has no executable surface; the processing pipeline (LO, PyMuPDF) is unchanged
- Routing fix: text format check now respects `output_mode` (previously TXT/HTML/XML/CSV always went through WeasyPrint regardless of mode)

## Capabilities

### New Capabilities

- `text-extraction`: Direct text extraction from documents in text mode — LO txt conversion for office formats, PyMuPDF text extraction for PDFs, JSON output format, fallback detection for scanned/image-only sources

### Modified Capabilities

- `document-conversion`: Text mode adds an alternative output path; PNG mode behavior is unchanged
- `cli`: New `SCRUB_OUTPUT_MODE` env var documented alongside existing `SCRUB_WORKERS` and `SCRUB_TIMEOUT`

## Impact

- `scrub/pipeline.py`: Route to text extraction path when `SCRUB_OUTPUT_MODE=text`
- `scrub/converter.py`: Add LO txt conversion and PyMuPDF text extraction functions
- `scrub/fs.py`: Add JSON output writer alongside existing PNG writer
- `scrub/cli.py`: Read and validate `SCRUB_OUTPUT_MODE`
- No new dependencies (LO txt conversion and PyMuPDF text extraction are already available)
- Existing `png` mode behavior is completely unchanged
