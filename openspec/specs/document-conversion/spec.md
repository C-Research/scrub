## ADDED Requirements

### Requirement: Format detection by magic bytes
The system SHALL detect file format using magic bytes (file signature), never by file extension. Supported formats: PDF, DOCX, DOC, XLSX, XLS, PPTX, PPT.

#### Scenario: Correct format detected from magic bytes
- **WHEN** a file with extension `.txt` contains PDF magic bytes `%PDF`
- **THEN** the system SHALL route it as a PDF

#### Scenario: Unsupported format detected
- **WHEN** a file's magic bytes do not match any supported format
- **THEN** the system SHALL quarantine the file with `error_type: "UnsupportedFormat"`

---

### Requirement: Pre-flight size check
The system SHALL reject files exceeding a configurable maximum size (default 100MB) before downloading content beyond the S3 object metadata.

#### Scenario: Oversized file rejected
- **WHEN** an S3 object's `ContentLength` exceeds the size limit
- **THEN** the system SHALL quarantine it with `error_type: "FileTooLarge"` without downloading the full content

---

### Requirement: Office document conversion via LibreOffice
The system SHALL convert DOCX, DOC, PPTX, PPT to PDF using LibreOffice headless as a subprocess. The system SHALL convert XLSX, XLS to PDF using LibreOffice headless with each sheet scaled to fit exactly one page.

#### Scenario: DOCX converts to multi-page PDF
- **WHEN** a valid DOCX file is processed
- **THEN** LibreOffice SHALL produce a PDF where each page corresponds to one document page

#### Scenario: XLSX converts with one page per sheet
- **WHEN** a valid XLSX file with 3 sheets is processed
- **THEN** LibreOffice SHALL produce a PDF with exactly 3 pages, one per sheet

#### Scenario: LibreOffice process times out
- **WHEN** LibreOffice does not complete within the configured timeout
- **THEN** the system SHALL SIGKILL the process and quarantine the file with `error_type: "LibreOfficeTimeout"`

#### Scenario: LibreOffice exits with non-zero code
- **WHEN** LibreOffice exits with a non-zero return code
- **THEN** the system SHALL quarantine the file with `error_type: "LibreOfficeError"`

---

### Requirement: Fresh LibreOffice user profile per invocation
The system SHALL create a temporary directory for the LibreOffice user profile for each subprocess invocation and delete it upon subprocess completion or failure.

#### Scenario: Profile directory cleaned up after success
- **WHEN** LibreOffice completes successfully
- **THEN** the temporary profile directory SHALL be deleted

#### Scenario: Profile directory cleaned up after failure
- **WHEN** LibreOffice crashes or is killed
- **THEN** the temporary profile directory SHALL still be deleted

---

### Requirement: PDF rasterization via PyMuPDF
The system SHALL rasterize each PDF page to raw RGB pixel data using PyMuPDF (fitz). The PDF may originate from a direct PDF input or from LibreOffice conversion.

#### Scenario: Multi-page PDF produces one pixmap per page
- **WHEN** a PDF with N pages is rasterized
- **THEN** the system SHALL produce N pixmaps, one per page, in order

#### Scenario: PDF with zero pages is quarantined
- **WHEN** a PDF reports zero pages
- **THEN** the system SHALL quarantine the file with `error_type: "EmptyDocument"`

---

### Requirement: Pillow PNG re-encode from raw pixels
The system SHALL re-encode each PyMuPDF pixmap as a PNG by constructing a Pillow Image from raw RGB bytes, then saving to PNG. The system SHALL NOT pass PyMuPDF-produced PNG bytes directly to output.

#### Scenario: Output PNG constructed from pixel data
- **WHEN** a page pixmap is encoded
- **THEN** Pillow SHALL construct the image via `Image.frombuffer()` from raw RGB bytes and save as PNG

#### Scenario: Output PNG has no metadata
- **WHEN** a PNG is saved
- **THEN** it SHALL contain no EXIF, XMP, or other metadata

---

### Requirement: LibreOffice macro and Java hardening
The system SHALL invoke LibreOffice with macro execution disabled and Java integration disabled.

#### Scenario: Macro-bearing document processed safely
- **WHEN** a DOCX containing VBA macros is converted
- **THEN** LibreOffice SHALL not execute any macro code

#### Scenario: Java disabled
- **WHEN** LibreOffice is invoked
- **THEN** it SHALL run without Java integration enabled
