import logging
import sys
from pathlib import Path


def setup(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("scrub")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)-5s %(message)s")
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(fmt)
        logger.addHandler(stdout_handler)
    return logger


def startup(logger: logging.Logger, **fields) -> None:
    parts = "  ".join(f"{k}={v}" for k, v in fields.items())
    logger.info(f"[startup] {parts}")


def debug(logger: logging.Logger, input_path: str, event: str, detail: str = "") -> None:
    logger.debug(f"{input_path} {event} {detail}".rstrip())


def start(logger: logging.Logger, input_path: str, fmt: str) -> None:
    logger.info(f"{input_path} START format={fmt}")


def success(logger: logging.Logger, input_path: str, page_count: int) -> None:
    logger.info(f"{input_path} SUCCESS pages={page_count}")


def quarantine(logger: logging.Logger, input_path: str, error_type: str, detail: str = "") -> None:
    logger.warning(f"{input_path} QUARANTINE error_type={error_type} {detail}".rstrip())


def fatal(logger: logging.Logger, msg: str) -> None:
    logger.error(msg)


def summary(logger: logging.Logger, total: int, clean: int, quarantined: int) -> None:
    logger.info(f"[done] total={total}  clean={clean}  quarantined={quarantined}")
