## ADDED Requirements

### Requirement: Failed files quarantined, not output
The system SHALL NOT upload any output PNGs for a file that fails at any stage of processing. The clean output prefix SHALL remain uncontaminated by partial or failed conversions.

#### Scenario: No partial output on failure
- **WHEN** a file fails after some pages have been rasterized but before upload completes
- **THEN** no PNG files for that file SHALL appear in the output prefix

---

### Requirement: JSON manifest written to quarantine directory
The system SHALL write a JSON manifest to `<quarantine_dir>/<relative_input_path>.json` for every quarantined file, mirroring the source folder structure.

#### Scenario: Manifest path mirrors source path
- **WHEN** `source/reports/q1/malware.docx` is quarantined
- **THEN** the manifest SHALL be written to `quarantine/reports/q1/malware.docx.json`

---

### Requirement: Quarantine manifest content
Each quarantine manifest SHALL contain the following fields:
- `input_path`: relative path from source root (string, e.g. `reports/q1/malware.docx`)
- `timestamp`: ISO 8601 UTC timestamp of the failure (string)
- `format_detected`: magic-bytes detected format, or `"unknown"` if detection failed (string)
- `error_type`: machine-readable error category (string)
- `error_detail`: human-readable error message (string)
- `stack_trace`: full Python stack trace, or `null` for ClamAV detections (string | null)
- `file_size_bytes`: size of the input file in bytes (integer)
- `sha256`: hex-encoded SHA-256 digest of the raw input bytes (string)
- `virus_name`: ClamAV signature name if `error_type` is `ClamAVDetection`, otherwise `null` (string | null)
- `scanned_file`: name of the PNG that triggered the ClamAV detection if `error_type` is `ClamAVDetection`, otherwise `null` (string | null)

#### Scenario: Manifest contains all required fields
- **WHEN** a file is quarantined
- **THEN** the JSON manifest SHALL contain all ten fields listed above

#### Scenario: SHA256 computed from original input bytes
- **WHEN** a manifest is written
- **THEN** the `sha256` field SHALL be the digest of the original downloaded file bytes, before any processing

#### Scenario: SHA256 computed from original input bytes
- **WHEN** a manifest is written
- **THEN** the `sha256` field SHALL be the digest of the original source file bytes, before any processing

#### Scenario: ClamAV detection manifest includes virus name and scanned file
- **WHEN** a file is quarantined due to a ClamAV detection
- **THEN** `virus_name` SHALL contain the ClamAV signature string and `scanned_file` SHALL name the triggering PNG

---

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
- `ClamAVDetection`: ClamAV reported a threat in one or more output PNGs
- `ClamAVError`: ClamAV scan failed (daemon unavailable, socket timeout, non-zero exit)
- `UnexpectedError`: any other unhandled exception

#### Scenario: Correct error type assigned for timeout
- **WHEN** LibreOffice is killed due to timeout
- **THEN** `error_type` SHALL be `"LibreOfficeTimeout"`

#### Scenario: Correct error type for unknown exception
- **WHEN** an unexpected exception occurs
- **THEN** `error_type` SHALL be `"UnexpectedError"` and `error_detail` SHALL include the exception message
