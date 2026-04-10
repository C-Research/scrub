## ADDED Requirements

### Requirement: CSV files converted via LibreOffice Calc
The system SHALL convert `.csv` files to output PNGs using the LibreOffice document path (LibreOffice → PDF → PyMuPDF rasterize → Pillow re-encode). CSV format SHALL be detected by file extension when no magic bytes match. Output files SHALL use the `sheet_` naming convention (`sheet_001.png`, `sheet_002.png`, …).

#### Scenario: CSV file produces sheet PNGs
- **WHEN** a file with `.csv` extension is placed in the source directory
- **THEN** scrub SHALL convert it via LibreOffice and write `<name>.csv.sheet_001.png` (and additional sheets if present) to the clean directory

#### Scenario: Multi-sheet CSV produces one PNG per sheet
- **WHEN** a `.csv` file results in multiple sheets after LibreOffice import
- **THEN** each sheet SHALL produce a separate `sheet_NNN.png` output file

#### Scenario: CSV with injection formulas is neutralised
- **WHEN** a `.csv` file contains CSV injection payloads (e.g. `=CMD|'/c calc'!A1`, DDE formulas)
- **THEN** LibreOffice SHALL open the file with macro security level 4, preventing formula execution, and the output PNG SHALL be a visual render of the cell contents

### Requirement: CSV format detected by extension, not magic bytes
The system SHALL detect CSV format using the `.csv` file extension when no magic bytes match. If a file has a `.csv` extension but its content matches a known magic byte pattern (e.g. it is actually a PDF), the magic byte result SHALL take precedence.

#### Scenario: .csv extension with no magic bytes routes to CSV path
- **WHEN** a file named `data.csv` contains plain text with no matching magic byte prefix
- **THEN** `detect_format()` SHALL return `"csv"` and the file SHALL be routed to the document conversion path

#### Scenario: Magic bytes take precedence over .csv extension
- **WHEN** a file named `data.csv` begins with `%PDF`
- **THEN** `detect_format()` SHALL return `"pdf"` and the file SHALL be routed accordingly

### Requirement: CSV LibreOffice conversion uses explicit import filter
The system SHALL invoke LibreOffice with `--infilter="Text - txt - csv (StarCalc)"` when converting CSV files to ensure consistent import behaviour across LibreOffice versions.

#### Scenario: CSV conversion uses StarCalc infilter
- **WHEN** LibreOffice is invoked to convert a `.csv` file
- **THEN** the command SHALL include `--infilter="Text - txt - csv (StarCalc)"`
