from __future__ import annotations

import logging
import os
import re
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_DEFAULT_LEVEL = "INFO"
_CONFIGURED = False


def _configure_logger() -> None:
    """Configure the shared API logger once."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    level_name = os.getenv("API_LOG_LEVEL", _DEFAULT_LEVEL).upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    handler = TimedRotatingFileHandler(
        LOG_DIR / "api.log",
        when="midnight",
        backupCount=int(os.getenv("API_LOG_RETENTION_DAYS", "14")),
        encoding="utf-8",
    )
    handler.suffix = "%Y-%m-%d.log"
    handler.extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}\.log$")
    handler.setFormatter(formatter)

    logger = logging.getLogger("api")
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False

    if os.getenv("API_STDOUT_LOG", "false").lower() in {"1", "true", "yes"}:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    _CONFIGURED = True


def get_api_logger(name: str | None = None) -> logging.Logger:
    """Return a scoped API logger."""
    _configure_logger()
    base = logging.getLogger("api")
    return base if not name else base.getChild(name)
