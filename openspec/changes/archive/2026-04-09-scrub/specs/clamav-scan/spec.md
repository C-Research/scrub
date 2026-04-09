## ADDED Requirements

### Requirement: ClamAV daemon readiness check at startup
The system SHALL verify the ClamAV daemon is responsive via its Unix socket before starting any file workers. The system SHALL poll with exponential backoff and fail with a fatal error if the daemon does not respond within a configurable timeout (default 60s).

#### Scenario: Daemon ready before workers start
- **WHEN** clamd responds on the Unix socket within the startup timeout
- **THEN** the system SHALL proceed to start file processing workers

#### Scenario: Daemon never responds at startup
- **WHEN** clamd does not respond within the startup timeout
- **THEN** the system SHALL exit with a fatal error and code 1 without processing any files

---

### Requirement: ClamAV scan of each output PNG before upload
The system SHALL scan every output PNG with `clamdscan` via the clamd Unix socket after Pillow re-encode and before S3 upload. Scanning SHALL be performed per-file (all pages of a document scanned before any page is uploaded).

#### Scenario: All pages scanned before any upload
- **WHEN** a document produces 5 output PNGs
- **THEN** all 5 SHALL be scanned before any is uploaded to S3

#### Scenario: Clean scan proceeds to upload
- **WHEN** clamdscan reports no threat on a PNG
- **THEN** the system SHALL upload that PNG to the output S3 prefix

---

### Requirement: ClamAV detection quarantines the file
The system SHALL quarantine any file for which clamdscan reports a detection on any output PNG. No output PNGs for that file SHALL be uploaded to S3.

#### Scenario: Detection on one page quarantines entire file
- **WHEN** clamdscan detects a threat in `page_002.png` of a 5-page document
- **THEN** none of the 5 output PNGs SHALL be uploaded, and the file SHALL be quarantined with `error_type: "ClamAVDetection"`

#### Scenario: Quarantine manifest includes virus name
- **WHEN** a ClamAV detection occurs
- **THEN** the quarantine manifest SHALL include the `virus_name` field containing the ClamAV signature name (e.g. `"Win.Exploit.CVE-2024-1234.Trojan"`)

#### Scenario: Quarantine manifest includes scanned file name
- **WHEN** a ClamAV detection occurs
- **THEN** the quarantine manifest SHALL include the `scanned_file` field with the name of the PNG that triggered the detection

---

### Requirement: ClamAV scan error quarantines the file
The system SHALL quarantine any file for which clamdscan fails (non-zero exit, socket timeout, daemon unavailable). Security-first: a scan that cannot complete is treated as a detection.

#### Scenario: Socket timeout quarantines file
- **WHEN** clamdscan does not complete within 30 seconds
- **THEN** the file SHALL be quarantined with `error_type: "ClamAVError"` and `error_detail` describing the timeout

#### Scenario: Daemon unavailable mid-run quarantines file
- **WHEN** the clamd daemon becomes unavailable after startup
- **THEN** any file being scanned at that moment SHALL be quarantined with `error_type: "ClamAVError"`

---

### Requirement: ClamAV communicates via Unix socket on shared volume
The system SHALL invoke `clamdscan --no-summary --infected --socket=<path>` where `<path>` is the clamd Unix socket mounted from the shared volume at `/run/clamav/clamd.sock`.

#### Scenario: Scan uses Unix socket, not TCP
- **WHEN** clamdscan is invoked
- **THEN** it SHALL communicate via the Unix socket path, requiring no network interface on the gVisor container

---

### Requirement: ClamAV scan is async
The system SHALL invoke clamdscan as an asyncio subprocess (`asyncio.create_subprocess_exec`) so that concurrent workers are not blocked waiting for scan results.

#### Scenario: Concurrent scans do not block each other
- **WHEN** multiple workers finish conversion simultaneously
- **THEN** their clamdscan invocations SHALL run concurrently without blocking the event loop
