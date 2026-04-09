import asyncio
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScanResult:
    clean: bool
    virus_name: str | None = None
    scanned_file: str | None = None
    error: str | None = None


async def wait_for_daemon(socket_path: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    delay = 0.5
    while True:
        try:
            _, writer = await asyncio.open_unix_connection(socket_path)
            writer.close()
            await writer.wait_closed()
            return
        except OSError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(
                    f"ClamAV daemon not responsive at {socket_path} after {timeout}s"
                )
            await asyncio.sleep(min(delay, remaining))
            delay = min(delay * 2, 10.0)


async def scan_pngs(
    png_paths: list[Path],
    socket_path: str,
    timeout: int = 30,
) -> ScanResult:
    cmd = [
        "clamdscan",
        "--no-summary",
        "--infected",
        "--stream",  # stream file content over socket; clamd has no access to our fs
        "--config-file=/etc/clamav/clamd.conf",
        "--",
        *[str(p) for p in png_paths],
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
            return ScanResult(
                clean=False, error=f"clamdscan timed out after {timeout}s"
            )
    except Exception as e:
        return ScanResult(clean=False, error=f"clamdscan launch failed: {e}")

    if proc.returncode == 0:
        return ScanResult(clean=True)

    if proc.returncode == 1:
        # Virus found — parse: "<filepath>: <VirusName> FOUND"
        output = stdout.decode(errors="replace")
        for line in output.splitlines():
            if "FOUND" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return ScanResult(
                        clean=False,
                        virus_name=parts[1].strip().removesuffix(" FOUND").strip(),
                        scanned_file=Path(parts[0].strip()).name,
                    )
        return ScanResult(clean=False, virus_name="unknown", scanned_file=None)

    err = stderr.decode(errors="replace").strip()
    return ScanResult(
        clean=False, error=f"clamdscan exit {proc.returncode}: {err[:500]}"
    )
