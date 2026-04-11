## ADDED Requirements

### Requirement: Text extraction output mode
The system SHALL support a text extraction mode activated by setting `SCRUB_OUTPUT_MODE=text`. In text mode, documents with an extractable text layer SHALL produce a `.txt` output file instead of PNG images. Documents without a text layer (images, scanned PDFs) SHALL fall back to PNG rasterization.

#### Scenario: Office document produces TXT in text mode
- **WHEN** `SCRUB_OUTPUT_MODE=text` and a DOCX file is processed
- **THEN** the system SHALL write a single `.txt` file to the clean directory (not page PNGs)

#### Scenario: Image input falls back to PNG in text mode
- **WHEN** `SCRUB_OUTPUT_MODE=text` and a JPEG file is processed
- **THEN** the system SHALL produce PNG output via the standard rasterize path

#### Scenario: PNG mode unchanged
- **WHEN** `SCRUB_OUTPUT_MODE` is unset or set to `png`
- **THEN** the system SHALL behave identically to current behavior

---

### Requirement: Scanned PDF fallback detection
In text mode, the system SHALL detect scanned PDFs by attempting text extraction via PyMuPDF. If the total extracted text across all pages contains fewer than 50 non-whitespace characters, the document SHALL be treated as scanned and fall back to PNG rasterization.

#### Scenario: Scanned PDF falls back to PNG
- **WHEN** `SCRUB_OUTPUT_MODE=text` and a PDF with no text layer is processed
- **THEN** the system SHALL produce PNG output, not a TXT file

#### Scenario: PDF with text layer produces TXT
- **WHEN** `SCRUB_OUTPUT_MODE=text` and a PDF with an embedded text layer (>=50 non-whitespace chars) is processed
- **THEN** the system SHALL produce a `.txt` file with all page text concatenated

---

### Requirement: TXT output structure
The system SHALL write text output as a UTF-8 plain text file. All pages or sheets SHALL be concatenated in order, separated by a form-feed character (`\f`, ASCII 0x0C) between pages/sheets.

#### Scenario: Multi-page document produces concatenated text
- **WHEN** a DOCX with 3 pages is processed in text mode
- **THEN** the `.txt` file SHALL contain the text of all 3 pages, separated by `\f`

#### Scenario: Single-page document produces plain text
- **WHEN** a PDF with 1 page is processed in text mode
- **THEN** the `.txt` file SHALL contain the page text with no separator

#### Scenario: TXT output is valid UTF-8
- **WHEN** a document contains non-ASCII characters
- **THEN** the `.txt` file SHALL be valid UTF-8 with characters preserved

---

### Requirement: Text output file naming
In text mode, the system SHALL write a single `.txt` file per input document. The output path SHALL follow the same directory mirroring logic as PNG outputs but with a `.txt` extension replacing page-numbered PNGs.

#### Scenario: Output path mirrors source structure
- **WHEN** a file at `source/subdir/report.docx` is processed in text mode
- **THEN** the output SHALL be written to `clean/subdir/report.docx.txt`

#### Scenario: Already-clean detection works in text mode
- **WHEN** `clean/subdir/report.docx.txt` already exists
- **THEN** the system SHALL skip reprocessing that file

---

### Requirement: Plain text format passthrough in text mode
In text mode, TXT and CSV files SHALL be decoded directly to UTF-8 and written as `.txt` output. No structural transformation is applied.

#### Scenario: TXT passthrough
- **WHEN** `SCRUB_OUTPUT_MODE=text` and a `.txt` file is processed
- **THEN** the system SHALL write a `.txt` output with the decoded content preserved

#### Scenario: CSV passthrough
- **WHEN** `SCRUB_OUTPUT_MODE=text` and a `.csv` file is processed
- **THEN** the system SHALL write a `.txt` output with the decoded CSV content as-is

---

### Requirement: HTML text extraction in text mode
In text mode, HTML and HTM files SHALL have all tags stripped. The content of `<script>` and `<style>` elements SHALL be excluded entirely (not just their tags).

#### Scenario: HTML tags stripped
- **WHEN** `SCRUB_OUTPUT_MODE=text` and an HTML file is processed
- **THEN** the `.txt` output SHALL contain only the visible text content, with all markup removed

#### Scenario: Script and style bodies excluded
- **WHEN** an HTML file contains `<script>` or `<style>` elements
- **THEN** the `.txt` output SHALL not contain the JavaScript or CSS source text from those elements

---

### Requirement: XML text extraction in text mode
In text mode, XML files SHALL have their element text content extracted via tree iteration. Markup, tag names, and attributes SHALL NOT appear in the output.

#### Scenario: XML element text extracted
- **WHEN** `SCRUB_OUTPUT_MODE=text` and an XML file is processed
- **THEN** the `.txt` output SHALL contain the text nodes from all elements, joined by newlines

---

### Requirement: PNG mode unchanged for text formats
When `SCRUB_OUTPUT_MODE=png` (or unset), TXT, CSV, HTML, HTM, and XML files SHALL continue to be processed via WeasyPrint→rasterize, producing PNG output identical to current behavior.

#### Scenario: Text formats still produce PNG in png mode
- **WHEN** `SCRUB_OUTPUT_MODE` is unset and an HTML file is processed
- **THEN** the system SHALL produce PNG output via the WeasyPrint rasterize path
