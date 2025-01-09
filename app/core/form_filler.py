"""
Form filling module for AutoApply.

This module handles automated form detection and filling using Playwright
for web automation and integrates with our AI-powered field mapping service.

File location: app/core/form_filler.py
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import Browser, BrowserContext, Page, Response
from pydantic import BaseModel

from app.services.huggingface_integration import huggingface_service
from app.utils.config import settings
from app.utils.logging import LoggerMixin


class FormField(BaseModel):
    """Model representing a form field."""

    selector: str
    field_type: str
    label: str
    required: bool
    value: Optional[str] = None
    confidence: float = 0.0


class FormFillingError(Exception):
    """Custom exception for form filling errors."""

    pass


class FormFiller(LoggerMixin):
    """Handles automated form detection and filling."""

    def __init__(self) -> None:
        """Initialize the form filler."""
        super().__init__()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.profile_data: Dict[str, Any] = {}

    async def initialize(self, profile_data: Dict[str, Any]) -> None:
        """
        Initialize the form filler with profile data.

        Args:
            profile_data: The user's profile data for form filling.
        """
        try:
            self.log_operation_start("initialization")
            self.profile_data = profile_data

            # Initialize Hugging Face service if not already initialized
            await huggingface_service.initialize()

            self.log_operation_end("initialization")

        except Exception as e:
            self.log_error(e, "initialization")
            raise FormFillingError(f"Failed to initialize form filler: {str(e)}")

    async def start_browser(self) -> None:
        """Start the browser session."""
        try:
            self.log_operation_start("browser startup")

            from playwright.async_api import async_playwright

            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=settings.headless, args=settings.browser_args
            )

            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()

            self.log_operation_end("browser startup")

        except Exception as e:
            self.log_error(e, "browser startup")
            raise FormFillingError(f"Failed to start browser: {str(e)}")

    async def navigate_to_form(self, url: str) -> None:
        """
        Navigate to the form URL.

        Args:
            url: The URL of the job application form.
        """
        try:
            self.log_operation_start("navigation", url=url)

            if not self.page:
                await self.start_browser()

            response = await self.page.goto(url, wait_until="networkidle")

            if not response:
                raise FormFillingError("Failed to load page")

            if response.status >= 400:
                raise FormFillingError(f"Page returned status code {response.status}")

            self.log_operation_end("navigation")

        except Exception as e:
            self.log_error(e, "navigation")
            raise FormFillingError(f"Failed to navigate to form: {str(e)}")

    async def detect_form_fields(self) -> List[FormField]:
        """
        Detect and analyze form fields on the current page.

        Returns:
            List of detected form fields with their properties.
        """
        try:
            self.log_operation_start("form detection")

            if not self.page:
                raise FormFillingError("Browser not initialized")

            # Detect form fields using Playwright
            fields = []

            # Find input elements
            input_elements = await self.page.query_selector_all(
                "input:not([type='hidden']), select, textarea"
            )

            for element in input_elements:
                # Get field properties
                field_type = await element.get_attribute("type") or "text"
                name = await element.get_attribute("name")
                id_attr = await element.get_attribute("id")
                placeholder = await element.get_attribute("placeholder")
                required = await element.get_attribute("required") is not None

                # Find label for the field
                label = await self._find_field_label(element, id_attr)

                # Create field object
                field = FormField(
                    selector=f"#{id_attr}" if id_attr else f"[name='{name}']",
                    field_type=field_type,
                    label=label or placeholder or name or "",
                    required=required,
                )

                fields.append(field)

            self.log_operation_end("form detection", field_count=len(fields))
            return fields

        except Exception as e:
            self.log_error(e, "form detection")
            raise FormFillingError(f"Failed to detect form fields: {str(e)}")

    async def fill_form(
        self, fields: List[FormField], resume_path: Optional[Path] = None
    ) -> List[FormField]:
        """
        Fill detected form fields with profile data.

        Args:
            fields: List of detected form fields.
            resume_path: Optional path to resume file for upload.

        Returns:
            List of filled form fields with confidence scores.
        """
        try:
            self.log_operation_start("form filling")

            if not self.page:
                raise FormFillingError("Browser not initialized")

            filled_fields = []

            for field in fields:
                # Skip file upload fields if no resume provided
                if field.field_type == "file" and not resume_path:
                    continue

                # Handle file upload
                if field.field_type == "file" and resume_path:
                    await self._handle_file_upload(field, resume_path)
                    filled_fields.append(field)
                    continue

                # Map field to profile data
                value, confidence = await self._map_field_value(field)

                if value:
                    # Fill the field
                    await self._fill_field(field, value)

                    field.value = value
                    field.confidence = confidence
                    filled_fields.append(field)

            self.log_operation_end("form filling", filled_count=len(filled_fields))
            return filled_fields

        except Exception as e:
            self.log_error(e, "form filling")
            raise FormFillingError(f"Failed to fill form: {str(e)}")

    async def submit_form(self) -> Optional[Response]:
        """
        Submit the filled form.

        Returns:
            Optional[Response]: The response from form submission.
        """
        try:
            self.log_operation_start("form submission")

            if not self.page:
                raise FormFillingError("Browser not initialized")

            # Find submit button
            submit_button = await self.page.query_selector(
                "button[type='submit'], input[type='submit']"
            )

            if not submit_button:
                raise FormFillingError("Submit button not found")

            # Click submit and wait for navigation
            async with self.page.expect_navigation() as navigation:
                await submit_button.click()
                response = await navigation.value

            self.log_operation_end("form submission")
            return response

        except Exception as e:
            self.log_error(e, "form submission")
            raise FormFillingError(f"Failed to submit form: {str(e)}")

    async def cleanup(self) -> None:
        """Clean up browser resources."""
        try:
            if self.browser:
                await self.browser.close()
                self.browser = None
                self.context = None
                self.page = None

        except Exception as e:
            self.log_error(e, "cleanup")
            raise FormFillingError(f"Failed to clean up resources: {str(e)}")

    async def _find_field_label(
        self, element: Any, element_id: Optional[str]
    ) -> Optional[str]:
        """Find the label text for a form field."""
        try:
            # Check for aria-label
            aria_label = await element.get_attribute("aria-label")
            if aria_label:
                return aria_label

            # Check for associated label element
            if element_id:
                label_element = await self.page.query_selector(
                    f"label[for='{element_id}']"
                )
                if label_element:
                    return await label_element.inner_text()

            # Check for parent label element
            parent_label = await element.evaluate(
                "el => el.closest('label')?.textContent"
            )
            if parent_label:
                return parent_label

            return None

        except Exception:
            return None

    async def _map_field_value(self, field: FormField) -> Tuple[str, float]:
        """Map form field to profile data using AI service."""
        try:
            # Get candidate values for selection fields
            candidate_values = None
            if field.field_type in ["select", "radio"]:
                candidate_values = await self._get_field_options(field)

            # Use Hugging Face service to map field
            value, confidence = await huggingface_service.map_field(
                field.label, field.field_type, self.profile_data, candidate_values
            )

            return value, confidence

        except Exception as e:
            self.log_error(e, "field mapping")
            return "", 0.0

    async def _get_field_options(self, field: FormField) -> List[str]:
        """Get available options for selection fields."""
        try:
            options = []

            if field.field_type == "select":
                option_elements = await self.page.query_selector_all(
                    f"{field.selector} option"
                )
                for option in option_elements:
                    text = await option.inner_text()
                    if text:
                        options.append(text)

            elif field.field_type == "radio":
                radio_elements = await self.page.query_selector_all(
                    f"input[type='radio'][name='{field.selector}']"
                )
                for radio in radio_elements:
                    label = await self._find_field_label(
                        radio, await radio.get_attribute("id")
                    )
                    if label:
                        options.append(label)

            return options

        except Exception:
            return []

    async def _fill_field(self, field: FormField, value: str) -> None:
        """Fill a form field with the provided value."""
        try:
            if field.field_type in ["text", "email", "tel", "url"]:
                await self.page.fill(field.selector, value)

            elif field.field_type == "select":
                await self.page.select_option(field.selector, value)

            elif field.field_type == "radio":
                await self.page.check(f"input[type='radio'][value='{value}']")

            elif field.field_type == "textarea":
                await self.page.fill(field.selector, value)

        except Exception as e:
            self.log_error(e, "field filling")
            raise FormFillingError(f"Failed to fill field {field.selector}: {str(e)}")

    async def _handle_file_upload(self, field: FormField, file_path: Path) -> None:
        """Handle file upload fields."""
        try:
            if not file_path.exists():
                raise FormFillingError(f"Resume file not found: {file_path}")

            await self.page.set_input_files(field.selector, str(file_path))

        except Exception as e:
            self.log_error(e, "file upload")
            raise FormFillingError(f"Failed to upload file: {str(e)}")


# Global instance
form_filler = FormFiller()
