import asyncio
import json
import os
from pathlib import Path
from typing import AsyncIterator

import aiofiles


def _name_max() -> int:
    try:
        return os.pathconf("/", "PC_NAME_MAX")
    except (AttributeError, ValueError):
        return 255  # Windows fallback


def _cap_filename(stem: str, suffix: str) -> str:
    """Return stem+suffix truncating stem so the total fits within NAME_MAX bytes.

    Truncation respects UTF-8 byte boundaries.  The full suffix (e.g.
    '.docx.page_001.png', '.xls.json') is always preserved unchanged.
    """
    limit = _name_max()
    suffix_bytes = suffix.encode("utf-8")
    stem_limit = limit - len(suffix_bytes)
    stem_bytes = stem.encode("utf-8")
    if len(stem_bytes) <= stem_limit:
        return stem + suffix
    return stem_bytes[:stem_limit].decode("utf-8", errors="ignore") + suffix


def is_os_artifact(name: str) -> bool:
    """True for OS-generated junk that should never be processed as documents.

    macOS: __MACOSX/ directory, AppleDouble resource forks (._*), .DS_Store
    Windows: Office lock files (~$*) — same extension as the locked doc but not a document
    """
    p = Path(name)
    if "__MACOSX" in p.parts:
        return True
    if p.name.startswith("._") or p.name == ".DS_Store":
        return True
    if p.name.startswith("~$"):
        return True
    return False


async def walk_source(source_dir: Path) -> AsyncIterator[Path]:
    loop = asyncio.get_running_loop()

    def _walk(d: Path) -> list[Path]:
        results = []
        try:
            for entry in os.scandir(d):
                if entry.is_dir(follow_symlinks=False):
                    results.extend(_walk(Path(entry.path)))
                elif entry.is_file(follow_symlinks=False):
                    results.append(Path(entry.path))
        except PermissionError:
            pass
        return results

    paths = await loop.run_in_executor(None, _walk, source_dir)
    for p in paths:
        yield p


def validate_dirs(source: Path, clean: Path, errors: Path) -> None:
    if not source.is_dir() or not os.access(source, os.R_OK):
        raise RuntimeError(f"Source directory not readable: {source}")
    for d in (clean, errors):
        d.mkdir(parents=True, exist_ok=True)
        if not os.access(d, os.W_OK):
            raise RuntimeError(f"Directory not writable: {d}")


def derive_output_paths(
    source_dir: Path,
    clean_dir: Path,
    rel_path: Path,
    page_count: int,
    is_xlsx: bool,
) -> list[Path]:
    prefix = "sheet" if is_xlsx else "page"
    stem = rel_path.name.replace("/", "_")
    base_dir = clean_dir / rel_path.parent
    return [
        base_dir / _cap_filename(stem, f".{prefix}_{i + 1:03d}.png")
        for i in range(page_count)
    ]


def derive_txt_output_path(
    source_dir: Path,
    clean_dir: Path,
    rel_path: Path,
) -> Path:
    stem = rel_path.name.replace("/", "_")
    base_dir = clean_dir / rel_path.parent
    return base_dir / _cap_filename(stem, ".txt")


async def write_txt(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(text)


async def write_png(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "wb") as f:
        await f.write(data)


async def write_quarantine_manifest(
    quarantine_dir: Path, rel_path: Path, manifest: dict
) -> None:
    out = quarantine_dir / rel_path.parent / _cap_filename(rel_path.name, ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(out, "w", encoding="utf-8") as f:
        await f.write(json.dumps(manifest, indent=2))


def derive_error_manifest_path(errors_dir: Path, rel_path: Path) -> Path:
    return errors_dir / rel_path.parent / _cap_filename(rel_path.name, ".json")


async def write_error_manifest(
    errors_dir: Path, rel_path: Path, manifest: dict
) -> None:
    out = derive_error_manifest_path(errors_dir, rel_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(out, "w", encoding="utf-8") as f:
        await f.write(json.dumps(manifest, indent=2))
