"""Unit tests for logging configuration.

Tests the logging configuration functionality including JSON formatting
and log level configuration.
"""

import json
import logging

from src.logging_config import JSONFormatter, configure_logging


class TestJSONFormatter:
    """Test cases for JSONFormatter."""

    def test_json_formatter_basic(self) -> None:
        """Test basic JSON formatting of log records.

        Verifies that log records are formatted as valid JSON with
        required fields: timestamp, level, logger, message.
        """
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")

        # Create a log record
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Format the record
        formatted = formatter.format(record)

        # Parse JSON
        log_data = json.loads(formatted)

        # Verify required fields
        assert "timestamp" in log_data
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.logger"
        assert log_data["message"] == "Test message"

    def test_json_formatter_with_exception(self) -> None:
        """Test JSON formatting with exception information.

        Verifies that exception information is included in the JSON output.
        """
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")

        # Create an exception
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        # Create a log record with exception
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        # Format the record
        formatted = formatter.format(record)

        # Parse JSON
        log_data = json.loads(formatted)

        # Verify exception field exists
        assert "exception" in log_data
        assert "ValueError: Test error" in log_data["exception"]

    def test_json_formatter_with_extra_fields(self) -> None:
        """Test JSON formatting with extra fields.

        Verifies that extra fields added to the log record are included
        in the JSON output.
        """
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")

        # Create a log record
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add extra fields
        record.user_id = "12345"  # type: ignore
        record.request_id = "abc-def"  # type: ignore

        # Format the record
        formatted = formatter.format(record)

        # Parse JSON
        log_data = json.loads(formatted)

        # Verify extra fields are included
        assert log_data["user_id"] == "12345"
        assert log_data["request_id"] == "abc-def"


class TestConfigureLogging:
    """Test cases for configure_logging function."""

    def test_configure_logging_text_format(self) -> None:
        """Test logging configuration with text format.

        Verifies that logging is configured with text format and
        the specified log level.
        """
        # Clear existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Configure logging
        configure_logging(log_level="DEBUG", json_format=False)

        # Verify root logger level
        assert root_logger.level == logging.DEBUG

        # Verify handler exists
        assert len(root_logger.handlers) > 0

        # Verify formatter is not JSONFormatter
        handler = root_logger.handlers[0]
        assert not isinstance(handler.formatter, JSONFormatter)

    def test_configure_logging_json_format(self) -> None:
        """Test logging configuration with JSON format.

        Verifies that logging is configured with JSON format.
        """
        # Clear existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Configure logging
        configure_logging(log_level="INFO", json_format=True)

        # Verify root logger level
        assert root_logger.level == logging.INFO

        # Verify handler exists
        assert len(root_logger.handlers) > 0

        # Verify formatter is JSONFormatter
        handler = root_logger.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_configure_logging_log_levels(self) -> None:
        """Test logging configuration with different log levels.

        Verifies that different log levels are correctly configured.
        """
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level_str in log_levels:
            # Clear existing handlers
            root_logger = logging.getLogger()
            root_logger.handlers.clear()

            # Configure logging
            configure_logging(log_level=level_str, json_format=False)

            # Verify root logger level
            expected_level = getattr(logging, level_str)
            assert root_logger.level == expected_level

    def test_configure_logging_case_insensitive(self) -> None:
        """Test logging configuration with case-insensitive log level.

        Verifies that log level strings are case-insensitive.
        """
        # Clear existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Configure logging with lowercase level
        configure_logging(log_level="info", json_format=False)

        # Verify root logger level
        assert root_logger.level == logging.INFO

    def test_configure_logging_third_party_loggers(self) -> None:
        """Test that third-party loggers are configured with reduced verbosity.

        Verifies that paho.mqtt and serial loggers are set to WARNING level.
        """
        # Clear existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Configure logging
        configure_logging(log_level="DEBUG", json_format=False)

        # Verify third-party loggers are set to WARNING
        paho_logger = logging.getLogger("paho.mqtt")
        serial_logger = logging.getLogger("serial")

        assert paho_logger.level == logging.WARNING
        assert serial_logger.level == logging.WARNING
