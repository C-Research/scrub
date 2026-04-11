import asyncio
import csv
import html
import io
import os
import random
import shutil
import tempfile
from html.parser import HTMLParser
from pathlib import Path

import defusedxml.ElementTree as _safe_et
import fitz  # PyMuPDF

# Semaphore capping concurrent LibreOffice processes. Multiple simultaneous
# LO instances contend over system resources (pipes, process table, gVisor
# limits) and fail with EAGAIN. Default: 1. Override with SCRUB_LO_WORKERS env var.
_lo_sem: asyncio.Semaphore | None = None

# Retry up to this many times on EAGAIN before surfacing the error.
_LO_RETRIES = 3
_LO_RETRY_BASE = 0.5  # seconds; doubled each attempt
_EAGAIN_PHRASES = ("resource temporarily unavailable", "try again later", "eagain")


def _is_eagain(e: "ConversionError") -> bool:
    return any(p in e.detail.lower() for p in _EAGAIN_PHRASES)


def _lo_semaphore() -> asyncio.Semaphore:
    global _lo_sem
    if _lo_sem is None:
        # Default 1: each LibreOffice instance spawns ~50 threads; in gVisor/containers
        # running multiple concurrently exhausts thread/PID table limits quickly.
        # Raise via SCRUB_LO_WORKERS if your host can sustain more.
        default = 1
        limit = max(1, int(os.environ.get("SCRUB_LO_WORKERS", str(default)) or str(default)))
        _lo_sem = asyncio.Semaphore(limit)
    return _lo_sem


# Macro security level 4 = no macros run
_MACRO_SECURITY_XCU = """\
<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry"
           xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <item oor:path="/org.openoffice.Office.Common/Security/Scripting">
    <prop oor:name="MacroSecurityLevel" oor:op="fuse">
      <value>4</value>
    </prop>
  </item>
</oor:items>
"""


class ConversionError(Exception):
    def __init__(self, error_type: str, detail: str):
        self.error_type = error_type
        self.detail = detail
        super().__init__(detail)


def _setup_lo_profile(profile_dir: Path) -> None:
    user_dir = profile_dir / "user"
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "registrymodifications.xcu").write_text(
        _MACRO_SECURITY_XCU, encoding="utf-8"
    )


def _lo_cmd(input_path: Path, fmt: str, profile_dir: Path, out_dir: Path) -> list[str]:
    cmd = [
        "libreoffice",
        "--headless",
        "--norestore",
        f"-env:UserInstallation=file://{profile_dir}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
    ]
    if fmt == "xlsx":
        # Explicit filter for XLSX (Open XML); XLS (OLE binary) auto-detects correctly
        cmd += ["--infilter=Calc MS Excel 2007 XML"]
    if fmt == "csv":
        cmd += ["--infilter=Text - txt - csv (StarCalc)"]
    cmd.append(str(input_path))
    return cmd


async def convert_to_pdf(
    input_path: Path,
    fmt: str,
    timeout: int = 60,
) -> Path:
    """Convert office document to PDF via LibreOffice. Returns path to temp PDF; caller deletes it."""
    for attempt in range(_LO_RETRIES):
        async with _lo_semaphore():
            try:
                return await _convert_to_pdf(input_path, fmt, timeout)
            except ConversionError as e:
                if _is_eagain(e) and attempt < _LO_RETRIES - 1:
                    pass  # release semaphore, back off, retry
                else:
                    raise
        await asyncio.sleep(_LO_RETRY_BASE * (2**attempt) + random.uniform(0, _LO_RETRY_BASE))
    raise ConversionError("LibreOfficeError", "LibreOffice resource unavailable after retries")


