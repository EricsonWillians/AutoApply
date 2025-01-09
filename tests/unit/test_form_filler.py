"""
Unit tests for the form filler module.

This module contains comprehensive tests for the form filling functionality,
ensuring reliable form detection, field mapping, and submission processes.

File location: tests/unit/test_form_filler.py
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from playwright.async_api import Browser, BrowserContext, Page, Response

from app.core.form_filler import (FormField, FormFiller, FormFillingError,
                                  form_filler)
from app.services.huggingface_integration import huggingface_service


@pytest.fixture
def sample_profile_data() -> Dict[str, Any]:
    """Provide sample profile data for testing."""
    return {
        "full_name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+1234567890",
        "headline": "Senior Software Engineer",
        "location": "San Francisco Bay Area",
        "skills": ["Python", "JavaScript", "Docker"],
        "languages": ["English", "Spanish"],
    }


@pytest.fixture
def sample_form_fields() -> List[FormField]:
    """Provide sample form fields for testing."""
    return [
        FormField(
            selector="#full_name", field_type="text", label="Full Name", required=True
        ),
        FormField(
            selector="#email", field_type="email", label="Email Address", required=True
        ),
        FormField(
            selector="#phone", field_type="tel", label="Phone Number", required=False
        ),
        FormField(
            selector="#resume", field_type="file", label="Resume Upload", required=True
        ),
        FormField(
            selector="#preferred_language",
            field_type="select",
            label="Preferred Language",
            required=True,
        ),
    ]


@pytest.fixture
async def mock_browser() -> Mock:
    """Provide a mock browser instance."""
    browser = Mock(spec=Browser)
    browser.new_context = AsyncMock(return_value=Mock(spec=BrowserContext))
    return browser


@pytest.fixture
async def mock_page() -> Mock:
    """Provide a mock page instance."""
    page = Mock(spec=Page)
    page.goto = AsyncMock(return_value=Mock(spec=Response, status=200, ok=True))
    page.query_selector_all = AsyncMock(return_value=[])
    page.query_selector = AsyncMock(return_value=Mock())
    return page


@pytest.fixture
async def form_filler_instance(
    mock_browser: Mock, mock_page: Mock, sample_profile_data: Dict[str, Any]
) -> FormFiller:
    """Provide a configured FormFiller instance."""
    filler = FormFiller()
    filler.browser = mock_browser
    filler.page = mock_page
    await filler.initialize(sample_profile_data)
    return filler


@pytest.mark.asyncio
class TestFormFiller:
    """Tests for the FormFiller class."""

    async def test_initialization(
        self, form_filler_instance: FormFiller, sample_profile_data: Dict[str, Any]
    ):
        """Test FormFiller initialization."""
        assert form_filler_instance.profile_data == sample_profile_data
        assert form_filler_instance.browser is not None
        assert form_filler_instance.page is not None

    async def test_browser_startup(self, form_filler_instance: FormFiller):
        """Test browser startup process."""
        with patch("playwright.async_api.async_playwright") as mock_playwright:
            mock_playwright.return_value.start = AsyncMock()
            mock_playwright.return_value.chromium.launch = AsyncMock(
                return_value=Mock(spec=Browser)
            )

            await form_filler_instance.start_browser()
            assert form_filler_instance.browser is not None
            assert form_filler_instance.context is not None
            assert form_filler_instance.page is not None

    async def test_navigation(self, form_filler_instance: FormFiller, mock_page: Mock):
        """Test navigation to form URL."""
        url = "https://example.com/apply"
        await form_filler_instance.navigate_to_form(url)

        mock_page.goto.assert_called_once_with(url, wait_until="networkidle")

    async def test_navigation_error(
        self, form_filler_instance: FormFiller, mock_page: Mock
    ):
        """Test handling of navigation errors."""
        mock_page.goto = AsyncMock(
            return_value=Mock(spec=Response, status=404, ok=False)
        )

        with pytest.raises(FormFillingError):
            await form_filler_instance.navigate_to_form("https://example.com")

    async def test_form_field_detection(
        self, form_filler_instance: FormFiller, mock_page: Mock
    ):
        """Test form field detection."""

        # Mock element attributes
        async def mock_get_attribute(attr: str) -> str:
            attributes = {
                "type": "text",
                "name": "full_name",
                "id": "full_name",
                "required": "required",
            }
            return attributes.get(attr)

        element = Mock()
        element.get_attribute = AsyncMock(side_effect=mock_get_attribute)
        mock_page.query_selector_all.return_value = [element]

        fields = await form_filler_instance.detect_form_fields()
        assert len(fields) > 0
        assert isinstance(fields[0], FormField)

    async def test_field_mapping(
        self, form_filler_instance: FormFiller, sample_form_fields: List[FormField]
    ):
        """Test field mapping with profile data."""
        with patch.object(
            huggingface_service, "map_field", new_callable=AsyncMock
        ) as mock_map:
            mock_map.return_value = ("John Doe", 0.95)

            field = sample_form_fields[0]  # Full Name field
            value, confidence = await form_filler_instance._map_field_value(field)

            assert value == "John Doe"
            assert confidence == 0.95
            mock_map.assert_called_once()

    async def test_form_filling(
        self,
        form_filler_instance: FormFiller,
        sample_form_fields: List[FormField],
        mock_page: Mock,
    ):
        """Test form filling process."""
        with patch.object(
            form_filler_instance, "_map_field_value", new_callable=AsyncMock
        ) as mock_map:
            mock_map.return_value = ("Test Value", 0.9)

            filled_fields = await form_filler_instance.fill_form(sample_form_fields)

            assert len(filled_fields) > 0
            assert all(field.value for field in filled_fields)
            assert mock_page.fill.call_count > 0

    async def test_file_upload(
        self,
        form_filler_instance: FormFiller,
        sample_form_fields: List[FormField],
        tmp_path: Path,
    ):
        """Test resume file upload."""
        # Create temporary resume file
        resume_path = tmp_path / "resume.pdf"
        resume_path.touch()

        file_field = next(f for f in sample_form_fields if f.field_type == "file")

        await form_filler_instance._handle_file_upload(file_field, resume_path)
        assert form_filler_instance.page.set_input_files.called

    async def test_form_submission(
        self, form_filler_instance: FormFiller, mock_page: Mock
    ):
        """Test form submission."""
        submit_button = Mock()
        submit_button.click = AsyncMock()
        mock_page.query_selector.return_value = submit_button

        with patch.object(mock_page, "expect_navigation") as mock_nav:
            mock_nav.return_value.__aenter__.return_value.value = Mock(
                spec=Response, ok=True
            )

            response = await form_filler_instance.submit_form()
            assert response is not None
            assert response.ok
            assert submit_button.click.called

    async def test_cleanup(self, form_filler_instance: FormFiller):
        """Test resource cleanup."""
        await form_filler_instance.cleanup()
        assert form_filler_instance.browser is None
        assert form_filler_instance.context is None
        assert form_filler_instance.page is None


@pytest.mark.asyncio
class TestFormFillerIntegration:
    """Integration tests for FormFiller."""

    async def test_complete_form_submission(
        self,
        form_filler_instance: FormFiller,
        sample_form_fields: List[FormField],
        tmp_path: Path,
    ):
        """Test complete form submission process."""
        resume_path = tmp_path / "resume.pdf"
        resume_path.touch()

        # Mock form detection
        with patch.object(
            form_filler_instance, "detect_form_fields", return_value=sample_form_fields
        ):
            # Navigate to form
            await form_filler_instance.navigate_to_form("https://example.com")

            # Fill form
            filled_fields = await form_filler_instance.fill_form(
                sample_form_fields, resume_path
            )

            # Submit form
            response = await form_filler_instance.submit_form()

            assert len(filled_fields) > 0
            assert response is not None
            assert response.ok

    async def test_error_handling(
        self, form_filler_instance: FormFiller, mock_page: Mock
    ):
        """Test error handling during form operations."""
        mock_page.goto.side_effect = Exception("Navigation failed")

        with pytest.raises(FormFillingError):
            await form_filler_instance.navigate_to_form("https://example.com")


if __name__ == "__main__":
    pytest.main(["-v"])
