### Requirement: TXT files rendered to PNG via weasyprint
The system SHALL convert `.txt` files to output PNGs using the text rendering path: plain text wrapped in an HTML `<pre>` block → weasyprint → PDF → PyMuPDF rasterize → Pillow re-encode. No LibreOffice subprocess SHALL be invoked for `.txt` files.

#### Scenario: TXT file produces page PNGs
- **WHEN** a file with `.txt` extension is placed in the source directory
- **THEN** scrub SHALL convert it via weasyprint and write `<name>.txt.page_001.png` (and additional pages if the text spans multiple pages) to the clean directory

#### Scenario: TXT file with no printable content produces an empty-page PNG
- **WHEN** a `.txt` file contains only whitespace or non-printable characters
- **THEN** scrub SHALL produce a single blank-page PNG rather than an error

---

### Requirement: HTML files rendered to PNG via weasyprint with external fetches blocked
The system SHALL convert `.html` and `.htm` files to output PNGs using the text rendering path: weasyprint with a custom `url_fetcher` that raises immediately for any non-`data:` URL → PDF → PyMuPDF rasterize → Pillow re-encode. No LibreOffice subprocess SHALL be invoked for HTML files.

#### Scenario: HTML file produces page PNGs
- **WHEN** a file with `.html` or `.htm` extension is placed in the source directory
- **THEN** scrub SHALL convert it via weasyprint and write `<name>.page_001.png` (and additional pages if the content spans multiple pages) to the clean directory

#### Scenario: HTML with external image reference does not trigger a network request
- **WHEN** an HTML file contains `<img src="https://example.com/beacon.png">`
- **THEN** scrub SHALL render the page without fetching the URL; the image SHALL be absent from the output PNG; no outbound network connection SHALL be made

#### Scenario: HTML with embedded data URI image renders inline content
- **WHEN** an HTML file contains `<img src="data:image/png;base64,...">`
- **THEN** scrub SHALL render the image inline from the data URI without any network fetch

#### Scenario: HTML with embedded scripts produces visual-only output
- **WHEN** an HTML file contains `<script>` blocks
- **THEN** scrub SHALL render the page without executing any JavaScript; the output PNG SHALL reflect only the static HTML structure

---

### Requirement: XML text content rendered to PNG via weasyprint
The system SHALL convert `.xml` files to output PNGs by extracting all text nodes (using a safe XML parser), joining them with newlines, wrapping in an HTML `<pre>` block, and rendering via weasyprint → PDF → PyMuPDF rasterize → Pillow re-encode. XML tags, attributes, and structure SHALL NOT appear in the output. No LibreOffice subprocess SHALL be invoked for `.xml` files.

#### Scenario: XML file produces page PNGs showing text content only
- **WHEN** a file with `.xml` extension is placed in the source directory
- **THEN** scrub SHALL extract the text nodes and write `<name>.xml.page_001.png` to the clean directory; the output SHALL contain only the text values, not XML markup

#### Scenario: Malformed XML falls back to plain-text rendering
- **WHEN** a file with `.xml` extension contains content that cannot be parsed as valid XML
- **THEN** scrub SHALL fall back to rendering the raw file bytes as plain text (same path as `.txt`) rather than emitting an error

#### Scenario: XML with external entity references is neutralised
- **WHEN** an XML file contains an external entity declaration (`<!ENTITY foo SYSTEM "file:///etc/passwd">`)
- **THEN** scrub SHALL reject the entity via the safe XML parser before any content is accessed, and SHALL proceed to render what text content is available

---

### Requirement: CSV files rendered to PNG via weasyprint HTML table
The system SHALL convert `.csv` files to output PNGs by parsing with `csv.reader`, HTML-escaping all cell values, emitting a plain `<table>`, and rendering via weasyprint → PDF → PyMuPDF rasterize → Pillow re-encode. No LibreOffice subprocess SHALL be invoked for `.csv` files. Output files SHALL use the `sheet_` naming convention (`sheet_001.png`).

#### Scenario: CSV file produces a sheet PNG
- **WHEN** a file with `.csv` extension is placed in the source directory
- **THEN** scrub SHALL parse it and write `<name>.csv.sheet_001.png` to the clean directory

#### Scenario: CSV with formula injection payloads is neutralised
- **WHEN** a `.csv` file contains cells starting with `=`, `+`, `-`, or `@` (CSV injection payloads)
- **THEN** scrub SHALL render the literal cell text via HTML-escaped output without evaluating any formula

#### Scenario: CSV cell values containing HTML are escaped
- **WHEN** a `.csv` file contains a cell value such as `<script>alert(1)</script>`
- **THEN** the output PNG SHALL display the literal text `<script>alert(1)</script>`, not render it as HTML

---

### Requirement: weasyprint renderer blocks all external resource fetches
The system SHALL configure weasyprint with a `url_fetcher` that raises immediately for any URL that is not a `data:` URI. No network connection SHALL be initiated during text-format rendering regardless of container network policy.

#### Scenario: External CSS stylesheet is not fetched
- **WHEN** an HTML file contains `<link rel="stylesheet" href="https://example.com/style.css">`
- **THEN** scrub SHALL render the file without fetching the stylesheet; the fetch attempt SHALL be silently suppressed and the output PNG produced without that resource

#### Scenario: External fetch failure does not abort processing
- **WHEN** weasyprint encounters an external URL and the fetcher raises
- **THEN** scrub SHALL continue rendering and produce output PNGs; the blocked fetch SHALL be noted in the log but SHALL NOT cause the file to be routed to errors