async def _convert_to_pdf(input_path: Path, fmt: str, timeout: int) -> Path:
    profile_dir = Path(tempfile.mkdtemp(prefix="lo_profile_"))
    out_dir = Path(tempfile.mkdtemp(prefix="lo_out_"))

    try:
        _setup_lo_profile(profile_dir)

        try:
            proc = await asyncio.create_subprocess_exec(
                *_lo_cmd(input_path, fmt, profile_dir, out_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (BlockingIOError, OSError) as exc:
            raise ConversionError(
                "LibreOfficeError",
                f"resource temporarily unavailable: {exc}",
            )

        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise ConversionError(
                "LibreOfficeTimeout",
                f"LibreOffice exceeded {timeout}s timeout",
            )

        if proc.returncode != 0:
            err = stderr.decode(errors="replace").strip()
            raise ConversionError(
                "LibreOfficeError",
                f"LibreOffice exited {proc.returncode}: {err[:500]}",
            )

        pdfs = list(out_dir.glob("*.pdf"))
        if not pdfs:
            raise ConversionError(
                "LibreOfficeError", "LibreOffice produced no PDF output"
            )

        # Move PDF out so we can clean up out_dir
        fd, _pdf_dest = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        pdf_dest = Path(_pdf_dest)
        shutil.move(str(pdfs[0]), pdf_dest)
        return pdf_dest

    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)


async def convert_to_txt(
    input_path: Path,
    fmt: str,
    timeout: int = 60,
) -> str:
    """Convert office document to plain text via LibreOffice. Returns text content as a string."""
    for attempt in range(_LO_RETRIES):
        async with _lo_semaphore():
            try:
                return await _convert_to_txt(input_path, fmt, timeout)
            except ConversionError as e:
                if _is_eagain(e) and attempt < _LO_RETRIES - 1:
                    pass
                else:
                    raise
        await asyncio.sleep(_LO_RETRY_BASE * (2**attempt) + random.uniform(0, _LO_RETRY_BASE))
    raise ConversionError("LibreOfficeError", "LibreOffice resource unavailable after retries")


async def _convert_to_txt(input_path: Path, fmt: str, timeout: int) -> str:
    profile_dir = Path(tempfile.mkdtemp(prefix="lo_profile_"))
    out_dir = Path(tempfile.mkdtemp(prefix="lo_out_"))

    try:
        _setup_lo_profile(profile_dir)

        _CALC_FORMATS = {"xls", "xlsx"}
        convert_to_arg = (
            "txt:Text - txt - csv (StarCalc)"
            if fmt in _CALC_FORMATS
            else "txt:Text"
        )

        cmd = [
            "libreoffice",
            "--headless",
            "--norestore",
            f"-env:UserInstallation=file://{profile_dir}",
            "--convert-to",
            convert_to_arg,
            "--outdir",
            str(out_dir),
        ]
        if fmt == "xlsx":
            cmd += ["--infilter=Calc MS Excel 2007 XML"]
        cmd.append(str(input_path))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (BlockingIOError, OSError) as exc:
            raise ConversionError(
                "LibreOfficeError",
                f"resource temporarily unavailable: {exc}",
            )

        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            raise ConversionError(
                "LibreOfficeTimeout",
                f"LibreOffice exceeded {timeout}s timeout",
            )

        if proc.returncode != 0:
            err = stderr.decode(errors="replace").strip()
            raise ConversionError(
                "LibreOfficeError",
                f"LibreOffice exited {proc.returncode}: {err[:500]}",
            )

        txts = list(out_dir.glob("*.txt"))
        if not txts:
            raise ConversionError(
                "LibreOfficeError", "LibreOffice produced no text output"
            )

        return txts[0].read_text(encoding="utf-8", errors="replace")

    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)


_SCANNED_THRESHOLD = 50  # non-whitespace chars below this → treat as scanned

_SPREADSHEET_FORMATS = {"xlsx", "xls", "csv"}


def is_spreadsheet_fmt(fmt: str) -> bool:
    return fmt in _SPREADSHEET_FORMATS


def extract_text_from_pdf(pdf_path: Path) -> list[str] | None:
    """Extract per-page text from a PDF via PyMuPDF.

    Returns a list of strings (one per page), or None if the document appears
    to be scanned (total non-whitespace chars below threshold).
    """
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        raise ConversionError("PyMuPDFError", f"fitz.open failed: {e}")

    try:
        if doc.page_count == 0:
            raise ConversionError("EmptyDocument", "PDF has zero pages")

        texts = []
        for page in doc:
            try:
                texts.append(page.get_text())
            except Exception as e:
                raise ConversionError(
                    "PyMuPDFError", f"page {page.number} text extraction failed: {e}"
                )

        total_nonws = sum(1 for c in "".join(texts) if not c.isspace())
        if total_nonws < _SCANNED_THRESHOLD:
            return None  # treat as scanned, caller should fall back to PNG
        return texts
    finally:
        doc.close()


