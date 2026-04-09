## ADDED Requirements

### Requirement: Configurable file size limit via env var
The system SHALL read `SCRUB_MAX_FILE_SIZE` from the environment as an integer number of megabytes. If unset or empty, the default SHALL be 100 (100 MB). If set to a non-integer value, the system SHALL print an error and exit with code 1.

#### Scenario: Default file size limit applied
- **WHEN** `SCRUB_MAX_FILE_SIZE` is not set
- **THEN** the per-file size limit SHALL be 104857600 bytes (100 MB)

#### Scenario: Custom file size limit applied
- **WHEN** `SCRUB_MAX_FILE_SIZE=50` is set
- **THEN** the per-file size limit SHALL be 52428800 bytes (50 MB)

---

### Requirement: Configurable archive member count limit via env var
The system SHALL read `SCRUB_MAX_ARCHIVE_MEMBERS` from the environment as an integer. If unset or empty, the default SHALL be 1000. If set to a non-integer value, the system SHALL print an error and exit with code 1.

#### Scenario: Default member count limit applied
- **WHEN** `SCRUB_MAX_ARCHIVE_MEMBERS` is not set
- **THEN** the per-archive member count limit SHALL be 1000

---

### Requirement: Configurable archive total size limit via env var
The system SHALL read `SCRUB_MAX_ARCHIVE_TOTAL_MB` from the environment as an integer number of megabytes. If unset or empty, the default SHALL be 500 (500 MB). If set to a non-integer value, the system SHALL print an error and exit with code 1.

#### Scenario: Default total size limit applied
- **WHEN** `SCRUB_MAX_ARCHIVE_TOTAL_MB` is not set
- **THEN** the per-archive total uncompressed size limit SHALL be 524288000 bytes (500 MB)
