## Context

The current pipeline has two processing paths: image (Pillow) and document (LibreOffice → PDF → rasterize). Text-based formats — TXT, HTML, XML, CSV — are either unsupported or routed through LibreOffice (CSV only). LibreOffice is a general-purpose office suite that can initiate network connections when processing HTML content, creating a smoke-signal risk in a CDR context where all inputs are treated as adversarially crafted.

The goal is a third path: a Python-only text renderer that produces PDFs for the existing rasterize pipeline, with hard application-level control over external resource fetching.

## Goals / Non-Goals

**Goals:**
- Support TXT, HTML, HTM, XML, CSV as first-class input formats
- Eliminate any possibility of outbound network requests during text-format processing
- Reuse the existing `rasterize_pdf()` path — no new image output logic
- Move CSV off LibreOffice
- Keep the rendering engine swappable (contained in `converter.py`)

**Non-Goals:**
- Pixel-perfect HTML rendering (weasyprint is not a browser; CSS fidelity is sufficient for CDR)
- XML structure/schema preservation — text content only
- SVG support (separate concern, not in scope)
- Multi-sheet CSV output (weasyprint renders one table; CSV produces one PNG like a single document page)

## Decisions

### 1. weasyprint as the text rendering engine

**Decision:** Use weasyprint for HTML → PDF and as the final render step for CSV and XML (after pre-processing to HTML).

**Rationale:** weasyprint is pure Python, has no JS engine, and exposes a `url_fetcher` hook that lets us block all external resource fetches at the application layer — before any network call is attempted. This means no outbound connections, no timeouts, no smoke signals regardless of container network policy.

**Alternatives considered:**
- *LibreOffice for HTML*: Has network fetch risk; hard to disable reliably via config.
- *wkhtmltopdf*: Uses WebKit, executes JS unless explicitly disabled; binary dependency; less actively maintained.
- *Headless browser (Playwright)*: Executes JS by default; overkill; large attack surface.
- *Pillow with ImageDraw*: Viable for TXT; requires bundled TTF and manual text layout; not suitable for HTML/CSV tables.

### 2. XML → text extraction via defusedxml

**Decision:** Parse XML with `defusedxml.ElementTree`, extract all text nodes via `itertext()`, join with newlines, discard tags entirely.

**Rationale:** The CDR goal for XML is neutralisation of active content, not faithful rendering. Preserving tag structure adds complexity with no security benefit. `defusedxml` prevents XXE, billion-laughs, and quadratic blowup before any text is touched. If the file fails to parse as XML (malformed, or misnamed), fall back to plain-text treatment.

**Alternatives considered:**
- *lxml with resolve_entities=False*: More powerful but heavier dependency; overkill for text extraction.
- *Render XML structure as-is via LO*: LO renders raw tags visually; more faithful but carries the network risk and subprocess overhead.

### 3. CSV → Python csv.reader → HTML table

**Decision:** Parse with `csv.reader`, escape all cell values with `html.escape()`, emit a plain HTML `<table>`, render via weasyprint.

**Rationale:** CSV has no external reference capability, so the network risk is lower than HTML — but routing through LO means LibreOffice formula evaluation risk (CSV injection). Parsing in Python gives us explicit control: we only emit the cell text values, never evaluate them. The `html.escape()` step ensures no cell value can inject HTML into the table.

**Alternatives considered:**
- *Keep LO for CSV*: LO macro security level 4 prevents formula execution, but LO is heavier than needed for plain tabular data.
- *Pillow grid rendering*: Full manual table layout; fragile for variable column widths.

### 4. URL fetcher blocks all external resources

**Decision:** Pass a `url_fetcher` to weasyprint that raises `ValueError` immediately for any URL that is not a `data:` URI.

```python
def _block_external(url: str) -> dict:
    if not url.startswith("data:"):
        raise ValueError(f"external fetch blocked: {url}")
    # data URIs are fine — they're inline
    return weasyprint.default_url_fetcher(url)
```

**Rationale:** This fires at the weasyprint layer before any socket is opened. Even if the container network were open, no connection would be attempted. Fails fast and loudly (logged as a processing warning, not a hard error — the PDF is still produced with the resource missing).

### 5. Format detection: content sniff + extension fallback

**Decision:**
- HTML: sniff first 512 bytes (after BOM strip) for `<!doctype html`, `<html`, `<head`, `<body` (case-insensitive)
- XML: sniff for `<?xml` or determine by `.xml` extension when sniff is inconclusive
- TXT: extension only (`.txt`) — no reliable content signal
- CSV: extension only (`.csv`) — same as today; magic bytes still take precedence

**Rationale:** Text formats have no binary magic bytes. Content sniffing for HTML and XML catches misnamed files. TXT and CSV are trusted by extension with the existing magic-bytes-first guarantee preserving safety.

### 6. New `_process_text_document()` path in pipeline.py

**Decision:** Add a third processing branch alongside `_process_image` and `_process_document`. CSV is removed from `_OFFICE_FORMATS` and added to a new `_TEXT_FORMATS` set.

**Rationale:** Keeps routing logic clean and explicit. The text path shares the same scan/write/ClamAV structure as the document path, just with a different converter call.

## Risks / Trade-offs

- **weasyprint PDF fidelity** → weasyprint renders a subset of CSS; complex HTML will look different than in a browser. Acceptable: CDR goal is neutralisation, not preview quality.
- **weasyprint system deps** → requires Pango, fontconfig, and related libraries in the Docker image. These are standard on Debian/Ubuntu; Dockerfile update needed.
- **Malformed XML fallback** → if `defusedxml` raises on parse, the file is treated as plain text. An adversary could craft XML that fails to parse cleanly; the result is a TXT render of the raw bytes, which is a safe degradation.
- **CSV multi-sheet** → weasyprint produces a single-page PDF from a CSV; LO could produce multiple sheets. Multi-sheet CSV was an edge case with LO anyway. Documented as a deliberate scope reduction.
- **Large TXT/CSV files** → very large files will produce very tall PDFs; PyMuPDF will rasterize them into many pages. Existing `SCRUB_MAX_FILE_SIZE` limit applies.

## Open Questions

- Should the weasyprint `<pre>` block for TXT/XML use a monospace font? (Suggested: yes, for readability — `font-family: monospace` in the inline style.)
- Should CSS styling be minimal inline styles or a small embedded `<style>` block? (Suggested: inline only, to avoid any `@import` or external stylesheet risk even within weasyprint's own CSS handling.)
