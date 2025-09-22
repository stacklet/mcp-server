from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

from stacklet.mcp.settings import SETTINGS, Settings


@pytest.fixture(autouse=True)
def default_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Settings]:
    """Ensure default values are set for Settings."""

    defaults = {name: field.default for name, field in Settings.model_fields.items()}
    # Use pytest temp directory for downloads
    defaults["downloads_path"] = tmp_path / "downloads"
    settings = Settings(**defaults)
    monkeypatch.setattr("stacklet.mcp.settings.SETTINGS", settings)
    yield settings


@pytest.fixture
def override_setting(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str, Any], Settings]]:
    """Function to override value for a setting."""

    def override(attr: str, value: Any) -> Settings:
        monkeypatch.setattr(SETTINGS, attr, value)

    yield override
