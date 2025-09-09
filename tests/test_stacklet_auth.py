#!/usr/bin/env python3

import json
import os

from pathlib import Path
from unittest.mock import patch

import pytest

from stacklet.mcp.stacklet_auth import StackletCredentials, get_stacklet_dir, load_stacklet_auth


@pytest.fixture
def temp_stacklet_dir(tmp_path):
    """Create a temporary .stacklet directory for testing."""
    stacklet_dir = tmp_path / ".stacklet"
    stacklet_dir.mkdir()
    return stacklet_dir


# Environment setup fixtures
@pytest.fixture
def clean_env():
    """Clean environment with no Stacklet vars."""
    with patch.dict(os.environ, {}, clear=True):
        yield


@pytest.fixture
def mock_env_vars():
    """Environment with test Stacklet credentials."""
    with patch.dict(
        os.environ,
        {"STACKLET_ENDPOINT": "https://env.example.com", "STACKLET_API_KEY": "env-key"},
        clear=True,
    ):
        yield


@pytest.fixture
def partial_env_vars():
    """Environment with only API key set."""
    with patch.dict(os.environ, {"STACKLET_API_KEY": "env-key"}, clear=True):
        yield


@pytest.fixture
def endpoint_only_env():
    """Environment with only endpoint set."""
    with patch.dict(os.environ, {"STACKLET_ENDPOINT": "https://example.com"}, clear=True):
        yield


@pytest.fixture
def empty_env_vars():
    """Environment with empty Stacklet variables."""
    with patch.dict(os.environ, {"STACKLET_ENDPOINT": "", "STACKLET_API_KEY": ""}, clear=True):
        yield


# Mock patching fixtures
@pytest.fixture
def mock_no_stacklet_dir():
    """Mock get_stacklet_dir to return None."""
    with patch("stacklet.mcp.stacklet_auth.get_stacklet_dir", return_value=None):
        yield


@pytest.fixture
def mock_stacklet_dir(temp_stacklet_dir):
    """Mock get_stacklet_dir to return temp directory."""
    with patch("stacklet.mcp.stacklet_auth.get_stacklet_dir", return_value=temp_stacklet_dir):
        yield temp_stacklet_dir


# File creation fixtures
@pytest.fixture
def valid_config_file(temp_stacklet_dir):
    """Create valid config.json file."""
    config_file = temp_stacklet_dir / "config.json"
    config_data = {"api": "https://config.example.com"}
    config_file.write_text(json.dumps(config_data))
    return config_file


@pytest.fixture
def valid_credentials_file(temp_stacklet_dir):
    """Create valid credentials file."""
    creds_file = temp_stacklet_dir / "credentials"
    creds_file.write_text("config-file-key")
    return creds_file


@pytest.fixture
def complete_config_files(valid_config_file, valid_credentials_file):
    """Both config and credentials files exist."""
    return {"config": valid_config_file, "credentials": valid_credentials_file}


@pytest.fixture
def invalid_json_config_file(temp_stacklet_dir):
    """Create config.json file with invalid JSON."""
    config_file = temp_stacklet_dir / "config.json"
    config_file.write_text('{"api": "https://example.com"')  # Missing closing brace
    return config_file


@pytest.fixture
def config_file_no_api_field(temp_stacklet_dir):
    """Create config.json file without 'api' field."""
    config_file = temp_stacklet_dir / "config.json"
    config_data = {"other_field": "value"}
    config_file.write_text(json.dumps(config_data))
    return config_file


@pytest.fixture
def whitespace_credentials_file(temp_stacklet_dir):
    """Create credentials file with only whitespace."""
    creds_file = temp_stacklet_dir / "credentials"
    creds_file.write_text("   \n\t  \n  ")
    return creds_file


@pytest.fixture
def credentials_with_whitespace(temp_stacklet_dir):
    """Create credentials file with whitespace around key."""
    creds_file = temp_stacklet_dir / "credentials"
    creds_file.write_text("  file-api-key  \n")
    return creds_file


class TestStackletCredentials:
    """Test the StackletCredentials NamedTuple."""

    def test_credentials_creation(self):
        """Test basic credential object creation."""
        creds = StackletCredentials("https://api.example.com", "test-key")
        assert creds.endpoint == "https://api.example.com"
        assert creds.api_key == "test-key"


class TestGetStackletDir:
    """Test the get_stacklet_dir function."""

    def test_get_stacklet_dir_success(self):
        """Test successful retrieval of stacklet directory."""
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path("/mock/home")
            result = get_stacklet_dir()
            assert result == Path("/mock/home/.stacklet")

    def test_get_stacklet_dir_home_error(self):
        """Test handling when home directory cannot be determined."""
        with patch("pathlib.Path.home", side_effect=OSError("No home")):
            result = get_stacklet_dir()
            assert result is None


