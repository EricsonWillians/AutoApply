"""
Unit tests for the Hugging Face integration module.

This module contains comprehensive tests for the AI-powered field mapping
functionality, ensuring reliable form field mapping and proper model
interaction.

File location: tests/unit/test_huggingface_integration.py
"""

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest
import torch
from transformers import Pipeline

from app.services.huggingface_integration import (FieldMappingError,
                                                  HuggingFaceService,
                                                  huggingface_service)
from app.utils.config import settings


@pytest.fixture
def sample_profile_data() -> Dict[str, Any]:
    """Provide sample profile data for testing."""
    return {
        "full_name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+1234567890",
        "headline": "Senior Software Engineer",
        "summary": "Experienced software engineer specializing in Python and AI",
        "experience": [
            {
                "title": "Senior Software Engineer",
                "company": "TechCorp",
                "duration": "2 years",
            }
        ],
        "education": [
            {
                "degree": "Master of Science",
                "field": "Computer Science",
                "school": "Stanford University",
            }
        ],
        "skills": ["Python", "Machine Learning", "Docker"],
        "languages": ["English", "Spanish"],
    }


@pytest.fixture
def mock_pipeline() -> Mock:
    """Provide a mock transformer pipeline."""
    pipeline = Mock(spec=Pipeline)
    pipeline.return_value = {
        "sequence": "test input",
        "labels": ["test hypothesis"],
        "scores": [0.95],
    }
    return pipeline


@pytest.fixture
async def huggingface_instance(mock_pipeline: Mock) -> HuggingFaceService:
    """Provide a configured HuggingFaceService instance."""
    with patch("transformers.pipeline", return_value=mock_pipeline):
        service = HuggingFaceService()
        await service.initialize()
        return service


