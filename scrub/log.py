import logging
import sys
from pathlib import Path

logger = logging.getLogger("scrub")


def setup(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s")
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(fmt)
        logger.addHandler(stdout_handler)


def startup(**fields) -> None:
    parts = "  ".join(f"{k}={v}" for k, v in fields.items())
    logger.info(f"[startup] {parts}")


def debug(input_path: str, event: str, detail: str = "") -> None:
    logger.debug(f"{input_path} {event} {detail}".rstrip())


def start(input_path: str, fmt: str) -> None:
    logger.info(f"{input_path} START format={fmt}")


def success(input_path: str, page_count: int) -> None:
    logger.info(f"{input_path} SUCCESS pages={page_count}")




def error(input_path: str, error_type: str, detail: str = "") -> None:
    logger.warning(f"{input_path} ERROR error_type={error_type} {detail}".rstrip())


def skip(input_path: str, reason: str) -> None:
    logger.info(f"{input_path} SKIPPED reason={reason or '(none)'}")


def fatal(msg: str) -> None:
    logger.error(msg)


def summary(
    total: int, clean: int, errors: int, skipped: int, expanded: int = 0
) -> None:
    logger.info(
        f"[done] total={total}  clean={clean}  errors={errors}  skipped={skipped}  expanded={expanded}"
    )
