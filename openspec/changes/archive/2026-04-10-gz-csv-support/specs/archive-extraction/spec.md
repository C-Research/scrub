## MODIFIED Requirements

### Requirement: Archive pre-processing pass before walk
The system SHALL expand all `.zip`, `.rar`, `.gz`, `.tar.gz`, and `.tgz` files found in the source directory before `walk_source` runs. Archive detection SHALL use file extension only (`.tar.gz` and `.tgz` detected by full-name suffix match before plain `.gz`). The expansion pass SHALL collect all archive paths first, then expand each once — extracted files SHALL NOT be re-expanded.

#### Scenario: ZIP members extracted before walk
- **WHEN** `source/docs/archive.zip` contains `report.docx`
- **THEN** `source/docs/report.docx` SHALL exist before `walk_source` begins

#### Scenario: RAR members extracted before walk
- **WHEN** `source/scans/photos.rar` contains `scan.jpg`
- **THEN** `source/scans/scan.jpg` SHALL exist before `walk_source` begins

#### Scenario: tar.gz members extracted before walk
- **WHEN** `source/export.tar.gz` contains `data.csv` and `report.pdf`
- **THEN** `source/data.csv` and `source/report.pdf` SHALL exist before `walk_source` begins

#### Scenario: tgz members extracted before walk
- **WHEN** `source/bundle.tgz` contains `invoice.docx`
- **THEN** `source/invoice.docx` SHALL exist before `walk_source` begins

#### Scenario: Plain .gz decompresses to single file
- **WHEN** `source/report.pdf.gz` is a gzip-compressed single file
- **THEN** `source/report.pdf` SHALL exist before `walk_source` begins and the decompressed filename SHALL be the archive name with `.gz` stripped

#### Scenario: Nested archive not re-expanded
- **WHEN** `source/outer.zip` contains `inner.zip`
- **THEN** `source/inner.zip` SHALL be extracted but its contents SHALL NOT be expanded

## ADDED Requirements

### Requirement: Plain .gz size limit enforced via chunked read
The system SHALL enforce the per-file size limit when decompressing plain `.gz` files by reading in chunks and aborting if the running decompressed total exceeds `SCRUB_MAX_FILE_SIZE`. A warning SHALL be logged and the partially decompressed file SHALL be discarded.

#### Scenario: Oversized .gz aborted mid-decompress
- **WHEN** a `.gz` file decompresses to more bytes than `SCRUB_MAX_FILE_SIZE`
- **THEN** decompression SHALL be aborted, no output file SHALL be written, and a warning SHALL be logged

### Requirement: tar.gz and tgz apply same safety checks as zip/rar
The system SHALL apply path traversal protection, symlink skipping, per-member size limits, total bytes limit, and member count limit to `.tar.gz` and `.tgz` archives, identical to the behaviour for `.zip` archives.

#### Scenario: tar.gz path traversal member skipped
- **WHEN** a `.tar.gz` archive contains a member with path `../../etc/passwd`
- **THEN** that member SHALL be skipped and a warning SHALL be logged

#### Scenario: tar.gz symlink member skipped
- **WHEN** a `.tar.gz` archive contains a symlink entry
- **THEN** that entry SHALL be skipped

#### Scenario: tar.gz member count limit enforced
- **WHEN** a `.tar.gz` archive contains more members than `SCRUB_MAX_ARCHIVE_MEMBERS`
- **THEN** extraction SHALL stop at the limit and a warning SHALL be logged
