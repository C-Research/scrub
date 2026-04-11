## REMOVED Requirements

### Requirement: ClamAV daemon readiness check at startup
**Reason**: ClamAV removed entirely. The CDR pixel re-encoding is the security guarantee; scanning already-sanitized PNGs adds no meaningful detection surface.
**Migration**: No replacement. Workers start immediately without waiting for any daemon.

### Requirement: ClamAV scan of each output PNG before upload
**Reason**: ClamAV removed entirely.
**Migration**: Output PNGs are written directly to the clean directory after Pillow re-encode.

### Requirement: ClamAV detection quarantines the file
**Reason**: ClamAV removed entirely. No quarantine path exists.
**Migration**: N/A — detection events no longer occur.

### Requirement: ClamAV scan error quarantines the file
**Reason**: ClamAV removed entirely.
**Migration**: N/A — scan errors no longer occur.

### Requirement: ClamAV communicates via Unix socket on shared volume
**Reason**: ClamAV removed entirely.
**Migration**: N/A.

### Requirement: ClamAV scan is async
**Reason**: ClamAV removed entirely.
**Migration**: N/A.
