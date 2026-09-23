# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

from typing import Any, Callable, Iterator

import pytest

from stacklet.mcp.settings import SETTINGS, Settings


@pytest.fixture(autouse=True)
def default_settings(monkeypatch: pytest.MonkeyPatch, tmp_path_factory) -> Iterator[Settings]:
    """Ensure default values are set for Settings."""

    defaults = {name: field.default for name, field in Settings.model_fields.items()}
    # Use pytest temp directory for downloads
    defaults["downloads_path"] = tmp_path_factory.mktemp("downloads")
    # Name a data source id, so a test that exercises a query is not also
    # exercising the lookup that resolves one. The lookup has its own tests,
    # which opt back in by setting this to None.
    defaults["assetdb_datasource"] = 1
    for attr, value in defaults.items():
        monkeypatch.setattr(SETTINGS, attr, value)

    yield SETTINGS


@pytest.fixture
def override_setting(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str, Any], None]]:
    """Function to override value for a setting."""

    def override(attr: str, value: Any) -> None:
        monkeypatch.setattr(SETTINGS, attr, value)

    yield override
