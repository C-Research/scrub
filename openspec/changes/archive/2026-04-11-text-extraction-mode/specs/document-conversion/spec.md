## ADDED Requirements

### Requirement: Per-page text extraction from PDF via PyMuPDF
In text mode, the system SHALL extract text from each page of a PDF using PyMuPDF `page.get_text()`. Text extraction SHALL be attempted before rasterization. The system SHALL return per-page text as a list of strings, one per page.

#### Scenario: Text extracted from PDF with text layer
- **WHEN** `SCRUB_OUTPUT_MODE=text` and a PDF with embedded text is processed
- **THEN** PyMuPDF SHALL return non-empty text for at least one page without rasterization

#### Scenario: PDF with zero pages raises EmptyDocument
- **WHEN** a PDF reports zero pages in text mode
- **THEN** the system SHALL quarantine the file with `error_type: "EmptyDocument"`

---

### Requirement: Office documents converted to PDF then text-extracted
In text mode, the system SHALL route office documents (DOCX, DOC, XLSX, XLS, PPTX, PPT) through the existing LibreOffice → PDF conversion step, then extract text per-page from the resulting PDF via PyMuPDF. The `--convert-to txt` LibreOffice filter SHALL NOT be used.

#### Scenario: DOCX text extracted via LO→PDF→PyMuPDF in text mode
- **WHEN** `SCRUB_OUTPUT_MODE=text` and a DOCX is processed
- **THEN** LibreOffice SHALL convert it to PDF, and PyMuPDF SHALL extract text per-page from that PDF

#### Scenario: XLSX text extracted in text mode
- **WHEN** `SCRUB_OUTPUT_MODE=text` and an XLSX with 2 sheets is processed
- **THEN** the resulting JSON SHALL contain a `sheets` array with 2 entries
