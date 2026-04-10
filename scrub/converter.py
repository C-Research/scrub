import asyncio
import csv
import html
import io
import os
import shutil
import tempfile
from pathlib import Path

import defusedxml.ElementTree as _safe_et
import fitz  # PyMuPDF

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
    profile_dir = Path(tempfile.mkdtemp(prefix="lo_profile_"))
    out_dir = Path(tempfile.mkdtemp(prefix="lo_out_"))

    try:
        _setup_lo_profile(profile_dir)

        proc = await asyncio.create_subprocess_exec(
            *_lo_cmd(input_path, fmt, profile_dir, out_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
