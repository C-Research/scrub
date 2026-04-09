"""
Basic sanity tests. No ClamAV daemon required — scan_pngs is patched where needed.
No LibreOffice required — document conversion tests use the image pipeline only.
"""
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from scrub import quarantine as qmod
from scrub.clamav import ScanResult
from scrub.fs import derive_output_paths
from scrub.pipeline import detect_format, process_file
from scrub.sanitize import reencode_png

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_png(width: int = 8, height: int = 8, color: tuple = (128, 64, 32)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=color).save(buf, format="PNG")
    return buf.getvalue()


def _write_png(path: Path, **kwargs) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_make_png(**kwargs))


# ---------------------------------------------------------------------------
# detect_format
# ---------------------------------------------------------------------------

class TestDetectFormat:
    def test_pdf(self):
        assert detect_format(b"%PDF-1.4 rest", "report.pdf") == "pdf"

    def test_png(self):
        assert detect_format(b"\x89PNG\r\n\x1a\n rest", "image.png") == "png"

    def test_jpg(self):
        assert detect_format(b"\xff\xd8\xff rest", "photo.jpg") == "jpg"

    def test_docx(self):
        assert detect_format(b"PK\x03\x04 rest", "doc.docx") == "docx"

    def test_xlsx(self):
        assert detect_format(b"PK\x03\x04 rest", "sheet.xlsx") == "xlsx"

    def test_pptx(self):
        assert detect_format(b"PK\x03\x04 rest", "deck.pptx") == "pptx"

    def test_ole_doc(self):
        assert detect_format(b"\xd0\xcf\x11\xe0 rest", "doc.doc") == "doc"

    def test_ole_xls(self):
        assert detect_format(b"\xd0\xcf\x11\xe0 rest", "sheet.xls") == "xls"

    def test_unknown(self):
        assert detect_format(b"XXXXXXXXXX", "foo.bin") == "unknown"

    # Real fixture files — authentic magic bytes
    def test_fixture_pdf(self):
        raw = (FIXTURES / "eicar-adobe-acrobat-attachment.pdf").read_bytes()
        assert detect_format(raw[:16], "eicar-adobe-acrobat-attachment.pdf") == "pdf"

    def test_fixture_doc(self):
        raw = (FIXTURES / "eicar-word-macro-powershell-echo.doc").read_bytes()
        assert detect_format(raw[:16], "eicar-word-macro-powershell-echo.doc") == "doc"

    def test_fixture_xls(self):
        raw = (FIXTURES / "eicar-excel-macro-powershell-echo.xls").read_bytes()
        assert detect_format(raw[:16], "eicar-excel-macro-powershell-echo.xls") == "xls"


# ---------------------------------------------------------------------------
# derive_output_paths
# ---------------------------------------------------------------------------

class TestDeriveOutputPaths:
    def test_single_page(self, tmp_path):
        paths = derive_output_paths(tmp_path / "s", tmp_path / "c", Path("report.pdf"), 1, False)
        assert paths == [tmp_path / "c/report/page_001.png"]

    def test_multi_page(self, tmp_path):
        paths = derive_output_paths(tmp_path / "s", tmp_path / "c", Path("report.pdf"), 3, False)
        assert paths == [
            tmp_path / "c/report/page_001.png",
            tmp_path / "c/report/page_002.png",
            tmp_path / "c/report/page_003.png",
        ]

    def test_xlsx_sheet_prefix(self, tmp_path):
        paths = derive_output_paths(tmp_path / "s", tmp_path / "c", Path("budget.xlsx"), 2, True)
        assert paths[0].name == "sheet_001.png"
        assert paths[1].name == "sheet_002.png"

    def test_preserves_subdirectory(self, tmp_path):
        paths = derive_output_paths(
            tmp_path / "s", tmp_path / "c", Path("finance/q1/budget.pdf"), 1, False
        )
        assert paths == [tmp_path / "c/finance/q1/budget/page_001.png"]

    def test_zero_padding_to_three_digits(self, tmp_path):
        paths = derive_output_paths(tmp_path / "s", tmp_path / "c", Path("f.pdf"), 10, False)
        assert paths[9].name == "page_010.png"


# ---------------------------------------------------------------------------
# quarantine module
# ---------------------------------------------------------------------------

