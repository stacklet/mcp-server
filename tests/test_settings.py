import json

from pathlib import Path
from typing import Any

import pytest

from stacklet.mcp.settings import SETTINGS, Settings


class TestSettings:
    """Test cases for Settings configuration."""

    def test_default_settings(self, default_settings: Settings) -> None:
        """Test that default settings are properly initialized."""
        assert default_settings.downloads_path.name == "downloads"
        assert "pytest-of-" in str(default_settings.downloads_path)
        assert default_settings.assetdb_datasource == 1
        assert default_settings.assetdb_allow_save is False
        assert default_settings.assetdb_allow_archive is False
        assert default_settings.platform_allow_mutations is False

    def test_env_prefix_configuration(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables with STACKLET_MCP_ prefix are loaded."""
        monkeypatch.setenv("STACKLET_MCP_DOWNLOADS_PATH", "/custom/path")
        monkeypatch.setenv("STACKLET_MCP_ASSETDB_DATASOURCE", "2")
        monkeypatch.setenv("STACKLET_MCP_ASSETDB_ALLOW_SAVE", "true")
        monkeypatch.setenv("STACKLET_MCP_ASSETDB_ALLOW_ARCHIVE", "true")
        monkeypatch.setenv("STACKLET_MCP_PLATFORM_ALLOW_MUTATIONS", "true")

        settings = Settings()

        assert settings.downloads_path == Path("/custom/path")
        assert settings.assetdb_datasource == 2
        assert settings.assetdb_allow_save is True
        assert settings.assetdb_allow_archive is True
        assert settings.platform_allow_mutations is True


class TestDownloadsPath:
    """Test cases for downloads_path configuration and download_file functionality."""

    def test_downloads_path_default(self, default_settings: Settings) -> None:
        """Test that downloads_path defaults to pytest temp directory in tests."""
        assert default_settings.downloads_path.name == "downloads"
        assert "pytest-of-" in str(default_settings.downloads_path)

    def test_downloads_path_custom(self, tmp_path: Path) -> None:
        """Test that downloads_path can be set to custom directory."""
        settings = Settings(downloads_path=tmp_path)
        assert settings.downloads_path == tmp_path

    def test_downloads_path_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that downloads_path can be set via environment variable."""
        monkeypatch.setenv("STACKLET_MCP_DOWNLOADS_PATH", str(tmp_path))
        settings = Settings()
        assert settings.downloads_path == tmp_path

    def test_download_file_creates_directory(self, tmp_path: Path) -> None:
        """Test that download_file creates the downloads directory if it doesn't exist."""
        downloads_dir = tmp_path / "downloads"
        settings = Settings(downloads_path=downloads_dir)

        # Directory doesn't exist yet
        assert not downloads_dir.exists()

        # download_file should create it
        with settings.download_file("w", "test", ".json") as f:
            assert downloads_dir.exists()
            assert downloads_dir.is_dir()
            # File should be in the downloads directory
            assert Path(f.name).parent == downloads_dir

    def test_download_file_mode_and_naming(self, tmp_path: Path) -> None:
        """Test that download_file respects mode, prefix, and suffix parameters."""
        settings = Settings(downloads_path=tmp_path)

        with settings.download_file("w", "assetdb_test", ".json") as f:
            # File should be created in downloads path
            assert Path(f.name).parent == tmp_path

            # File should have correct prefix and suffix
            filename = Path(f.name).name
            assert filename.startswith("assetdb_test")
            assert filename.endswith(".json")

            # Should be writable
            f.write('{"test": "data"}')

    def test_download_file_different_modes(self, tmp_path: Path) -> None:
        """Test that download_file works with different file modes."""
        settings = Settings(downloads_path=tmp_path)

        # Test write mode with text
        with settings.download_file("w", "text_test", ".txt") as f:
            f.write("Hello, World!")
            text_path = Path(f.name)

        # Test write mode with binary
        with settings.download_file("wb", "binary_test", ".bin") as f:
            f.write(b"Binary data")
            binary_path = Path(f.name)

        # Both files should exist and be in the correct directory
        assert text_path.exists()
        assert binary_path.exists()
        assert text_path.parent == tmp_path
        assert binary_path.parent == tmp_path

    def test_download_file_persistent(self, tmp_path: Path) -> None:
        """Test that download_file creates persistent files (delete=False)."""
        settings = Settings(downloads_path=tmp_path)

        # Create file and write data
        file_path = None
        with settings.download_file("w", "persistent_test", ".json") as f:
            file_path = Path(f.name)
            json.dump({"test": "persistence"}, f)

        # File should still exist after context manager exits
        assert file_path is not None
        assert file_path.exists()

        # Should be able to read the data back
        with open(file_path, "r") as f:
            data = json.load(f)
            assert data == {"test": "persistence"}

    def test_download_file_with_global_settings(
        self, tmp_path: Path, override_setting: Any
    ) -> None:
        """Test that download_file works with the global SETTINGS object."""
        # Override the global settings downloads_path
        override_setting("downloads_path", tmp_path)

        with SETTINGS.download_file("w", "global_test", ".json") as f:
            file_path = Path(f.name)
            json.dump({"global": "test"}, f)

        # File should be in the configured directory
        assert file_path.parent == tmp_path
        assert file_path.exists()

    def test_download_file_parents_created(self, tmp_path: Path) -> None:
        """Test that download_file creates parent directories when needed."""
        nested_path = tmp_path / "level1" / "level2" / "downloads"
        settings = Settings(downloads_path=nested_path)

        # None of the parent directories exist
        assert not nested_path.exists()
        assert not nested_path.parent.exists()
        assert not nested_path.parent.parent.exists()

        # download_file should create all parent directories
        with settings.download_file("w", "nested_test", ".txt") as f:
            assert nested_path.exists()
            assert nested_path.is_dir()
            assert Path(f.name).parent == nested_path

    def test_download_file_existing_directory(self, tmp_path: Path) -> None:
        """Test that download_file works when directory already exists."""
        downloads_dir = tmp_path / "existing"
        downloads_dir.mkdir()
        settings = Settings(downloads_path=downloads_dir)

        # Should work fine with existing directory
        with settings.download_file("w", "existing_test", ".json") as f:
            assert Path(f.name).parent == downloads_dir