def rasterize_pdf(pdf_path: Path) -> list[tuple[bytes, int, int]]:
    """Rasterize each PDF page to raw RGB bytes. Returns list of (rgb_bytes, width, height)."""
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        raise ConversionError("PyMuPDFError", f"fitz.open failed: {e}")

    try:
        if doc.page_count == 0:
            raise ConversionError("EmptyDocument", "PDF has zero pages")

        mat = fitz.Matrix(150 / 72, 150 / 72)  # ~150 dpi
        results = []
        for page in doc:
            try:
                pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
                results.append((bytes(pix.samples), pix.width, pix.height))
            except Exception as e:
                raise ConversionError(
                    "PyMuPDFError", f"page {page.number} render failed: {e}"
                )
        return results
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Text-format extractor (text mode — no WeasyPrint)
# ---------------------------------------------------------------------------


class _TextExtractor(HTMLParser):
    """Strip HTML tags; suppress content inside <script> and <style> elements."""

    _SUPPRESS = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._suppress_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SUPPRESS:
            self._suppress_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SUPPRESS and self._suppress_depth > 0:
            self._suppress_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._suppress_depth == 0:
            self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def extract_plain_text(raw: bytes, fmt: str) -> str:
    """Extract plain text from a text-format file (txt, csv, html, htm, xml).

    txt/csv: UTF-8 passthrough.
    html/htm: tags stripped, <script>/<style> bodies excluded.
    xml: element text extracted via defusedxml itertext.
    """
    if fmt in ("txt", "csv"):
        return raw.decode("utf-8", errors="replace")
    if fmt in ("html", "htm"):
        parser = _TextExtractor()
        parser.feed(raw.decode("utf-8", errors="replace"))
        return parser.get_text()
    if fmt == "xml":
        try:
            root = _safe_et.fromstring(raw)
            return "\n".join(t for t in root.itertext() if t.strip())
        except Exception:
            return raw.decode("utf-8", errors="replace")
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Text-format renderer (weasyprint)
# ---------------------------------------------------------------------------

_HTML_WRAPPER = """\
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body{{margin:1em;font-family:monospace;white-space:pre-wrap;word-break:break-all}}
table{{border-collapse:collapse;font-family:sans-serif;font-size:0.85em}}
td,th{{border:1px solid #ccc;padding:3px 6px}}</style>
</head><body>{content}</body></html>"""


def _block_external_fetches(url: str) -> dict:
    """weasyprint url_fetcher — passes data: URIs, blocks everything else."""
    if url.startswith("data:"):
        import weasyprint

        return weasyprint.default_url_fetcher(url)
    raise ValueError(f"external fetch blocked: {url}")


def _txt_to_html(text: str) -> str:
    return _HTML_WRAPPER.format(content=html.escape(text))


def _csv_to_html(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    cells = "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    content = f"<table>{cells}</table>"
    return _HTML_WRAPPER.format(content=content)


def _xml_to_text(raw: bytes) -> str:
    try:
        root = _safe_et.fromstring(raw)
        text = "\n".join(t for t in root.itertext() if t.strip())
    except Exception:
        text = raw.decode("utf-8", errors="replace")
    return _txt_to_html(text)


def text_to_pdf(raw: bytes, fmt: str) -> Path:
    """Convert a text-based file to PDF via weasyprint. Returns temp PDF path; caller deletes."""
    if fmt == "csv":
        markup = _csv_to_html(raw)
    elif fmt == "xml":
        markup = _xml_to_text(raw)
    else:
        # txt, html, htm — html/htm rendered directly; txt wrapped in <pre>
        if fmt in ("html", "htm"):
            markup = raw.decode("utf-8", errors="replace")
        else:
            markup = _txt_to_html(raw.decode("utf-8", errors="replace"))

    try:
        import weasyprint

        pdf_bytes = weasyprint.HTML(
            string=markup, url_fetcher=_block_external_fetches
        ).write_pdf()
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError("TextRenderError", f"weasyprint failed: {e}")

    fd, _pdf_dest = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    pdf_dest = Path(_pdf_dest)
    try:
        pdf_dest.write_bytes(pdf_bytes)
    except Exception as e:
        pdf_dest.unlink(missing_ok=True)
        raise ConversionError("TextRenderError", f"PDF write failed: {e}")
    return pdf_dest
