"""Console and rotating-file logging with EST timestamps."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

from app.config import Settings

EST = ZoneInfo("America/New_York")


class EstFormatter(logging.Formatter):
    """Format records with a localized America/New_York timestamp."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        from datetime import datetime

        stamp = datetime.fromtimestamp(record.created, tz=EST)
        if datefmt:
            return stamp.strftime(datefmt)
        return stamp.strftime("%Y-%m-%d %H:%M:%S %Z")


def setup_logging(settings: Settings) -> logging.Logger:
    """Attach rotating file and console handlers. Returns the app logger."""
    settings.log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = EstFormatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S %Z",
    )
    logger = logging.getLogger()
    logger.setLevel(settings.log_level.upper())
    logger.handlers.clear()

    file_handler = RotatingFileHandler(
        settings.log_path,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    app_logger = logging.getLogger(settings.app_name)
    app_logger.debug("Logging initialized at %s", settings.log_path)
    return app_logger
