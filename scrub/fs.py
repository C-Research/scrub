import asyncio
import json
import os
from pathlib import Path
from typing import AsyncIterator


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


def validate_dirs(source: Path, clean: Path, quarantine: Path) -> None:
    if not source.is_dir() or not os.access(source, os.R_OK):
        raise RuntimeError(f"Source directory not readable: {source}")
    for d in (clean, quarantine):
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
    base = clean_dir / rel_path.parent / rel_path.stem
    return [base / f"{prefix}_{i + 1:03d}.png" for i in range(page_count)]


async def write_png(path: Path, data: bytes) -> None:
    await asyncio.get_running_loop().run_in_executor(None, _write_bytes, path, data)


async def write_quarantine_manifest(
    quarantine_dir: Path, rel_path: Path, manifest: dict
) -> None:
    out = quarantine_dir / (str(rel_path) + ".json")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _write_json, out, manifest)


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
