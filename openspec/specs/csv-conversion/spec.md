### Requirement: CSV files converted via weasyprint
The system SHALL convert `.csv` files to output PNGs using the text rendering path (weasyprint) rather than LibreOffice. CSV format SHALL be detected by file extension when no magic bytes match. Output files SHALL use the `sheet_` naming convention (`sheet_001.png`).

#### Scenario: CSV file produces sheet PNGs
- **WHEN** a file with `.csv` extension is placed in the source directory
- **THEN** scrub SHALL convert it via weasyprint and write `<name>.csv.sheet_001.png` to the clean directory

#### Scenario: Multi-sheet CSV is not supported; single PNG is produced
- **WHEN** a `.csv` file contains multiple logical sheets
- **THEN** scrub SHALL render a single PNG from the full parsed table; multi-sheet output is not produced

#### Scenario: CSV with injection formulas is neutralised
- **WHEN** a `.csv` file contains CSV injection payloads (e.g. `=CMD|'/c calc'!A1`, DDE formulas)
- **THEN** scrub SHALL render the literal cell text without evaluating any formula; no LibreOffice macro evaluation occurs

---

### Requirement: CSV format detected by extension, not magic bytes
The system SHALL detect CSV format using the `.csv` file extension when no magic bytes match. If a file has a `.csv` extension but its content matches a known magic byte pattern (e.g. it is actually a PDF), the magic byte result SHALL take precedence.

#### Scenario: .csv extension with no magic bytes routes to CSV path
- **WHEN** a file named `data.csv` contains plain text with no matching magic byte prefix
- **THEN** `detect_format()` SHALL return `"csv"` and the file SHALL be routed to the document conversion path

#### Scenario: Magic bytes take precedence over .csv extension
- **WHEN** a file named `data.csv` begins with `%PDF`
- **THEN** `detect_format()` SHALL return `"pdf"` and the file SHALL be routed accordingly

