# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

import json

from pathlib import Path
from typing import Any

import pytest

from stacklet.mcp.settings import SETTINGS, Settings
from stacklet.mcp.utils.file import download_file


class TestSettings:
    """Test cases for Settings configuration."""

    def test_default_settings(self) -> None:
        """Test that default settings are properly initialized."""
        assert SETTINGS.downloads_path.name.startswith("downloads")
        assert "pytest-of-" in str(SETTINGS.downloads_path)
        assert SETTINGS.assetdb_datasource == 1
        assert SETTINGS.assetdb_allow_save is False
        assert SETTINGS.assetdb_allow_archive is False
        assert SETTINGS.platform_allow_mutations is False

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


class TestDownloadFile:
    def test_download_file_mode_and_naming(self, default_settings) -> None:
        """Test that download_file respects mode, prefix, and suffix parameters."""
        with download_file("w", "assetdb_test", ".json") as f:
            # File should be created in downloads path
            assert Path(f.name).parent == SETTINGS.downloads_path

            # File should have correct prefix and suffix
            filename = Path(f.name).name
            assert filename.startswith("assetdb_test")
            assert filename.endswith(".json")

            # Should be writable
            f.write('{"test": "data"}')

    def test_download_file_different_modes(self) -> None:
        """Test that download_file works with different file modes."""

        # Test write mode with text
        with download_file("w", "text_test", ".txt") as f:
            f.write("Hello, World!")
            text_path = Path(f.name)

        # Test write mode with binary
        with download_file("wb", "binary_test", ".bin") as f:
            f.write(b"Binary data")
            binary_path = Path(f.name)

        # Both files should exist and be in the correct directory
        assert text_path.exists()
        assert binary_path.exists()
        assert text_path.parent == SETTINGS.downloads_path
        assert binary_path.parent == SETTINGS.downloads_path

    def test_download_file_persistent(self) -> None:
        """Test that download_file creates persistent files (delete=False)."""

        # Create file and write data
        file_path = None
        with download_file("w", "persistent_test", ".json") as f:
            file_path = Path(f.name)
            json.dump({"test": "persistence"}, f)

        # File should still exist after context manager exits
        assert file_path is not None
        assert file_path.exists()

        # Should be able to read the data back
        with open(file_path, "r") as f:
            data = json.load(f)
            assert data == {"test": "persistence"}

    def test_download_file_parents_created(self, override_setting: Any) -> None:
        """Test that download_file creates parent directories when needed."""
        # Create a nested path in the temp directory
        nested_path = SETTINGS.downloads_path / "level1" / "level2" / "downloads"
        override_setting("downloads_path", nested_path)

        # None of the parent directories exist
        assert not nested_path.exists()
        assert not nested_path.parent.exists()
        assert not nested_path.parent.parent.exists()

        # download_file should create all parent directories
        with download_file("w", "nested_test", ".txt") as f:
            assert nested_path.exists()
            assert nested_path.is_dir()
            assert Path(f.name).parent == nested_path

    def test_download_file_existing_directory(self) -> None:
        """Test that download_file works when directory already exists."""
        downloads_dir = SETTINGS.downloads_path
        downloads_dir.mkdir(exist_ok=True)

        # Should work fine with existing directory
        with download_file("w", "existing_test", ".json") as f:
            assert Path(f.name).parent == downloads_dir
