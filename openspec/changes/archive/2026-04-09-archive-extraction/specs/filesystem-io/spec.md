## MODIFIED Requirements

### Requirement: Source directory modified only by archive pre-processing pass
The system SHALL treat the source directory as read-only during the pipeline walk and per-file processing. The archive pre-processing pass (which runs before `walk_source`) MAY write extracted members into the source directory. No source file SHALL be modified, moved, or deleted by the pipeline.

#### Scenario: Source file unchanged after processing
- **WHEN** a file is processed successfully or quarantined
- **THEN** the original file in the source directory SHALL be unmodified

#### Scenario: Extracted members written to source directory
- **WHEN** an archive is expanded during the pre-processing pass
- **THEN** extracted members SHALL be written into the source directory alongside the archive
