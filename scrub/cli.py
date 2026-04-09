import asyncio
import os
import sys
from pathlib import Path

from . import archive, clamav, fs, log
from .pipeline import process_file

# Fixed container-internal paths (match bind mount targets in docker-compose.yml)
_SOURCE = Path("/data/source")
_CLEAN = Path("/data/clean")
_QUARANTINE = Path("/data/quarantine")
_ERRORS = Path("/data/errors")
_LOG = Path("/var/log/scrub/scrub.log")
_SOCKET = "/run/clamav/clamd.sock"


def _optional_int(name: str, default: int) -> int:
    val = os.environ.get(name, "").strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        print(f"ERROR: {name} must be an integer, got {val!r}", file=sys.stderr)
        sys.exit(1)


async def _run() -> int:
    workers = _optional_int("SCRUB_WORKERS", max(1, (os.cpu_count() or 1) * 2 - 1))
    timeout = _optional_int("SCRUB_TIMEOUT", 60)
    max_file_bytes = _optional_int("SCRUB_MAX_FILE_SIZE", 100) * 1024 * 1024
    max_archive_members = _optional_int("SCRUB_MAX_ARCHIVE_MEMBERS", 1000)
    max_archive_total_bytes = _optional_int("SCRUB_MAX_ARCHIVE_TOTAL_MB", 500) * 1024 * 1024

    log.setup(_LOG)
    log.startup(
        workers=workers,
        timeout=f"{timeout}s",
        source=_SOURCE,
        clean=_CLEAN,
        quarantine=_QUARANTINE,
        errors=_ERRORS,
        socket=_SOCKET,
        log=_LOG,
    )

    try:
        fs.validate_dirs(_SOURCE, _CLEAN, _QUARANTINE, _ERRORS)
    except RuntimeError as e:
        log.fatal(str(e))
        return 1

    log.debug("[clamav]", f"waiting for daemon at {_SOCKET}")
    try:
        await clamav.wait_for_daemon(_SOCKET, timeout=60)
    except RuntimeError as e:
        log.fatal(str(e))
        return 1
    log.debug("[clamav]", "daemon ready")

    expanded_count = await archive.expand_archives(
        _SOURCE, max_file_bytes, max_archive_members, max_archive_total_bytes
    )
    if expanded_count:
        log.debug("[archive]", f"expanded {expanded_count} archive(s)")

    sem = asyncio.Semaphore(workers)
    clean_count = 0
    quarantine_count = 0
    error_count = 0
    skipped_count = 0

    async def _bounded(rel_path: Path) -> None:
        nonlocal clean_count, quarantine_count, error_count, skipped_count
        async with sem:
            result = await process_file(
                rel_path=rel_path,
                source_dir=_SOURCE,
                clean_dir=_CLEAN,
                quarantine_dir=_QUARANTINE,
                errors_dir=_ERRORS,
                socket_path=_SOCKET,
                timeout=timeout,
            )
            if result == "clean":
                clean_count += 1
            elif result == "quarantine":
                quarantine_count += 1
            elif result == "skipped":
                skipped_count += 1
            else:
                error_count += 1

    tasks = []
    async for abs_path in fs.walk_source(_SOURCE):
        rel_path = abs_path.relative_to(_SOURCE)
        tasks.append(asyncio.create_task(_bounded(rel_path)))

    if not tasks:
        log.fatal(f"No files found in source directory: {_SOURCE}")
        return 0

    log.debug("[queue]", f"dispatching {len(tasks)} file(s) across {workers} worker(s)")
    await asyncio.gather(*tasks)
    log.summary(
        total=len(tasks),
        clean=clean_count,
        quarantined=quarantine_count,
        errors=error_count,
        skipped=skipped_count,
        expanded=expanded_count,
    )
    return 1 if (quarantine_count or error_count) else 0


def main() -> None:
    sys.exit(asyncio.run(_run()))
