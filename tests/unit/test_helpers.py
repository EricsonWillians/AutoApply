"""
Unit tests for the helpers module.

This module contains comprehensive tests for utility functions that provide
shared functionality across the application, ensuring reliability and
proper error handling.

File location: tests/unit/test_helpers.py
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest

from app.utils.helpers import UtilityHelpers, ValidationError, utils
from app.utils.logging import LoggerMixin


class TestURLValidation:
    """Tests for URL validation functionality."""

    def test_valid_urls(self):
        """Test validation of correctly formatted URLs."""
        valid_urls = [
            "https://example.com",
            "http://subdomain.example.com/path",
            "https://example.com:8080/path?query=value",
            "http://example.com/path#section",
            "https://user:pass@example.com",
        ]

        for url in valid_urls:
            assert utils.validate_url(url) is True

    def test_invalid_urls(self):
        """Test validation of incorrectly formatted URLs."""
        invalid_urls = [
            "not_a_url",
            "http:/example.com",
            "https://",
            "ftp://example.com",
            "",
            None,
        ]

        for url in invalid_urls:
            assert utils.validate_url(url) is False


class TestFileHandling:
    """Tests for file handling utilities."""

    def test_file_type_validation(self):
        """Test validation of file types."""
        allowed_extensions = [".pdf", ".docx", ".txt"]

        assert utils.validate_file_type("document.pdf", allowed_extensions)
        assert utils.validate_file_type("document.DOCX", allowed_extensions)
        assert not utils.validate_file_type("document.exe", allowed_extensions)
        assert not utils.validate_file_type("document", allowed_extensions)

    def test_filename_sanitization(self):
        """Test sanitization of filenames."""
        test_cases = [
            ("file name.pdf", "file_name.pdf"),
            ('file<>:"/\\|?*.txt', "file.txt"),
            ("../path/file.doc", "pathfile.doc"),
            ("file name with spaces.pdf", "file_name_with_spaces.pdf"),
        ]

        for input_name, expected in test_cases:
            assert utils.sanitize_filename(input_name) == expected


class TestDateHandling:
    """Tests for date handling utilities."""

    def test_date_formatting(self):
        """Test date formatting functionality."""
        test_date = datetime(2024, 1, 15, 14, 30, 45)

        # Test default format
        assert utils.format_date(test_date) == "2024-01-15 14:30:45"

        # Test custom format
        custom_format = "%Y-%m-%d"
        assert utils.format_date(test_date, custom_format) == "2024-01-15"

    def test_date_parsing(self):
        """Test date parsing functionality."""
        test_cases = [
            ("2024-01-15", datetime(2024, 1, 15)),
            ("15/01/2024", datetime(2024, 1, 15)),
            ("January 15, 2024", datetime(2024, 1, 15)),
            ("Jan 15, 2024", datetime(2024, 1, 15)),
        ]

        for date_str, expected in test_cases:
            parsed = utils.parse_date(date_str)
            assert parsed == expected

    def test_invalid_date_parsing(self):
        """Test handling of invalid date strings."""
        invalid_dates = [
            "not a date",
            "2024-13-45",
            "",
            "2024/01/15",  # Unsupported format
        ]

        for date_str in invalid_dates:
            assert utils.parse_date(date_str) is None


class TestTextProcessing:
    """Tests for text processing utilities."""

    def test_email_validation(self):
        """Test email address validation."""
        valid_emails = [
            "user@example.com",
            "user.name@example.co.uk",
            "user+label@example.com",
            "123.456@example.com",
            "user@subdomain.example.com",
        ]

        invalid_emails = [
            "not_an_email",
            "@example.com",
            "user@",
            "user@.com",
            "user@example",
            "user@example.",
        ]

        for email in valid_emails:
            assert utils.validate_email(email) is True

        for email in invalid_emails:
            assert utils.validate_email(email) is False

    def test_phone_validation(self):
        """Test phone number validation."""
        valid_phones = [
            "+1234567890",
            "1234567890",
            "+44 123 456 7890",
            "(123) 456-7890",
            "123-456-7890",
        ]

        invalid_phones = ["123", "abcdefghij", "+123abc4567", "", "++1234567890"]

        for phone in valid_phones:
            assert utils.validate_phone(phone) is True

        for phone in invalid_phones:
            assert utils.validate_phone(phone) is False

    def test_text_chunking(self):
        """Test text chunking functionality."""
        text = "This is a test text that needs to be split into chunks with proper overlap."
        chunk_size = 10
        overlap = 3

        chunks = utils.chunk_text(text, chunk_size, overlap)

        assert all(len(chunk) <= chunk_size for chunk in chunks)
        assert len(chunks) > 1

        # Verify overlap
        for i in range(len(chunks) - 1):
            current_end = chunks[i][-overlap:]
            next_start = chunks[i + 1][:overlap]
            assert current_end.strip() == next_start.strip()

    def test_text_similarity(self):
        """Test text similarity calculation."""
        text1 = "This is a test string"
        text2 = "This is a test string"
        text3 = "This is different"

        assert utils.calculate_similarity(text1, text2) == 1.0
        assert utils.calculate_similarity(text1, text3) < 1.0
        assert utils.calculate_similarity(text1, "") == 0.0

    def test_keyword_extraction(self):
        """Test keyword extraction functionality."""
        text = "Software engineer with experience in Python programming and machine learning"
        keywords = utils.extract_keywords(text)

        assert "software" in keywords
        assert "engineer" in keywords
        assert "python" in keywords
        assert "programming" in keywords
        assert "machine" in keywords
        assert "learning" in keywords
        assert "with" not in keywords  # Stop word
        assert "in" not in keywords  # Stop word


class TestDataAccess:
    """Tests for data access utilities."""

    def test_safe_dictionary_access(self):
        """Test safe dictionary access functionality."""
        test_data = {"level1": {"level2": {"level3": "value"}}}

        # Test successful access
        assert utils.safe_get(test_data, ["level1", "level2", "level3"]) == "value"

        # Test missing keys
        assert utils.safe_get(test_data, ["nonexistent"]) is None
        assert utils.safe_get(test_data, ["level1", "nonexistent"]) is None

        # Test with default value
        default = "default_value"
        assert utils.safe_get(test_data, ["nonexistent"], default) == default

    def test_byte_formatting(self):
        """Test byte size formatting functionality."""
        test_cases = [
            (500, "500.00 B"),
            (1024, "1.00 KB"),
            (1024 * 1024, "1.00 MB"),
            (1024 * 1024 * 1024, "1.00 GB"),
            (1024 * 1024 * 1024 * 1024, "1.00 TB"),
        ]

        for size, expected in test_cases:
            assert utils.format_bytes(size) == expected


class TestHelperIntegration:
    """Integration tests for helper utilities."""

    def test_complete_text_processing_workflow(self):
        """Test complete text processing workflow."""
        original_text = """Software engineer with 5+ years of experience in Python
        programming and machine learning. Contact: user@example.com or
        +1-234-567-8900."""

        # Extract and validate email
        words = original_text.split()
        emails = [word for word in words if utils.validate_email(word)]
        assert len(emails) == 1
        assert emails[0] == "user@example.com"

        # Extract and validate phone
        phones = [word for word in words if utils.validate_phone(word)]
        assert len(phones) == 1

        # Extract keywords
        keywords = utils.extract_keywords(original_text)
        assert len(keywords) > 0
        assert "software" in keywords
        assert "engineer" in keywords
        assert "python" in keywords

        # Create text chunks
        chunks = utils.chunk_text(original_text, chunk_size=50, overlap=10)
        assert len(chunks) > 1

        # Calculate similarity between chunks
        similarity = utils.calculate_similarity(chunks[0], chunks[1])
        assert 0 <= similarity <= 1


if __name__ == "__main__":
    pytest.main(["-v"])