class TestLoadStackletAuth:
    """Test the load_stacklet_auth function."""

    def test_direct_parameters_priority(self, mock_env_vars):
        """Test that direct parameters take highest priority."""
        creds = load_stacklet_auth(endpoint="https://direct.example.com", api_key="direct-key")

        assert creds is not None
        assert creds.endpoint == "https://direct.example.com"
        assert creds.api_key == "direct-key"

    def test_environment_variables_priority(self, mock_env_vars):
        """Test that environment variables are used when direct params not provided."""
        creds = load_stacklet_auth()

        assert creds is not None
        assert creds.endpoint == "https://env.example.com"
        assert creds.api_key == "env-key"

    def test_partial_direct_parameters(self, mock_env_vars):
        """Test mixing direct parameters with environment variables."""
        # Only provide endpoint directly
        creds = load_stacklet_auth(endpoint="https://direct.example.com")

        assert creds is not None
        assert creds.endpoint == "https://direct.example.com"
        assert creds.api_key == "env-key"

    def test_config_file_loading(self, valid_config_file, partial_env_vars, mock_stacklet_dir):
        """Test loading configuration from ~/.stacklet/config.json."""
        creds = load_stacklet_auth()

        assert creds is not None
        assert creds.endpoint == "https://config.example.com"
        assert creds.api_key == "env-key"

    def test_credentials_file_loading(
        self, credentials_with_whitespace, endpoint_only_env, mock_stacklet_dir
    ):
        """Test loading API key from ~/.stacklet/credentials."""
        creds = load_stacklet_auth()

        assert creds is not None
        assert creds.endpoint == "https://example.com"
        assert creds.api_key == "file-api-key"  # Should be stripped

    def test_full_config_file_loading(self, complete_config_files, clean_env, mock_stacklet_dir):
        """Test loading both endpoint and API key from config files."""
        creds = load_stacklet_auth()

        assert creds is not None
        assert creds.endpoint == "https://config.example.com"
        assert creds.api_key == "config-file-key"

    def test_missing_endpoint_returns_none(self, partial_env_vars, mock_no_stacklet_dir):
        """Test that missing endpoint returns None."""
        creds = load_stacklet_auth()
        assert creds is None

    def test_missing_api_key_returns_none(self, endpoint_only_env, mock_no_stacklet_dir):
        """Test that missing API key returns None."""
        creds = load_stacklet_auth()
        assert creds is None

    def test_missing_both_returns_none(self, clean_env, mock_no_stacklet_dir):
        """Test that missing both endpoint and API key returns None."""
        creds = load_stacklet_auth()
        assert creds is None

    def test_no_stacklet_dir_returns_none(self, clean_env, mock_no_stacklet_dir):
        """Test that when get_stacklet_dir returns None, no config files are read."""
        creds = load_stacklet_auth()
        assert creds is None


class TestConfigFileErrorHandling:
    """Test error handling when reading configuration files."""

    def test_invalid_json_in_config_file(
        self, invalid_json_config_file, partial_env_vars, mock_stacklet_dir
    ):
        """Test handling of invalid JSON in config file."""
        creds = load_stacklet_auth()
        # Should gracefully handle JSON error and not find endpoint
        assert creds is None

    def test_missing_api_field_in_config(
        self, config_file_no_api_field, partial_env_vars, mock_stacklet_dir
    ):
        """Test handling of missing 'api' field in config file."""
        creds = load_stacklet_auth()
        # Should not find endpoint, return None
        assert creds is None

    def test_config_file_permission_error(
        self, valid_config_file, partial_env_vars, mock_stacklet_dir
    ):
        """Test handling of permission errors when reading config file."""
        # Make file unreadable by mocking open to raise IOError
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            creds = load_stacklet_auth()
            # Should handle error gracefully
            assert creds is None

    def test_credentials_file_permission_error(
        self, valid_credentials_file, endpoint_only_env, mock_stacklet_dir
    ):
        """Test handling of permission errors when reading credentials file."""
        # Mock read_text to raise IOError
        with patch("pathlib.Path.read_text", side_effect=IOError("Permission denied")):
            creds = load_stacklet_auth()
            # Should handle error gracefully
            assert creds is None


class TestEdgeCases:
    """Test edge cases and unusual scenarios."""

    def test_empty_strings_treated_as_missing(self, clean_env, mock_no_stacklet_dir):
        """Test that empty strings are treated as missing values."""
        creds = load_stacklet_auth(endpoint="", api_key="")
        assert creds is None

    def test_empty_env_vars_treated_as_missing(self, empty_env_vars, mock_no_stacklet_dir):
        """Test that empty environment variables are treated as missing."""
        creds = load_stacklet_auth()
        assert creds is None

    def test_whitespace_only_credentials_file(
        self, whitespace_credentials_file, endpoint_only_env, mock_stacklet_dir
    ):
        """Test handling of whitespace-only credentials file."""
        creds = load_stacklet_auth()
        # After strip(), becomes empty string, which is falsy
        assert creds is None

    def test_missing_config_files(self, clean_env, mock_stacklet_dir):
        """Test when config files don't exist."""
        # temp_stacklet_dir exists but no files are created by fixtures
        creds = load_stacklet_auth()
        # No files exist, no env vars, should return None
        assert creds is None

    def test_config_file_exists_but_credentials_missing(
        self, valid_config_file, clean_env, mock_stacklet_dir
    ):
        """Test when config file exists but credentials file doesn't."""
        creds = load_stacklet_auth()
        # Has endpoint but no API key
        assert creds is None
