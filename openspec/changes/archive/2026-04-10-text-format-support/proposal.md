## Why

LibreOffice is a network-capable process: HTML files with embedded external references (`<img src>`, stylesheets) can trigger outbound fetches during conversion, leaking the existence of the file to an attacker and causing timeouts when the container's network is isolated. Text-based formats (TXT, HTML, XML, CSV) don't need the full LO stack — a Python-only renderer gives deterministic output with zero network risk.

## What Changes

- Add support for four new input formats: `.txt`, `.html`/`.htm`, `.xml`, `.csv` (CSV already supported via LO — this moves it)
- Introduce a Python-only text rendering engine (weasyprint) for all four formats
- CSV moves out of LibreOffice entirely; all external fetch risk is eliminated for text-based formats
- XML processing extracts text nodes only (`itertext()`), ignoring tags and structure — output is plain readable text, not a visual XML render
- HTML is rendered by weasyprint with all external URL fetches blocked at the application level (not just network level)
- All four formats produce PDF → existing `rasterize_pdf()` path unchanged
- Content sniffing added for `.html`/`.htm` and `.xml` (TXT and CSV remain extension-only)

## Capabilities

### New Capabilities
- `text-format-rendering`: Python-only rendering engine (weasyprint) that converts TXT, HTML, XML, and CSV to PDF for rasterization; blocks all external resource fetches
- `text-format-detection`: Content sniffing for HTML and XML; extension-based detection for TXT and CSV; BOM-tolerant; falls back to plain-text treatment on parse failure

### Modified Capabilities
- `csv-conversion`: CSV moves from the LibreOffice document path to the new weasyprint text rendering path; LibreOffice infilter no longer used

## Impact

- **`scrub/pipeline.py`**: New `_TEXT_FORMATS` set; new `_process_text_document()` async function; CSV removed from `_OFFICE_FORMATS`; detection extended for `.txt`, `.html`, `.htm`, `.xml`
- **`scrub/converter.py`**: New `text_to_pdf()` function using weasyprint; CSV/XML/TXT pre-processing logic (csv.reader table builder, defusedxml itertext extractor)
- **`scrub/pipeline.py` `_MAGIC` / `detect_format()`**: Content sniff for `<?xml` and `<html`/`<!doctype html`; BOM stripping
- **Dependencies**: Add `weasyprint`, `defusedxml` to `pyproject.toml`; add corresponding system packages to Dockerfile (weasyprint requires Pango/fontconfig)
- **Specs**: `csv-conversion` spec updated; new specs for `text-format-rendering` and `text-format-detection`