class TestQuarantine:
    def test_sha256_deterministic(self):
        assert qmod.sha256(b"hello") == qmod.sha256(b"hello")

    def test_sha256_differs_for_different_input(self):
        assert qmod.sha256(b"hello") != qmod.sha256(b"world")

    def test_sha256_known_value(self):
        # echo -n "" | sha256sum
        assert qmod.sha256(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_build_manifest_required_fields(self):
        m = qmod.build_manifest("a.pdf", "pdf", "ClamAVDetection", "threat", None, 1024, "abc123")
        assert m["input_path"] == "a.pdf"
        assert m["format_detected"] == "pdf"
        assert m["error_type"] == "ClamAVDetection"
        assert m["error_detail"] == "threat"
        assert m["file_size_bytes"] == 1024
        assert m["sha256"] == "abc123"
        assert "timestamp" in m

    def test_build_manifest_virus_fields(self):
        m = qmod.build_manifest(
            "bad.png", "png", "ClamAVDetection", "threat",
            None, 512, "def456",
            virus_name="Eicar.Test", scanned_file="page_001.png",
        )
        assert m["virus_name"] == "Eicar.Test"
        assert m["scanned_file"] == "page_001.png"

    def test_build_manifest_stack_trace(self):
        m = qmod.build_manifest("f.doc", "doc", "LibreOfficeError", "crash", "tb here", 0, "")
        assert m["stack_trace"] == "tb here"


# ---------------------------------------------------------------------------
# sanitize
# ---------------------------------------------------------------------------

class TestReencodePng:
    def test_output_is_valid_png(self):
        img = Image.new("RGB", (16, 16), color=(255, 0, 0))
        result = reencode_png(img.tobytes(), 16, 16)
        out = Image.open(io.BytesIO(result))
        assert out.size == (16, 16)
        assert out.mode == "RGB"

    def test_pixel_values_preserved(self):
        img = Image.new("RGB", (4, 4), color=(10, 20, 30))
        result = reencode_png(img.tobytes(), 4, 4)
        out = Image.open(io.BytesIO(result))
        assert out.getpixel((0, 0)) == (10, 20, 30)

    def test_metadata_stripped(self):
        img = Image.new("RGB", (8, 8))
        raw = img.tobytes()
        result = reencode_png(raw, 8, 8)
        out = Image.open(io.BytesIO(result))
        # No EXIF, no comment, no extra chunks
        assert not out.info


# ---------------------------------------------------------------------------
# pipeline — image path, ClamAV mocked
# ---------------------------------------------------------------------------

class TestProcessFileImagePath:
    async def test_clean_image_written_to_clean_dir(self, tmp_path, monkeypatch):
        _write_png(tmp_path / "source/photo.png")
        monkeypatch.setattr("scrub.pipeline.scan_pngs", AsyncMock(return_value=ScanResult(clean=True)))

        result = await process_file(
            rel_path=Path("photo.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            quarantine_dir=tmp_path / "quarantine",
            errors_dir=tmp_path / "errors",
            socket_path="/dev/null",
        )

        assert result == "clean"
        assert (tmp_path / "clean/photo/page_001.png").exists()

    async def test_clean_image_not_in_quarantine_or_errors(self, tmp_path, monkeypatch):
        _write_png(tmp_path / "source/photo.png")
        monkeypatch.setattr("scrub.pipeline.scan_pngs", AsyncMock(return_value=ScanResult(clean=True)))

        await process_file(
            rel_path=Path("photo.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            quarantine_dir=tmp_path / "quarantine",
            errors_dir=tmp_path / "errors",
            socket_path="/dev/null",
        )

        assert not list((tmp_path / "quarantine").rglob("*.json")) if (tmp_path / "quarantine").exists() else True
        assert not list((tmp_path / "errors").rglob("*.json")) if (tmp_path / "errors").exists() else True

    async def test_detection_goes_to_quarantine(self, tmp_path, monkeypatch):
        _write_png(tmp_path / "source/bad.png")
        monkeypatch.setattr(
            "scrub.pipeline.scan_pngs",
            AsyncMock(return_value=ScanResult(clean=False, virus_name="Eicar.Test", scanned_file="page_001.png")),
        )

        result = await process_file(
            rel_path=Path("bad.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            quarantine_dir=tmp_path / "quarantine",
            errors_dir=tmp_path / "errors",
            socket_path="/dev/null",
        )

        assert result == "quarantine"
        manifest = json.loads((tmp_path / "quarantine/bad.png.json").read_text())
        assert manifest["error_type"] == "ClamAVDetection"
        assert manifest["virus_name"] == "Eicar.Test"

    async def test_detection_does_not_write_to_clean(self, tmp_path, monkeypatch):
        _write_png(tmp_path / "source/bad.png")
        monkeypatch.setattr(
            "scrub.pipeline.scan_pngs",
            AsyncMock(return_value=ScanResult(clean=False, virus_name="Eicar.Test", scanned_file="page_001.png")),
        )

        await process_file(
            rel_path=Path("bad.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            quarantine_dir=tmp_path / "quarantine",
            errors_dir=tmp_path / "errors",
            socket_path="/dev/null",
        )

        assert not (tmp_path / "clean").exists() or not list((tmp_path / "clean").rglob("*.png"))

    async def test_clamav_error_goes_to_quarantine(self, tmp_path, monkeypatch):
        _write_png(tmp_path / "source/suspect.png")
        monkeypatch.setattr(
            "scrub.pipeline.scan_pngs",
            AsyncMock(return_value=ScanResult(clean=False, error="socket timeout")),
        )

        result = await process_file(
            rel_path=Path("suspect.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            quarantine_dir=tmp_path / "quarantine",
            errors_dir=tmp_path / "errors",
            socket_path="/dev/null",
        )

        assert result == "quarantine"
        manifest = json.loads((tmp_path / "quarantine/suspect.png.json").read_text())
        assert manifest["error_type"] == "ClamAVError"

    async def test_unsupported_extension_skipped(self, tmp_path):
        src = tmp_path / "source/movie.mp4"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b"fake mp4 data")

        result = await process_file(
            rel_path=Path("movie.mp4"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            quarantine_dir=tmp_path / "quarantine",
            errors_dir=tmp_path / "errors",
            socket_path="/dev/null",
        )

        assert result == "skipped"
        assert not list((tmp_path / "errors").rglob("*")) if (tmp_path / "errors").exists() else True

    async def test_unsupported_magic_bytes_goes_to_errors(self, tmp_path, monkeypatch):
        # Extension is supported (.pdf) but magic bytes are wrong → UnsupportedFormat error
        src = tmp_path / "source/fake.pdf"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b"XXXXX not a real pdf XXXXX")
        monkeypatch.setattr("scrub.pipeline.scan_pngs", AsyncMock(return_value=ScanResult(clean=True)))

        result = await process_file(
            rel_path=Path("fake.pdf"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            quarantine_dir=tmp_path / "quarantine",
            errors_dir=tmp_path / "errors",
            socket_path="/dev/null",
        )

        assert result == "error"
        manifest = json.loads((tmp_path / "errors/fake.pdf.json").read_text())
        assert manifest["error_type"] == "UnsupportedFormat"

    async def test_file_too_large_goes_to_errors(self, tmp_path, monkeypatch):
        src = tmp_path / "source/big.png"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(_make_png())
        # Fake the stat size past the 100 MB limit
        monkeypatch.setattr("scrub.pipeline.os.stat", lambda _: type("S", (), {"st_size": 200 * 1024 * 1024})())

        result = await process_file(
            rel_path=Path("big.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            quarantine_dir=tmp_path / "quarantine",
            errors_dir=tmp_path / "errors",
            socket_path="/dev/null",
        )

        assert result == "error"
        manifest = json.loads((tmp_path / "errors/big.png.json").read_text())
        assert manifest["error_type"] == "FileTooLarge"

    async def test_subdirectory_structure_preserved(self, tmp_path, monkeypatch):
        _write_png(tmp_path / "source/reports/q1/photo.png")
        monkeypatch.setattr("scrub.pipeline.scan_pngs", AsyncMock(return_value=ScanResult(clean=True)))

        await process_file(
            rel_path=Path("reports/q1/photo.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            quarantine_dir=tmp_path / "quarantine",
            errors_dir=tmp_path / "errors",
            socket_path="/dev/null",
        )

        assert (tmp_path / "clean/reports/q1/photo/page_001.png").exists()
