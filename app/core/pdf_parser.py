# app/core/pdf_parser.py

from __future__ import annotations

import json
import re
import traceback
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import pdfplumber
from pydantic import BaseModel, Field, ValidationError, validator

from app.services.huggingface_integration import (HuggingFaceService,
                                                  huggingface_service)
from app.utils.config import settings
from app.utils.exceptions import ProfileParsingError
from app.utils.logging import LoggerMixin, get_logger

logger = get_logger(__name__)


class DateParsingMixin:
    """Mixin providing date parsing functionality for LinkedIn date formats."""

    @staticmethod
    def parse_date_str(date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse LinkedIn date formats into datetime objects.

        Args:
            date_str: Date string in various LinkedIn formats

        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not date_str:
            return None

        # Handle Portuguese month names
        month_map = {
            "janeiro": "01",
            "fevereiro": "02",
            "março": "03",
            "abril": "04",
            "maio": "05",
            "junho": "06",
            "julho": "07",
            "agosto": "08",
            "setembro": "09",
            "outubro": "10",
            "novembro": "11",
            "dezembro": "12",
        }

        try:
            # Convert Portuguese format to ISO
            pattern = r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro) de (\d{4})"
            match = re.search(pattern, date_str.lower())

            if match:
                month, year = match.groups()
                iso_date = f"{year}-{month_map[month]}"
                return datetime.strptime(iso_date, "%Y-%m")

            # Try other common formats
            for fmt in ("%B %Y", "%Y-%m", "%Y"):
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue

            return None

        except Exception as e:
            logger.warning(f"Date parsing failed for {date_str}: {str(e)}")
            return None


class Experience(BaseModel, DateParsingMixin):
    """Model representing a professional experience entry."""

    title: str
    company: str
    location: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    description: Optional[str] = None
    skills: List[str] = Field(default_factory=list)

    @validator("start_date", "end_date", pre=True)
    def parse_date(cls, value: Optional[str]) -> Optional[datetime]:
        """Parse date strings into datetime objects."""
        return cls.parse_date_str(value)

    class Config:
        json_encoders = {datetime: lambda v: v.strftime("%Y-%m")}


class Education(BaseModel, DateParsingMixin):
    """Model representing an educational background entry."""

    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    description: Optional[str] = None

    @validator("start_date", "end_date", pre=True)
    def parse_date(cls, value: Optional[str]) -> Optional[datetime]:
        """Parse date strings into datetime objects."""
        return cls.parse_date_str(value)

    class Config:
        json_encoders = {datetime: lambda v: v.strftime("%Y-%m")}


class Language(BaseModel):
    """Model representing language proficiency."""

    language: str
    proficiency: str

    @validator("proficiency")
    def validate_proficiency(cls, value: str) -> str:
        """Validate and standardize proficiency levels."""
        valid_levels = {
            "Native or Bilingual",
            "Professional Working",
            "Full Professional",
            "Limited Working",
            "Elementary",
        }
        if value not in valid_levels:
            closest = min(valid_levels, key=lambda x: abs(len(x) - len(value)))
            return closest
        return value


class LinkedInProfile(BaseModel):
    """Model representing a complete LinkedIn profile."""

    full_name: str
    headline: Optional[str] = None
    location: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    about: Optional[str] = None
    experiences: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    volunteer: List[Dict[str, Any]] = Field(default_factory=list)

    def to_json(self, path: Union[str, Path]) -> None:
        """
        Save profile data to a JSON file.

        Args:
            path: Path where the JSON file should be saved
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.dict(), f, indent=2, default=str)

    @classmethod
    def from_json(cls, path: Union[str, Path]) -> LinkedInProfile:
        """
        Load profile data from a JSON file.

        Args:
            path: Path to the JSON file

        Returns:
            LinkedInProfile instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValidationError: If the JSON data is invalid
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


