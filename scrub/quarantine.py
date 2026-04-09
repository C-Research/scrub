import hashlib
from datetime import datetime, timezone


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_manifest(
    input_path: str,
    format_detected: str,
    error_type: str,
    error_detail: str,
    stack_trace: str | None,
    file_size_bytes: int,
    file_sha256: str,
    virus_name: str | None = None,
    scanned_file: str | None = None,
) -> dict:
    return {
        "input_path": input_path,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "format_detected": format_detected,
        "error_type": error_type,
        "error_detail": error_detail,
        "stack_trace": stack_trace,
        "file_size_bytes": file_size_bytes,
        "sha256": file_sha256,
        "virus_name": virus_name,
        "scanned_file": scanned_file,
    }
