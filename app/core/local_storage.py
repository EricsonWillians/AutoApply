"""
Local storage management module for AutoApply.

This module provides secure data persistence capabilities for the application,
handling profile data storage and application tracking while ensuring proper
encryption and validation of sensitive information.

File location: app/core/local_storage.py
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from cryptography.fernet import Fernet
from pydantic import BaseModel, Field, validator

from app.utils.config import settings
from app.utils.logging import LoggerMixin


class StorageError(Exception):
    """Custom exception for storage-related errors."""

    pass


class ApplicationRecord(BaseModel):
    """Model representing a job application record."""

    job_url: str
    company_name: Optional[str] = None
    position_title: Optional[str] = None
    application_date: datetime = Field(default_factory=datetime.utcnow)
    status: str = "submitted"
    verification_duration: float
    confidence_scores: Dict[str, float]
    modifications_made: bool
    resume_used: Optional[Path] = None

    @validator("status")
    def validate_status(cls, value: str) -> str:
        """Validate the application status."""
        valid_statuses = {"submitted", "pending", "accepted", "rejected"}
        if value.lower() not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        return value.lower()


class StorageManager(LoggerMixin):
    """Manages secure local storage of application data."""

    def __init__(self) -> None:
        """Initialize the storage manager."""
        super().__init__()
        self._encryption_key: Optional[bytes] = None
        self._cipher_suite: Optional[Fernet] = None
        self._initialize_encryption()

    def _initialize_encryption(self) -> None:
        """Initialize encryption for sensitive data."""
        try:
            key_path = settings.data_dir / ".encryption_key"

            if not key_path.exists():
                self._encryption_key = Fernet.generate_key()
                with open(key_path, "wb") as f:
                    f.write(self._encryption_key)
            else:
                with open(key_path, "rb") as f:
                    self._encryption_key = f.read()

            self._cipher_suite = Fernet(self._encryption_key)

        except Exception as e:
            self.log_error(e, "encryption initialization")
            raise StorageError(f"Failed to initialize encryption: {str(e)}")

    def _encrypt_data(self, data: Union[str, bytes]) -> bytes:
        """
        Encrypt sensitive data.

        Args:
            data: Data to encrypt.

        Returns:
            Encrypted data as bytes.
        """
        if not self._cipher_suite:
            raise StorageError("Encryption not initialized")

        try:
            if isinstance(data, str):
                data = data.encode()
            return self._cipher_suite.encrypt(data)

        except Exception as e:
            self.log_error(e, "data encryption")
            raise StorageError(f"Failed to encrypt data: {str(e)}")

    def _decrypt_data(self, encrypted_data: bytes) -> str:
        """
        Decrypt sensitive data.

        Args:
            encrypted_data: Data to decrypt.

        Returns:
            Decrypted data as string.
        """
        if not self._cipher_suite:
            raise StorageError("Encryption not initialized")

        try:
            decrypted = self._cipher_suite.decrypt(encrypted_data)
            return decrypted.decode()

        except Exception as e:
            self.log_error(e, "data decryption")
            raise StorageError(f"Failed to decrypt data: {str(e)}")

    def store_profile_data(
        self, profile_data: Dict[str, Any], encrypt_sensitive: bool = True
    ) -> None:
        """
        Store LinkedIn profile data securely.

        Args:
            profile_data: Profile data to store.
            encrypt_sensitive: Whether to encrypt sensitive fields.
        """
        try:
            self.log_operation_start("profile storage")

            # Create a copy of the data for modification
            storage_data = profile_data.copy()

            if encrypt_sensitive:
                # Encrypt sensitive fields
                sensitive_fields = {"email", "phone", "address"}
                for field in sensitive_fields:
                    if field in storage_data:
                        encrypted = self._encrypt_data(str(storage_data[field]))
                        storage_data[field] = encrypted.hex()

            # Store the data
            profile_path = settings.data_dir / "user_profile.json"
            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(storage_data, f, indent=2, default=str)

            self.log_operation_end("profile storage")

        except Exception as e:
            self.log_error(e, "profile storage")
            raise StorageError(f"Failed to store profile data: {str(e)}")

    def load_profile_data(self, decrypt_sensitive: bool = True) -> Dict[str, Any]:
        """
        Load stored profile data.

        Args:
            decrypt_sensitive: Whether to decrypt sensitive fields.

        Returns:
            Dictionary containing profile data.
        """
        try:
            self.log_operation_start("profile loading")

            profile_path = settings.data_dir / "user_profile.json"
            if not profile_path.exists():
                raise StorageError("Profile data not found")

            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if decrypt_sensitive:
                # Decrypt sensitive fields
                sensitive_fields = {"email", "phone", "address"}
                for field in sensitive_fields:
                    if field in data:
                        encrypted = bytes.fromhex(data[field])
                        data[field] = self._decrypt_data(encrypted)

            self.log_operation_end("profile loading")
            return data

        except Exception as e:
            self.log_error(e, "profile loading")
            raise StorageError(f"Failed to load profile data: {str(e)}")

    def store_application_record(self, record: ApplicationRecord) -> None:
        """
        Store a job application record.

        Args:
            record: ApplicationRecord instance to store.
        """
        try:
            self.log_operation_start("application record storage")

            # Load existing records
            records_path = settings.data_dir / "application_records.json"
            records: List[Dict[str, Any]] = []

            if records_path.exists():
                with open(records_path, "r", encoding="utf-8") as f:
                    records = json.load(f)

            # Add new record
            records.append(record.dict())

            # Store updated records
            with open(records_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)

            self.log_operation_end("application record storage")

        except Exception as e:
            self.log_error(e, "application record storage")
            raise StorageError(f"Failed to store application record: {str(e)}")

    def get_application_records(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> List[ApplicationRecord]:
        """
        Retrieve job application records within a date range.

        Args:
            start_date: Optional start date for filtering records.
            end_date: Optional end date for filtering records.

        Returns:
            List of ApplicationRecord instances.
        """
        try:
            self.log_operation_start("application records retrieval")

            records_path = settings.data_dir / "application_records.json"
            if not records_path.exists():
                return []

            with open(records_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Convert records to ApplicationRecord instances
            records = []
            for record_data in data:
                record = ApplicationRecord(**record_data)

                # Apply date filtering if specified
                if start_date and record.application_date < start_date:
                    continue
                if end_date and record.application_date > end_date:
                    continue

                records.append(record)

            self.log_operation_end(
                "application records retrieval", record_count=len(records)
            )
            return records

        except Exception as e:
            self.log_error(e, "application records retrieval")
            raise StorageError(f"Failed to retrieve application records: {str(e)}")

    def update_application_status(
        self, job_url: str, new_status: str, application_date: Optional[datetime] = None
    ) -> None:
        """
        Update the status of a job application.

        Args:
            job_url: URL of the job application.
            new_status: New status to set.
            application_date: Optional date to identify specific application.
        """
        try:
            self.log_operation_start("application status update")

            records_path = settings.data_dir / "application_records.json"
            if not records_path.exists():
                raise StorageError("No application records found")

            with open(records_path, "r", encoding="utf-8") as f:
                records = json.load(f)

            # Find and update the matching record
            updated = False
            for record in records:
                if record["job_url"] == job_url:
                    if application_date:
                        record_date = datetime.fromisoformat(record["application_date"])
                        if record_date != application_date:
                            continue

                    record["status"] = new_status
                    updated = True
                    break

            if not updated:
                raise StorageError("Application record not found")

            # Store updated records
            with open(records_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)

            self.log_operation_end("application status update")

        except Exception as e:
            self.log_error(e, "application status update")
            raise StorageError(f"Failed to update application status: {str(e)}")


# Global instance
storage_manager = StorageManager()