@pytest.mark.asyncio
class TestHuggingFaceService:
    """Tests for the HuggingFaceService class."""

    async def test_initialization(self, mock_pipeline: Mock):
        """Test service initialization."""
        with patch("transformers.pipeline", return_value=mock_pipeline):
            service = HuggingFaceService()
            await service.initialize()

            assert service._pipeline is not None
            assert service._device in ["cuda", "cpu"]

    async def test_initialization_error(self):
        """Test handling of initialization errors."""
        with patch(
            "transformers.pipeline",
            side_effect=Exception("Model initialization failed"),
        ):
            service = HuggingFaceService()
            with pytest.raises(FieldMappingError):
                await service.initialize()

    async def test_map_text_field(
        self,
        huggingface_instance: HuggingFaceService,
        sample_profile_data: Dict[str, Any],
    ):
        """Test mapping of text input fields."""
        field_label = "Full Name"
        field_type = "text"

        value, confidence = await huggingface_instance.map_field(
            field_label, field_type, sample_profile_data
        )

        assert value == "John Doe"
        assert confidence > 0.0
        assert huggingface_instance._pipeline.called

    async def test_map_email_field(
        self,
        huggingface_instance: HuggingFaceService,
        sample_profile_data: Dict[str, Any],
    ):
        """Test mapping of email fields."""
        field_label = "Email Address"
        field_type = "email"

        value, confidence = await huggingface_instance.map_field(
            field_label, field_type, sample_profile_data
        )

        assert value == "john.doe@example.com"
        assert confidence > 0.0

    async def test_map_phone_field(
        self,
        huggingface_instance: HuggingFaceService,
        sample_profile_data: Dict[str, Any],
    ):
        """Test mapping of phone number fields."""
        field_label = "Phone Number"
        field_type = "tel"

        value, confidence = await huggingface_instance.map_field(
            field_label, field_type, sample_profile_data
        )

        assert value == "+1234567890"
        assert confidence > 0.0

    async def test_map_selection_field(
        self,
        huggingface_instance: HuggingFaceService,
        sample_profile_data: Dict[str, Any],
    ):
        """Test mapping of selection fields with candidates."""
        field_label = "Preferred Language"
        field_type = "select"
        candidates = ["English", "Spanish", "French", "German"]

        value, confidence = await huggingface_instance.map_field(
            field_label, field_type, sample_profile_data, candidates
        )

        assert value in ["English", "Spanish"]
        assert confidence > 0.0

    async def test_map_field_no_match(
        self,
        huggingface_instance: HuggingFaceService,
        sample_profile_data: Dict[str, Any],
    ):
        """Test handling of fields with no matching data."""
        field_label = "Nonexistent Field"
        field_type = "text"

        value, confidence = await huggingface_instance.map_field(
            field_label, field_type, sample_profile_data
        )

        assert value == ""
        assert confidence == 0.0

    async def test_map_field_error(
        self,
        huggingface_instance: HuggingFaceService,
        sample_profile_data: Dict[str, Any],
    ):
        """Test handling of mapping errors."""
        huggingface_instance._pipeline.side_effect = Exception("Mapping failed")

        with pytest.raises(FieldMappingError):
            await huggingface_instance.map_field(
                "Test Field", "text", sample_profile_data
            )

    async def test_hypothesis_generation(
        self, huggingface_instance: HuggingFaceService
    ):
        """Test generation of mapping hypotheses."""
        test_cases = [
            ("email", "This field requires an email address"),
            ("tel", "This field requires a phone number"),
            ("text", "This field requires full name"),
        ]

        for field_type, expected in test_cases:
            hypothesis = huggingface_instance._generate_mapping_hypothesis(
                "Full Name", field_type
            )
            assert isinstance(hypothesis, str)
            assert len(hypothesis) > 0

    async def test_candidate_classification(
        self, huggingface_instance: HuggingFaceService, mock_pipeline: Mock
    ):
        """Test classification of candidate values."""
        hypothesis = "This field requires a programming language"
        candidates = ["Python", "Java", "JavaScript"]

        result = await huggingface_instance._classify_candidates(hypothesis, candidates)

        assert "labels" in result
        assert "scores" in result
        assert len(result["labels"]) > 0
        assert len(result["scores"]) > 0

    async def test_device_selection(self):
        """Test proper device selection based on availability."""
        with patch("torch.cuda.is_available", return_value=True):
            service = HuggingFaceService()
            assert service._device == "cuda"

        with patch("torch.cuda.is_available", return_value=False):
            service = HuggingFaceService()
            assert service._device == "cpu"


@pytest.mark.asyncio
class TestHuggingFaceServiceIntegration:
    """Integration tests for HuggingFaceService."""

    async def test_complete_field_mapping(
        self,
        huggingface_instance: HuggingFaceService,
        sample_profile_data: Dict[str, Any],
    ):
        """Test complete field mapping process."""
        test_fields = [
            ("Full Name", "text"),
            ("Email Address", "email"),
            ("Phone Number", "tel"),
            ("Current Position", "text"),
            ("Education Level", "select", ["Bachelor's", "Master's", "PhD"]),
        ]

        for field_data in test_fields:
            field_label, field_type = field_data[:2]
            candidates = field_data[2] if len(field_data) > 2 else None

            value, confidence = await huggingface_instance.map_field(
                field_label, field_type, sample_profile_data, candidates
            )

            assert isinstance(value, str)
            assert isinstance(confidence, float)
            assert 0 <= confidence <= 1

    async def test_model_reuse(
        self,
        huggingface_instance: HuggingFaceService,
        sample_profile_data: Dict[str, Any],
    ):
        """Test efficient model reuse across multiple mappings."""
        # First mapping
        value1, conf1 = await huggingface_instance.map_field(
            "Name", "text", sample_profile_data
        )

        # Second mapping should reuse the model
        value2, conf2 = await huggingface_instance.map_field(
            "Email", "email", sample_profile_data
        )

        assert huggingface_instance._pipeline is not None
        assert huggingface_instance._pipeline.call_count == 2


if __name__ == "__main__":
    pytest.main(["-v"])
