"""
Verification module for AutoApply.

This module handles the human verification process for form submissions,
ensuring accuracy and user control over automated form filling.

File location: app/core/verification.py
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from playwright.async_api import Page
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.core.form_filler import FormField
from app.utils.config import settings
from app.utils.logging import LoggerMixin


class VerificationError(Exception):
    """Custom exception for verification errors."""

    pass


class VerificationResult(BaseModel):
    """Model representing the verification result."""

    approved: bool
    modifications: Dict[str, str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    verification_duration: float
    confidence_threshold_met: bool


class FormVerification(LoggerMixin):
    """Handles human verification of filled form data."""

    def __init__(self, console: Optional[Console] = None) -> None:
        """
        Initialize the form verification handler.

        Args:
            console: Optional Rich console instance for output.
        """
        super().__init__()
        self.console = console or Console()
        self._verification_start: Optional[datetime] = None

    async def verify_form_data(
        self,
        page: Page,
        filled_fields: List[FormField],
        confidence_threshold: float = 0.8,
    ) -> VerificationResult:
        """
        Present filled form data for human verification.

        Args:
            page: The Playwright page containing the form.
            filled_fields: List of filled form fields.
            confidence_threshold: Minimum confidence score for automatic approval.

        Returns:
            VerificationResult containing the verification outcome.
        """
        try:
            self.log_operation_start("form verification")
            self._verification_start = datetime.utcnow()

            # Present form data for verification
            await self._display_verification_interface(filled_fields)

            # Check confidence scores
            confidence_threshold_met = all(
                field.confidence >= confidence_threshold
                for field in filled_fields
                if field.field_type != "file"
            )

            # Get user verification
            modifications: Dict[str, str] = {}
            approved = False

            while not approved:
                # Display verification prompt
                self.console.print(
                    "\nPlease verify the filled form data:", style="bold blue"
                )
                self.console.print("1. Approve and submit")
                self.console.print("2. Modify fields")
                self.console.print("3. Cancel submission")

                choice = await self._get_user_input("Enter your choice (1-3): ")

                if choice == "1":
                    approved = True
                elif choice == "2":
                    modifications = await self._handle_modifications(
                        page, filled_fields
                    )
                elif choice == "3":
                    raise VerificationError("Submission cancelled by user")
                else:
                    self.console.print(
                        "Invalid choice. Please try again.", style="bold red"
                    )

            # Calculate verification duration
            verification_duration = (
                datetime.utcnow() - self._verification_start
            ).total_seconds()

            result = VerificationResult(
                approved=approved,
                modifications=modifications,
                verification_duration=verification_duration,
                confidence_threshold_met=confidence_threshold_met,
            )

            self.log_operation_end(
                "form verification",
                approved=approved,
                modification_count=len(modifications),
            )

            return result

        except Exception as e:
            self.log_error(e, "form verification")
            raise VerificationError(f"Verification failed: {str(e)}")

    async def _display_verification_interface(
        self, filled_fields: List[FormField]
    ) -> None:
        """
        Display the verification interface with filled form data.

        Args:
            filled_fields: List of filled form fields.
        """
        # Create a table for field display
        table = Table(
            title="Form Field Verification",
            show_header=True,
            header_style="bold magenta",
        )

        # Add columns
        table.add_column("Field", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Value", style="yellow")
        table.add_column("Confidence", style="blue")

        # Add rows for each field
        for field in filled_fields:
            confidence_color = "green" if field.confidence >= 0.8 else "yellow"
            if field.confidence < 0.6:
                confidence_color = "red"

            table.add_row(
                field.label,
                field.field_type,
                str(field.value),
                f"{field.confidence:.2%}" if field.field_type != "file" else "N/A",
                style=None if field.required else "dim",
            )

        # Display the table
        self.console.print(table)

    async def _handle_modifications(
        self, page: Page, filled_fields: List[FormField]
    ) -> Dict[str, str]:
        """
        Handle user modifications to filled form data.

        Args:
            page: The Playwright page containing the form.
            filled_fields: List of filled form fields.

        Returns:
            Dictionary of modifications made by the user.
        """
        modifications = {}

        self.console.print("\nEnter field modifications:", style="bold blue")
        self.console.print("(Press Enter without input to skip a field)")

        for field in filled_fields:
            if field.field_type == "file":
                continue

            current_value = field.value or ""
            new_value = await self._get_user_input(f"{field.label} [{current_value}]: ")

            if new_value and new_value != current_value:
                modifications[field.selector] = new_value
                # Update the field value
                await page.fill(field.selector, new_value)
                field.value = new_value

        return modifications

    async def _get_user_input(self, prompt: str) -> str:
        """
        Get user input from the console.

        Args:
            prompt: The prompt to display to the user.

        Returns:
            The user's input as a string.
        """
        self.console.print(prompt, end="", style="yellow")
        return await asyncio.get_event_loop().run_in_executor(None, input)

    async def handle_verification_timeout(self) -> None:
        """Handle verification timeout by cleaning up resources."""
        if self._verification_start:
            elapsed = (datetime.utcnow() - self._verification_start).total_seconds()

            if elapsed >= settings.verification_timeout:
                self.log_error(
                    Exception("Verification timeout"), "verification timeout"
                )
                raise VerificationError(
                    f"Verification timed out after {settings.verification_timeout} seconds"
                )


# Global instance
form_verification = FormVerification()
