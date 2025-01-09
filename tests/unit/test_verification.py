"""
Unit tests for the verification module.

This module contains comprehensive tests for the form verification functionality,
ensuring proper user control and security in the application process.

File location: tests/unit/test_verification.py
"""

import asyncio
from datetime import datetime, timedelta
from typing import List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from playwright.async_api import Page
from rich.console import Console

from app.core.form_filler import FormField
from app.core.verification import (FormVerification, VerificationError,
                                   VerificationResult, form_verification)
from app.utils.config import settings


@pytest.fixture
def mock_console() -> Mock:
    """Provide a mock console for testing output."""
    console = Mock(spec=Console)
    console.print = Mock()
    return console


@pytest.fixture
def sample_form_fields() -> List[FormField]:
    """Provide sample filled form fields for testing."""
    return [
        FormField(
            selector="#name",
            field_type="text",
            label="Full Name",
            required=True,
            value="John Doe",
            confidence=0.95,
        ),
        FormField(
            selector="#email",
            field_type="email",
            label="Email Address",
            required=True,
            value="john.doe@example.com",
            confidence=0.90,
        ),
        FormField(
            selector="#experience",
            field_type="textarea",
            label="Work Experience",
            required=True,
            value="Senior Software Engineer with 5 years of experience",
            confidence=0.85,
        ),
        FormField(
            selector="#resume",
            field_type="file",
            label="Resume",
            required=True,
            value="/path/to/resume.pdf",
            confidence=1.0,
        ),
    ]


@pytest.fixture
def mock_page() -> Mock:
    """Provide a mock Playwright page."""
    page = Mock(spec=Page)
    page.fill = AsyncMock()
    return page


@pytest.fixture
async def verification_instance(mock_console: Mock) -> FormVerification:
    """Provide a configured FormVerification instance."""
    return FormVerification(console=mock_console)


