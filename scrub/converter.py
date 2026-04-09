import asyncio
import os
import shutil
import tempfile
from pathlib import Path

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
    if fmt in ("xlsx", "xls"):
        # Request calc PDF export; fit-to-page depends on document's own page settings
        cmd += ["--infilter=Calc MS Excel 2007 XML"]
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
