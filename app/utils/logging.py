"""Structured logging infrastructure."""

import json
import logging
import sys
import warnings
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredLogger:
    """
    Structured logger with concise output support.

    Provides consistent logging across the application with support for
    both human-readable and JSON formats.
    """

    def __init__(
        self,
        name: str,
        log_level: str = "INFO",
        log_format: str = "text",
        log_file: Optional[Path] = None
    ):
        """
        Initialize structured logger.

        Args:
            name: Logger name (typically module name)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_format: Output format ('json' or 'text')
            log_file: Optional file path for logging
        """
        self.name = name
        self.log_format = log_format
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # Suppress noisy library logs
        _suppress_library_noise()

        # Remove existing handlers
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))

        if log_format == "json":
            console_handler.setFormatter(JSONFormatter())
        else:
            console_handler.setFormatter(TextFormatter())

        self.logger.addHandler(console_handler)

        # File handler if specified
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(getattr(logging, log_level.upper()))
            file_handler.setFormatter(JSONFormatter())
            self.logger.addHandler(file_handler)

    def _log(
        self,
        level: str,
        message: str,
        **kwargs: Any
    ) -> None:
        """
        Internal logging method.

        Args:
            level: Log level
            message: Log message
            **kwargs: Additional context fields
        """
        extra = {
            "timestamp": datetime.now().isoformat(),
            "logger_name": self.name,
            **kwargs
        }

        log_method = getattr(self.logger, level.lower())
        log_method(message, extra={"context": extra})

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self._log("ERROR", message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._log("CRITICAL", message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        extra = {
            "timestamp": datetime.now().isoformat(),
            "logger_name": self.name,
            **kwargs
        }
        self.logger.exception(message, extra={"context": extra})


class JSONFormatter(logging.Formatter):
    """JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name
        }

        # Add context if available
        if hasattr(record, "context"):
            log_data.update(record.context)

        # Add exception info if available
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Clean human-readable text formatter."""

    def __init__(self):
        """Initialize text formatter."""
        super().__init__(
            fmt="[%(asctime)s] %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S"
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text."""
        base_message = super().format(record)

        # Add context if available (only specific fields like batch/total)
        if hasattr(record, "context"):
            important_fields = ["batch", "total", "count", "error", "progress"]
            context_parts = [
                f"{k}={v}" for k, v in record.context.items()
                if k in important_fields
            ]
            if context_parts:
                base_message += f" | {' '.join(context_parts)}"

        return base_message


def _suppress_library_noise():
    """Silence noisy third-party libraries."""
    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.filterwarnings("ignore", message=".*Accessing `__path__`.*")
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("github").setLevel(logging.WARNING)


# Global logger cache
_loggers: Dict[str, StructuredLogger] = {}


def get_logger(
    name: str,
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    log_file: Optional[Path] = None
) -> StructuredLogger:
    """
    Get or create a structured logger.

    Args:
        name: Logger name
        log_level: Optional log level override
        log_format: Optional format override
        log_file: Optional log file path

    Returns:
        StructuredLogger instance
    """
    if name not in _loggers:
        # Avoid circular dependency by using defaults if config not loaded
        level = log_level or "INFO"
        fmt = log_format or "text"
        _loggers[name] = StructuredLogger(
            name=name,
            log_level=level,
            log_format=fmt,
            log_file=log_file
        )

    return _loggers[name]


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "text",
    log_dir: Optional[Path] = None
) -> None:
    """
    Setup application-wide logging.

    Args:
        log_level: Default log level
        log_format: Default log format
        log_dir: Directory for log files
    """
    _suppress_library_noise()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(TextFormatter())
    root_logger.addHandler(console_handler)

    # File handler if log directory specified
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

# Made with Bob
