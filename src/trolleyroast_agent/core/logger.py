import json
import logging
import sys
import warnings
from logging.config import dictConfig
from typing import Any

from .config import get_settings

CONSOLE_LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
)

CONSOLE_LOG_FORMAT_DEBUG = (
    "[\033[32m%(asctime)s\033[0m %(levelname)s] "
    "\033[34m%(name)s\033[0m:%(funcName)s:%(lineno)d - \033[36m%(message)s\033[0m"
)

CONSOLE_LOG_DATE_FORMAT = "%H:%M:%S"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S %z"


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)

        log_data = {
            "timestamp": self.formatTime(record, LOG_DATE_FORMAT),
            "level": record.levelname,
            "process": record.process,
            "logger": record.name,
            "message": record.getMessage(),
            "source": f"{record.filename}:{record.lineno}",
        }

        extra = getattr(record, "extra", {})
        log_data.update(extra)

        if record.exc_text:
            log_data["exception"] = record.exc_text

        return json.dumps(log_data)


def setup_logging():
    """Configure applications logging infrastructure."""

    settings = get_settings()

    if not settings.debug and settings.logging.default_level == "DEBUG":
        warnings.warn(
            (
                "DEBUG logging is not recommended for production. "
                "This may lead to leak of sensitive information."
            ),
            stacklevel=2,
        )

    console_format = (
        CONSOLE_LOG_FORMAT_DEBUG
        if settings.debug and sys.stdout.isatty()
        else CONSOLE_LOG_FORMAT
    )

    handlers: dict[str, Any] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console_style",
            "stream": sys.stdout,
        },
    }

    if settings.logging.file_directory is not None:
        settings.logging.file_directory.mkdir(parents=True, exist_ok=True)
        log_file = settings.logging.file_directory / "worker.log"

        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_file),
            "level": settings.logging.file_default_level,
            "formatter": "json_style",
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 10,
            "encoding": "utf8",
        }

    root_handlers = list(handlers.keys())

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console_style": {
                "format": console_format,
                "datefmt": CONSOLE_LOG_DATE_FORMAT,
            },
            "json_style": {
                "()": JsonLogFormatter,
                "datefmt": LOG_DATE_FORMAT,
            },
        },
        "handlers": handlers,
        "loggers": {
            "root": {
                "handlers": root_handlers,
                "level": settings.logging.default_level,
            },
            "httpx": {
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }

    dictConfig(logging_config)
