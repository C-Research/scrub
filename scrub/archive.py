import asyncio
import stat
import zipfile
from pathlib import Path

import aiofiles
import rarfile

from . import log

rarfile.UNRAR_TOOL = "/usr/bin/bsdtar"


async def expand_archives(
    source_dir: Path,
    max_file_bytes: int,
    max_members: int,
    max_total_bytes: int,
) -> int:
    """Expand .zip and .rar archives into source_dir in-place.

    Collects all archives first, then expands each once — extracted archives
    are not re-expanded. Returns the count of archives processed.
    """
    loop = asyncio.get_running_loop()
    archives = await loop.run_in_executor(
        None,
        lambda: [
            p
            for p in sorted(source_dir.rglob("*"))
            if p.is_file() and p.suffix.lower() in {".zip", ".rar"}
        ],
    )
    count = 0
    for archive_path in archives:
        archive_str = str(archive_path)
        try:
            if archive_path.suffix.lower() == ".zip":
                await _expand_zip(archive_path, max_file_bytes, max_members, max_total_bytes)
            else:
                await _expand_rar(archive_path, max_file_bytes, max_members, max_total_bytes)
            count += 1
        except Exception as e:
            log.debug(archive_str, "ARCHIVE_ERROR", str(e))
    return count


def _safe_dest(member_path_str: str, dest_dir: Path) -> Path | None:
    """Return resolved destination path, or None if the path is unsafe."""
    p = Path(member_path_str)
    if p.is_absolute():
        return None
    if ".." in p.parts:
        return None
    dest = (dest_dir / p).resolve()
    try:
        dest.relative_to(dest_dir.resolve())
    except ValueError:
        return None
    return dest


async def _expand_zip(
    archive_path: Path,
    max_file_bytes: int,
    max_members: int,
    max_total_bytes: int,
) -> None:
    archive_str = str(archive_path)
    dest_dir = archive_path.parent
    with zipfile.ZipFile(archive_path, "r") as zf:
        total_bytes = 0
        for i, info in enumerate(zf.infolist()):
            if i >= max_members:
                log.debug(archive_str, "ARCHIVE_ABORT", f"member count limit reached ({max_members})")
                break
            if info.is_dir():
                continue
            if stat.S_ISLNK(info.external_attr >> 16):
                log.debug(archive_str, "ARCHIVE_SKIP", f"symlink: {info.filename}")
                continue
            dest = _safe_dest(info.filename, dest_dir)
            if dest is None:
                log.debug(archive_str, "ARCHIVE_SKIP", f"unsafe path: {info.filename}")
                continue
            if info.file_size > max_file_bytes:
                log.debug(archive_str, "ARCHIVE_SKIP", f"oversized ({info.file_size} bytes): {info.filename}")
                continue
            if total_bytes + info.file_size > max_total_bytes:
                log.debug(archive_str, "ARCHIVE_ABORT", f"total bytes limit reached ({max_total_bytes})")
                break
            if dest.exists():
                log.debug(archive_str, "ARCHIVE_SKIP", f"already exists: {info.filename}")
                continue
            total_bytes += info.file_size
            data = zf.read(info)
            dest.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(dest, "wb") as f:
                await f.write(data)
            log.debug(archive_str, "ARCHIVE_EXTRACT", info.filename)


async def _expand_rar(
    archive_path: Path,
    max_file_bytes: int,
    max_members: int,
    max_total_bytes: int,
) -> None:
    archive_str = str(archive_path)
    dest_dir = archive_path.parent
    with rarfile.RarFile(archive_path, "r") as rf:
        total_bytes = 0
        for i, info in enumerate(rf.infolist()):
            if i >= max_members:
                log.debug(archive_str, "ARCHIVE_ABORT", f"member count limit reached ({max_members})")
                break
            if info.is_dir():
                continue
            if info.is_symlink():
                log.debug(archive_str, "ARCHIVE_SKIP", f"symlink: {info.filename}")
                continue
            dest = _safe_dest(info.filename, dest_dir)
            if dest is None:
                log.debug(archive_str, "ARCHIVE_SKIP", f"unsafe path: {info.filename}")
                continue
            if info.file_size > max_file_bytes:
                log.debug(archive_str, "ARCHIVE_SKIP", f"oversized ({info.file_size} bytes): {info.filename}")
                continue
            if total_bytes + info.file_size > max_total_bytes:
                log.debug(archive_str, "ARCHIVE_ABORT", f"total bytes limit reached ({max_total_bytes})")
                break
            if dest.exists():
                log.debug(archive_str, "ARCHIVE_SKIP", f"already exists: {info.filename}")
                continue
            total_bytes += info.file_size
            data = rf.read(info.filename)
            dest.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(dest, "wb") as f:
                await f.write(data)
            log.debug(archive_str, "ARCHIVE_EXTRACT", info.filename)
