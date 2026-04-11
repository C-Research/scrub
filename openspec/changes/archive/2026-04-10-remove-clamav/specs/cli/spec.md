## MODIFIED Requirements

### Requirement: CLI entrypoint via scrub command
The system SHALL provide a `scrub` CLI command that accepts the following arguments:
- `--source` (required): path to the source directory containing input files (read-only)
- `--clean` (required): path to the output directory for sanitized PNG images
- `--log` (required): absolute path to the log file (e.g. `/var/log/scrub/scrub.log`)
- `--workers` (optional): number of concurrent workers; default `ncpu * 2 - 1`
- `--timeout` (optional): seconds before a LibreOffice subprocess is killed; default `60`
- `--memory-limit` (optional): MB of memory allowed per LibreOffice subprocess; default `512`

#### Scenario: CLI invoked with required arguments
- **WHEN** `scrub --source /data/source --clean /data/clean --log /var/log/scrub/scrub.log` is run
- **THEN** the tool SHALL recursively process all files under `/data/source` and write outputs to `/data/clean`

#### Scenario: Missing required argument
- **WHEN** any of `--source`, `--clean`, or `--log` is omitted
- **THEN** the CLI SHALL print a usage error and exit with code 1

---

### Requirement: Startup validation before processing
The system SHALL validate at startup that `--source` is a readable directory and `--clean` is a writable directory. The system SHALL exit with code 1 and a fatal log line if any check fails, before processing any files.

#### Scenario: Unreadable source directory causes fatal exit
- **WHEN** the path given to `--source` does not exist or is not readable
- **THEN** the system SHALL log a fatal error and exit with code 1

---

### Requirement: Structured log output to file
The system SHALL write structured log lines to the configured log file path. Each line SHALL include: ISO 8601 UTC timestamp, log level, input path (relative to source root), event type, and details.

Event types: `START`, `SUCCESS`, `ERROR`.

#### Scenario: START logged when file processing begins
- **WHEN** a worker begins processing a file
- **THEN** a `START` log line SHALL be written with the relative input path and detected format

#### Scenario: SUCCESS logged on clean output
- **WHEN** all output PNGs for a file are written successfully
- **THEN** a `SUCCESS` log line SHALL be written with the relative input path and number of pages produced

#### Scenario: ERROR logged on failure
- **WHEN** a file fails processing
- **THEN** an `ERROR` log line SHALL be written with the relative input path and `error_type`

#### Scenario: Log file created if not present
- **WHEN** the configured log file path does not exist
- **THEN** the system SHALL create it (including parent directories if needed)

---

### Requirement: Exit code reflects run outcome
The system SHALL exit with code `0` if all files were processed successfully, and code `1` if any file produced an error.

#### Scenario: All files succeed
- **WHEN** every file converts without error
- **THEN** the process SHALL exit with code 0

#### Scenario: Any file errors
- **WHEN** at least one file fails processing
- **THEN** the process SHALL exit with code 1
