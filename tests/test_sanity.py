"""
Basic sanity tests. No LibreOffice required — document conversion tests use the image pipeline only.
"""

import io
import json
from pathlib import Path

from PIL import Image

from scrub.converter import _block_external_fetches, _csv_to_html, _xml_to_text
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

    # Text format detection
    def test_txt_by_extension(self):
        assert detect_format(b"Hello world", "notes.txt") == "txt"

    def test_html_by_doctype(self):
        assert detect_format(b"<!DOCTYPE html><html>", "page.html") == "html"

    def test_html_by_tag(self):
        assert detect_format(b"<html><head>", "page.htm") == "html"

    def test_html_by_extension_only(self):
        assert detect_format(b"some text content", "page.html") == "html"

    def test_htm_extension(self):
        assert detect_format(b"<body>hi</body>", "page.htm") == "html"

    def test_xml_by_declaration(self):
        assert detect_format(b"<?xml version='1.0'?>", "data.xml") == "xml"

    def test_xml_by_extension(self):
        assert detect_format(b"<root><item>text</item></root>", "data.xml") == "xml"

    def test_html_bom_stripped(self):
        # UTF-8 BOM before <!DOCTYPE html>
        bom_html = b"\xef\xbb\xbf<!doctype html><html>"
        assert detect_format(bom_html, "page.html") == "html"

    def test_xml_bom_stripped(self):
        bom_xml = b"\xef\xbb\xbf<?xml version='1.0'?>"
        assert detect_format(bom_xml, "data.xml") == "xml"

    def test_html_content_overrides_txt_extension(self):
        # File named .txt but starts with HTML markers — sniff wins
        assert detect_format(b"<html><head></head>", "trick.txt") == "html"

    def test_magic_bytes_take_precedence_over_html_sniff(self):
        # ZIP magic bytes — should not be detected as html even if content follows
        assert detect_format(b"PK\x03\x04<html>", "doc.docx") == "docx"

    def test_csv_by_extension(self):
        assert detect_format(b"name,value\nalpha,1\n", "data.csv") == "csv"

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
        paths = derive_output_paths(
            tmp_path / "s", tmp_path / "c", Path("report.pdf"), 1, False
        )
        assert paths == [tmp_path / "c/report.pdf.page_001.png"]

    def test_multi_page(self, tmp_path):
        paths = derive_output_paths(
            tmp_path / "s", tmp_path / "c", Path("report.pdf"), 3, False
        )
        assert paths == [
            tmp_path / "c/report.pdf.page_001.png",
            tmp_path / "c/report.pdf.page_002.png",
            tmp_path / "c/report.pdf.page_003.png",
        ]

    def test_xlsx_sheet_prefix(self, tmp_path):
        paths = derive_output_paths(
            tmp_path / "s", tmp_path / "c", Path("budget.xlsx"), 2, True
        )
        assert paths[0].name == "budget.xlsx.sheet_001.png"
        assert paths[1].name == "budget.xlsx.sheet_002.png"

    def test_preserves_subdirectory(self, tmp_path):
        paths = derive_output_paths(
            tmp_path / "s", tmp_path / "c", Path("finance/q1/budget.pdf"), 1, False
        )
        assert paths == [tmp_path / "c/finance/q1/budget.pdf.page_001.png"]

    def test_zero_padding_to_three_digits(self, tmp_path):
        paths = derive_output_paths(
            tmp_path / "s", tmp_path / "c", Path("f.pdf"), 10, False
        )
        assert paths[9].name == "f.pdf.page_010.png"


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
# pipeline — image path
# ---------------------------------------------------------------------------


