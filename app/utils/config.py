"""
Configuration module for AutoApply.

This module handles all configuration management for the application,
including environment variables, application settings, and Hugging Face
model configurations.
"""

import os
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

# Load environment variables
load_dotenv()


class Settings(BaseSettings):
    """Application settings and configuration management."""

    # API Tokens and Secrets
    huggingface_api_token: SecretStr = Field(
        default_factory=lambda: os.environ.get("HUGGINGFACE_API_TOKEN", "")
    )

    # Application Paths
    base_dir: Path = Field(default=Path(__file__).parent.parent.parent)
    data_dir: Path = Field(default=Path(__file__).parent.parent.parent / "data")
    resumes_dir: Path = Field(
        default=Path(__file__).parent.parent.parent / "data" / "resumes"
    )

    # Model Configuration
    model_name: str = Field(default="bert-base-uncased")
    max_sequence_length: int = Field(default=512)

    # Playwright Configuration
    browser_type: str = Field(default="chromium")
    headless: bool = Field(default=True)
    browser_args: list = Field(default_factory=lambda: ["--disable-dev-shm-usage"])

    # Application Settings
    verification_timeout: int = Field(default=300)  # 5 minutes
    max_retries: int = Field(default=3)
    log_level: str = Field(default="INFO")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }

    def get_huggingface_token(self) -> str:
        """Safely retrieve the Hugging Face API token."""
        return self.huggingface_api_token.get_secret_value()

    def get_directory_paths(self) -> Dict[str, Path]:
        """Get all directory paths as a dictionary."""
        return {
            "base_dir": self.base_dir,
            "data_dir": self.data_dir,
            "resumes_dir": self.resumes_dir,
        }

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        for directory in self.get_directory_paths().values():
            directory.mkdir(parents=True, exist_ok=True)

    def validate_paths(self) -> bool:
        """Validate that all required paths exist and are accessible."""
        try:
            self.ensure_directories()
            return all(path.exists() for path in self.get_directory_paths().values())
        except Exception:
            return False


# Global settings instance
settings = Settings()
