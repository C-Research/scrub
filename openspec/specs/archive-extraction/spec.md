## ADDED Requirements

### Requirement: Archive pre-processing pass before walk
The system SHALL expand all `.zip` and `.rar` files found in the source directory before `walk_source` runs. Archive detection SHALL use file extension only. The expansion pass SHALL collect all archive paths first, then expand each once — extracted files SHALL NOT be re-expanded.

#### Scenario: ZIP members extracted before walk
- **WHEN** `source/docs/archive.zip` contains `report.docx`
- **THEN** `source/docs/report.docx` SHALL exist before `walk_source` begins

#### Scenario: RAR members extracted before walk
- **WHEN** `source/scans/photos.rar` contains `scan.jpg`
- **THEN** `source/scans/scan.jpg` SHALL exist before `walk_source` begins

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

### Requirement: Archive expansion count logged in summary
The system SHALL include the count of archives expanded in the startup summary log line.

#### Scenario: Summary includes expanded count
- **WHEN** 3 archives are expanded during the pre-processing pass
- **THEN** the summary log line SHALL include `expanded=3`
