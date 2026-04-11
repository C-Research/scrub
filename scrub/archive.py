import asyncio
import gzip
import stat
import tarfile
import zipfile
from pathlib import Path

import aiofiles
import rarfile

from . import fs, log

rarfile.UNRAR_TOOL = "/usr/bin/bsdtar"


def _archive_stem(p: Path) -> str:
    name = p.name
    if name.endswith(".tar.gz"):
        return name[:-7]
    if name.endswith(".tgz"):
        return name[:-4]
    return p.stem


async def expand_archives(
    source_dir: Path,
    extracts_dir: Path,
    max_file_bytes: int,
    max_members: int,
    max_total_bytes: int,
) -> int:
    """Expand .zip, .rar, .tar.gz, .tgz, and .gz archives into extracts_dir.

    Extracts into extracts_dir/<source-relative-parent>/<archive-stem>/<member-path>.
    For single-file .gz, extracts to extracts_dir/<source-relative-parent>/<stem>.
    Checks first non-dir member of each archive against source_dir as a sentinel:
    if the first member exists in source, the archive is assumed already extracted and skipped.
    Returns the count of archives processed.
    """
    loop = asyncio.get_running_loop()
    archives = await loop.run_in_executor(
        None,
        lambda: [
            p for p in sorted(source_dir.rglob("*")) if p.is_file() and _is_archive(p)
        ],
    )
    count = 0
    for archive_path in archives:
        archive_str = str(archive_path)
        try:
            name = archive_path.name
            rel_parent = archive_path.relative_to(source_dir).parent
            stem = _archive_stem(archive_path)
            if name.endswith(".tar.gz") or name.endswith(".tgz"):
                if _targz_first_member_in_source(archive_path, source_dir):
                    log.debug(archive_str, "ARCHIVE_SKIP", "already in source")
                    continue
                dest_dir = extracts_dir / rel_parent / stem
                await _expand_targz(
                    archive_path, dest_dir, max_file_bytes, max_members, max_total_bytes
                )
            elif archive_path.suffix.lower() == ".zip":
                if _zip_first_member_in_source(archive_path, source_dir):
                    log.debug(archive_str, "ARCHIVE_SKIP", "already in source")
                    continue
                dest_dir = extracts_dir / rel_parent / stem
                await _expand_zip(
                    archive_path, dest_dir, max_file_bytes, max_members, max_total_bytes
                )
            elif archive_path.suffix.lower() == ".rar":
                if _rar_first_member_in_source(archive_path, source_dir):
                    log.debug(archive_str, "ARCHIVE_SKIP", "already in source")
                    continue
                dest_dir = extracts_dir / rel_parent / stem
                await _expand_rar(
                    archive_path, dest_dir, max_file_bytes, max_members, max_total_bytes
                )
            else:
                # .gz single-file: sentinel is source_dir / rel_parent / archive_path.stem
                if (source_dir / rel_parent / archive_path.stem).exists():
                    log.debug(archive_str, "ARCHIVE_SKIP", "already in source")
                    continue
                dest_dir = extracts_dir / rel_parent
                await _expand_gz(archive_path, dest_dir, max_file_bytes)
            count += 1
        except Exception as e:
            log.debug(archive_str, "ARCHIVE_ERROR", str(e))
    return count


def _is_archive(p: Path) -> bool:
    name = p.name
    if name.endswith(".tar.gz") or name.endswith(".tgz"):
        return True
    return p.suffix.lower() in {".zip", ".rar", ".gz"}



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


def _zip_first_member_in_source(archive_path: Path, source_dir: Path) -> bool:
    """True if the first non-dir member of the ZIP already exists in source_dir."""
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                p = Path(info.filename)
                if p.is_absolute() or ".." in p.parts:
                    continue
                return (source_dir / p).exists()
    except Exception:
        pass
    return False


def _targz_first_member_in_source(archive_path: Path, source_dir: Path) -> bool:
    """True if the first non-dir, non-symlink member of the tar.gz exists in source_dir."""
    try:
        with tarfile.open(archive_path, mode="r:gz") as tf:
            for info in tf.getmembers():
                if info.isdir() or info.issym() or info.islnk():
                    continue
                p = Path(info.name)
                if p.is_absolute() or ".." in p.parts:
                    continue
                return (source_dir / p).exists()
    except Exception:
        pass
    return False


def _rar_first_member_in_source(archive_path: Path, source_dir: Path) -> bool:
    """True if the first non-dir, non-symlink member of the RAR exists in source_dir."""
    try:
        with rarfile.RarFile(archive_path, "r") as rf:
            for info in rf.infolist():
                if info.is_dir() or info.is_symlink():
                    continue
                p = Path(info.filename)
                if p.is_absolute() or ".." in p.parts:
                    continue
                return (source_dir / p).exists()
    except Exception:
        pass
    return False


