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
            message: Primary error message.
            details: Additional error details for debugging.
            original_error: Original exception that caused this error.
        """
        self.message = message
        self.details = details or {}
        self.original_error = original_error

        # Build the full error message
        full_message = message
        if details:
            full_message += f"\nDetails: {details}"
        if original_error:
            full_message += f"\nOriginal error: {str(original_error)}"

        super().__init__(full_message)


class ConfigurationError(AutoApplyError):
    """Raised when there are issues with application configuration."""

    def __init__(
        self, message: str = "Configuration error occurred", **kwargs: Any
    ) -> None:
        """Initialize the configuration error."""
        super().__init__(f"Configuration Error: {message}", **kwargs)


class ProfileError(AutoApplyError):
    """Base class for profile-related errors."""

    def __init__(
        self, message: str = "Profile operation failed", **kwargs: Any
    ) -> None:
        """Initialize the profile error."""
        super().__init__(f"Profile Error: {message}", **kwargs)


class ProfileExtractionError(ProfileError):
    """Raised when profile extraction from PDF fails."""

    def __init__(
        self, message: str = "Failed to extract profile data from PDF", **kwargs: Any
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


class StorageError(AutoApplyError):
    """Base class for storage-related errors."""

    def __init__(
        self, message: str = "Storage operation failed", **kwargs: Any
    ) -> None:
        """Initialize the storage error."""
        super().__init__(f"Storage Error: {message}", **kwargs)


class EncryptionError(StorageError):
    """Raised when encryption or decryption operations fail."""

    def __init__(
        self, message: str = "Encryption operation failed", **kwargs: Any
    ) -> None:
        """Initialize the encryption error."""
        super().__init__(f"Encryption Error: {message}", **kwargs)


class AutomationError(AutoApplyError):
    """Base class for automation-related errors."""

    def __init__(
        self, message: str = "Automation operation failed", **kwargs: Any
    ) -> None:
        """Initialize the automation error."""
        super().__init__(f"Automation Error: {message}", **kwargs)


class BrowserError(AutomationError):
    """Raised when browser automation operations fail."""

    def __init__(
        self, message: str = "Browser operation failed", **kwargs: Any
    ) -> None:
        """Initialize the browser error."""
        super().__init__(f"Browser Error: {message}", **kwargs)


class FormError(AutomationError):
    """Base class for form-related errors."""

    def __init__(self, message: str = "Form operation failed", **kwargs: Any) -> None:
        """Initialize the form error."""
        super().__init__(f"Form Error: {message}", **kwargs)


class FormDetectionError(FormError):
    """Raised when form field detection fails."""

    def __init__(
        self, message: str = "Failed to detect form fields", **kwargs: Any
    ) -> None:
        """Initialize the form detection error."""
        super().__init__(f"Detection Error: {message}", **kwargs)


class FormFillingError(FormError):
    """Raised when form filling operations fail."""

    def __init__(
        self, message: str = "Failed to fill form fields", **kwargs: Any
    ) -> None:
        """Initialize the form filling error."""
        super().__init__(f"Filling Error: {message}", **kwargs)


class FormSubmissionError(FormError):
    """Raised when form submission fails."""

    def __init__(self, message: str = "Failed to submit form", **kwargs: Any) -> None:
        """Initialize the form submission error."""
        super().__init__(f"Submission Error: {message}", **kwargs)


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
        """Initialize the input validation error."""
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
        """Initialize the timeout error."""
        if operation and timeout:
            message = f"{operation} timed out after {timeout} seconds"
        super().__init__(f"Timeout Error: {message}", **kwargs)
