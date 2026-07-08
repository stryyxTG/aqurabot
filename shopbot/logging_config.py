from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import LOG_DIR


DISPLAY_TZ = timezone(timedelta(hours=3), "GMT+3")


class BotLogFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        dt = datetime.fromtimestamp(record.created, DISPLAY_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat(timespec="milliseconds")


def _handler(handler: logging.Handler, level: int, formatter: logging.Formatter) -> logging.Handler:
    handler.setLevel(level)
    handler.setFormatter(formatter)
    return handler


def configure_logging(*, level: int = logging.INFO) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    main_log = LOG_DIR / "bot.log"
    error_log = LOG_DIR / "errors.log"
    formatter = BotLogFormatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)

    handlers: list[logging.Handler] = [
        _handler(logging.StreamHandler(), level, formatter),
        _handler(RotatingFileHandler(main_log, maxBytes=10 * 1024 * 1024, backupCount=7, encoding="utf-8"), level, formatter),
        _handler(RotatingFileHandler(error_log, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"), logging.ERROR, formatter),
    ]
    for handler in handlers:
        root_logger.addHandler(handler)

    for noisy_logger in ("aiogram.event", "aiogram.dispatcher", "telethon.network", "telethon.extensions"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    logging.getLogger("shopbot").info("Logging configured | level=%s | dir=%s", logging.getLevelName(level), Path(LOG_DIR))
