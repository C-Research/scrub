## REMOVED Requirements

### Requirement: JSON manifest written to quarantine directory
**Reason**: The quarantine directory and path were exclusively for ClamAV detections. With ClamAV removed, the quarantine concept is eliminated. Processing failures continue to produce error manifests in `data/errors/`.
**Migration**: Use `data/errors/` manifests for all failure inspection.

### Requirement: Quarantine manifest content
**Reason**: Quarantine manifests no longer exist. Error manifests in `data/errors/` remain unchanged.
**Migration**: Read error manifests from `data/errors/` for failure details.

## MODIFIED Requirements

### Requirement: Known error types
The system SHALL use the following `error_type` values:
- `FileTooLarge`: input exceeds size limit
- `UnsupportedFormat`: magic bytes do not match any supported format
- `LibreOfficeTimeout`: LibreOffice subprocess exceeded timeout
- `LibreOfficeError`: LibreOffice subprocess exited with non-zero code
- `PyMuPDFError`: PyMuPDF raised an exception during rasterization
- `EmptyDocument`: document reports zero pages
- `ImageDecodeError`: Pillow could not open or decode an image input
- `PillowEncodeError`: Pillow raised an exception during PNG re-encode
- `UnexpectedError`: any other unhandled exception

#### Scenario: Correct error type assigned for timeout
- **WHEN** LibreOffice is killed due to timeout
- **THEN** `error_type` SHALL be `"LibreOfficeTimeout"`

#### Scenario: Correct error type for unknown exception
- **WHEN** an unexpected exception occurs
- **THEN** `error_type` SHALL be `"UnexpectedError"` and `error_detail` SHALL include the exception message