async def _expand_targz(
    archive_path: Path,
    dest_dir: Path,
    max_file_bytes: int,
    max_members: int,
    max_total_bytes: int,
) -> None:
    archive_str = str(archive_path)
    with tarfile.open(archive_path, mode="r:gz") as tf:
        total_bytes = 0
        for i, info in enumerate(tf.getmembers()):
            if i >= max_members:
                log.debug(
                    archive_str,
                    "ARCHIVE_ABORT",
                    f"member count limit reached ({max_members})",
                )
                break
            if info.isdir():
                continue
            if info.issym() or info.islnk():
                log.debug(archive_str, "ARCHIVE_SKIP", f"symlink: {info.name}")
                continue
            if fs.is_os_artifact(info.name):
                log.debug(archive_str, "ARCHIVE_SKIP", f"macos artifact: {info.name}")
                continue
            dest = _safe_dest(info.name, dest_dir)
            if dest is None:
                log.debug(archive_str, "ARCHIVE_SKIP", f"unsafe path: {info.name}")
                continue
            if info.size > max_file_bytes:
                log.debug(
                    archive_str,
                    "ARCHIVE_SKIP",
                    f"oversized ({info.size} bytes): {info.name}",
                )
                continue
            if total_bytes + info.size > max_total_bytes:
                log.debug(
                    archive_str,
                    "ARCHIVE_ABORT",
                    f"total bytes limit reached ({max_total_bytes})",
                )
                break
            if dest.exists():
                log.debug(archive_str, "ARCHIVE_SKIP", f"already exists: {info.name}")
                continue
            total_bytes += info.size
            data = tf.extractfile(info)
            if data is None:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(dest, "wb") as f:
                await f.write(data.read())
            log.debug(archive_str, "ARCHIVE_EXTRACT", info.name)


async def _expand_gz(
    archive_path: Path,
    dest_dir: Path,
    max_file_bytes: int,
) -> None:
    archive_str = str(archive_path)
    dest = dest_dir / archive_path.stem
    if dest.exists():
        log.debug(archive_str, "ARCHIVE_SKIP", f"already exists: {dest.name}")
        return

    chunks: list[bytes] = []
    total = 0
    chunk_size = 256 * 1024  # 256 KB
    with gzip.open(archive_path, "rb") as gz:
        while True:
            chunk = gz.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > max_file_bytes:
                log.debug(
                    archive_str,
                    "ARCHIVE_ABORT",
                    f"decompressed size exceeds limit ({max_file_bytes} bytes)",
                )
                return
            chunks.append(chunk)

    dest.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(dest, "wb") as f:
        for chunk in chunks:
            await f.write(chunk)
    log.debug(archive_str, "ARCHIVE_EXTRACT", dest.name)


async def _expand_zip(
    archive_path: Path,
    dest_dir: Path,
    max_file_bytes: int,
    max_members: int,
    max_total_bytes: int,
) -> None:
    archive_str = str(archive_path)
    with zipfile.ZipFile(archive_path, "r") as zf:
        total_bytes = 0
        for i, info in enumerate(zf.infolist()):
            if i >= max_members:
                log.debug(
                    archive_str,
                    "ARCHIVE_ABORT",
                    f"member count limit reached ({max_members})",
                )
                break
            if info.is_dir():
                continue
            if stat.S_ISLNK(info.external_attr >> 16):
                log.debug(archive_str, "ARCHIVE_SKIP", f"symlink: {info.filename}")
                continue
            if fs.is_os_artifact(info.filename):
                log.debug(archive_str, "ARCHIVE_SKIP", f"macos artifact: {info.filename}")
                continue
            dest = _safe_dest(info.filename, dest_dir)
            if dest is None:
                log.debug(archive_str, "ARCHIVE_SKIP", f"unsafe path: {info.filename}")
                continue
            if info.file_size > max_file_bytes:
                log.debug(
                    archive_str,
                    "ARCHIVE_SKIP",
                    f"oversized ({info.file_size} bytes): {info.filename}",
                )
                continue
            if total_bytes + info.file_size > max_total_bytes:
                log.debug(
                    archive_str,
                    "ARCHIVE_ABORT",
                    f"total bytes limit reached ({max_total_bytes})",
                )
                break
            if dest.exists():
                log.debug(
                    archive_str, "ARCHIVE_SKIP", f"already exists: {info.filename}"
                )
                continue
            total_bytes += info.file_size
            data = zf.read(info)
            dest.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(dest, "wb") as f:
                await f.write(data)
            log.debug(archive_str, "ARCHIVE_EXTRACT", info.filename)


async def _expand_rar(
    archive_path: Path,
    dest_dir: Path,
    max_file_bytes: int,
    max_members: int,
    max_total_bytes: int,
) -> None:
    archive_str = str(archive_path)
    with rarfile.RarFile(archive_path, "r") as rf:
        total_bytes = 0
        for i, info in enumerate(rf.infolist()):
            if i >= max_members:
                log.debug(
                    archive_str,
                    "ARCHIVE_ABORT",
                    f"member count limit reached ({max_members})",
                )
                break
            if info.is_dir():
                continue
            if info.is_symlink():
                log.debug(archive_str, "ARCHIVE_SKIP", f"symlink: {info.filename}")
                continue
            if fs.is_os_artifact(info.filename):
                log.debug(archive_str, "ARCHIVE_SKIP", f"macos artifact: {info.filename}")
                continue
            dest = _safe_dest(info.filename, dest_dir)
            if dest is None:
                log.debug(archive_str, "ARCHIVE_SKIP", f"unsafe path: {info.filename}")
                continue
            if info.file_size > max_file_bytes:
                log.debug(
                    archive_str,
                    "ARCHIVE_SKIP",
                    f"oversized ({info.file_size} bytes): {info.filename}",
                )
                continue
            if total_bytes + info.file_size > max_total_bytes:
                log.debug(
                    archive_str,
                    "ARCHIVE_ABORT",
                    f"total bytes limit reached ({max_total_bytes})",
                )
                break
            if dest.exists():
                log.debug(
                    archive_str, "ARCHIVE_SKIP", f"already exists: {info.filename}"
                )
                continue
            total_bytes += info.file_size
            data = rf.read(info.filename)
            dest.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(dest, "wb") as f:
                await f.write(data)
            log.debug(archive_str, "ARCHIVE_EXTRACT", info.filename)