class TestProcessFileImagePath:
    async def test_clean_image_written_to_clean_dir(self, tmp_path):
        _write_png(tmp_path / "source/photo.png")

        result = await process_file(
            rel_path=Path("photo.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
        )

        assert result == "clean"
        assert (tmp_path / "clean/photo.png.page_001.png").exists()

    async def test_clean_image_not_in_errors(self, tmp_path):
        _write_png(tmp_path / "source/photo.png")

        await process_file(
            rel_path=Path("photo.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
        )

        assert (
            not list((tmp_path / "errors").rglob("*.json"))
            if (tmp_path / "errors").exists()
            else True
        )

    async def test_unsupported_extension_skipped(self, tmp_path):
        src = tmp_path / "source/movie.mp4"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b"fake mp4 data")

        result = await process_file(
            rel_path=Path("movie.mp4"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
        )

        assert result == "skipped"
        assert (
            not list((tmp_path / "errors").rglob("*"))
            if (tmp_path / "errors").exists()
            else True
        )

    async def test_unsupported_magic_bytes_goes_to_errors(self, tmp_path):
        # Extension is supported (.pdf) but magic bytes are wrong → UnsupportedFormat error
        src = tmp_path / "source/fake.pdf"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b"XXXXX not a real pdf XXXXX")

        result = await process_file(
            rel_path=Path("fake.pdf"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
        )

        assert result == "error"
        manifest = json.loads((tmp_path / "errors/fake.pdf.json").read_text())
        assert manifest["error_type"] == "UnsupportedFormat"

    async def test_file_too_large_goes_to_errors(self, tmp_path, monkeypatch):
        src = tmp_path / "source/big.png"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(_make_png())
        # Fake the stat size past the 100 MB limit
        monkeypatch.setattr(
            "scrub.pipeline.os.stat",
            lambda _: type("S", (), {"st_size": 200 * 1024 * 1024})(),
        )

        result = await process_file(
            rel_path=Path("big.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
        )

        assert result == "error"
        manifest = json.loads((tmp_path / "errors/big.png.json").read_text())
        assert manifest["error_type"] == "FileTooLarge"

    async def test_subdirectory_structure_preserved(self, tmp_path):
        _write_png(tmp_path / "source/reports/q1/photo.png")

        await process_file(
            rel_path=Path("reports/q1/photo.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
        )

        assert (tmp_path / "clean/reports/q1/photo.png.page_001.png").exists()

    async def test_already_clean_skipped(self, tmp_path):
        _write_png(tmp_path / "source/photo.png")
        # Pre-populate clean output so the file appears already processed
        sentinel = tmp_path / "clean/photo.png.page_001.png"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_bytes(b"fake")

        result = await process_file(
            rel_path=Path("photo.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
        )

        assert result == "skipped"
        assert sentinel.read_bytes() == b"fake"  # not overwritten

    async def test_already_clean_skipped_subdir(self, tmp_path):
        _write_png(tmp_path / "source/reports/q1/photo.png")
        sentinel = tmp_path / "clean/reports/q1/photo.png.page_001.png"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_bytes(b"fake")

        result = await process_file(
            rel_path=Path("reports/q1/photo.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
        )

        assert result == "skipped"
        assert sentinel.read_bytes() == b"fake"  # not overwritten


# ---------------------------------------------------------------------------
# _block_external_fetches
# ---------------------------------------------------------------------------


class TestBlockExternalFetches:
    def test_raises_on_http_url(self):
        import pytest

        with pytest.raises(ValueError, match="external fetch blocked"):
            _block_external_fetches("http://example.com/beacon.png")

    def test_raises_on_https_url(self):
        import pytest

        with pytest.raises(ValueError, match="external fetch blocked"):
            _block_external_fetches("https://example.com/style.css")

    def test_passes_data_uri(self):
        # A data URI should not raise our ValueError — it's inline content
        uri = "data:text/plain;base64,SGVsbG8="
        try:
            _block_external_fetches(uri)
        except Exception as exc:
            assert "external fetch blocked" not in str(exc)


# ---------------------------------------------------------------------------
# _csv_to_html
# ---------------------------------------------------------------------------


class TestCsvToHtml:
    def test_formula_injection_escaped(self):
        raw = b"name,value\n=CMD|'/c calc'!A1,evil\n"
        result = _csv_to_html(raw)
        assert "<script" not in result
        # Formula cell text is present as literal text, not evaluated
        assert "=CMD" in result

    def test_html_injection_escaped(self):
        raw = b'name,payload\nalpha,"<script>alert(1)</script>"\n'
        result = _csv_to_html(raw)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_table_structure(self):
        raw = b"a,b\n1,2\n"
        result = _csv_to_html(raw)
        assert "<table>" in result
        assert "<td>a</td>" in result
        assert "<td>1</td>" in result

    def test_empty_csv(self):
        result = _csv_to_html(b"")
        assert "<table>" in result  # empty table, no crash


# ---------------------------------------------------------------------------
# _xml_to_text
# ---------------------------------------------------------------------------


class TestXmlToText:
    def test_extracts_text_nodes(self):
        xml = b"<?xml version='1.0'?><root><a>Hello</a><b>World</b></root>"
        result = _xml_to_text(xml)
        assert "Hello" in result
        assert "World" in result

    def test_discards_tags(self):
        xml = b"<root><item>text</item></root>"
        result = _xml_to_text(xml)
        assert "<item>" not in result
        assert "<root>" not in result

    def test_malformed_xml_fallback(self):
        bad = b"this is not xml at all <<<<"
        result = _xml_to_text(bad)
        assert "this is not xml" in result

    def test_xxe_blocked(self):
        xxe = (
            b"<?xml version='1.0'?>"
            b"<!DOCTYPE foo [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]>"
            b"<root>&xxe;</root>"
        )
        # defusedxml raises; fallback renders raw bytes — must not contain passwd contents
        result = _xml_to_text(xxe)
        assert "/root:" not in result


# ---------------------------------------------------------------------------
# pipeline — text format path (text_to_pdf mocked)
# ---------------------------------------------------------------------------


class TestProcessFileTextPath:
    async def test_txt_file_routed_to_text_path(self, tmp_path, monkeypatch):
        src = tmp_path / "source/notes.txt"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("Hello scrub")

        def _fake_text_to_pdf(raw, fmt):
            import os
            import tempfile

            import fitz

            doc = fitz.open()
            page = doc.new_page()
            page.insert_text((72, 72), raw.decode("utf-8", errors="replace"))
            fd, path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            doc.save(path)
            doc.close()
            return Path(path)

        monkeypatch.setattr("scrub.pipeline.text_to_pdf", _fake_text_to_pdf)

        result = await process_file(
            rel_path=Path("notes.txt"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
        )

        assert result == "clean"
        assert (tmp_path / "clean/notes.txt.page_001.png").exists()

    async def test_csv_uses_sheet_naming(self, tmp_path, monkeypatch):
        src = tmp_path / "source/data.csv"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("a,b\n1,2\n")

        def _fake_text_to_pdf(raw, fmt):
            import os
            import tempfile

            import fitz

            doc = fitz.open()
            doc.new_page()
            fd, path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            doc.save(path)
            doc.close()
            return Path(path)

        monkeypatch.setattr("scrub.pipeline.text_to_pdf", _fake_text_to_pdf)

        result = await process_file(
            rel_path=Path("data.csv"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
        )

        assert result == "clean"
        assert (tmp_path / "clean/data.csv.sheet_001.png").exists()
