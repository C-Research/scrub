## REMOVED Requirements

### Requirement: Quarantine manifest written to quarantine directory
**Reason**: The quarantine directory is removed along with ClamAV. All failure manifests go to `data/errors/`.
**Migration**: No quarantine directory is created or mounted. Error manifests remain in `data/errors/`.

## MODIFIED Requirements

### Requirement: Startup directory validation
The system SHALL verify at startup that the source directory is readable and that the clean and errors directories are writable. The system SHALL exit with a fatal error if any check fails.

#### Scenario: Unwritable clean directory causes fatal exit
- **WHEN** the clean directory is not writable by the container process
- **THEN** the system SHALL log a fatal error and exit with code 1 before processing any files
