"""
Unit tests for the PDF parser module.

This module contains comprehensive tests for the PDF parsing functionality,
ensuring reliable extraction of LinkedIn profile data from PDF exports.

File location: tests/unit/test_pdf_parser.py
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from app.core.pdf_parser import (Education, Experience, LinkedInProfile,
                                 PDFParser, create_profile_from_pdf)
from app.utils.exceptions import ProfileExtractionError


@pytest.fixture
def sample_pdf_content() -> str:
    """Provide sample PDF content for testing."""
    return """
    JOHN DOE
    Software Engineer | Python Developer
    San Francisco Bay Area

    EXPERIENCE
    Senior Software Engineer
    TechCorp Inc.
    January 2020 - Present
    Led development of microservices architecture
    Python, Docker, Kubernetes

    Software Engineer
    StartupCo
    March 2018 - December 2019
    Developed web applications using Django

    EDUCATION
    Master of Science in Computer Science
    Stanford University
    2016 - 2018

    Bachelor of Science in Computer Engineering
    University of California, Berkeley
    2012 - 2016

    SKILLS
    Python, Java, JavaScript, Docker, Kubernetes, AWS

    LANGUAGES
    English (Native), Spanish (Professional)

    CERTIFICATIONS
    AWS Certified Solutions Architect
    Docker Certified Associate
    """


@pytest.fixture
def sample_profile_data() -> dict:
    """Provide sample profile data for testing."""
    return {
        "full_name": "John Doe",
        "headline": "Software Engineer | Python Developer",
        "location": "San Francisco Bay Area",
        "experiences": [
            {
                "title": "Senior Software Engineer",
                "company": "TechCorp Inc.",
                "start_date": "2020-01",
                "description": "Led development of microservices architecture",
                "skills": ["Python", "Docker", "Kubernetes"],
            },
            {
                "title": "Software Engineer",
                "company": "StartupCo",
                "start_date": "2018-03",
                "end_date": "2019-12",
                "description": "Developed web applications using Django",
            },
        ],
        "education": [
            {
                "institution": "Stanford University",
                "degree": "Master of Science",
                "field_of_study": "Computer Science",
                "start_date": "2016",
                "end_date": "2018",
            },
            {
                "institution": "University of California, Berkeley",
                "degree": "Bachelor of Science",
                "field_of_study": "Computer Engineering",
                "start_date": "2012",
                "end_date": "2016",
            },
        ],
        "skills": ["Python", "Java", "JavaScript", "Docker", "Kubernetes", "AWS"],
        "languages": ["English", "Spanish"],
        "certifications": [
            "AWS Certified Solutions Architect",
            "Docker Certified Associate",
        ],
    }


class TestExperienceModel:
    """Tests for the Experience model."""

    def test_valid_experience(self):
        """Test creating a valid Experience instance."""
        data = {
            "title": "Software Engineer",
            "company": "TechCorp",
            "start_date": "2020-01",
            "end_date": "2021-12",
            "description": "Development work",
            "skills": ["Python", "Docker"],
        }
        experience = Experience(**data)
        assert experience.title == "Software Engineer"
        assert experience.company == "TechCorp"
        assert experience.start_date.year == 2020
        assert experience.start_date.month == 1

    def test_experience_without_end_date(self):
        """Test Experience instance with no end date (current position)."""
        data = {
            "title": "Software Engineer",
            "company": "TechCorp",
            "start_date": "2020-01",
        }
        experience = Experience(**data)
        assert experience.end_date is None

    def test_invalid_date_format(self):
        """Test Experience creation with invalid date format."""
        data = {
            "title": "Software Engineer",
            "company": "TechCorp",
            "start_date": "invalid-date",
        }
        with pytest.raises(ValidationError):
            Experience(**data)

    def test_missing_required_fields(self):
        """Test Experience creation with missing required fields."""
        data = {"title": "Software Engineer"}
        with pytest.raises(ValidationError):
            Experience(**data)


class TestEducationModel:
    """Tests for the Education model."""

    def test_valid_education(self):
        """Test creating a valid Education instance."""
        data = {
            "institution": "Stanford University",
            "degree": "Master of Science",
            "field_of_study": "Computer Science",
            "start_date": "2016",
            "end_date": "2018",
        }
        education = Education(**data)
        assert education.institution == "Stanford University"
        assert education.degree == "Master of Science"
        assert education.start_date.year == 2016

    def test_education_without_field_of_study(self):
        """Test Education instance without field of study."""
        data = {
            "institution": "Stanford University",
            "degree": "Master of Science",
            "start_date": "2016",
        }
        education = Education(**data)
        assert education.field_of_study is None

    def test_invalid_institution(self):
        """Test Education creation with invalid institution."""
        data = {"institution": "", "degree": "Master of Science", "start_date": "2016"}
        with pytest.raises(ValidationError):
            Education(**data)


class TestLinkedInProfile:
    """Tests for the LinkedInProfile model."""

    def test_valid_profile(self, sample_profile_data):
        """Test creating a valid LinkedInProfile instance."""
        profile = LinkedInProfile(**sample_profile_data)
        assert profile.full_name == "John Doe"
        assert len(profile.experiences) == 2
        assert len(profile.education) == 2
        assert len(profile.skills) == 6

    def test_profile_json_serialization(self, sample_profile_data, tmp_path):
        """Test JSON serialization of LinkedInProfile."""
        profile = LinkedInProfile(**sample_profile_data)
        json_path = tmp_path / "profile.json"
        profile.to_json(json_path)

        # Read and verify JSON
        with open(json_path, "r") as f:
            loaded_data = json.load(f)

        assert loaded_data["full_name"] == "John Doe"
        assert len(loaded_data["experiences"]) == 2

    def test_profile_from_json(self, sample_profile_data, tmp_path):
        """Test creating LinkedInProfile from JSON file."""
        json_path = tmp_path / "profile.json"
        with open(json_path, "w") as f:
            json.dump(sample_profile_data, f)

        profile = LinkedInProfile.from_json(json_path)
        assert profile.full_name == "John Doe"
        assert len(profile.experiences) == 2


class TestPDFParser:
    """Tests for the PDFParser class."""

    @pytest.fixture
    def parser(self):
        """Provide a PDFParser instance."""
        return PDFParser()

    def test_extract_text_sections(self, parser, sample_pdf_content):
        """Test extraction of text sections from PDF."""
        with patch("pdfplumber.open") as mock_pdf:
            # Mock PDF page with our sample content
            mock_page = Mock()
            mock_page.extract_text.return_value = sample_pdf_content
            mock_pdf.return_value.__enter__.return_value.pages = [mock_page]

            sections = parser.extract_text_sections("dummy.pdf")
            assert len(sections) > 0

            # Verify section detection
            section_titles = [s["title"] for s in sections]
            assert "EXPERIENCE" in section_titles
            assert "EDUCATION" in section_titles

    def test_parse_profile(self, parser, sample_pdf_content):
        """Test parsing complete LinkedIn profile."""
        with patch("pdfplumber.open") as mock_pdf:
            mock_page = Mock()
            mock_page.extract_text.return_value = sample_pdf_content
            mock_pdf.return_value.__enter__.return_value.pages = [mock_page]

            profile = parser.parse_profile("dummy.pdf")
            assert isinstance(profile, LinkedInProfile)
            assert profile.full_name == "John Doe"
            assert len(profile.experiences) > 0
            assert len(profile.education) > 0

    def test_invalid_pdf(self, parser):
        """Test handling of invalid PDF file."""
        with pytest.raises(ProfileExtractionError):
            parser.parse_profile("nonexistent.pdf")


def test_create_profile_from_pdf(sample_pdf_content, tmp_path):
    """Test the create_profile_from_pdf function."""
    with patch("pdfplumber.open") as mock_pdf:
        mock_page = Mock()
        mock_page.extract_text.return_value = sample_pdf_content
        mock_pdf.return_value.__enter__.return_value.pages = [mock_page]

        # Create temporary PDF file
        pdf_path = tmp_path / "profile.pdf"
        pdf_path.touch()

        profile = create_profile_from_pdf(pdf_path)
        assert isinstance(profile, LinkedInProfile)
        assert profile.full_name == "John Doe"

        # Verify JSON file creation
        json_path = Path(settings.data_dir) / "user_profile.json"
        assert json_path.exists()


if __name__ == "__main__":
    pytest.main(["-v"])
