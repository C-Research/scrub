import asyncio
import hashlib
import os
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import fs, log, sanitize
from .converter import ConversionError, convert_to_pdf, rasterize_pdf, text_to_pdf


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name, "").strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        print(f"ERROR: {name} must be an integer, got {val!r}", file=sys.stderr)
        sys.exit(1)


_MAX_SIZE = _env_int("SCRUB_MAX_FILE_SIZE", 100) * 1024 * 1024

# (magic_bytes_prefix, format_string)
_MAGIC: list[tuple[bytes, str]] = [
    (b"%PDF", "pdf"),
    (b"PK\x03\x04", "zip"),  # DOCX, XLSX, PPTX (ZIP-based Office)
    (b"\xd0\xcf\x11\xe0", "ole"),  # DOC, XLS, PPT (OLE/CFB)
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
    (b"II*\x00", "tiff"),
    (b"MM\x00*", "tiff"),
    (b"BM", "bmp"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
]

_ZIP_EXT_MAP = {".docx": "docx", ".pptx": "pptx", ".xlsx": "xlsx"}
_OLE_EXT_MAP = {".doc": "doc", ".ppt": "ppt", ".xls": "xls"}
_IMAGE_FORMATS = {"png", "jpg", "tiff", "bmp", "gif"}
_OFFICE_FORMATS = {"pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt"}
_TEXT_FORMATS = {"txt", "html", "htm", "xml", "csv"}

_SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
    ".png",
    ".jpg",
    ".jpeg",
    ".tiff",
    ".tif",
    ".bmp",
    ".gif",
    ".csv",
    ".txt",
    ".html",
    ".htm",
    ".xml",
}


_UTF8_BOM = b"\xef\xbb\xbf"
_HTML_SNIFF = (b"<!doctype html", b"<html", b"<head", b"<body")


def _sniff_text_format(header: bytes, ext: str) -> str | None:
    """Return a text format string if the header/extension match, else None."""
    sniff = header.lstrip(_UTF8_BOM).lower()
    if any(sniff.startswith(marker) for marker in _HTML_SNIFF):
        return "html"
    if sniff.startswith(b"<?xml"):
        return "xml"
    if ext == ".html" or ext == ".htm":
        return "html"
    if ext == ".xml":
        return "xml"
    if ext == ".txt":
        return "txt"
    if ext == ".csv":
        return "csv"
    return None


