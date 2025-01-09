# app/core/pdf_parser.py

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pdfplumber
from pydantic import BaseModel, Field, validator

from app.services.huggingface_integration import huggingface_service
from app.utils.config import settings
from app.utils.logging import LoggerMixin


class Experience(BaseModel):
    """Model representing work experience entry."""

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
        if not value:
            return None
        for fmt in ("%B %Y", "%Y-%m", "%Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None


class Education(BaseModel):
    """Model representing educational background."""

    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    description: Optional[str] = None

    @validator("start_date", "end_date", pre=True)
    def parse_date(cls, value: Optional[str]) -> Optional[datetime]:
        """Parse date strings into datetime objects."""
        if not value:
            return None
        for fmt in ("%B %Y", "%Y-%m", "%Y"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return None


class LinkedInProfile(BaseModel):
    """Model representing the complete LinkedIn profile."""

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


async def extract_basic_info_with_hf(
    text: str, hf_service: "HuggingFaceService"
) -> Dict[str, Optional[str]]:
    """Extract basic information using regex and Hugging Face classification."""
    basic_info = {
        "full_name": None,
        "email": None,
        "phone": None,
        "linkedin": None,
        "headline": None,
    }

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Extract email
    email_match = re.search(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", text
    )
    if email_match:
        basic_info["email"] = email_match.group()

    # Extract phone (international format)
    phone_match = re.search(
        r"(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text
    )
    if phone_match:
        basic_info["phone"] = phone_match.group()

    # Extract LinkedIn URL
    linkedin_match = re.search(
        r"(https?://)?(www\.)?linkedin\.com/in/[A-Za-z0-9-_/]+", text
    )
    if linkedin_match:
        basic_info["linkedin"] = linkedin_match.group()

    # Extract name - look for "Contato" pattern in LinkedIn exports
    for i, line in enumerate(lines):
        if line.startswith("Contato "):
            basic_info["full_name"] = line.replace("Contato ", "").strip()
            # Try to get headline from the next non-empty lines
            for next_line in lines[i + 1 :]:
                if next_line and not next_line.startswith(
                    ("Contato", "+", "www", "http")
                ):
                    basic_info["headline"] = next_line
                    break
            break

    # Fallback to HuggingFace classification if name not found
    if not basic_info["full_name"] and lines:
        try:
            classification = await hf_service.zero_shot_classify(
                sequences=lines[:2], candidate_labels=["full_name", "headline", "other"]
            )

            predictions = classification[0] if classification else {}

            for i, line in enumerate(lines[:2]):
                if i == 0 and predictions.get("scores", [0])[0] > 0.8:
                    basic_info["full_name"] = line
                elif i == 1 and not basic_info["headline"]:
                    basic_info["headline"] = line

        except Exception as e:
            print(f"Classification Error: {e}")

    return basic_info


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
            "email": None,
            "phone": None,
            "linkedin": None,
            "full_name": None,
            "headline": None,
            "location": None,
            "about": None,
        }

    async def parse_profile(self, pdf_path: Union[str, Path]) -> LinkedInProfile:
        """Parse LinkedIn profile data from a PDF file."""
        self.log_operation_start("profile parsing", pdf_path=str(pdf_path))

        try:
            raw_text = self.extract_raw_text(pdf_path)
            self.log_info("Raw text extracted")

            # Extract basic info
            basic_info = await extract_basic_info_with_hf(raw_text, huggingface_service)
            self.profile_data.update(basic_info)

            # Parse sections
            sections = self.segment_sections(raw_text)
            self.parse_sections(sections)

            # Validate mandatory fields
            if not self.profile_data.get("full_name"):
                raise ValueError("Full name is missing from the profile data.")

            profile = LinkedInProfile(**self.profile_data)
            self.log_operation_end("profile parsing")
            return profile

        except Exception as e:
            self.log_error(e, "profile parsing")
            raise

    def extract_raw_text(self, pdf_path: Union[str, Path]) -> str:
        """Extract and preprocess raw text from the PDF file."""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
            return full_text.replace("\r", "\n").strip()
        except Exception as e:
            self.log_error(e, "Raw text extraction")
            raise

    def segment_sections(self, text: str) -> Dict[str, str]:
        """Segment the raw text into sections."""
        sections = {}
        current_section = "header"
        current_content = []

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Identify section headers
            if (
                line.upper() == line and len(line) > 3
            ):  # Section headers are typically uppercase
                if current_content:
                    sections[current_section] = "\n".join(current_content)
                current_section = line.lower()
                current_content = []
            else:
                current_content.append(line)

        # Add the last section
        if current_content:
            sections[current_section] = "\n".join(current_content)

        return sections

    def parse_sections(self, sections: Dict[str, str]) -> None:
        """Parse each section and populate profile_data."""
        for section, content in sections.items():
            if "experience" in section:
                self.parse_experience_section(content)
            elif "education" in section:
                self.parse_education_section(content)
            elif "skill" in section:
                self.profile_data["skills"] = [s.strip() for s in content.split(",")]
            elif "language" in section:
                self.profile_data["languages"] = [l.strip() for l in content.split(",")]
            elif "certification" in section:
                self.profile_data["certifications"] = [
                    c.strip() for c in content.split("\n")
                ]

    def parse_experience_section(self, content: str) -> None:
        """Parse experience section content."""
        experiences = []
        current_exp = {}

        for line in content.split("\n"):
            line = line.strip()
            if not line:
                if current_exp:
                    experiences.append(Experience(**current_exp))
                    current_exp = {}
            elif not current_exp:
                current_exp = {"title": line}
            elif "title" in current_exp and "company" not in current_exp:
                current_exp["company"] = line

        if current_exp:
            experiences.append(Experience(**current_exp))

        self.profile_data["experiences"] = experiences

    def parse_education_section(self, content: str) -> None:
        """Parse education section content."""
        education = []
        current_edu = {}

        for line in content.split("\n"):
            line = line.strip()
            if not line:
                if current_edu:
                    education.append(Education(**current_edu))
                    current_edu = {}
            elif not current_edu:
                current_edu = {"institution": line}
            elif "institution" in current_edu and "degree" not in current_edu:
                current_edu["degree"] = line

        if current_edu:
            education.append(Education(**current_edu))

        self.profile_data["education"] = education


async def create_profile_from_pdf(pdf_path: Union[str, Path]) -> LinkedInProfile:
    """Create a LinkedInProfile instance from a PDF file."""
    parser = PDFParser()
    profile = await parser.parse_profile(pdf_path)

    # Save the profile data
    json_path = settings.data_dir / "user_profile.json"
    profile.to_json(json_path)

    return profile
