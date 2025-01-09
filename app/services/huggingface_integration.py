# app/services/huggingface_integration.py

import os
import traceback
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv

from app.utils.config import settings
from app.utils.logging import LoggerMixin


class FieldMappingError(Exception):
    """Custom exception for field mapping errors."""

    pass


class HuggingFaceService(LoggerMixin):
    """Service for handling Hugging Face model interactions via inference endpoint."""

    def __init__(self, api_url: str, api_token: str) -> None:
        """Initialize the Hugging Face service with the inference endpoint."""
        super().__init__()
        self.api_url = api_url
        self.api_token = api_token

    async def zero_shot_classify(
        self, sequences: List[str], candidate_labels: List[str]
    ) -> Dict[str, Any]:
        """
        Perform zero-shot classification using the inference endpoint.

        Args:
            sequences: List of text sequences to classify.
            candidate_labels: List of candidate labels.

        Returns:
            Classification results as JSON.
        """
        payload = {
            "inputs": sequences,
            "parameters": {"candidate_labels": candidate_labels, "multi_label": False},
        }

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:  # Increased timeout
            try:
                response = await client.post(
                    self.api_url, headers=headers, json=payload
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                self.log_error(
                    exc,
                    f"zero_shot_classify failed with status {exc.response.status_code}: {exc.response.text}",
                )
                raise FieldMappingError(
                    f"Zero-shot classification failed: {exc}"
                ) from exc
            except httpx.ReadTimeout as exc:
                self.log_error(exc, "zero_shot_classify request timed out.")
                raise FieldMappingError(
                    "Zero-shot classification request timed out."
                ) from exc
            except Exception as exc:
                self.log_error(exc, "zero_shot_classify")
                raise FieldMappingError(
                    f"An error occurred during zero-shot classification: {exc}"
                ) from exc


huggingface_service = HuggingFaceService(
    api_url=os.getenv("HUGGINGFACE_API_URL"),
    api_token=os.getenv("HUGGINGFACE_API_TOKEN"),
)
