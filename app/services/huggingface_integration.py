"""
Hugging Face integration module for AutoApply.

This module handles all interactions with the Hugging Face transformers
library, providing intelligent form field mapping capabilities through
natural language processing.

File location: app/services/huggingface_integration.py
"""

from typing import Any, Dict, List, Optional, Tuple

import torch
from transformers import AutoModel, AutoTokenizer, Pipeline, pipeline

from app.utils.config import settings
from app.utils.logging import LoggerMixin


class FieldMappingError(Exception):
    """Custom exception for field mapping errors."""

    pass


class HuggingFaceService(LoggerMixin):
    """Service for handling Hugging Face model interactions."""

    def __init__(self) -> None:
        """Initialize the Hugging Face service."""
        super().__init__()
        self._model: Optional[AutoModel] = None
        self._tokenizer: Optional[AutoTokenizer] = None
        self._pipeline: Optional[Pipeline] = None
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self.logger.info(f"Using device: {self._device}")

    async def initialize(self) -> None:
        """
        Initialize the model and tokenizer asynchronously.

        This method should be called before using any other methods of the class.
        """
        try:
            self.log_operation_start("model initialization")

            # Initialize the zero-shot classification pipeline
            self._pipeline = pipeline(
                "zero-shot-classification",
                model=settings.model_name,
                device=self._device,
                token=settings.get_huggingface_token(),
            )

            self.log_operation_end("model initialization")

        except Exception as e:
            self.log_error(e, "model initialization")
            raise FieldMappingError(
                f"Failed to initialize Hugging Face model: {str(e)}"
            )

    async def map_field(
        self,
        field_label: str,
        field_type: str,
        profile_data: Dict[str, Any],
        candidate_values: Optional[List[str]] = None,
    ) -> Tuple[str, float]:
        """
        Map a form field to the corresponding profile data.

        Args:
            field_label: The label or placeholder text of the form field.
            field_type: The HTML input type or field type.
            profile_data: The user's profile data.
            candidate_values: Optional list of candidate values for selection fields.

        Returns:
            A tuple containing the mapped value and confidence score.
        """
        try:
            self.log_operation_start(
                "field mapping", field_label=field_label, field_type=field_type
            )

            # Prepare the mapping hypothesis
            hypothesis = self._generate_mapping_hypothesis(field_label, field_type)

            if candidate_values:
                # Handle selection fields (dropdowns, radio buttons, etc.)
                return await self._map_selection_field(
                    hypothesis, candidate_values, profile_data
                )

            # Handle text input fields
            return await self._map_text_field(
                hypothesis, field_label, field_type, profile_data
            )

        except Exception as e:
            self.log_error(e, "field mapping")
            raise FieldMappingError(f"Failed to map field {field_label}: {str(e)}")

    async def _map_selection_field(
        self, hypothesis: str, candidates: List[str], profile_data: Dict[str, Any]
    ) -> Tuple[str, float]:
        """
        Map a selection field to the best matching candidate value.

        Args:
            hypothesis: The mapping hypothesis.
            candidates: List of candidate values.
            profile_data: The user's profile data.

        Returns:
            The best matching candidate and confidence score.
        """
        try:
            # Use zero-shot classification to find the best match
            result = await self._classify_candidates(hypothesis, candidates)

            if not result["scores"]:
                raise FieldMappingError("No valid candidates found")

            # Return the best matching candidate and its confidence score
            return result["labels"][0], result["scores"][0]

        except Exception as e:
            self.log_error(e, "selection field mapping")
            raise FieldMappingError(f"Failed to map selection field: {str(e)}")

    async def _map_text_field(
        self,
        hypothesis: str,
        field_label: str,
        field_type: str,
        profile_data: Dict[str, Any],
    ) -> Tuple[str, float]:
        """
        Map a text input field to the corresponding profile data.

        Args:
            hypothesis: The mapping hypothesis.
            field_label: The label of the field.
            field_type: The type of the field.
            profile_data: The user's profile data.

        Returns:
            The mapped value and confidence score.
        """
        try:
            # Extract potential values from profile data based on field type
            candidate_values = self._extract_candidate_values(field_type, profile_data)

            if not candidate_values:
                return "", 0.0

            # Use zero-shot classification to find the best match
            result = await self._classify_candidates(hypothesis, candidate_values)

            if not result["scores"]:
                return "", 0.0

            # Return the best matching value and its confidence score
            return result["labels"][0], result["scores"][0]

        except Exception as e:
            self.log_error(e, "text field mapping")
            raise FieldMappingError(f"Failed to map text field: {str(e)}")

    def _generate_mapping_hypothesis(self, field_label: str, field_type: str) -> str:
        """
        Generate a hypothesis for field mapping.

        Args:
            field_label: The label of the field.
            field_type: The type of the field.

        Returns:
            A string containing the mapping hypothesis.
        """
        # Clean and normalize the field label
        normalized_label = field_label.lower().strip()

        # Generate hypothesis based on field type
        if field_type == "email":
            return "This field requires an email address"
        elif field_type == "tel":
            return "This field requires a phone number"
        elif field_type == "date":
            return "This field requires a date"
        else:
            return f"This field requires {normalized_label}"

    def _extract_candidate_values(
        self, field_type: str, profile_data: Dict[str, Any]
    ) -> List[str]:
        """
        Extract candidate values from profile data based on field type.

        Args:
            field_type: The type of the field.
            profile_data: The user's profile data.

        Returns:
            List of candidate values.
        """
        candidates = []

        # Extract values based on field type
        if field_type == "email":
            if profile_data.get("email"):
                candidates.append(profile_data["email"])
        elif field_type == "tel":
            if profile_data.get("phone"):
                candidates.append(profile_data["phone"])
        else:
            # Add relevant profile fields as candidates
            for key, value in profile_data.items():
                if isinstance(value, str):
                    candidates.append(value)
                elif isinstance(value, list):
                    candidates.extend([str(v) for v in value if v])

        return candidates

    async def _classify_candidates(
        self, hypothesis: str, candidates: List[str]
    ) -> Dict[str, Any]:
        """
        Classify candidate values against the hypothesis.

        Args:
            hypothesis: The mapping hypothesis.
            candidates: List of candidate values.

        Returns:
            Dictionary containing classification results.
        """
        if not self._pipeline:
            await self.initialize()

        return self._pipeline(
            sequences=candidates, candidate_labels=[hypothesis], multi_label=False
        )


# Global instance
huggingface_service = HuggingFaceService()
