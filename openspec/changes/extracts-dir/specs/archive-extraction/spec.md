## MODIFIED Requirements

### Requirement: Archive pre-processing pass before walk
The system SHALL expand all `.zip`, `.rar`, `.gz`, `.tar.gz`, and `.tgz` files found in the source directory before `walk_source` runs. Archive detection SHALL use file extension only (`.tar.gz` and `.tgz` detected by full-name suffix match before plain `.gz`). The expansion pass SHALL collect all archive paths first, then expand each once — extracted files SHALL NOT be re-expanded. Extracted members SHALL be written into `/data/extracts` (not the source directory).

#### Scenario: ZIP members extracted into extracts before walk
- **WHEN** `source/docs/archive.zip` contains `report.docx`
- **THEN** `extracts/docs/archive/report.docx` SHALL exist before `walk_source` begins

#### Scenario: RAR members extracted into extracts before walk
- **WHEN** `source/scans/photos.rar` contains `scan.jpg`
- **THEN** `extracts/scans/photos/scan.jpg` SHALL exist before `walk_source` begins

#### Scenario: tar.gz members extracted into extracts before walk
- **WHEN** `source/export.tar.gz` contains `data.csv` and `report.pdf`
- **THEN** `extracts/export/data.csv` and `extracts/export/report.pdf` SHALL exist before `walk_source` begins

#### Scenario: tgz members extracted into extracts before walk
- **WHEN** `source/bundle.tgz` contains `invoice.docx`
- **THEN** `extracts/bundle/invoice.docx` SHALL exist before `walk_source` begins

#### Scenario: Plain .gz decompresses into extracts as single file
- **WHEN** `source/report.pdf.gz` is a gzip-compressed single file
- **THEN** `extracts/report.pdf` SHALL exist before `walk_source` begins

#### Scenario: Nested archive not re-expanded
- **WHEN** `source/outer.zip` contains `inner.zip`
- **THEN** `extracts/outer/inner.zip` SHALL be extracted but its contents SHALL NOT be expanded

### Requirement: First-member sentinel dedup check
Before extracting any member, the system SHALL peek at the first member's relative path and check whether that path exists in the source directory. If it does, the archive SHALL be skipped entirely and an `ARCHIVE_SKIP` event SHALL be logged with reason "already in source".

#### Scenario: Archive skipped when first member exists in source
- **WHEN** `source/docs/archive.zip` contains `report.docx` as its first member AND `source/docs/report.docx` already exists
- **THEN** no members SHALL be extracted and an `ARCHIVE_SKIP` log event SHALL be emitted

#### Scenario: Archive extracted when first member absent from source
- **WHEN** `source/docs/archive.zip` contains `report.docx` as its first member AND `source/docs/report.docx` does NOT exist
- **THEN** members SHALL be extracted to `extracts/docs/archive/`

## MODIFIED Requirements

### Requirement: Dedup by destination path
For each archive member, the system SHALL check whether the destination path already exists in the `extracts` directory. If it does, the member SHALL be skipped.

#### Scenario: Existing extracts file not overwritten
- **WHEN** `source/docs/archive.zip` contains `report.docx` AND `extracts/docs/archive/report.docx` already exists
- **THEN** the existing file in extracts SHALL NOT be overwritten and extraction of that member SHALL be skipped
