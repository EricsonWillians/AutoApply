"""
Unit tests for the storage module.

This module contains comprehensive tests for secure data storage functionality,
ensuring proper handling of profile data and application records with
appropriate encryption and data integrity checks.

File location: tests/unit/test_storage.py
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
from cryptography.fernet import Fernet

from app.core.local_storage import (ApplicationRecord, StorageError,
                                    StorageManager, storage_manager)
from app.utils.config import settings


@pytest.fixture
def sample_profile_data():
    """Provide sample profile data for testing."""
    return {
        "full_name": "John Doe",
        "email": "john.doe@example.com",
        "phone": "+1234567890",
        "headline": "Senior Software Engineer",
        "location": "San Francisco Bay Area",
        "skills": ["Python", "Machine Learning", "Docker"],
        "languages": ["English", "Spanish"],
    }


@pytest.fixture
def sample_application_record():
    """Provide a sample application record for testing."""
    return {
        "job_url": "https://example.com/job/123",
        "company_name": "TechCorp",
        "position_title": "Senior Software Engineer",
        "application_date": datetime.utcnow(),
        "status": "submitted",
        "verification_duration": 45.5,
        "confidence_scores": {"name": 0.95, "email": 0.98},
        "modifications_made": False,
        "resume_used": Path("/path/to/resume.pdf"),
    }


@pytest.fixture
def storage_instance(tmp_path):
    """Provide a configured StorageManager instance."""
    with patch("app.utils.config.settings.data_dir", tmp_path):
        manager = StorageManager()
        return manager


class TestStorageManager:
    """Tests for the StorageManager class."""

    def test_encryption_initialization(self, storage_instance):
        """Test encryption initialization."""
        assert storage_instance._encryption_key is not None
        assert storage_instance._cipher_suite is not None
        assert isinstance(storage_instance._cipher_suite, Fernet)

    def test_encryption_key_persistence(self, tmp_path):
        """Test encryption key persistence across instances."""
        with patch("app.utils.config.settings.data_dir", tmp_path):
            # Create first instance
            manager1 = StorageManager()
            key1 = manager1._encryption_key

            # Create second instance
            manager2 = StorageManager()
            key2 = manager2._encryption_key

            assert key1 == key2

    def test_data_encryption_decryption(self, storage_instance):
        """Test encryption and decryption of sensitive data."""
        test_data = "sensitive information"

        # Encrypt data
        encrypted = storage_instance._encrypt_data(test_data)
        assert encrypted != test_data.encode()

        # Decrypt data
        decrypted = storage_instance._decrypt_data(encrypted)
        assert decrypted == test_data

    def test_store_profile_data(self, storage_instance, sample_profile_data, tmp_path):
        """Test storing profile data with encryption."""
        storage_instance.store_profile_data(sample_profile_data)

        profile_path = tmp_path / "user_profile.json"
        assert profile_path.exists()

        # Verify stored data
        with open(profile_path, "r") as f:
            stored_data = json.load(f)

        # Check encryption of sensitive fields
        assert stored_data["email"] != sample_profile_data["email"]
        assert stored_data["phone"] != sample_profile_data["phone"]

        # Verify non-sensitive fields
        assert stored_data["full_name"] == sample_profile_data["full_name"]
        assert stored_data["skills"] == sample_profile_data["skills"]

    def test_load_profile_data(self, storage_instance, sample_profile_data, tmp_path):
        """Test loading and decrypting profile data."""
        # Store data first
        storage_instance.store_profile_data(sample_profile_data)

        # Load and verify data
        loaded_data = storage_instance.load_profile_data()

        assert loaded_data["email"] == sample_profile_data["email"]
        assert loaded_data["phone"] == sample_profile_data["phone"]
        assert loaded_data["full_name"] == sample_profile_data["full_name"]

    def test_store_application_record(
        self, storage_instance, sample_application_record
    ):
        """Test storing application records."""
        record = ApplicationRecord(**sample_application_record)
        storage_instance.store_application_record(record)

        records = storage_instance.get_application_records()
        assert len(records) == 1
        assert records[0].job_url == sample_application_record["job_url"]
        assert records[0].company_name == sample_application_record["company_name"]

    def test_get_application_records_with_date_filter(
        self, storage_instance, sample_application_record
    ):
        """Test retrieving application records with date filtering."""
        # Create records with different dates
        record1 = sample_application_record.copy()
        record1["application_date"] = datetime.utcnow() - timedelta(days=5)

        record2 = sample_application_record.copy()
        record2["application_date"] = datetime.utcnow() - timedelta(days=2)

        storage_instance.store_application_record(ApplicationRecord(**record1))
        storage_instance.store_application_record(ApplicationRecord(**record2))

        # Test date filtering
        start_date = datetime.utcnow() - timedelta(days=3)
        records = storage_instance.get_application_records(start_date=start_date)

        assert len(records) == 1
        assert records[0].application_date > start_date

    def test_update_application_status(
        self, storage_instance, sample_application_record
    ):
        """Test updating application status."""
        record = ApplicationRecord(**sample_application_record)
        storage_instance.store_application_record(record)

        # Update status
        storage_instance.update_application_status(record.job_url, "accepted")

        # Verify update
        records = storage_instance.get_application_records()
        assert len(records) == 1
        assert records[0].status == "accepted"

    def test_handle_missing_profile(self, storage_instance):
        """Test handling of missing profile data."""
        with pytest.raises(StorageError):
            storage_instance.load_profile_data()

    def test_handle_invalid_status_update(
        self, storage_instance, sample_application_record
    ):
        """Test handling invalid status updates."""
        with pytest.raises(StorageError):
            storage_instance.update_application_status("nonexistent_url", "accepted")

    def test_encryption_error_handling(self, storage_instance):
        """Test handling of encryption/decryption errors."""
        # Corrupt the cipher suite
        storage_instance._cipher_suite = None

        with pytest.raises(StorageError):
            storage_instance._encrypt_data("test data")

    def test_handle_corrupted_data(
        self, storage_instance, sample_profile_data, tmp_path
    ):
        """Test handling of corrupted stored data."""
        profile_path = tmp_path / "user_profile.json"

        # Write corrupted JSON
        with open(profile_path, "w") as f:
            f.write("corrupted data{")

        with pytest.raises(StorageError):
            storage_instance.load_profile_data()


class TestApplicationRecord:
    """Tests for the ApplicationRecord model."""

    def test_valid_application_record(self, sample_application_record):
        """Test creating a valid ApplicationRecord."""
        record = ApplicationRecord(**sample_application_record)
        assert record.job_url == sample_application_record["job_url"]
        assert record.company_name == sample_application_record["company_name"]
        assert record.status == "submitted"

    def test_invalid_status(self, sample_application_record):
        """Test validation of invalid application status."""
        sample_application_record["status"] = "invalid_status"
        with pytest.raises(ValueError):
            ApplicationRecord(**sample_application_record)

    def test_default_values(self):
        """Test default values in ApplicationRecord."""
        minimal_record = {
            "job_url": "https://example.com/job",
            "verification_duration": 30.0,
            "confidence_scores": {},
            "modifications_made": False,
        }

        record = ApplicationRecord(**minimal_record)
        assert record.status == "submitted"
        assert isinstance(record.application_date, datetime)


class TestStorageManagerIntegration:
    """Integration tests for StorageManager."""

    def test_complete_storage_workflow(
        self, storage_instance, sample_profile_data, sample_application_record
    ):
        """Test complete storage workflow with profile and applications."""
        # Store profile data
        storage_instance.store_profile_data(sample_profile_data)

        # Store multiple application records
        record1 = ApplicationRecord(**sample_application_record)
        record2 = sample_application_record.copy()
        record2["job_url"] = "https://example.com/job/456"
        record2 = ApplicationRecord(**record2)

        storage_instance.store_application_record(record1)
        storage_instance.store_application_record(record2)

        # Verify stored data
        loaded_profile = storage_instance.load_profile_data()
        assert loaded_profile["email"] == sample_profile_data["email"]

        records = storage_instance.get_application_records()
        assert len(records) == 2

        # Update and verify status
        storage_instance.update_application_status(record1.job_url, "accepted")
        updated_records = storage_instance.get_application_records()
        assert any(r.status == "accepted" for r in updated_records)


if __name__ == "__main__":
    pytest.main(["-v"])
