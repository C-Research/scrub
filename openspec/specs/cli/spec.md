## ADDED Requirements

### Requirement: CLI entrypoint via scrub command
The system SHALL provide a `scrub` CLI command that accepts the following arguments:
- `--source` (required): path to the source directory containing input files (read-only)
- `--clean` (required): path to the output directory for sanitized PNG images
- `--quarantine` (required): path to the directory for quarantine JSON manifests
- `--log` (required): absolute path to the log file (e.g. `/var/log/scrub/scrub.log`)
- `--workers` (optional): number of concurrent workers; default `ncpu * 2 - 1`
- `--timeout` (optional): seconds before a LibreOffice subprocess is killed; default `60`
- `--memory-limit` (optional): MB of memory allowed per LibreOffice subprocess; default `512`
- `--clamav-socket` (optional): path to clamd Unix socket; default `/run/clamav/clamd.sock`

#### Scenario: CLI invoked with required arguments
- **WHEN** `scrub --source /data/source --clean /data/clean --quarantine /data/quarantine --log /var/log/scrub/scrub.log` is run
- **THEN** the tool SHALL recursively process all files under `/data/source` and write outputs to `/data/clean`

#### Scenario: Missing required argument
- **WHEN** any of `--source`, `--clean`, `--quarantine`, or `--log` is omitted
- **THEN** the CLI SHALL print a usage error and exit with code 1

---

### Requirement: Startup validation before processing
The system SHALL validate at startup that `--source` is a readable directory, `--clean` and `--quarantine` are writable directories, and the ClamAV daemon is responsive. The system SHALL exit with code 1 and a fatal log line if any check fails, before processing any files.

#### Scenario: Unreadable source directory causes fatal exit
- **WHEN** the path given to `--source` does not exist or is not readable
- **THEN** the system SHALL log a fatal error and exit with code 1

#### Scenario: ClamAV daemon not responsive causes fatal exit
- **WHEN** the clamd socket does not respond within the startup timeout
- **THEN** the system SHALL log a fatal error and exit with code 1

---

### Requirement: Structured log output to file
The system SHALL write structured log lines to the configured log file path. Each line SHALL include: ISO 8601 UTC timestamp, log level, input path (relative to source root), event type, and details.

Event types: `START`, `SUCCESS`, `QUARANTINE`.

#### Scenario: START logged when file processing begins
- **WHEN** a worker begins processing a file
- **THEN** a `START` log line SHALL be written with the relative input path and detected format

#### Scenario: SUCCESS logged on clean output
- **WHEN** all output PNGs for a file are written successfully
- **THEN** a `SUCCESS` log line SHALL be written with the relative input path and number of pages produced

#### Scenario: QUARANTINE logged on failure
- **WHEN** a file is quarantined
- **THEN** a `QUARANTINE` log line SHALL be written with the relative input path and `error_type`

#### Scenario: Log file created if not present
- **WHEN** the configured log file path does not exist
- **THEN** the system SHALL create it (including parent directories if needed)

---

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

---

### Requirement: Exit code reflects run outcome
The system SHALL exit with code `0` if all files were processed successfully, and code `1` if any file was quarantined.

#### Scenario: All files succeed
- **WHEN** every file converts without error
- **THEN** the process SHALL exit with code 0

#### Scenario: Any file quarantined
- **WHEN** at least one file is quarantined
- **THEN** the process SHALL exit with code 1
