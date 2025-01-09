"""
Integration tests for core AutoApply functionality.

This module contains comprehensive integration tests that verify the proper
interaction between major system components in realistic application scenarios.

File location: tests/integration/test_core_integration.py
"""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from playwright.async_api import Page, Response

from app.core.form_filler import form_filler
from app.core.local_storage import storage_manager
from app.core.pdf_parser import create_profile_from_pdf
from app.core.verification import form_verification
from app.services.huggingface_integration import huggingface_service
from app.utils.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


@pytest.fixture
def sample_pdf_content():
    """Provide sample LinkedIn PDF content."""
    return """
    JOHN DOE
    Software Engineer
    San Francisco Bay Area

    EXPERIENCE
    Senior Software Engineer
    TechCorp Inc.
    January 2020 - Present
    • Led development of microservices architecture
    • Implemented CI/CD pipelines
    • Technologies: Python, Docker, Kubernetes

    Software Engineer
    StartupCo
    March 2018 - December 2019
    • Developed web applications
    • Managed cloud infrastructure
    • Technologies: Python, AWS, React

    EDUCATION
    Master of Science in Computer Science
    Stanford University
    2016 - 2018

    Bachelor of Science in Computer Engineering
    UC Berkeley
    2012 - 2016

    SKILLS
    Python, Java, JavaScript, Docker, Kubernetes, AWS
    """


@pytest.fixture
def mock_job_page():
    """Provide mock job application page content."""
    return """
    <form id="application-form">
        <input type="text" id="full_name" name="full_name" required>
        <input type="email" id="email" name="email" required>
        <input type="tel" id="phone" name="phone">
        <textarea id="experience" name="experience" required></textarea>
        <input type="file" id="resume" name="resume" required>
        <select id="preferred_language" name="preferred_language" required>
            <option value="en">English</option>
            <option value="es">Spanish</option>
        </select>
        <button type="submit">Apply</button>
    </form>
    """


@pytest.fixture
async def mock_page(mock_job_page):
    """Provide a configured mock page."""
    page = Mock(spec=Page)
    page.goto = AsyncMock(return_value=Mock(spec=Response, status=200, ok=True))
    page.content = AsyncMock(return_value=mock_job_page)
    page.fill = AsyncMock()
    page.select_option = AsyncMock()
    page.set_input_files = AsyncMock()
    return page


