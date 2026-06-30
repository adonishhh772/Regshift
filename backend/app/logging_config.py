import logging
import os
import sys
from typing import Final

LOG_FORMAT: Final[str] = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"


def resolve_log_level() -> int:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def configure_logging() -> None:
    level = resolve_log_level()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "app"):
        named_logger = logging.getLogger(logger_name)
        named_logger.setLevel(level)
        named_logger.propagate = True

    logging.getLogger(__name__).info("Logging configured level=%s", logging.getLevelName(level))
