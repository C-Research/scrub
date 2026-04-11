## ADDED Requirements

### Requirement: SCRUB_OUTPUT_MODE env var
The system SHALL read `SCRUB_OUTPUT_MODE` from the environment. Accepted values are `png` (default) and `text`. If set to any other value, the system SHALL print an error and exit with code 1.

#### Scenario: Default output mode is PNG
- **WHEN** `SCRUB_OUTPUT_MODE` is not set
- **THEN** the system SHALL operate in PNG mode (current behavior)

#### Scenario: Text mode activated
- **WHEN** `SCRUB_OUTPUT_MODE=text` is set
- **THEN** the system SHALL operate in text extraction mode

#### Scenario: Invalid value causes fatal exit
- **WHEN** `SCRUB_OUTPUT_MODE=html` is set
- **THEN** the system SHALL print an error message and exit with code 1 before processing any files
