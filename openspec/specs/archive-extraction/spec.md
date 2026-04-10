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

---

### Requirement: Office ZIP formats skipped during archive extraction
The system SHALL NOT expand files with extensions `.docx`, `.xlsx`, or `.pptx` during the archive pre-processing pass, even though they share the ZIP format.

#### Scenario: DOCX not expanded as archive
- **WHEN** `source/report.docx` exists in the source directory
- **THEN** it SHALL NOT be treated as a ZIP archive during the pre-processing pass

---

### Requirement: Dedup by destination path
For each archive member, the system SHALL check whether the destination path already exists in the source directory. If it does, the member SHALL be skipped.

#### Scenario: Existing file not overwritten
- **WHEN** `source/docs/archive.zip` contains `report.docx` AND `source/docs/report.docx` already exists
- **THEN** the existing `report.docx` SHALL NOT be overwritten and extraction of that member SHALL be skipped

---

### Requirement: Path traversal protection
The system SHALL reject any archive member whose path contains `..`, is absolute, or resolves to a location outside the archive's parent directory. Symlinks inside archives SHALL be skipped.

#### Scenario: Path traversal member skipped
- **WHEN** an archive contains a member with path `../../etc/passwd`
- **THEN** that member SHALL be skipped and a warning SHALL be logged

#### Scenario: Absolute path member skipped
- **WHEN** an archive contains a member with an absolute path such as `/etc/passwd`
- **THEN** that member SHALL be skipped and a warning SHALL be logged

#### Scenario: Symlink member skipped
- **WHEN** an archive contains a symlink entry
- **THEN** that entry SHALL be skipped

---

### Requirement: Zip bomb limits enforced during extraction
The system SHALL enforce three configurable limits during archive extraction. When any limit is reached, the remaining members of that archive SHALL be skipped and a warning SHALL be logged.

Limits (all configurable via env vars):
- Per-member uncompressed size: `SCRUB_MAX_FILE_SIZE` MB (default 100 MB)
- Total uncompressed bytes per archive: `SCRUB_MAX_ARCHIVE_TOTAL_MB` (default 500 MB)
- Member count per archive: `SCRUB_MAX_ARCHIVE_MEMBERS` (default 1000)

#### Scenario: Oversized member skipped
- **WHEN** an archive member's uncompressed size exceeds `SCRUB_MAX_FILE_SIZE`
- **THEN** that member SHALL be skipped and a warning SHALL be logged

#### Scenario: Total size limit aborts remaining members
- **WHEN** cumulative uncompressed bytes across members exceeds `SCRUB_MAX_ARCHIVE_TOTAL_MB`
- **THEN** extraction of remaining members SHALL stop and a warning SHALL be logged

#### Scenario: Member count limit aborts remaining members
- **WHEN** the number of members in an archive exceeds `SCRUB_MAX_ARCHIVE_MEMBERS`
- **THEN** extraction of remaining members SHALL stop and a warning SHALL be logged

---

### Requirement: Plain .gz size limit enforced via chunked read
The system SHALL enforce the per-file size limit when decompressing plain `.gz` files by reading in chunks and aborting if the running decompressed total exceeds `SCRUB_MAX_FILE_SIZE`. A warning SHALL be logged and the partially decompressed file SHALL be discarded.

#### Scenario: Oversized .gz aborted mid-decompress
- **WHEN** a `.gz` file decompresses to more bytes than `SCRUB_MAX_FILE_SIZE`
- **THEN** decompression SHALL be aborted, no output file SHALL be written, and a warning SHALL be logged

---

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

---

### Requirement: Archive expansion count logged in summary
The system SHALL include the count of archives expanded in the startup summary log line.

#### Scenario: Summary includes expanded count
- **WHEN** 3 archives are expanded during the pre-processing pass
- **THEN** the summary log line SHALL include `expanded=3`
