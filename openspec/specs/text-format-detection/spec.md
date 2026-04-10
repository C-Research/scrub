### Requirement: HTML format detected by content sniff
The system SHALL detect HTML format by sniffing the first 512 bytes of the file (after stripping any leading byte-order mark) for the case-insensitive presence of `<!doctype html`, `<html`, `<head`, or `<body`. If any of these patterns match, `detect_format()` SHALL return `"html"` regardless of file extension. Magic byte detection always takes precedence over content sniffing.

#### Scenario: File with .html extension and matching content is detected as html
- **WHEN** a file named `report.html` begins with `<!DOCTYPE html>`
- **THEN** `detect_format()` SHALL return `"html"`

#### Scenario: File with .htm extension is detected as html
- **WHEN** a file named `page.htm` begins with `<html>`
- **THEN** `detect_format()` SHALL return `"html"`

#### Scenario: File with no HTML extension but HTML content sniffs as html
- **WHEN** a file named `document.txt` begins with `<html><head>`
- **THEN** `detect_format()` SHALL return `"html"` (content sniff overrides extension)

#### Scenario: HTML with UTF-8 BOM is detected correctly
- **WHEN** a file begins with the UTF-8 BOM (`\xef\xbb\xbf`) followed by `<!DOCTYPE html>`
- **THEN** `detect_format()` SHALL strip the BOM before sniffing and return `"html"`

#### Scenario: Binary magic bytes take precedence over HTML content sniff
- **WHEN** a file begins with `PK\x03\x04` (ZIP magic) but later contains `<html>`
- **THEN** `detect_format()` SHALL return the ZIP-derived format, not `"html"`

---

### Requirement: XML format detected by content sniff
The system SHALL detect XML format by sniffing the first 512 bytes of the file (after stripping any leading byte-order mark) for the prefix `<?xml`. If the prefix matches, `detect_format()` SHALL return `"xml"`. If the file extension is `.xml` and no magic bytes or HTML sniff match, `detect_format()` SHALL also return `"xml"`. Magic byte detection and HTML sniff take precedence over XML detection.

#### Scenario: File beginning with <?xml declaration is detected as xml
- **WHEN** a file begins with `<?xml version="1.0"?>`
- **THEN** `detect_format()` SHALL return `"xml"`

#### Scenario: File with .xml extension and no magic bytes defaults to xml
- **WHEN** a file named `data.xml` contains no matching magic bytes and does not sniff as HTML
- **THEN** `detect_format()` SHALL return `"xml"`

#### Scenario: XML with UTF-8 BOM is detected correctly
- **WHEN** a file begins with the UTF-8 BOM followed by `<?xml version="1.0"?>`
- **THEN** `detect_format()` SHALL strip the BOM and return `"xml"`

---

### Requirement: TXT format detected by extension
The system SHALL detect plain-text format using the `.txt` file extension when no magic bytes, HTML sniff, or XML sniff match. `detect_format()` SHALL return `"txt"` for files with a `.txt` extension that do not match any other format.

#### Scenario: .txt file with no magic bytes routes to txt
- **WHEN** a file named `notes.txt` contains plain ASCII text with no matching magic byte prefix
- **THEN** `detect_format()` SHALL return `"txt"`

#### Scenario: Magic bytes take precedence over .txt extension
- **WHEN** a file named `data.txt` begins with `%PDF`
- **THEN** `detect_format()` SHALL return `"pdf"`, not `"txt"`