class PDFParser(LoggerMixin):
    """Parser for extracting LinkedIn profile data from PDF files."""

    def __init__(self) -> None:
        """Initialize the PDF parser with empty profile data structure."""
        super().__init__()
        self.profile_data: Dict[str, Any] = {
            "experiences": [],
            "education": [],
            "skills": [],
            "languages": [],
            "certifications": [],
            "volunteer": [],
            "email": None,
            "phone": None,
            "linkedin": None,
            "full_name": None,
            "headline": None,
            "location": None,
            "about": None,
        }

    def extract_raw_text(self, pdf_path: Union[str, Path]) -> str:
        """
        Extract and preprocess raw text from the PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted and preprocessed text

        Raises:
            IOError: If the PDF file cannot be read
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text_chunks: List[str] = []
                for page in pdf.pages:
                    if page_text := page.extract_text():
                        text_chunks.append(page_text)

            return "\n".join(text_chunks).replace("\r", "\n").strip()

        except Exception as e:
            self.log_error(e, "Raw text extraction failed")
            raise IOError(f"Failed to extract text from PDF: {str(e)}") from e

    def segment_sections(self, text: str) -> Dict[str, str]:
        """
        Segment the LinkedIn PDF text into logical sections.

        Args:
            text: Raw text extracted from PDF

        Returns:
            Dictionary mapping section names to their content
        """
        sections: Dict[str, str] = {}
        current_section = "header"
        current_content: List[str] = []

        lines = text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # Define section markers with their corresponding names
            section_markers = {
                "Experiência": "experience",
                "Formação acadêmica": "education",
                "Resumo": "about",
                "Principais competências": "skills",
                "Languages": "languages",
                "Certificações": "certifications",
                "Voluntariado": "volunteer",
            }

            # Check for section transitions
            for marker, section_name in section_markers.items():
                if marker in line:
                    if current_content:
                        sections[current_section] = "\n".join(current_content)
                    current_section = section_name
                    current_content = []

                    # Special handling for about section
                    if section_name == "about":
                        i += 1
                        while i < len(lines) and not any(
                            m in lines[i] for m in section_markers
                        ):
                            if lines[i].strip():
                                current_content.append(lines[i].strip())
                            i += 1
                        continue
                    break
            else:
                current_content.append(line)

            i += 1

        # Add final section
        if current_content:
            sections[current_section] = "\n".join(current_content)

        return sections

    def parse_experience_section(self, content: str) -> None:
        """
        Parse the experience section with comprehensive details.

        Args:
            content: Raw text content of the experience section
        """
        experiences: List[Experience] = []
        current_exp: Dict[str, Any] = {}
        description_lines: List[str] = []

        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # Handle company duration header
            if re.search(r"\d+\s+anos?\s+\d+\s+meses?", line):
                if current_exp and description_lines:
                    current_exp["description"] = " ".join(description_lines)
                    try:
                        experiences.append(Experience(**current_exp))
                    except ValidationError as e:
                        self.log_error(
                            e, f"Failed to validate experience: {current_exp}"
                        )
                current_exp = {}
                description_lines = []
                i += 1
                continue

            # Process job details
            try:
                self._process_job_details(
                    line, lines, i, current_exp, description_lines
                )
            except Exception as e:
                self.log_error(e, f"Error processing job details at line {i}: {line}")

            i += 1

        # Add final experience
        if current_exp:
            if description_lines:
                current_exp["description"] = " ".join(description_lines)
            try:
                experiences.append(Experience(**current_exp))
            except ValidationError as e:
                self.log_error(e, f"Failed to validate final experience: {current_exp}")

        self.profile_data["experiences"] = experiences

    def parse_education_section(self, content: str) -> None:
        """
        Parse education section with detailed information.

        Args:
            content: Raw text content of the education section
        """
        education_entries: List[Education] = []
        current_edu: Dict[str, Any] = {}
        description_lines: List[str] = []

        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = clean_text(lines[i])

            if not line:
                i += 1
                continue

            # New education entry starts with institution
            if not current_edu and not re.search(r"\d{4}", line):
                current_edu["institution"] = line
                i += 1
                continue

            # Extract degree and dates
            date_pattern = r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro) de (\d{4})"
            if date_match := re.search(date_pattern, line, re.IGNORECASE):
                dates = re.findall(date_pattern, line, re.IGNORECASE)
                if dates:
                    current_edu["start_date"] = f"{dates[0][0]} de {dates[0][1]}"
                    if len(dates) > 1:
                        current_edu["end_date"] = f"{dates[1][0]} de {dates[1][1]}"

                if i > 0 and "degree" not in current_edu:
                    current_edu["degree"] = clean_text(lines[i - 1])

                if description_lines:
                    current_edu["description"] = " ".join(description_lines)

                try:
                    education_entries.append(Education(**current_edu))
                except ValidationError as e:
                    self.log_error(
                        e, f"Failed to validate education entry: {current_edu}"
                    )

                current_edu = {}
                description_lines = []

            elif current_edu.get("institution") and not current_edu.get("degree"):
                description_lines.append(line)

            i += 1

        # Add final education entry
        if current_edu:
            if description_lines:
                current_edu["description"] = " ".join(description_lines)
            try:
                education_entries.append(Education(**current_edu))
            except ValidationError as e:
                self.log_error(
                    e, f"Failed to validate final education entry: {current_edu}"
                )

        self.profile_data["education"] = education_entries

    def parse_skills_section(self, content: str) -> None:
        """
        Parse skills section with categorization.

        Args:
            content: Raw text content of the skills section
        """
        skills: List[str] = []
        current_category: Optional[str] = None

        for line in content.split("\n"):
            line = clean_text(line)
            if not line:
                continue

            if line.endswith(":"):
                current_category = line[:-1]
            else:
                if current_category:
                    skills.append(f"{current_category}: {line}")
                else:
                    skills.append(line)

        self.profile_data["skills"] = skills

    def parse_languages_section(self, content: str) -> None:
        """
        Parse languages section with proficiency levels.

        Args:
            content: Raw text content of the languages section
        """
        self.profile_data["languages"] = parse_language_proficiency(content)

    def _process_job_details(
        self,
        line: str,
        lines: List[str],
        i: int,
        current_exp: Dict[str, Any],
        description_lines: List[str],
    ) -> None:
        """
        Process job details from a single line.

        Args:
            line: Current line being processed
            lines: All lines in the section
            i: Current line index
            current_exp: Current experience entry being built
            description_lines: List of description lines for current experience
        """
        # Extract job title
        if not current_exp and re.match(r"^[A-Za-z\s&]+$", line):
            current_exp["title"] = line
            return

        # Extract dates and location
        date_pattern = r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro) de (\d{4})"
        if re.search(date_pattern, line, re.IGNORECASE):
            dates = re.findall(date_pattern, line, re.IGNORECASE)
            if dates:
                current_exp["start_date"] = f"{dates[0][0]} de {dates[0][1]}"
                if len(dates) > 1:
                    current_exp["end_date"] = f"{dates[1][0]} de {dates[1][1]}"

            # Extract location
            location_parts = line.split(",")
            if len(location_parts) > 1:
                current_exp["location"] = location_parts[-1].strip()

            # Extract company name from previous line
            if i > 0:
                current_exp["company"] = lines[i - 1].strip()
            return

        # Collect description points
        if current_exp.get("company"):
            if line.startswith(("- ", "• ")):
                description_lines.append(line[2:].strip())
            elif len(line) > 20:  # Likely a description line
                description_lines.append(line)

    # ... [Previous education, skills, and languages parsing methods remain the same]

    async def _extract_basic_info(
        self, text: str, hf_service: Optional[HuggingFaceService] = None
    ) -> Dict[str, Optional[str]]:
        """
        Extract basic profile information using regex and Hugging Face classification.

        Args:
            text: Raw text content from PDF
            hf_service: Optional HuggingFace service instance. Uses default if None.

        Returns:
            Dictionary containing basic profile information

        Raises:
            FieldMappingError: If classification fails
        """
        basic_info = {
            "full_name": None,
            "email": None,
            "phone": None,
            "linkedin": None,
            "headline": None,
        }

        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Extract email
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        if email_match := re.search(email_pattern, text):
            basic_info["email"] = email_match.group()

        # Extract phone (international format)
        phone_pattern = r"(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        if phone_match := re.search(phone_pattern, text):
            basic_info["phone"] = phone_match.group()

        # Extract LinkedIn URL
        linkedin_pattern = r"(https?://)?(www\.)?linkedin\.com/in/[A-Za-z0-9-_/]+"
        if linkedin_match := re.search(linkedin_pattern, text):
            basic_info["linkedin"] = linkedin_match.group()

        # Extract name - look for "Contato" pattern in LinkedIn exports
        for i, line in enumerate(lines):
            if line.startswith("Contato "):
                basic_info["full_name"] = line.replace("Contato ", "").strip()
                # Try to get headline from the next non-empty lines
                for next_line in lines[i + 1 :]:
                    if next_line and not any(
                        next_line.startswith(prefix)
                        for prefix in ("Contato", "+", "www", "http")
                    ):
                        basic_info["headline"] = next_line
                        break
                break

        # Fallback to HuggingFace classification if name not found
        if not basic_info["full_name"] and lines:
            service = hf_service or huggingface_service
            try:
                classification = await service.zero_shot_classify(
                    sequences=lines[:2],
                    candidate_labels=["full_name", "headline", "other"],
                )

                predictions = classification[0] if classification else {}

                for i, line in enumerate(lines[:2]):
                    if i == 0 and predictions.get("scores", [0])[0] > 0.8:
                        basic_info["full_name"] = line
                    elif i == 1 and not basic_info["headline"]:
                        basic_info["headline"] = line

            except Exception as e:
                self.log_error(e, "Classification Error")
                raise FieldMappingError(
                    f"Failed to classify profile fields: {str(e)}"
                ) from e

        return basic_info

    def parse_sections(self, sections: Dict[str, Any]) -> None:
        """
        Parse the extracted sections and store them in the parser.
        """
        experience_data = sections.get("experience")
        if isinstance(experience_data, str):
            # Convert string content to a list of experiences
            self.experience_data = self._parse_experience_text(experience_data)
            print("EXPERIENCE DATA", self.experience_data)
        elif not isinstance(experience_data, list):
            # Fallback if it's neither string nor list
            experience_data = []

    async def parse_profile(self, pdf_path: Union[str, Path]) -> LinkedInProfile:
        """
        Parse complete LinkedIn profile from PDF file.

        Args:
            pdf_path: Path to the LinkedIn profile PDF

        Returns:
            LinkedInProfile instance

        Raises:
            ProfileParsingError: If parsing fails
            ValidationError: If profile data is invalid
        """
        self.log_operation_start("profile parsing", pdf_path=str(pdf_path))

        try:
            raw_text = self.extract_raw_text(pdf_path)
            self.log_info("Raw text extracted")

            # Extract basic info
            basic_info = await self._extract_basic_info(raw_text)
            self.profile_data.update(basic_info)

            # Parse all sections
            sections = self.segment_sections(raw_text)
            self.parse_sections(sections)
            self.profile_data.update(
                {
                    "experiences": self.experience_data
                    if len(self.experience_data) > 0
                    else []
                }
            )

            # Validate profile data
            if not self.profile_data.get("full_name"):
                raise ProfileParsingError("Full name is missing from the profile data")

            try:
                profile = LinkedInProfile(**self.profile_data)
            except ValidationError as e:
                raise ProfileParsingError(f"Invalid profile data: {str(e)}") from e

            self.log_operation_end("profile parsing")
            return profile

        except Exception as e:
            self.log_error(e, "profile parsing")
            traceback.print_exc()
            raise ProfileParsingError(f"Failed to parse profile: {str(e)}") from e

    def _parse_experience_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Naive approach to convert a raw experience string into parsed data.
        Extend or replace this logic for more advanced parsing.
        """
        results = []
        for block in text.split("\n"):
            block = block.strip()
            if block:
                results.append({"title": block})
        return results

    def _parse_experience(self, experience_data: List[Dict[str, Any]]) -> None:
        """
        Refactored function to handle the final experience list.
        """
        parsed_experiences = []
        for exp in experience_data:
            if not isinstance(exp, dict):
                # Minimal handling if entry is still just a string
                parsed_experiences.append({"title": str(exp)})
                continue
            parsed_experiences.append(
                {
                    "start_date": exp.get("start_date"),
                    "end_date": exp.get("end_date"),
                    "company": exp.get("company"),
                    "location": exp.get("location"),
                    "title": exp.get("title"),
                }
            )
        self.experience = parsed_experiences


