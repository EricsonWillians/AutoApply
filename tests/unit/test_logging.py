"""
Unit tests for the logging module.

This module contains comprehensive tests for the application logging system,
ensuring proper log message handling, structured logging configuration,
and integration with the rich console output.

File location: tests/unit/test_logging.py
"""

import logging
import sys
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest
import structlog
from rich.console import Console

from app.utils.config import settings
from app.utils.logging import LoggerMixin, get_logger, setup_logging


@pytest.fixture
def mock_console():
    """Provide a mock console for testing."""
    return Mock(spec=Console)


@pytest.fixture
def sample_log_context():
    """Provide sample context data for log messages."""
    return {
        "operation": "test_operation",
        "user_id": "test123",
        "duration": 1.5,
        "status": "success",
    }


class TestLoggingSetup:
    """Tests for logging system initialization."""

    def test_logging_configuration(self):
        """Test basic logging configuration setup."""
        setup_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.getLevelName(settings.log_level)
        assert len(root_logger.handlers) > 0
        assert any(
            isinstance(handler, logging.StreamHandler)
            for handler in root_logger.handlers
        )

    def test_structlog_configuration(self):
        """Test structured logging configuration."""
        setup_logging()

        # Verify processors
        processors = structlog.get_config()["processors"]
        assert any("merge_contextvars" in str(p) for p in processors)
        assert any("add_log_level" in str(p) for p in processors)
        assert any("TimeStamper" in str(p) for p in processors)

    def test_console_handler_configuration(self, mock_console):
        """Test rich console handler setup."""
        with patch("rich.console.Console", return_value=mock_console):
            setup_logging()

            root_logger = logging.getLogger()
            rich_handlers = [
                h for h in root_logger.handlers if "RichHandler" in str(type(h))
            ]

            assert len(rich_handlers) > 0
            assert rich_handlers[0].console == mock_console

    def test_log_level_validation(self):
        """Test validation of log levels."""
        with patch.object(settings, "log_level", "INVALID"):
            with pytest.raises(ValueError):
                setup_logging()

        with patch.object(settings, "log_level", "DEBUG"):
            setup_logging()
            assert logging.getLogger().level == logging.DEBUG


class TestLoggerRetrieval:
    """Tests for logger instance retrieval."""

    def test_get_logger(self):
        """Test getting a logger instance."""
        setup_logging()
        logger = get_logger("test_logger")

        assert isinstance(logger, structlog.BoundLogger)
        assert logger._context.get("logger_name") == "test_logger"

    def test_logger_context_isolation(self):
        """Test isolation between different logger instances."""
        setup_logging()
        logger1 = get_logger("logger1")
        logger2 = get_logger("logger2")

        logger1.bind(key="value1")
        logger2.bind(key="value2")

        assert logger1._context != logger2._context


class SampleClass(LoggerMixin):
    """Sample class for testing LoggerMixin."""

    def __init__(self):
        """Initialize the sample class."""
        super().__init__()


class TestLoggerMixin:
    """Tests for the LoggerMixin functionality."""

    def test_mixin_initialization(self):
        """Test logger initialization in mixin."""
        instance = SampleClass()
        assert hasattr(instance, "logger")
        assert isinstance(instance.logger, structlog.BoundLogger)

    def test_operation_logging(self):
        """Test operation logging methods."""
        instance = SampleClass()

        # Test start logging
        instance.log_operation_start("test_operation", param1="value1", param2="value2")

        # Test end logging
        instance.log_operation_end("test_operation", duration=1.5, status="success")

    def test_error_logging(self):
        """Test error logging functionality."""
        instance = SampleClass()
        test_error = ValueError("Test error")

        instance.log_error(test_error, "test_operation", detail="Additional context")

    def test_context_preservation(self):
        """Test preservation of logging context."""
        instance = SampleClass()

        with structlog.threadlocal.tmp_bind(instance.logger):
            instance.logger.bind(request_id="123")
            instance.log_operation_start("test_operation")

            # Verify context is preserved
            assert "request_id" in instance.logger._context


class TestLogFormatting:
    """Tests for log message formatting."""

    def test_json_formatting(self):
        """Test JSON log formatting."""
        setup_logging()
        logger = get_logger("test_json")

        with patch("sys.stderr.isatty", return_value=False):
            with patch("structlog.processors.JSONRenderer.__call__") as json_mock:
                logger.info("test message")
                assert json_mock.called

    def test_console_formatting(self):
        """Test console log formatting."""
        setup_logging()
        logger = get_logger("test_console")

        with patch("sys.stderr.isatty", return_value=True):
            with patch("structlog.dev.ConsoleRenderer.__call__") as console_mock:
                logger.info("test message")
                assert console_mock.called

    def test_timestamp_formatting(self):
        """Test timestamp formatting in logs."""
        setup_logging()
        logger = get_logger("test_timestamp")

        with patch("structlog.processors.TimeStamper.__call__") as time_mock:
            logger.info("test message")
            assert time_mock.called


class TestLoggingIntegration:
    """Integration tests for logging functionality."""

    def test_complete_logging_workflow(self, sample_log_context):
        """Test complete logging workflow with context."""
        setup_logging()
        logger = get_logger("test_integration")

        # Bind initial context
        logger = logger.bind(session_id="test_session")

        # Log operation start
        logger.info("Operation started", operation=sample_log_context["operation"])

        # Log operation details
        logger.debug("Processing data", **sample_log_context)

        # Log operation completion
        logger.info("Operation completed", duration=sample_log_context["duration"])

    def test_error_handling_workflow(self):
        """Test error logging workflow."""
        setup_logging()
        logger = get_logger("test_error_handling")

        try:
            raise ValueError("Test error")
        except Exception as e:
            logger.error(
                "Operation failed",
                error_type=type(e).__name__,
                error_message=str(e),
                traceback=True,
            )

    def test_structured_data_logging(self, sample_log_context):
        """Test logging of structured data."""
        setup_logging()
        logger = get_logger("test_structured")

        # Log structured data
        logger.info(
            "Structured log message",
            **sample_log_context,
            extra_field={"nested": {"data": "value"}}
        )


if __name__ == "__main__":
    pytest.main(["-v"])