@pytest.mark.asyncio
class TestFormVerification:
    """Tests for the FormVerification class."""

    async def test_verification_interface_display(
        self,
        verification_instance: FormVerification,
        sample_form_fields: List[FormField],
    ):
        """Test display of verification interface."""
        await verification_instance._display_verification_interface(sample_form_fields)

        # Verify console output
        assert verification_instance.console.print.called

        # Check if table was created with appropriate columns
        calls = verification_instance.console.print.call_args_list
        assert any("Field" in str(call) for call in calls)
        assert any("Value" in str(call) for call in calls)
        assert any("Confidence" in str(call) for call in calls)

    async def test_verification_approval(
        self,
        verification_instance: FormVerification,
        sample_form_fields: List[FormField],
        mock_page: Mock,
    ):
        """Test form verification with user approval."""
        # Mock user input to approve the form
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor.return_value = "1"

            result = await verification_instance.verify_form_data(
                mock_page, sample_form_fields
            )

            assert isinstance(result, VerificationResult)
            assert result.approved
            assert result.modifications == {}
            assert result.verification_duration > 0
            assert result.confidence_threshold_met

    async def test_verification_modification(
        self,
        verification_instance: FormVerification,
        sample_form_fields: List[FormField],
        mock_page: Mock,
    ):
        """Test form verification with field modifications."""
        # Simulate user choosing to modify fields then approve
        user_inputs = ["2", "Updated Name", "", "", "", "1"]

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor.side_effect = user_inputs

            result = await verification_instance.verify_form_data(
                mock_page, sample_form_fields
            )

            assert result.approved
            assert "#name" in result.modifications
            assert result.modifications["#name"] == "Updated Name"
            assert mock_page.fill.called

    async def test_verification_cancellation(
        self,
        verification_instance: FormVerification,
        sample_form_fields: List[FormField],
        mock_page: Mock,
    ):
        """Test form verification cancellation."""
        # Simulate user choosing to cancel
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor.return_value = "3"

            with pytest.raises(VerificationError) as exc_info:
                await verification_instance.verify_form_data(
                    mock_page, sample_form_fields
                )

            assert "cancelled" in str(exc_info.value).lower()

    async def test_confidence_threshold(
        self,
        verification_instance: FormVerification,
        sample_form_fields: List[FormField],
        mock_page: Mock,
    ):
        """Test confidence threshold checking."""
        # Modify a field to have low confidence
        sample_form_fields[0].confidence = 0.5

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor.return_value = "1"

            result = await verification_instance.verify_form_data(
                mock_page, sample_form_fields, confidence_threshold=0.8
            )

            assert not result.confidence_threshold_met

    async def test_verification_timeout(
        self,
        verification_instance: FormVerification,
        sample_form_fields: List[FormField],
    ):
        """Test verification timeout handling."""
        # Set verification start time to exceed timeout
        verification_instance._verification_start = datetime.utcnow() - timedelta(
            seconds=settings.verification_timeout + 10
        )

        with pytest.raises(VerificationError) as exc_info:
            await verification_instance.handle_verification_timeout()

        assert "timeout" in str(exc_info.value).lower()

    async def test_invalid_user_input(
        self,
        verification_instance: FormVerification,
        sample_form_fields: List[FormField],
        mock_page: Mock,
    ):
        """Test handling of invalid user input."""
        # Simulate invalid input followed by valid input
        user_inputs = ["invalid", "1"]

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor.side_effect = user_inputs

            result = await verification_instance.verify_form_data(
                mock_page, sample_form_fields
            )

            assert result.approved
            assert verification_instance.console.print.called
            assert any(
                "Invalid choice" in str(call)
                for call in verification_instance.console.print.call_args_list
            )

    async def test_required_field_modification(
        self,
        verification_instance: FormVerification,
        sample_form_fields: List[FormField],
        mock_page: Mock,
    ):
        """Test modification of required fields."""
        # Simulate user modifying a required field
        user_inputs = ["2", "", "1"]  # Empty input for required field

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor.side_effect = user_inputs

            result = await verification_instance.verify_form_data(
                mock_page, sample_form_fields
            )

            assert result.approved
            assert "#name" not in result.modifications

    async def test_verification_result_creation(
        self,
        verification_instance: FormVerification,
        sample_form_fields: List[FormField],
        mock_page: Mock,
    ):
        """Test creation of verification result object."""
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor.return_value = "1"

            result = await verification_instance.verify_form_data(
                mock_page, sample_form_fields
            )

            assert isinstance(result.timestamp, datetime)
            assert isinstance(result.verification_duration, float)
            assert isinstance(result.confidence_threshold_met, bool)
            assert isinstance(result.modifications, dict)


@pytest.mark.asyncio
class TestFormVerificationIntegration:
    """Integration tests for FormVerification."""

    async def test_complete_verification_workflow(
        self,
        verification_instance: FormVerification,
        sample_form_fields: List[FormField],
        mock_page: Mock,
    ):
        """Test complete verification workflow with modifications."""
        # Simulate user modifying a field and then approving
        user_inputs = [
            "2",  # Choose to modify
            "Updated Name",  # Modify name
            "",  # Skip email
            "Updated experience",  # Modify experience
            "",  # Skip resume
            "1",  # Approve
        ]

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor.side_effect = user_inputs

            result = await verification_instance.verify_form_data(
                mock_page, sample_form_fields
            )

            assert result.approved
            assert len(result.modifications) == 2
            assert result.modifications["#name"] == "Updated Name"
            assert result.modifications["#experience"] == "Updated experience"
            assert mock_page.fill.call_count == 2

    async def test_verification_with_timeout_monitoring(
        self,
        verification_instance: FormVerification,
        sample_form_fields: List[FormField],
        mock_page: Mock,
    ):
        """Test verification with timeout monitoring."""

        # Simulate slow user response
        async def delayed_input(*args):
            await asyncio.sleep(0.1)
            return "1"

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_loop.return_value.run_in_executor.side_effect = delayed_input

            result = await verification_instance.verify_form_data(
                mock_page, sample_form_fields
            )

            assert result.verification_duration > 0
            assert result.approved


if __name__ == "__main__":
    pytest.main(["-v"])
