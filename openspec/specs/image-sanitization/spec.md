## ADDED Requirements

### Requirement: Image format detection by magic bytes
The system SHALL detect image format using magic bytes. Supported image formats: PNG, JPG/JPEG, TIFF, BMP, GIF.

#### Scenario: Image routed correctly by magic bytes
- **WHEN** a file's magic bytes identify it as a TIFF
- **THEN** the system SHALL route it through the image sanitization path, not the document conversion path

---

### Requirement: Direct Pillow re-encode for image inputs
The system SHALL process image inputs by opening them with Pillow, extracting raw pixel data, constructing a new Pillow Image from those pixels, and saving as PNG. The system SHALL NOT copy input bytes to output.

#### Scenario: Image re-encoded from pixel data
- **WHEN** a PNG image is processed
- **THEN** the system SHALL open it with Pillow, read pixel data, construct a new Image from raw pixels, and save as a new PNG

#### Scenario: Re-encoded image has no metadata
- **WHEN** a JPEG with EXIF metadata is processed
- **THEN** the output PNG SHALL contain no EXIF, XMP, IPTC, or other metadata

---

### Requirement: Single output page for image inputs
The system SHALL produce exactly one output PNG per image input file, named `page_001.png`.

#### Scenario: Single image produces single output
- **WHEN** a TIFF file is processed
- **THEN** exactly one file `page_001.png` SHALL be written to the output folder for that file

---

### Requirement: Corrupt or unreadable image quarantined
The system SHALL quarantine image files that Pillow cannot open or decode.

#### Scenario: Corrupt image file quarantined
- **WHEN** Pillow raises an exception opening an image file
- **THEN** the system SHALL quarantine it with `error_type: "ImageDecodeError"`
