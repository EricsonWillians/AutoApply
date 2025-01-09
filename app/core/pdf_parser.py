"""
PDF Parser module for extracting LinkedIn profile data.

This module handles the extraction and structuring of data from LinkedIn
profile PDFs, ensuring type safety and proper error handling throughout
the process.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pdfplumber
from pydantic import BaseModel, Field, validator

from app.utils.config import settings
from app.utils.logging import LoggerMixin


class Experience(BaseModel):
    """Model representing work experience entry."""

    title: str
    company: str
    location: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    description: Optional[str] = None
    skills: List[str] = Field(default_factory=list)

    @validator("start_date", "end_date", pre=True)
    def parse_date(cls, value: Optional[str]) -> Optional[datetime]:
        """Parse date strings into datetime objects."""
        if not value:
            return None
        try:
            return datetime.strptime(value, "%B %Y")
        except ValueError as e:
            try:
                return datetime.strptime(value, "%Y-%m")
            except ValueError:
                raise ValueError(f"Invalid date format: {value}") from e


class Education(BaseModel):
    """Model representing educational background."""

    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    activities: List[str] = Field(default_factory=list)
    grade: Optional[str] = None

    @validator("start_date", "end_date", pre=True)
    def parse_date(cls, value: Optional[str]) -> Optional[datetime]:
        """Parse date strings into datetime objects."""
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y")
        except ValueError as e:
            try:
                return datetime.strptime(value, "%B %Y")
            except ValueError:
                raise ValueError(f"Invalid date format: {value}") from e


class LinkedInProfile(BaseModel):
    """Model representing the complete LinkedIn profile."""

    full_name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    about: Optional[str] = None
    experiences: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    volunteer: List[Dict[str, Any]] = Field(default_factory=list)

    def to_json(self, path: Union[str, Path]) -> None:
        """Save profile data to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.dict(), f, indent=2, default=str)

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> "LinkedInProfile":
        """Load profile data from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


class PDFParser(LoggerMixin):
    """Parser for extracting LinkedIn profile data from PDF files."""

    def __init__(self) -> None:
        """Initialize the PDF parser."""
        super().__init__()
        self.profile_data: Dict[str, Any] = {
            "experiences": [],
            "education": [],
            "skills": [],
            "languages": [],
            "certifications": [],
            "volunteer": [],
        }

    def extract_text_sections(self, pdf_path: Union[str, Path]) -> List[Dict[str, str]]:
        """
        Extract text sections from the PDF file.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of dictionaries containing section titles and content.
        """
        sections = []
        current_section = {"title": "", "content": ""}

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    print(text)
                    if not text:
                        continue

                    lines = text.split("\n")
                    for line in lines:
                        if line.isupper() and len(line) > 3:  # Potential section header
                            if current_section["title"]:
                                sections.append(current_section.copy())
                            current_section = {"title": line.strip(), "content": ""}
                        else:
                            current_section["content"] += line + "\n"

                if current_section["title"]:
                    sections.append(current_section)

        except Exception as e:
            self.log_error(e, "PDF text extraction")
            raise

        return sections

    def parse_profile(self, pdf_path: Union[str, Path]) -> LinkedInProfile:
        """
        Parse LinkedIn profile data from a PDF file.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            LinkedInProfile object containing the extracted data.
        """
        self.log_operation_start("profile parsing", pdf_path=str(pdf_path))

        try:
            sections = self.extract_text_sections(pdf_path)

            for section in sections:
                title = section["title"].lower()
                content = section["content"].strip()

                if "experience" in title:
                    self._parse_experience_section(content)
                elif "education" in title:
                    self._parse_education_section(content)
                elif "skills" in title:
                    self._parse_skills_section(content)
                elif "languages" in title:
                    self._parse_languages_section(content)
                elif "certifications" in title:
                    self._parse_certifications_section(content)
                elif "volunteer" in title:
                    self._parse_volunteer_section(content)
                elif "contact" in title:
                    self._parse_contact_section(content)

            profile = LinkedInProfile(**self.profile_data)
            self.log_operation_end("profile parsing")
            return profile

        except Exception as e:
            self.log_error(e, "profile parsing")
            raise

    def _parse_experience_section(self, content: str) -> None:
        """Parse the experience section content."""
        # Implementation details for experience parsing
        pass

    def _parse_education_section(self, content: str) -> None:
        """Parse the education section content."""
        # Implementation details for education parsing
        pass

    def _parse_skills_section(self, content: str) -> None:
        """Parse the skills section content."""
        # Implementation details for skills parsing
        pass

    def _parse_languages_section(self, content: str) -> None:
        """Parse the languages section content."""
        # Implementation details for languages parsing
        pass

    def _parse_certifications_section(self, content: str) -> None:
        """Parse the certifications section content."""
        # Implementation details for certifications parsing
        pass

    def _parse_volunteer_section(self, content: str) -> None:
        """Parse the volunteer section content."""
        # Implementation details for volunteer parsing
        pass

    def _parse_contact_section(self, content: str) -> None:
        """Parse the contact section content."""
        # Implementation details for contact information parsing
        pass


def create_profile_from_pdf(pdf_path: Union[str, Path]) -> LinkedInProfile:
    """
    Create a LinkedInProfile instance from a PDF file.

    Args:
        pdf_path: Path to the LinkedIn profile PDF.

    Returns:
        LinkedInProfile object containing the extracted data.
    """
    parser = PDFParser()
    profile = parser.parse_profile(pdf_path)

    # Save the profile data
    json_path = settings.data_dir / "user_profile.json"
    profile.to_json(json_path)

    return profile