@pytest.mark.asyncio
class TestCompleteApplicationFlow:
    """Integration tests for complete application workflows."""

    async def test_successful_application_submission(
        self, tmp_path, sample_pdf_content, mock_page
    ):
        """Test successful end-to-end job application process."""
        try:
            # Set up test environment
            settings.data_dir = tmp_path
            pdf_path = tmp_path / "profile.pdf"

            # Create test PDF file
            with open(pdf_path, "w") as f:
                f.write(sample_pdf_content)

            # Initialize components
            await huggingface_service.initialize()

            # Extract profile data
            profile = create_profile_from_pdf(pdf_path)
            assert profile is not None
            assert profile.full_name == "John Doe"

            # Initialize form filler
            await form_filler.initialize(profile.dict())
            form_filler.page = mock_page

            # Simulate form filling
            await form_filler.navigate_to_form("https://example.com/job")
            fields = await form_filler.detect_form_fields()
            filled_fields = await form_filler.fill_form(fields)

            # Verify form data
            result = await form_verification.verify_form_data(mock_page, filled_fields)
            assert result.approved
            assert result.confidence_threshold_met

            # Submit application
            response = await form_filler.submit_form()
            assert response.ok

            # Verify application record
            records = storage_manager.get_application_records()
            assert len(records) == 1
            assert records[0].status == "submitted"

            logger.info(
                "Application workflow completed successfully",
                job_url="https://example.com/job",
            )

        finally:
            # Clean up resources
            await form_filler.cleanup()

    async def test_application_with_modifications(
        self, tmp_path, sample_pdf_content, mock_page
    ):
        """Test application process with user modifications."""
        try:
            # Set up test environment
            settings.data_dir = tmp_path
            pdf_path = tmp_path / "profile.pdf"

            with open(pdf_path, "w") as f:
                f.write(sample_pdf_content)

            # Extract and verify profile
            profile = create_profile_from_pdf(pdf_path)
            await huggingface_service.initialize()
            await form_filler.initialize(profile.dict())
            form_filler.page = mock_page

            # Simulate form interaction
            await form_filler.navigate_to_form("https://example.com/job")
            fields = await form_filler.detect_form_fields()
            filled_fields = await form_filler.fill_form(fields)

            # Simulate user modifications
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor.side_effect = [
                    "2",  # Choose to modify
                    "Updated Name",
                    "",  # Skip other fields
                    "",
                    "",
                    "1",  # Approve
                ]

                result = await form_verification.verify_form_data(
                    mock_page, filled_fields
                )

            assert result.approved
            assert len(result.modifications) > 0
            assert "Updated Name" in str(result.modifications)

            # Verify storage
            records = storage_manager.get_application_records()
            assert len(records) == 1
            assert records[0].modifications_made

            logger.info(
                "Application workflow with modifications completed",
                modification_count=len(result.modifications),
            )

        finally:
            await form_filler.cleanup()

    async def test_application_with_resume_upload(
        self, tmp_path, sample_pdf_content, mock_page
    ):
        """Test application process including resume upload."""
        try:
            # Set up test files
            settings.data_dir = tmp_path
            pdf_path = tmp_path / "profile.pdf"
            resume_path = tmp_path / "resume.pdf"

            # Create test files
            with open(pdf_path, "w") as f:
                f.write(sample_pdf_content)
            resume_path.touch()

            # Initialize components
            profile = create_profile_from_pdf(pdf_path)
            await huggingface_service.initialize()
            await form_filler.initialize(profile.dict())
            form_filler.page = mock_page

            # Process application with resume
            await form_filler.navigate_to_form("https://example.com/job")
            fields = await form_filler.detect_form_fields()
            filled_fields = await form_filler.fill_form(fields, resume_path=resume_path)

            # Verify form data
            result = await form_verification.verify_form_data(mock_page, filled_fields)

            assert result.approved
            assert mock_page.set_input_files.called

            # Verify storage
            records = storage_manager.get_application_records()
            assert len(records) == 1
            assert records[0].resume_used == resume_path

            logger.info(
                "Application workflow with resume upload completed",
                resume_path=str(resume_path),
            )

        finally:
            await form_filler.cleanup()

    async def test_error_recovery_workflow(
        self, tmp_path, sample_pdf_content, mock_page
    ):
        """Test application process with error recovery."""
        try:
            # Set up test environment
            settings.data_dir = tmp_path
            pdf_path = tmp_path / "profile.pdf"

            with open(pdf_path, "w") as f:
                f.write(sample_pdf_content)

            # Simulate network error during first attempt
            mock_page.goto.side_effect = [
                Exception("Network error"),
                Mock(spec=Response, status=200, ok=True),
            ]

            # Initialize components
            profile = create_profile_from_pdf(pdf_path)
            await huggingface_service.initialize()
            await form_filler.initialize(profile.dict())
            form_filler.page = mock_page

            # First attempt - should fail
            with pytest.raises(Exception):
                await form_filler.navigate_to_form("https://example.com/job")

            # Reset mock for second attempt
            mock_page.goto.reset_mock()

            # Second attempt - should succeed
            await form_filler.navigate_to_form("https://example.com/job")
            fields = await form_filler.detect_form_fields()
            filled_fields = await form_filler.fill_form(fields)

            result = await form_verification.verify_form_data(mock_page, filled_fields)

            assert result.approved
            assert mock_page.goto.call_count == 2

            logger.info(
                "Application workflow completed after error recovery", retry_count=2
            )

        finally:
            await form_filler.cleanup()


if __name__ == "__main__":
    pytest.main(["-v"])
