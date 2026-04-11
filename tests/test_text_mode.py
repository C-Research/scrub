"""
Tests for SCRUB_OUTPUT_MODE=text — text extraction pipeline.
No LibreOffice required for most tests; LO-dependent tests are skipped if unavailable.
"""

import io
import shutil
from pathlib import Path

import fitz
import pytest
from PIL import Image

from scrub.cli import _output_mode
from scrub.converter import extract_plain_text, extract_text_from_pdf
from scrub.pipeline import process_file

FIXTURES = Path(__file__).parent / "fixtures"

_HAS_LO = shutil.which("libreoffice") is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_pdf(
    text: str = "This document has sufficient text content for extraction purposes here.",
) -> bytes:
    """Create a single-page PDF with an embedded text layer (>50 non-whitespace chars)."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _make_blank_pdf() -> bytes:
    """Create a PDF with an empty page (no text layer — simulates scanned document)."""
    doc = fitz.open()
    doc.new_page()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _make_multipage_text_pdf(pages: list[str]) -> bytes:
    """Create a multi-page PDF with text on each page."""
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _make_png(width: int = 8, height: int = 8) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(128, 64, 32)).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Unit: extract_text_from_pdf
# ---------------------------------------------------------------------------


class TestExtractTextFromPdf:
    def test_text_pdf_returns_page_strings(self, tmp_path):
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(_make_text_pdf())

        result = extract_text_from_pdf(pdf_path)

        assert result is not None
        assert len(result) == 1
        assert "sufficient text content" in result[0]

    def test_multipage_pdf_returns_one_string_per_page(self, tmp_path):
        pages_text = [
            "Page one has enough words to exceed the detection threshold here.",
            "Page two also has enough words to exceed the detection threshold here.",
        ]
        pdf_path = tmp_path / "multi.pdf"
        pdf_path.write_bytes(_make_multipage_text_pdf(pages_text))

        result = extract_text_from_pdf(pdf_path)

        assert result is not None
        assert len(result) == 2
        assert "Page one" in result[0]
        assert "Page two" in result[1]

    def test_blank_pdf_returns_none(self, tmp_path):
        pdf_path = tmp_path / "blank.pdf"
        pdf_path.write_bytes(_make_blank_pdf())

        result = extract_text_from_pdf(pdf_path)

        assert result is None

    def test_below_threshold_returns_none(self, tmp_path):
        # Insert fewer than 50 non-whitespace characters (2 non-ws chars)
        pdf_path = tmp_path / "sparse.pdf"
        pdf_path.write_bytes(_make_text_pdf("Hi"))

        result = extract_text_from_pdf(pdf_path)

        assert result is None


# ---------------------------------------------------------------------------
# Integration: process_file in text mode — PDF path (no LO needed)
# ---------------------------------------------------------------------------


class TestProcessFileTextModePdf:
    async def test_text_pdf_produces_txt_file(self, tmp_path):
        src = tmp_path / "source/report.pdf"
        src.parent.mkdir(parents=True)
        src.write_bytes(_make_text_pdf())

        result = await process_file(
            rel_path=Path("report.pdf"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="text",
        )

        assert result == "clean"
        txt_file = tmp_path / "clean/report.pdf.txt"
        assert txt_file.exists()
        content = txt_file.read_text(encoding="utf-8")
        assert "sufficient text content" in content

    async def test_scanned_pdf_falls_back_to_png(self, tmp_path):
        src = tmp_path / "source/scan.pdf"
        src.parent.mkdir(parents=True)
        src.write_bytes(_make_blank_pdf())

        result = await process_file(
            rel_path=Path("scan.pdf"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="text",
        )

        assert result == "clean"
        assert not (tmp_path / "clean/scan.pdf.txt").exists()
        assert list((tmp_path / "clean").rglob("*.png"))

    async def test_multipage_pdf_uses_formfeed_separator(self, tmp_path):
        src = tmp_path / "source/multi.pdf"
        src.parent.mkdir(parents=True)
        src.write_bytes(_make_multipage_text_pdf([
            "First page has some words here.",
            "Second page has different words.",
        ]))

        await process_file(
            rel_path=Path("multi.pdf"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="text",
        )

        content = (tmp_path / "clean/multi.pdf.txt").read_text(encoding="utf-8")
        assert "\f" in content

    async def test_already_clean_skipped_in_text_mode(self, tmp_path):
        src = tmp_path / "source/report.pdf"
        src.parent.mkdir(parents=True)
        src.write_bytes(_make_text_pdf())

        # Pre-create the output
        txt_file = tmp_path / "clean/report.pdf.txt"
        txt_file.parent.mkdir(parents=True)
        txt_file.write_text("already done", encoding="utf-8")

        result = await process_file(
            rel_path=Path("report.pdf"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="text",
        )

        assert result == "skipped"


# ---------------------------------------------------------------------------
# Integration: image input always falls back to PNG in text mode
# ---------------------------------------------------------------------------


class TestProcessFileTextModeImageFallback:
    async def test_jpg_in_text_mode_produces_png(self, tmp_path):
        # Write a valid JPEG (use PNG bytes but with .jpg — Pillow handles it;
        # we'll just write real PNG bytes and name it .png since magic bytes matter)
        src = tmp_path / "source/photo.png"
        src.parent.mkdir(parents=True)
        src.write_bytes(_make_png())

        result = await process_file(
            rel_path=Path("photo.png"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="text",
        )

        assert result == "clean"
        assert not (tmp_path / "clean/photo.png.txt").exists()
        assert (tmp_path / "clean/photo.png.page_001.png").exists()


# ---------------------------------------------------------------------------
# Integration: LO-dependent (DOCX / XLSX) — skipped without LibreOffice
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_LO, reason="LibreOffice not installed")
class TestProcessFileTextModeLO:
    async def test_docx_produces_txt(self, tmp_path):
        src = tmp_path / "source/doc.doc"
        src.parent.mkdir(parents=True)
        src.write_bytes((FIXTURES / "eicar-word-macro-powershell-echo.doc").read_bytes())

        result = await process_file(
            rel_path=Path("doc.doc"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="text",
        )

        # Result is clean (txt) or clean (png fallback if scanned) — never error
        assert result == "clean"

    async def test_xls_produces_txt_or_png_fallback(self, tmp_path):
        src = tmp_path / "source/sheet.xls"
        src.parent.mkdir(parents=True)
        src.write_bytes((FIXTURES / "eicar-excel-macro-powershell-echo.xls").read_bytes())

        result = await process_file(
            rel_path=Path("sheet.xls"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="text",
        )

        assert result == "clean"


# ---------------------------------------------------------------------------
# Unit: SCRUB_OUTPUT_MODE env var validation
# ---------------------------------------------------------------------------


class TestOutputModeEnvVar:
    def test_unset_defaults_to_png(self, monkeypatch):
        monkeypatch.delenv("SCRUB_OUTPUT_MODE", raising=False)
        assert _output_mode() == "png"

    def test_png_explicit(self, monkeypatch):
        monkeypatch.setenv("SCRUB_OUTPUT_MODE", "png")
        assert _output_mode() == "png"

    def test_text_mode(self, monkeypatch):
        monkeypatch.setenv("SCRUB_OUTPUT_MODE", "text")
        assert _output_mode() == "text"

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("SCRUB_OUTPUT_MODE", "TEXT")
        assert _output_mode() == "text"

    def test_invalid_value_exits_1(self, monkeypatch):
        monkeypatch.setenv("SCRUB_OUTPUT_MODE", "html")
        with pytest.raises(SystemExit) as exc:
            _output_mode()
        assert exc.value.code == 1


# ---------------------------------------------------------------------------
# Unit: extract_plain_text
# ---------------------------------------------------------------------------


class TestExtractPlainText:
    def test_txt_passthrough(self):
        raw = b"hello world\nline two"
        assert extract_plain_text(raw, "txt") == "hello world\nline two"

    def test_csv_passthrough(self):
        raw = b"name,age\nAlice,30\nBob,25"
        assert extract_plain_text(raw, "csv") == "name,age\nAlice,30\nBob,25"

    def test_html_strips_tags(self):
        raw = b"<html><body><p>Hello <b>world</b></p></body></html>"
        result = extract_plain_text(raw, "html")
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result
        assert ">" not in result

    def test_html_excludes_script_body(self):
        raw = b"<html><body><script>var x = 1;</script><p>visible</p></body></html>"
        result = extract_plain_text(raw, "html")
        assert "visible" in result
        assert "var x" not in result

    def test_html_excludes_style_body(self):
        raw = b"<html><head><style>body { color: red; }</style></head><body>text</body></html>"
        result = extract_plain_text(raw, "htm")
        assert "text" in result
        assert "color" not in result

    def test_xml_extracts_element_text(self):
        raw = b"<root><item>first</item><item>second</item></root>"
        result = extract_plain_text(raw, "xml")
        assert "first" in result
        assert "second" in result
        assert "<" not in result

    def test_xml_malformed_falls_back_to_raw(self):
        raw = b"not valid xml <<<<"
        result = extract_plain_text(raw, "xml")
        assert "not valid xml" in result


# ---------------------------------------------------------------------------
# Integration: text formats in text mode produce .txt
# ---------------------------------------------------------------------------


class TestProcessFileTextModeTextFormats:
    async def test_txt_in_text_mode_produces_txt(self, tmp_path):
        src = tmp_path / "source/notes.txt"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"hello from a text file")

        result = await process_file(
            rel_path=Path("notes.txt"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="text",
        )

        assert result == "clean"
        out = tmp_path / "clean/notes.txt.txt"
        assert out.exists()
        assert "hello from a text file" in out.read_text(encoding="utf-8")

    async def test_csv_in_text_mode_produces_txt(self, tmp_path):
        src = tmp_path / "source/data.csv"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"col1,col2\nfoo,bar\nbaz,qux")

        result = await process_file(
            rel_path=Path("data.csv"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="text",
        )

        assert result == "clean"
        out = tmp_path / "clean/data.csv.txt"
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "col1" in content
        assert "foo" in content

    async def test_html_in_text_mode_strips_tags(self, tmp_path):
        src = tmp_path / "source/page.html"
        src.parent.mkdir(parents=True)
        src.write_bytes(
            b"<html><body><script>evil()</script><p>clean content</p></body></html>"
        )

        result = await process_file(
            rel_path=Path("page.html"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="text",
        )

        assert result == "clean"
        out = tmp_path / "clean/page.html.txt"
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "clean content" in content
        assert "evil()" not in content
        assert "<" not in content

    async def test_xml_in_text_mode_extracts_text(self, tmp_path):
        src = tmp_path / "source/feed.xml"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"<?xml version='1.0'?><root><entry>extracted text</entry></root>")

        result = await process_file(
            rel_path=Path("feed.xml"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="text",
        )

        assert result == "clean"
        out = tmp_path / "clean/feed.xml.txt"
        assert out.exists()
        assert "extracted text" in out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Regression: text formats in PNG mode still produce PNG via WeasyPrint
# ---------------------------------------------------------------------------


class TestPngModeTextFormatsRegression:
    async def test_txt_in_png_mode_produces_png(self, tmp_path):
        src = tmp_path / "source/notes.txt"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"some plain text content")

        result = await process_file(
            rel_path=Path("notes.txt"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="png",
        )

        assert result == "clean"
        assert not (tmp_path / "clean/notes.txt.txt").exists()
        assert list((tmp_path / "clean").rglob("*.png"))

    async def test_html_in_png_mode_produces_png(self, tmp_path):
        src = tmp_path / "source/page.html"
        src.parent.mkdir(parents=True)
        src.write_bytes(b"<html><body><p>hello</p></body></html>")

        result = await process_file(
            rel_path=Path("page.html"),
            source_dir=tmp_path / "source",
            clean_dir=tmp_path / "clean",
            errors_dir=tmp_path / "errors",
            output_mode="png",
        )

        assert result == "clean"
        assert not (tmp_path / "clean/page.html.txt").exists()
        assert list((tmp_path / "clean").rglob("*.png"))
