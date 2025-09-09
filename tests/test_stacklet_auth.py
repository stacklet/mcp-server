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
        {"STACKLET_ENDPOINT": "https://env.example.com", "STACKLET_ACCESS_TOKEN": "env-key"},
        clear=True,
    ):
        yield


@pytest.fixture
def mock_stacklet_dir(temp_stacklet_dir):
    """Mock get_stacklet_dir to return temp directory."""
    with patch("stacklet.mcp.stacklet_auth.get_stacklet_dir", return_value=temp_stacklet_dir):
        yield temp_stacklet_dir


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


class TestStackletCredentials:
    """Test the StackletCredentials NamedTuple."""

    def test_credentials_creation(self):
        """Test basic credential object creation."""
        creds = StackletCredentials("https://api.example.com", "test-key")
        assert creds.endpoint == "https://api.example.com"
        assert creds.access_token == "test-key"


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
        with patch("pathlib.Path.home", side_effect=RuntimeError("No home")):
            with pytest.raises(RuntimeError, match="No home"):
                get_stacklet_dir()


class TestLoadStackletAuth:
    """Test the load_stacklet_auth function."""

    def test_direct_parameters_priority(self, mock_env_vars):
        """Test that direct parameters take highest priority."""
        creds = load_stacklet_auth(endpoint="https://direct.example.com", access_token="direct-key")

        assert creds is not None
        assert creds.endpoint == "https://direct.example.com"
        assert creds.access_token == "direct-key"

    def test_environment_variables_priority(self, mock_env_vars):
        """Test that environment variables are used when direct params not provided."""
        creds = load_stacklet_auth()

        assert creds is not None
        assert creds.endpoint == "https://env.example.com"
        assert creds.access_token == "env-key"

    def test_config_file_loading(
        self, valid_config_file, valid_credentials_file, clean_env, mock_stacklet_dir
    ):
        """Test loading both endpoint and access token from config files."""
        creds = load_stacklet_auth()

        assert creds is not None
        assert creds.endpoint == "https://config.example.com"
        assert creds.access_token == "config-file-key"

    def test_missing_credentials_raises_error(self, clean_env, mock_stacklet_dir):
        """Test that missing credentials raises ValueError."""
        with pytest.raises(
            ValueError, match="Missing Stacklet credentials: endpoint, access_token"
        ):
            load_stacklet_auth()

    def test_home_dir_error_bubbles_up(self, clean_env):
        """Test that get_stacklet_dir errors bubble up."""
        with patch(
            "stacklet.mcp.stacklet_auth.get_stacklet_dir", side_effect=RuntimeError("no home dir")
        ):
            with pytest.raises(RuntimeError, match="no home dir"):
                load_stacklet_auth()


class TestExceptionBubbling:
    """Test that various exceptions bubble through load_stacklet_auth."""

    def test_json_decode_error_bubbles_up(self, clean_env, mock_stacklet_dir):
        """Test that JSON decode errors bubble up."""
        # Create invalid JSON config file
        config_file = mock_stacklet_dir / "config.json"
        config_file.write_text('{"api": "https://example.com"')  # Missing closing brace

        with pytest.raises(json.JSONDecodeError):
            load_stacklet_auth()

    def test_io_error_bubbles_up(self, clean_env, mock_stacklet_dir):
        """Test that IO errors bubble up."""
        # Create valid config file
        config_file = mock_stacklet_dir / "config.json"
        config_file.write_text('{"api": "https://example.com"}')

        # Mock open to raise IOError
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with pytest.raises(IOError, match="Permission denied"):
                load_stacklet_auth()
