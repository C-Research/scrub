## ADDED Requirements

### Requirement: Recursive source directory walk
The system SHALL recursively walk the source directory and enqueue all files for processing. Walking SHALL use `os.scandir` in `run_in_executor` to avoid blocking the event loop.

#### Scenario: Nested files are discovered
- **WHEN** the source directory contains `reports/q1/budget.xlsx`
- **THEN** that file SHALL be enqueued for processing with its relative path `reports/q1/budget.xlsx`

#### Scenario: Empty source directory
- **WHEN** the source directory contains no files
- **THEN** the system SHALL exit with code 0 and log a warning

---

### Requirement: Source directory modified only by archive pre-processing pass
The system SHALL treat the source directory as read-only during the pipeline walk and per-file processing. The archive pre-processing pass (which runs before `walk_source`) MAY write extracted members into the source directory. No source file SHALL be modified, moved, or deleted by the pipeline.

#### Scenario: Source file unchanged after processing
- **WHEN** a file is processed successfully or quarantined
- **THEN** the original file in the source directory SHALL be unmodified

#### Scenario: Extracted members written to source directory
- **WHEN** an archive is expanded during the pre-processing pass
- **THEN** extracted members SHALL be written into the source directory alongside the archive

---

### Requirement: Startup directory validation
The system SHALL verify at startup that the source directory is readable and that the clean and quarantine directories are writable. The system SHALL exit with a fatal error if any check fails.

#### Scenario: Unwritable clean directory causes fatal exit
- **WHEN** the clean directory is not writable by the container process
- **THEN** the system SHALL log a fatal error and exit with code 1 before processing any files

---

### Requirement: Output folder structure mirrors source
The system SHALL derive the output path by: replacing the source root with the clean root, replacing the filename with a folder of that name, and naming each image `page_NNN.png` or `sheet_NNN.png` (zero-padded to 3 digits).

#### Scenario: PDF output path structure
- **WHEN** `source/docs/report.pdf` is processed
- **THEN** outputs SHALL be written to `clean/docs/report/page_001.png`, `page_002.png`, etc.

#### Scenario: XLSX output path structure
- **WHEN** `source/finance/budget.xlsx` with 3 sheets is processed
- **THEN** outputs SHALL be written to `clean/finance/budget/sheet_001.png`, `sheet_002.png`, `sheet_003.png`

#### Scenario: Image output path structure
- **WHEN** `source/scans/photo.tiff` is processed
- **THEN** output SHALL be written to `clean/scans/photo/page_001.png`

---

### Requirement: Async PNG write via aiofiles
The system SHALL write each output PNG to the clean directory using aiofiles. Parent directories SHALL be created if they do not exist before writing.

#### Scenario: Parent directories created on write
- **WHEN** `clean/reports/q1/report/` does not exist
- **THEN** the system SHALL create it before writing `page_001.png`

---

### Requirement: Quarantine manifest written to quarantine directory
The system SHALL write the JSON quarantine manifest to `<quarantine_dir>/<relative_input_path>.json`, mirroring the source folder structure.

#### Scenario: Quarantine manifest path mirrors source path
- **WHEN** `source/reports/q1/malware.docx` is quarantined
- **THEN** the manifest SHALL be written to `quarantine/reports/q1/malware.docx.json`

#### Scenario: Quarantine parent directories created on write
- **WHEN** `quarantine/reports/q1/` does not exist
- **THEN** the system SHALL create it before writing the manifest

---

### Requirement: Concurrency limited by semaphore
The system SHALL limit the number of concurrently processed files to `ncpu * 2 - 1` (default) or the value passed via `--workers`.

#### Scenario: Concurrency cap enforced
- **WHEN** 100 files are queued and workers=7
- **THEN** no more than 7 files SHALL be in-flight simultaneously