def detect_format(header: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    for magic, fmt in _MAGIC:
        if header[: len(magic)] == magic:
            if fmt == "zip":
                return _ZIP_EXT_MAP.get(ext, "docx")
            if fmt == "ole":
                return _OLE_EXT_MAP.get(ext, "doc")
            return fmt
    text_fmt = _sniff_text_format(header[:512], ext)
    if text_fmt:
        return text_fmt
    return "unknown"


async def process_file(
    rel_path: Path,
    source_dir: Path,
    clean_dir: Path,
    errors_dir: Path,
    timeout: int = 60,
) -> str:
    """Process one file. Returns 'clean', 'skipped', or 'error'."""
    src = source_dir / rel_path
    rel_str = str(rel_path)

    # Skip unsupported extensions before any file I/O
    ext = rel_path.suffix.lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        log.skip(rel_str, ext)
        return "skipped"

    # Skip if clean output already exists
    out_dir = clean_dir / rel_path.parent
    sentinel = (f"{rel_path.name}.page_", f"{rel_path.name}.sheet_")
    try:
        with os.scandir(out_dir) as it:
            if any(e.name.startswith(sentinel) for e in it):
                log.skip(rel_str, "already_clean")
                return "skipped"
    except OSError:
        pass

    # Pre-flight: size check before reading full file
    try:
        file_size = os.stat(src).st_size
    except OSError as e:
        await _error(
            rel_str,
            errors_dir,
            rel_path,
            "unknown",
            "UnexpectedError",
            str(e),
            traceback.format_exc(),
            0,
            "",
        )
        return "error"

    if file_size > _MAX_SIZE:
        await _error(
            rel_str,
            errors_dir,
            rel_path,
            "unknown",
            "FileTooLarge",
            f"File size {file_size} exceeds {_MAX_SIZE} byte limit",
            None,
            file_size,
            "",
        )
        return "error"

    # Read file and hash
    raw = src.read_bytes()
    file_sha256 = hashlib.sha256(raw).hexdigest()
    log.debug(rel_str, "READ", f"size={file_size}  sha256={file_sha256[:16]}…")

    # Format detection from magic bytes
    fmt = detect_format(raw[:16], rel_path.name)
    log.start(rel_str, fmt)

    if fmt not in _IMAGE_FORMATS and fmt not in _OFFICE_FORMATS and fmt not in _TEXT_FORMATS:
        await _error(
            rel_str,
            errors_dir,
            rel_path,
            "unknown",
            "UnsupportedFormat",
            "Unrecognized magic bytes",
            None,
            file_size,
            file_sha256,
        )
        return "error"

    try:
        if fmt in _IMAGE_FORMATS:
            log.debug(rel_str, "PROCESS", "path=image")
            pages = await _process_image(raw, fmt)
        elif fmt in _TEXT_FORMATS:
            log.debug(rel_str, "PROCESS", "path=text  step=weasyprint→pdf")
            pages = await _process_text_document(raw, fmt)
        else:
            log.debug(rel_str, "PROCESS", "path=document  step=libreoffice→pdf")
            pages = await _process_document(raw, fmt, timeout)

        if isinstance(pages, ConversionError):
            await _error(
                rel_str,
                errors_dir,
                rel_path,
                fmt,
                pages.error_type,
                pages.detail,
                None,
                file_size,
                file_sha256,
            )
            return "error"

        log.debug(rel_str, "PROCESS", f"step=rasterized  pages={len(pages)}")

        # Write to clean dir
        is_xlsx = fmt in ("xlsx", "xls", "csv")
        out_paths = fs.derive_output_paths(
            source_dir, clean_dir, rel_path, len(pages), is_xlsx
        )
        for out_path, png_data in zip(out_paths, pages):
            if not png_data:
                continue
            log.debug(rel_str, "WRITE", str(out_path))
            await fs.write_png(out_path, png_data)

        log.success(rel_str, len(pages))
        return "clean"

    except ConversionError as e:
        await _error(
            rel_str,
            errors_dir,
            rel_path,
            fmt,
            e.error_type,
            e.detail,
            traceback.format_exc(),
            file_size,
            file_sha256,
        )
        return "error"
    except Exception as e:
        await _error(
            rel_str,
            errors_dir,
            rel_path,
            fmt,
            "UnexpectedError",
            str(e),
            traceback.format_exc(),
            file_size,
            file_sha256,
        )
        return "error"


async def _process_image(raw: bytes, fmt: str) -> list[bytes] | ConversionError:
    loop = asyncio.get_running_loop()
    fd, _tmp = tempfile.mkstemp(suffix=f".{fmt}")
    os.close(fd)
    tmp = Path(_tmp)
    try:
        tmp.write_bytes(raw)
        try:
            png_bytes = await loop.run_in_executor(
                None, sanitize.process_image_file, tmp
            )
        except Exception as e:
            return ConversionError("ImageDecodeError", f"Pillow failed: {e}")
    finally:
        tmp.unlink(missing_ok=True)

    return [png_bytes]


async def _process_document(
    raw: bytes, fmt: str, timeout: int
) -> list[bytes] | ConversionError:
    loop = asyncio.get_running_loop()
    fd, _tmp_input = tempfile.mkstemp(suffix=f".{fmt}")
    os.close(fd)
    tmp_input = Path(_tmp_input)
    pdf_path = None
    try:
        tmp_input.write_bytes(raw)

        try:
            pdf_path = await convert_to_pdf(tmp_input, fmt, timeout)
        except ConversionError:
            raise
        except Exception as e:
            raise ConversionError("LibreOfficeError", str(e))

        try:
            pixel_pages = await loop.run_in_executor(None, rasterize_pdf, pdf_path)
        except ConversionError:
            raise
        except Exception as e:
            raise ConversionError("PyMuPDFError", str(e))

        pages = []
        for i, (rgb_bytes, w, h) in enumerate(pixel_pages):
            try:
                png_bytes = await loop.run_in_executor(
                    None, sanitize.reencode_png, rgb_bytes, w, h
                )
            except Exception as e:
                raise ConversionError(
                    "PillowEncodeError", f"page {i + 1} re-encode failed: {e}"
                )
            pages.append(png_bytes)

        return pages
    finally:
        tmp_input.unlink(missing_ok=True)
        if pdf_path and pdf_path.exists():
            pdf_path.unlink(missing_ok=True)


async def _process_text_document(raw: bytes, fmt: str) -> list[bytes] | ConversionError:
    loop = asyncio.get_running_loop()
    pdf_path = None
    try:
        try:
            pdf_path = await loop.run_in_executor(None, text_to_pdf, raw, fmt)
        except ConversionError:
            raise
        except Exception as e:
            raise ConversionError("TextRenderError", str(e))

        try:
            pixel_pages = await loop.run_in_executor(None, rasterize_pdf, pdf_path)
        except ConversionError:
            raise
        except Exception as e:
            raise ConversionError("PyMuPDFError", str(e))

        pages = []
        for i, (rgb_bytes, w, h) in enumerate(pixel_pages):
            try:
                png_bytes = await loop.run_in_executor(
                    None, sanitize.reencode_png, rgb_bytes, w, h
                )
            except Exception as e:
                raise ConversionError(
                    "PillowEncodeError", f"page {i + 1} re-encode failed: {e}"
                )
            pages.append(png_bytes)

        return pages
    finally:
        if pdf_path and pdf_path.exists():
            pdf_path.unlink(missing_ok=True)


async def _error(
    rel_str: str,
    errors_dir: Path,
    rel_path: Path,
    fmt: str,
    error_type: str,
    error_detail: str,
    stack_trace: str | None,
    file_size: int,
    file_sha256: str,
) -> None:
    manifest = {
        "input_path": rel_str,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "format_detected": fmt,
        "error_type": error_type,
        "error_detail": error_detail,
        "stack_trace": stack_trace,
        "file_size_bytes": file_size,
        "sha256": file_sha256,
    }
    await fs.write_error_manifest(errors_dir, rel_path, manifest)
    log.error(rel_str, error_type, error_detail[:120])
