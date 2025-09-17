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
def clean_env(monkeypatch):
    """Clean environment with no Stacklet vars."""
    for name in ("STACKLET_ENDPOINT", "STACKLET_ACCESS_TOKEN", "STACKLET_IDENTITY_TOKEN"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def mock_env_vars():
    """Environment with test Stacklet credentials."""
    with patch.dict(
        os.environ,
        {
            "STACKLET_ENDPOINT": "https://api.example.com",
            "STACKLET_ACCESS_TOKEN": "env-key",
            "STACKLET_IDENTITY_TOKEN": "env-id-token",
        },
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
    config_data = {"api": "https://api.config-example.com"}
    config_file.write_text(json.dumps(config_data))
    return config_file


@pytest.fixture
def valid_credentials_file(temp_stacklet_dir):
    """Create valid credentials file."""
    creds_file = temp_stacklet_dir / "credentials"
    creds_file.write_text("config-file-key")
    return creds_file


@pytest.fixture
def valid_id_file(temp_stacklet_dir):
    """Create valid id file."""
    id_file = temp_stacklet_dir / "id"
    id_file.write_text("config-file-id-token")
    return id_file


class TestStackletCredentials:
    """Test the StackletCredentials NamedTuple."""

    def test_credentials_creation(self):
        """Test basic credential object creation."""
        creds = StackletCredentials("https://api.example.com", "test-key", "test-id-token")
        assert creds.endpoint == "https://api.example.com"
        assert creds.access_token == "test-key"
        assert creds.identity_token == "test-id-token"


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

    def test_environment_variables_priority(self, mock_env_vars):
        """Test that environment variables are used."""
        creds = load_stacklet_auth()

        assert creds is not None
        assert creds.endpoint == "https://api.example.com"
        assert creds.access_token == "env-key"
        assert creds.identity_token == "env-id-token"

    def test_config_file_loading(
        self, valid_config_file, valid_credentials_file, valid_id_file, clean_env, mock_stacklet_dir
    ):
        """Test loading endpoint, access token, and identity token from config files."""
        creds = load_stacklet_auth()

        assert creds is not None
        assert creds.endpoint == "https://api.config-example.com"
        assert creds.access_token == "config-file-key"
        assert creds.identity_token == "config-file-id-token"

    def test_missing_credentials_raises_error(self, clean_env, mock_stacklet_dir):
        """Test that missing credentials raises ValueError."""
        with pytest.raises(
            ValueError, match="Missing Stacklet credentials: endpoint, access_token, identity_token"
        ):
            load_stacklet_auth()

    def test_partial_credentials_raises_error(self, clean_env, mock_stacklet_dir):
        """Test that partial credentials raise ValueError."""
        # Only provide endpoint
        with patch.dict(os.environ, {"STACKLET_ENDPOINT": "https://test.example.com"}, clear=True):
            with pytest.raises(
                ValueError, match="Missing Stacklet credentials: access_token, identity_token"
            ):
                load_stacklet_auth()

    def test_home_dir_error_bubbles_up(self, clean_env):
        """Test that get_stacklet_dir errors bubble up."""
        with patch(
            "stacklet.mcp.stacklet_auth.get_stacklet_dir", side_effect=RuntimeError("no home dir")
        ):
            with pytest.raises(RuntimeError, match="no home dir"):
                load_stacklet_auth()

    def test_service_endpoint(self, mock_env_vars):
        """A service endpoint is returned correctly."""
        creds = load_stacklet_auth()
        assert creds.service_endpoint("redash") == "https://redash.example.com/"


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
        config_file.write_text('{"api": "https://api.example.com"}')

        # Mock open to raise IOError
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with pytest.raises(IOError, match="Permission denied"):
                load_stacklet_auth()
