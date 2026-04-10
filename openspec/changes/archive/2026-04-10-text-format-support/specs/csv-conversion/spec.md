## MODIFIED Requirements

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

## REMOVED Requirements

### Requirement: CSV LibreOffice conversion uses explicit import filter
**Reason:** CSV no longer routes through LibreOffice; the `--infilter=Text - txt - csv (StarCalc)` flag is no longer applicable.
**Migration:** No migration required. The weasyprint text rendering path handles CSV natively via Python's `csv.reader`.
