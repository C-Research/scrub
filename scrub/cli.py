import asyncio
import os
import sys
from pathlib import Path

from . import clamav, fs, log
from .pipeline import process_file

# Fixed container-internal paths (match bind mount targets in docker-compose.yml)
_SOURCE    = Path("/data/source")
_CLEAN     = Path("/data/clean")
_QUARANTINE = Path("/data/quarantine")
_LOG       = Path("/var/log/scrub/scrub.log")
_SOCKET    = "/run/clamav/clamd.sock"


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
    workers      = _optional_int("SCRUB_WORKERS",      max(1, (os.cpu_count() or 1) * 2 - 1))
    timeout      = _optional_int("SCRUB_TIMEOUT",      60)
    memory_limit = _optional_int("SCRUB_MEMORY_LIMIT", 512)

    logger = log.setup(_LOG)
    log.startup(
        logger,
        workers=workers,
        timeout=f"{timeout}s",
        memory_limit=f"{memory_limit}MB",
        source=_SOURCE,
        clean=_CLEAN,
        quarantine=_QUARANTINE,
        socket=_SOCKET,
        log=_LOG,
    )

    try:
        fs.validate_dirs(_SOURCE, _CLEAN, _QUARANTINE)
    except RuntimeError as e:
        log.fatal(logger, str(e))
        return 1

    logger.debug(f"[clamav] waiting for daemon at {_SOCKET}")
    try:
        await clamav.wait_for_daemon(_SOCKET, timeout=60)
    except RuntimeError as e:
        log.fatal(logger, str(e))
        return 1
    logger.debug("[clamav] daemon ready")

    sem = asyncio.Semaphore(workers)
    clean_count = 0
    quarantine_count = 0

    async def _bounded(rel_path: Path) -> None:
        nonlocal clean_count, quarantine_count
        async with sem:
            clean = await process_file(
                rel_path=rel_path,
                source_dir=_SOURCE,
                clean_dir=_CLEAN,
                quarantine_dir=_QUARANTINE,
                socket_path=_SOCKET,
                logger=logger,
                timeout=timeout,
                memory_limit_mb=memory_limit,
            )
            if clean:
                clean_count += 1
            else:
                quarantine_count += 1

    tasks = []
    async for abs_path in fs.walk_source(_SOURCE):
        rel_path = abs_path.relative_to(_SOURCE)
        tasks.append(asyncio.create_task(_bounded(rel_path)))

    if not tasks:
        log.fatal(logger, f"No files found in source directory: {_SOURCE}")
        return 0

    logger.debug(f"[queue] dispatching {len(tasks)} file(s) across {workers} worker(s)")
    await asyncio.gather(*tasks)
    log.summary(logger, total=len(tasks), clean=clean_count, quarantined=quarantine_count)
    return 1 if quarantine_count else 0


def main() -> None:
    sys.exit(asyncio.run(_run()))
