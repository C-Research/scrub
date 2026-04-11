## ADDED Requirements

### Requirement: Extracts directory as archive extraction target
The system SHALL write all archive members into `/data/extracts` rather than the source directory. The extracts directory SHALL be structured as `extracts/<source-relative-parent>/<archive-stem>/<member-path>`. For single-file `.gz` archives, the output SHALL be placed at `extracts/<source-relative-parent>/<decompressed-filename>` with no archive-stem subdirectory.

#### Scenario: ZIP member extracted into extracts with mirrored structure
- **WHEN** `source/subdir/foo.zip` contains member `docs/report.pdf`
- **THEN** the member SHALL be written to `extracts/subdir/foo/docs/report.pdf`

#### Scenario: tar.gz member extracted into extracts with mirrored structure
- **WHEN** `source/subdir/bundle.tar.gz` contains member `invoice.docx`
- **THEN** the member SHALL be written to `extracts/subdir/bundle/invoice.docx`

#### Scenario: Plain .gz extracted into extracts without archive-stem subdirectory
- **WHEN** `source/subdir/report.pdf.gz` is a gzip-compressed single file
- **THEN** the decompressed file SHALL be written to `extracts/subdir/report.pdf`

#### Scenario: Source root archive extracted into extracts root
- **WHEN** `source/archive.zip` contains member `file.pdf`
- **THEN** the member SHALL be written to `extracts/archive/file.pdf`

### Requirement: Extracts directory bind-mounted in Docker
The system SHALL mount `/data/extracts` as a writable bind mount in both `docker-compose.yml` and `docker-compose.dev.yml`, alongside the existing source, clean, quarantine, and errors mounts.

#### Scenario: Extracts directory available at container start
- **WHEN** the container starts with the standard docker-compose configuration
- **THEN** `/data/extracts` SHALL be writable by the container process
