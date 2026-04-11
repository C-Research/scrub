## Context

The current pipeline rasterizes every processed file to PNG regardless of content type. Users who want machine-readable text must run OCR on those PNGs — a lossy, slow, expensive step. For documents that already contain a text layer (DOCX, XLSX, PDFs with embedded text), direct extraction is faster, higher quality, and produces output orders of magnitude smaller than PNG.

The CDR guarantee on output is unchanged: plain UTF-8 text contains no executable surface. The processing pipeline attack surface is also unchanged — LO and PyMuPDF still parse the input, gVisor still sandboxes them.

## Goals / Non-Goals

**Goals:**
- Opt-in text extraction mode via `SCRUB_OUTPUT_MODE=text` env var
- Per-page JSON output for documents with text layers
- Automatic fallback to PNG for images and scanned documents
- Reuse the existing LO → PDF → PyMuPDF pipeline — no new LO invocation modes
- Zero change to `png` mode behavior

**Non-Goals:**
- Layout or formatting preservation
- HTML output
- OCR (that's the caller's responsibility)
- Improving text quality for already-garbled PDFs
- Per-word or bounding-box level output

## Decisions

### Text mode uses LO → PDF → PyMuPDF for office formats (not `--convert-to txt`)

LO's `--convert-to txt` produces a single text blob with no page structure. Going through PDF keeps the existing LO conversion step and lets PyMuPDF do per-page text extraction consistently across all document types.

**Alternative considered**: LO `--convert-to txt` directly. Rejected because it loses page boundaries and requires a separate code path from PDFs.

### PDFs skip LO entirely in text mode

For PDF inputs, PyMuPDF is already the tool that processes them. Routing through LO → PDF adds an unnecessary subprocess with no quality benefit.

**Alternative considered**: always route through LO for uniform handling. Rejected because PDF → LO → PDF is slower and LO's PDF handling is a larger attack surface.

### Scanned PDF detection via text content threshold

After `page.get_text()`, if the total extracted text across all pages is below 50 characters, the document is treated as scanned and falls back to PNG rasterization. This is a heuristic, not a guarantee.

**Alternative considered**: per-page fallback (some pages PNG, some JSON). Rejected because splitting one document across output formats complicates downstream processing.

**Threshold rationale**: 50 characters is enough to distinguish a real text layer from stray OCR artifacts or single-character labels. Configurable as `SCRUB_MIN_TEXT_CHARS` in a future iteration if needed.

### TXT output: one file per input document

Output: `<input_name>.txt` in the clean dir. Pages/sheets are concatenated in order, separated by a form-feed character (`\f`) between them. Single-page documents produce plain text with no separator.

**Alternative considered**: JSON with per-page structure. Rejected — the user is feeding this into OCR/NLP pipelines; plain text is smaller, simpler, and universally ingestible without a parsing step.

### Image inputs always fall back to PNG

PNG/JPG/TIFF/BMP/GIF contain no text layer by definition. In text mode they follow the existing `_process_image` path and produce PNG output.

## Risks / Trade-offs

- **PyMuPDF text quality** → Mitigation: this is expected; the user is running OCR anyway. Poor text from PyMuPDF is no worse than poor text from OCR on a PNG.
- **Scanned PDF misclassified as text** → Mitigation: threshold is conservative (50 chars); partially-scanned docs with any real text will extract that text and skip rasterization for remaining pages.
- **LO PDF for some office formats loses text** → Mitigation: out of scope; LO conversion quality is a pre-existing constraint, not introduced by this change.
- **Output file naming collision** (`.txt` vs existing `.png` sentinels) → Mitigation: update the `already_clean` sentinel check in `pipeline.py` to look for both `.txt` and page PNG files depending on mode.

### Text format routing restructure

The original implementation checked `fmt in _TEXT_FORMATS` before `output_mode == "text"`, so TXT/HTML/XML/CSV files always went through WeasyPrint→rasterize regardless of mode. In text mode this is wasteful and wrong — these formats have directly extractable text.

Fix: restructure the routing so `output_mode` is the outer branch (after images, which always go PNG):

```
if fmt in _IMAGE_FORMATS:
    → PNG (always)
elif output_mode == "text":
    if fmt in _TEXT_FORMATS:   → extract_plain_text → .txt
    elif fmt == "pdf":         → _process_pdf_text → .txt (or scanned fallback)
    else:                      → _process_document_text → .txt
else:  # png mode
    if fmt in _TEXT_FORMATS:   → _process_text_document (WeasyPrint) → PNG
    else:                      → _process_document → PNG
```

**PNG mode behavior is unchanged** — WeasyPrint path for text formats still exists, just guarded by `output_mode == "png"`.

### HTML extraction: strip tags + suppress script/style content

For a search index, stripping only HTML tags is insufficient — `<script>` and `<style>` element bodies would land in the index as JS/CSS blobs. Use `html.parser.HTMLParser` (stdlib) to suppress the full content of script and style elements, not just their tags.

**No new dependencies** — `html.parser` is stdlib.

### TXT and CSV: passthrough

Both are already UTF-8 text. In text mode: `raw.decode('utf-8', errors='replace')`, done. No structural transformation needed. The downstream consumer (search index) can ingest raw CSV syntax without issue.

### XML: reuse existing itertext() logic

`converter.py` already has `_xml_to_text` which calls `root.itertext()` and joins the result. In text mode, reuse that extraction and skip the WeasyPrint HTML wrapper entirely.

## Open Questions

- Should `SCRUB_OUTPUT_MODE` be validated at startup (exit 1 on unknown value) or silently default to `png`? **Lean toward exit 1** — same pattern as `SCRUB_MAX_FILE_SIZE`.
- Should the scanned fallback threshold (50 chars) be env-var configurable in this iteration? **Lean toward no** — keep scope tight, add later if needed.
