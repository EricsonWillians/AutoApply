# app/utils/exceptions.py

"""
Exceptions module for AutoApply.

This module defines all custom exceptions used throughout the application,
providing consistent error handling and informative error messages for both
debugging and user feedback.

File location: app/utils/exceptions.py
"""

from typing import Any, Dict, Optional


class AutoApplyError(Exception):
    """Base exception class for AutoApply application."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        """
        Initialize the base exception.

        Args:
            message: Primary error message
            details: Additional error details for debugging
            original_error: Original exception that caused this error
        """
        self.message = message
        self.details = details or {}
        self.original_error = original_error

        full_message = message
        if details:
            full_message += f"\nDetails: {details}"
        if original_error:
            full_message += f"\nOriginal error: {str(original_error)}"

        super().__init__(full_message)


class ProfileError(AutoApplyError):
    """Base class for profile-related errors."""

    def __init__(
        self, message: str = "Profile operation failed", **kwargs: Any
    ) -> None:
        """Initialize the profile error."""
        super().__init__(f"Profile Error: {message}", **kwargs)


class ProfileParsingError(ProfileError):
    """Raised when parsing LinkedIn profile content fails."""

    def __init__(
        self, message: str = "Failed to parse profile content", **kwargs: Any
    ) -> None:
        """Initialize the profile parsing error."""
        super().__init__(f"Parsing Error: {message}", **kwargs)


class ProfileExtractionError(ProfileError):
    """Raised when profile extraction from PDF fails."""

    def __init__(
        self, message: str = "Failed to extract profile data", **kwargs: Any
    ) -> None:
        """Initialize the profile extraction error."""
        super().__init__(f"Extraction Error: {message}", **kwargs)


class ProfileValidationError(ProfileError):
    """Raised when profile data validation fails."""

    def __init__(
        self, message: str = "Profile data validation failed", **kwargs: Any
    ) -> None:
        """Initialize the profile validation error."""
        super().__init__(f"Validation Error: {message}", **kwargs)


class PDFError(AutoApplyError):
    """Base class for PDF-related errors."""

    def __init__(self, message: str = "PDF operation failed", **kwargs: Any) -> None:
        """Initialize the PDF error."""
        super().__init__(f"PDF Error: {message}", **kwargs)


class PDFExtractionError(PDFError):
    """Raised when text extraction from PDF fails."""

    def __init__(
        self, message: str = "Failed to extract text from PDF", **kwargs: Any
    ) -> None:
        """Initialize the PDF extraction error."""
        super().__init__(f"Extraction Error: {message}", **kwargs)


class AIError(AutoApplyError):
    """Base class for AI-related errors."""

    def __init__(self, message: str = "AI operation failed", **kwargs: Any) -> None:
        """Initialize the AI error."""
        super().__init__(f"AI Error: {message}", **kwargs)


class ModelError(AIError):
    """Raised when AI model operations fail."""

    def __init__(self, message: str = "Model operation failed", **kwargs: Any) -> None:
        """Initialize the model error."""
        super().__init__(f"Model Error: {message}", **kwargs)


class FieldMappingError(AIError):
    """Raised when AI field mapping or classification fails."""

    def __init__(
        self, message: str = "Field mapping operation failed", **kwargs: Any
    ) -> None:
        """Initialize the field mapping error."""
        super().__init__(f"Field Mapping Error: {message}", **kwargs)


class ValidationError(AutoApplyError):
    """Base class for validation-related errors."""

    def __init__(self, message: str = "Validation failed", **kwargs: Any) -> None:
        """Initialize the validation error."""
        super().__init__(f"Validation Error: {message}", **kwargs)


class InputValidationError(ValidationError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str = "Input validation failed",
        field: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the input validation error.

        Args:
            message: Error message
            field: Name of the problematic field
            **kwargs: Additional error details
        """
        if field:
            message = f"Input validation failed for field '{field}': {message}"
        super().__init__(message, **kwargs)


class SecurityError(AutoApplyError):
    """Base class for security-related errors."""

    def __init__(self, message: str = "Security check failed", **kwargs: Any) -> None:
        """Initialize the security error."""
        super().__init__(f"Security Error: {message}", **kwargs)


class VerificationError(SecurityError):
    """Raised when verification operations fail."""

    def __init__(self, message: str = "Verification failed", **kwargs: Any) -> None:
        """Initialize the verification error."""
        super().__init__(f"Verification Error: {message}", **kwargs)


class TimeoutError(AutoApplyError):
    """Raised when operations exceed their time limit."""

    def __init__(
        self,
        message: str = "Operation timed out",
        operation: Optional[str] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the timeout error.

        Args:
            message: Error message
            operation: Name of the operation that timed out
            timeout: Duration after which the operation timed out
            **kwargs: Additional error details
        """
        if operation and timeout:
            message = f"{operation} timed out after {timeout} seconds"
        super().__init__(f"Timeout Error: {message}", **kwargs)
