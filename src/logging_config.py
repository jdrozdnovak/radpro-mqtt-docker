"""Logging configuration for RadPro MQTT Bridge.

This module provides structured logging configuration with support for
both human-readable and JSON output formats.
"""

import json
import logging
import sys
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Formats log records as JSON objects for production environments,
    making logs easier to parse and analyze.

    Requirements: 6.4, 9.9, 10.6
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.

        Args:
            record: The log record to format

        Returns:
            str: JSON-formatted log entry
        """
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from the record
        # Skip standard fields to avoid duplication
        skip_fields = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "stack_info",
        }

        for key, value in record.__dict__.items():
            if key not in skip_fields and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data)


def configure_logging(log_level: str = "INFO", json_format: bool = False) -> None:
    """Configure logging for the application.

    Sets up logging with the specified log level and output format.
    Logs are written to stdout for Docker compatibility.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: If True, use JSON format; if False, use human-readable format

    Requirements: 6.4, 9.9, 10.6
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create handler that logs to stdout (Requirement 6.4)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    # Configure formatter based on format preference
    if json_format:
        # JSON format for production (Requirement 6.4)
        formatter: logging.Formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(handler)

    # Reduce verbosity of third-party libraries
    logging.getLogger("paho.mqtt").setLevel(logging.WARNING)
    logging.getLogger("serial").setLevel(logging.WARNING)

    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configured: level={log_level.upper()}, "
        f"format={'JSON' if json_format else 'text'}"
    )
