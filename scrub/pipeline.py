import asyncio
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

from . import fs, log, quarantine, sanitize
from .clamav import scan_pngs
from .converter import ConversionError, convert_to_pdf, rasterize_pdf


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
}


def detect_format(header: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    for magic, fmt in _MAGIC:
        if header[: len(magic)] == magic:
            if fmt == "zip":
                return _ZIP_EXT_MAP.get(ext, "docx")
            if fmt == "ole":
                return _OLE_EXT_MAP.get(ext, "doc")
            return fmt
    return "unknown"


async def process_file(
    rel_path: Path,
    source_dir: Path,
    clean_dir: Path,
    quarantine_dir: Path,
    errors_dir: Path,
    socket_path: str,
    timeout: int = 60,
) -> str:
    """Process one file. Returns 'clean', 'quarantine', or 'error'."""
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
    file_sha256 = quarantine.sha256(raw)
    log.debug(rel_str, "READ", f"size={file_size}  sha256={file_sha256[:16]}…")

    # Format detection from magic bytes
    fmt = detect_format(raw[:16], rel_path.name)
    log.start(rel_str, fmt)

    if fmt not in _IMAGE_FORMATS and fmt not in _OFFICE_FORMATS:
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

    scan_dir = Path(tempfile.mkdtemp(prefix="scrub_scan_"))
    try:
        if fmt in _IMAGE_FORMATS:
            log.debug(rel_str, "PROCESS", "path=image")
            pages = await _process_image(raw, fmt, scan_dir)
        else:
            log.debug(rel_str, "PROCESS", "path=document  step=libreoffice→pdf")
            pages = await _process_document(raw, fmt, scan_dir, timeout)

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

        # ClamAV scan — all pages before any write
        scan_paths = [scan_dir / f"page_{i + 1:03d}.png" for i in range(len(pages))]
        log.debug(rel_str, "SCAN", f"pages={len(scan_paths)}")
        result = await scan_pngs(scan_paths, socket_path)

        if not result.clean:
            if result.error:
                log.debug(rel_str, "SCAN", f"result=error  detail={result.error}")
                await _quarantine(
                    rel_str,
                    quarantine_dir,
                    rel_path,
                    fmt,
                    "ClamAVError",
                    result.error,
                    None,
                    file_size,
                    file_sha256,
                )
            else:
                log.debug(
                    rel_str,
                    "SCAN",
                    f"result=threat  virus={result.virus_name}  file={result.scanned_file}",
                )
                await _quarantine(
                    rel_str,
                    quarantine_dir,
                    rel_path,
                    fmt,
                    "ClamAVDetection",
                    f"ClamAV detected threat in {result.scanned_file}",
                    None,
                    file_size,
                    file_sha256,
                    virus_name=result.virus_name,
                    scanned_file=result.scanned_file,
                )
            return "quarantine"

        log.debug(rel_str, "SCAN", "result=clean")

        # Write to clean dir
        is_xlsx = fmt in ("xlsx", "xls")
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
    finally:
        shutil.rmtree(scan_dir, ignore_errors=True)


async def _process_image(
    raw: bytes, fmt: str, scan_dir: Path
) -> list[bytes] | ConversionError:
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

    # Write to scan_dir for ClamAV
    scan_path = scan_dir / "page_001.png"
    try:
        await loop.run_in_executor(None, scan_path.write_bytes, png_bytes)
    except Exception as e:
        return ConversionError("PillowEncodeError", f"PNG write failed: {e}")

    return [png_bytes]


async def _process_document(
    raw: bytes, fmt: str, scan_dir: Path, timeout: int
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

            scan_path = scan_dir / f"page_{i + 1:03d}.png"
            await loop.run_in_executor(None, scan_path.write_bytes, png_bytes)
            pages.append(png_bytes)

        return pages
    finally:
        tmp_input.unlink(missing_ok=True)
        if pdf_path and pdf_path.exists():
            pdf_path.unlink(missing_ok=True)


async def _quarantine(
    rel_str: str,
    quarantine_dir: Path,
    rel_path: Path,
    fmt: str,
    error_type: str,
    error_detail: str,
    stack_trace: str | None,
    file_size: int,
    file_sha256: str,
    virus_name: str | None = None,
    scanned_file: str | None = None,
) -> None:
    manifest = quarantine.build_manifest(
        input_path=rel_str,
        format_detected=fmt,
        error_type=error_type,
        error_detail=error_detail,
        stack_trace=stack_trace,
        file_size_bytes=file_size,
        file_sha256=file_sha256,
        virus_name=virus_name,
        scanned_file=scanned_file,
    )
    await fs.write_quarantine_manifest(quarantine_dir, rel_path, manifest)
    log.quarantine(rel_str, error_type, error_detail[:120])


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
    manifest = quarantine.build_manifest(
        input_path=rel_str,
        format_detected=fmt,
        error_type=error_type,
        error_detail=error_detail,
        stack_trace=stack_trace,
        file_size_bytes=file_size,
        file_sha256=file_sha256,
    )
    await fs.write_error_manifest(errors_dir, rel_path, manifest)
    log.error(rel_str, error_type, error_detail[:120])
