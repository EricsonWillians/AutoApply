"""
Unit tests for the configuration module.

This module contains comprehensive tests for the application configuration
system, ensuring proper handling of settings, environment variables, and
path management.

File location: tests/unit/test_config.py
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.utils.config import Settings, settings
from app.utils.exceptions import ConfigurationError


@pytest.fixture
def env_vars():
    """Provide sample environment variables for testing."""
    return {
        "HUGGINGFACE_API_TOKEN": "test_token_123",
        "MODEL_NAME": "test-model",
        "LOG_LEVEL": "DEBUG",
    }


@pytest.fixture
def test_settings(env_vars, tmp_path):
    """Provide a configured Settings instance for testing."""
    with patch.dict(os.environ, env_vars):
        with patch("app.utils.config.Settings.base_dir", tmp_path):
            return Settings()


class TestSettings:
    """Tests for the Settings class."""

    def test_required_environment_variables(self, env_vars):
        """Test handling of required environment variables."""
        with patch.dict(os.environ, env_vars):
            config = Settings()
            assert config.get_huggingface_token() == "test_token_123"

    def test_missing_required_variables(self):
        """Test validation of missing required variables."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            assert "huggingface_api_token" in str(exc_info.value).lower()

    def test_default_values(self, test_settings):
        """Test default configuration values."""
        assert test_settings.model_name == "bert-base-uncased"
        assert test_settings.max_sequence_length == 512
        assert test_settings.browser_type == "chromium"
        assert test_settings.headless is True
        assert isinstance(test_settings.browser_args, list)
        assert test_settings.verification_timeout == 300
        assert test_settings.max_retries == 3
        assert test_settings.log_level == "INFO"

    def test_custom_configuration(self, env_vars):
        """Test customization of configuration values."""
        custom_env = env_vars.copy()
        custom_env.update(
            {
                "MODEL_NAME": "custom-model",
                "MAX_SEQUENCE_LENGTH": "1024",
                "BROWSER_TYPE": "firefox",
                "HEADLESS": "false",
                "VERIFICATION_TIMEOUT": "600",
                "MAX_RETRIES": "5",
                "LOG_LEVEL": "DEBUG",
            }
        )

        with patch.dict(os.environ, custom_env):
            config = Settings()
            assert config.model_name == "custom-model"
            assert config.max_sequence_length == 1024
            assert config.browser_type == "firefox"
            assert config.headless is False
            assert config.verification_timeout == 600
            assert config.max_retries == 5
            assert config.log_level == "DEBUG"

    def test_directory_path_management(self, test_settings, tmp_path):
        """Test management of application directory paths."""
        # Test directory paths
        paths = test_settings.get_directory_paths()
        assert isinstance(paths["base_dir"], Path)
        assert isinstance(paths["data_dir"], Path)
        assert isinstance(paths["resumes_dir"], Path)

        # Test directory creation
        test_settings.ensure_directories()
        assert paths["data_dir"].exists()
        assert paths["resumes_dir"].exists()

    def test_path_validation(self, test_settings):
        """Test validation of application paths."""
        assert test_settings.validate_paths() is True

        # Test with non-existent path
        with patch.object(test_settings, "data_dir", Path("/nonexistent/path")):
            assert test_settings.validate_paths() is False

    def test_secure_token_handling(self, test_settings):
        """Test secure handling of API tokens."""
        token = test_settings.get_huggingface_token()
        assert isinstance(token, str)
        assert token == "test_token_123"

        # Verify token is not exposed in string representation
        assert "test_token_123" not in str(test_settings)
        assert "test_token_123" not in repr(test_settings)

    def test_browser_configuration(self, test_settings):
        """Test browser configuration settings."""
        assert isinstance(test_settings.browser_args, list)
        assert "--disable-dev-shm-usage" in test_settings.browser_args
        assert test_settings.browser_type in ["chromium", "firefox", "webkit"]

    def test_invalid_configuration_values(self):
        """Test validation of invalid configuration values."""
        invalid_env = {
            "HUGGINGFACE_API_TOKEN": "test_token",
            "MAX_SEQUENCE_LENGTH": "invalid",
            "VERIFICATION_TIMEOUT": "-30",
            "MAX_RETRIES": "0",
        }

        with patch.dict(os.environ, invalid_env):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            assert "validation error" in str(exc_info.value).lower()

    def test_sensitive_data_protection(self, test_settings):
        """Test protection of sensitive configuration data."""
        # Verify token is properly hidden
        config_dict = test_settings.dict()
        assert isinstance(config_dict["huggingface_api_token"], str)
        assert "test_token_123" not in str(config_dict)

        # Test JSON serialization
        config_json = test_settings.json()
        assert "test_token_123" not in config_json

    def test_environment_file_loading(self, tmp_path):
        """Test loading configuration from environment file."""
        env_file = tmp_path / ".env"
        env_content = """
        HUGGINGFACE_API_TOKEN=test_token_from_file
        MODEL_NAME=model-from-file
        LOG_LEVEL=DEBUG
        """

        env_file.write_text(env_content)

        with patch.dict(os.environ, {}, clear=True):
            with patch("app.utils.config.Settings.Config.env_file", env_file):
                config = Settings()
                assert config.get_huggingface_token() == "test_token_from_file"
                assert config.model_name == "model-from-file"
                assert config.log_level == "DEBUG"


class TestSettingsIntegration:
    """Integration tests for Settings functionality."""

    def test_complete_configuration_workflow(self, tmp_path):
        """Test complete configuration workflow."""
        # Create environment file
        env_file = tmp_path / ".env"
        env_content = """
        HUGGINGFACE_API_TOKEN=test_integration_token
        MODEL_NAME=test-integration-model
        LOG_LEVEL=INFO
        BROWSER_TYPE=chromium
        HEADLESS=true
        """

        env_file.write_text(env_content)

        # Initialize settings
        with patch("app.utils.config.Settings.Config.env_file", env_file):
            with patch("app.utils.config.Settings.base_dir", tmp_path):
                config = Settings()

                # Verify configuration loading
                assert config.get_huggingface_token() == "test_integration_token"
                assert config.model_name == "test-integration-model"

                # Test directory creation
                config.ensure_directories()
                paths = config.get_directory_paths()
                assert all(path.exists() for path in paths.values())

                # Verify path validation
                assert config.validate_paths() is True

                # Test secure token handling
                token = config.get_huggingface_token()
                assert isinstance(token, str)
                assert "test_integration_token" not in str(config)

                # Verify browser configuration
                assert config.browser_type == "chromium"
                assert config.headless is True


if __name__ == "__main__":
    pytest.main(["-v"])
