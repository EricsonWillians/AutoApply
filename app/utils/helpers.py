"""
Utilities helper module for AutoApply.

This module provides shared functionality and helper functions used
throughout the application, ensuring consistency and reducing code
duplication.

File location: app/utils/helpers.py
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

from app.utils.logging import LoggerMixin


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


class UtilityHelpers(LoggerMixin):
    """Utility helper functions for the application."""

    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate a URL string.

        Args:
            url: URL string to validate.

        Returns:
            Boolean indicating whether the URL is valid.
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    @staticmethod
    def validate_file_type(
        file_path: Union[str, Path], allowed_extensions: List[str]
    ) -> bool:
        """
        Validate file type based on extension.

        Args:
            file_path: Path to the file.
            allowed_extensions: List of allowed file extensions.

        Returns:
            Boolean indicating whether the file type is valid.
        """
        return Path(file_path).suffix.lower() in allowed_extensions

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize a filename by removing invalid characters.

        Args:
            filename: Original filename.

        Returns:
            Sanitized filename.
        """
        # Remove invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', "", filename)
        # Replace spaces with underscores
        sanitized = sanitized.replace(" ", "_")
        return sanitized

    @staticmethod
    def format_date(date: datetime, format_str: Optional[str] = None) -> str:
        """
        Format a datetime object as a string.

        Args:
            date: Datetime object to format.
            format_str: Optional format string.

        Returns:
            Formatted date string.
        """
        if not format_str:
            format_str = "%Y-%m-%d %H:%M:%S"
        return date.strftime(format_str)

    @staticmethod
    def parse_date(
        date_str: str, formats: Optional[List[str]] = None
    ) -> Optional[datetime]:
        """
        Parse a date string into a datetime object.

        Args:
            date_str: Date string to parse.
            formats: Optional list of format strings to try.

        Returns:
            Parsed datetime object or None if parsing fails.
        """
        if not formats:
            formats = [
                "%Y-%m-%d",
                "%Y-%m-%d %H:%M:%S",
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%B %d, %Y",
                "%b %d, %Y",
            ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate an email address.

        Args:
            email: Email address to validate.

        Returns:
            Boolean indicating whether the email is valid.
        """
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """
        Validate a phone number.

        Args:
            phone: Phone number to validate.

        Returns:
            Boolean indicating whether the phone number is valid.
        """
        # Remove common separators
        cleaned = re.sub(r"[\s\-\(\)]", "", phone)
        # Check for valid format (adjust pattern as needed)
        pattern = r"^\+?[0-9]{10,15}$"
        return bool(re.match(pattern, cleaned))

    @staticmethod
    def extract_domain(url: str) -> Optional[str]:
        """
        Extract domain name from URL.

        Args:
            url: URL to process.

        Returns:
            Domain name or None if extraction fails.
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return None

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to split.
            chunk_size: Maximum size of each chunk.
            overlap: Number of characters to overlap between chunks.

        Returns:
            List of text chunks.
        """
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + chunk_size

            if end > text_length:
                end = text_length
            else:
                # Find the last space within the chunk
                last_space = text.rfind(" ", start, end)
                if last_space != -1:
                    end = last_space

            chunks.append(text[start:end].strip())
            start = end - overlap

        return chunks

    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """
        Calculate similarity ratio between two strings.

        Args:
            text1: First text string.
            text2: Second text string.

        Returns:
            Similarity ratio between 0 and 1.
        """
        from difflib import SequenceMatcher

        return SequenceMatcher(None, text1, text2).ratio()

    @staticmethod
    def extract_keywords(
        text: str, min_length: int = 3, max_words: Optional[int] = None
    ) -> List[str]:
        """
        Extract keywords from text.

        Args:
            text: Text to process.
            min_length: Minimum word length.
            max_words: Maximum number of keywords to return.

        Returns:
            List of keywords.
        """
        # Remove special characters and convert to lowercase
        cleaned = re.sub(r"[^\w\s]", "", text.lower())

        # Split into words and filter by length
        words = [word for word in cleaned.split() if len(word) >= min_length]

        # Remove common stop words (expand as needed)
        stop_words = {
            "the",
            "be",
            "to",
            "of",
            "and",
            "a",
            "in",
            "that",
            "have",
            "i",
            "it",
            "for",
            "not",
            "on",
            "with",
            "he",
            "as",
            "you",
            "do",
            "at",
            "this",
            "but",
            "his",
            "by",
            "from",
            "they",
            "we",
            "say",
            "her",
            "she",
            "or",
            "an",
            "will",
            "my",
            "one",
            "all",
            "would",
            "there",
            "their",
            "what",
            "so",
            "up",
            "out",
            "if",
            "about",
            "who",
            "get",
            "which",
            "go",
            "me",
        }

        keywords = [word for word in words if word not in stop_words]

        if max_words:
            keywords = keywords[:max_words]

        return keywords

    @staticmethod
    def safe_get(
        data: Dict[str, Any], keys: Union[str, List[str]], default: Any = None
    ) -> Any:
        """
        Safely get nested dictionary values.

        Args:
            data: Dictionary to search.
            keys: Key or list of keys to traverse.
            default: Default value if key not found.

        Returns:
            Value from dictionary or default.
        """
        if isinstance(keys, str):
            keys = [keys]

        current = data
        for key in keys:
            try:
                current = current[key]
            except (KeyError, TypeError, IndexError):
                return default

        return current

    @staticmethod
    def format_bytes(size: int) -> str:
        """
        Format byte size to human readable string.

        Args:
            size: Size in bytes.

        Returns:
            Formatted string representation.
        """
        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.2f} {units[unit_index]}"


# Global instance
utils = UtilityHelpers()
