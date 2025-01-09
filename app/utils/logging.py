"""
Logging configuration module for AutoApply.

This module sets up structured logging using structlog and provides
logging utilities for the entire application.
"""

import logging.config
import sys
from typing import Any, Dict, Optional

import structlog
from rich.console import Console
from rich.logging import RichHandler

from app.utils.config import settings

# Console setup for rich output
console = Console()


def setup_logging() -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(message)s",
        datefmt="[%Y-%m-%d %H:%M:%S]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer()
            if sys.stderr.isatty()
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a logger instance for the specified name.

    Args:
        name: The name of the logger, typically __name__ of the module.

    Returns:
        A configured structured logger instance.
    """
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the logger for the class."""
        super().__init__(*args, **kwargs)
        self.logger = get_logger(self.__class__.__name__)

    def log_operation_start(self, operation: str, **kwargs: Any) -> None:
        """
        Log the start of an operation.

        Args:
            operation: The name of the operation being started.
            **kwargs: Additional context to include in the log.
        """
        self.logger.info(f"Starting {operation}", **kwargs)

    def log_operation_end(self, operation: str, **kwargs: Any) -> None:
        """
        Log the successful completion of an operation.

        Args:
            operation: The name of the completed operation.
            **kwargs: Additional context to include in the log.
        """
        self.logger.info(f"Completed {operation}", **kwargs)

    def log_error(
        self, error: Exception, operation: Optional[str] = None, **kwargs: Any
    ) -> None:
        """
        Log an error that occurred during an operation.

        Args:
            error: The exception that occurred.
            operation: The name of the operation during which the error occurred.
            **kwargs: Additional context to include in the log.
        """
        context = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            **kwargs,
        }
        if operation:
            self.logger.error(f"Error during {operation}", **context)
        else:
            self.logger.error("Error occurred", **context)


# Initialize logging when the module is imported
setup_logging()