async def create_profile_from_pdf(pdf_path: Union[str, Path]) -> LinkedInProfile:
    """
    Create a LinkedInProfile instance from a PDF file.

    Args:
        pdf_path: Path to the LinkedIn profile PDF

    Returns:
        LinkedInProfile instance

    Raises:
        ProfileParsingError: If parsing fails
        ValidationError: If profile data is invalid
    """
    parser = PDFParser()
    profile = await parser.parse_profile(pdf_path)

    # Save the profile data
    json_path = settings.data_dir / "user_profile.json"
    profile.to_json(json_path)

    return profile


async def _extract_basic_info(
    text: str, hf_service: Optional[HuggingFaceService] = None
) -> Dict[str, Optional[str]]:
    """
    Extract basic profile information using regex and Hugging Face classification.

    Args:
        text: Raw text content from PDF
        hf_service: Optional HuggingFace service instance. Uses default if None.

    Returns:
        Dictionary containing basic profile information

    Raises:
        FieldMappingError: If classification fails
    """
    basic_info = {
        "full_name": None,
        "email": None,
        "phone": None,
        "linkedin": None,
        "headline": None,
    }

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Extract email
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    if email_match := re.search(email_pattern, text):
        basic_info["email"] = email_match.group()

    # Extract phone (international format)
    phone_pattern = r"(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    if phone_match := re.search(phone_pattern, text):
        basic_info["phone"] = phone_match.group()

    # Extract LinkedIn URL
    linkedin_pattern = r"(https?://)?(www\.)?linkedin\.com/in/[A-Za-z0-9-_/]+"
    if linkedin_match := re.search(linkedin_pattern, text):
        basic_info["linkedin"] = linkedin_match.group()

    # Extract name - look for "Contato" pattern in LinkedIn exports
    for i, line in enumerate(lines):
        if line.startswith("Contato "):
            basic_info["full_name"] = line.replace("Contato ", "").strip()
            # Try to get headline from the next non-empty lines
            for next_line in lines[i + 1 :]:
                if next_line and not any(
                    next_line.startswith(prefix)
                    for prefix in ("Contato", "+", "www", "http")
                ):
                    basic_info["headline"] = next_line
                    break
            break

    # Fallback to HuggingFace classification if name not found
    if not basic_info["full_name"] and lines:
        service = hf_service or huggingface_service
        try:
            classification = await service.zero_shot_classify(
                sequences=lines[:2], candidate_labels=["full_name", "headline", "other"]
            )

            predictions = classification[0] if classification else {}

            for i, line in enumerate(lines[:2]):
                if i == 0 and predictions.get("scores", [0])[0] > 0.8:
                    basic_info["full_name"] = line
                elif i == 1 and not basic_info["headline"]:
                    basic_info["headline"] = line

        except Exception as e:
            logger.error(f"Classification Error: {str(e)}")
            raise FieldMappingError(
                f"Failed to classify profile fields: {str(e)}"
            ) from e

    return basic_info


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.

    Args:
        text: Raw text to clean

    Returns:
        Cleaned and normalized text
    """
    # Remove multiple spaces
    text = re.sub(r"\s+", " ", text)
    # Remove Unicode control characters
    text = re.sub(r"[\x00-\x1F\x7F-\x9F]", "", text)
    # Normalize whitespace around punctuation
    text = re.sub(r"\s*([,.!?])\s*", r"\1 ", text)
    return text.strip()


def parse_duration(duration_str: str) -> tuple[Optional[int], Optional[int]]:
    """
    Parse duration string into years and months.

    Args:
        duration_str: Duration string (e.g., "2 anos 6 meses")

    Returns:
        Tuple of (years, months) as integers, None if parsing fails
    """
    years = None
    months = None

    year_pattern = r"(\d+)\s*anos?"
    month_pattern = r"(\d+)\s*meses?"

    if year_match := re.search(year_pattern, duration_str):
        years = int(year_match.group(1))
    if month_match := re.search(month_pattern, duration_str):
        months = int(month_match.group(1))

    return years, months


def parse_language_proficiency(text: str) -> List[Language]:
    """
    Parse language proficiencies from text.

    Args:
        text: Raw text containing language information

    Returns:
        List of Language objects
    """
    languages = []
    lines = text.split("\n")

    for line in lines:
        if "(" in line and ")" in line:
            parts = line.split("(")
            language_name = parts[0].strip()
            proficiency = parts[1].replace(")", "").strip()
            try:
                languages.append(
                    Language(language=language_name, proficiency=proficiency)
                )
            except ValidationError as e:
                logger.warning(f"Failed to parse language: {line} - {str(e)}")

    return languages
