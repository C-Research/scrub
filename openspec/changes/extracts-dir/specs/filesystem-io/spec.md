## MODIFIED Requirements

### Requirement: Source directory modified only by archive pre-processing pass
The system SHALL treat the source directory as strictly read-only during the entire run, including the archive pre-processing pass. No file SHALL be written to, modified, moved, or deleted in the source directory by any part of the system.

#### Scenario: Source file unchanged after processing
- **WHEN** a file is processed successfully or quarantined
- **THEN** the original file in the source directory SHALL be unmodified

#### Scenario: Archive extraction does not write to source
- **WHEN** an archive is expanded during the pre-processing pass
- **THEN** extracted members SHALL be written into `/data/extracts`, not into the source directory

### Requirement: Pipeline walks both source and extracts directories
The system SHALL walk `/data/source` and `/data/extracts` as two independent source roots, enqueuing all files from both for processing. Files from `extracts` SHALL be processed with `extracts` as their source root for path derivation.

#### Scenario: Extracted file processed by pipeline
- **WHEN** `extracts/subdir/foo/report.pdf` exists after archive expansion
- **THEN** that file SHALL be enqueued and processed, with output written to `clean/subdir/foo/report/page_001.png`

#### Scenario: Source and extracts files both enqueued
- **WHEN** `source/` contains `image.png` AND `extracts/` contains `archive/doc.docx`
- **THEN** both files SHALL be enqueued for processing in the same run
