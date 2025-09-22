# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025 Stacklet, Inc.
#

"""
Common test fixtures and configuration.
"""

from unittest.mock import MagicMock

import pytest

from fastmcp import Client

from stacklet.mcp.server import make_server
from stacklet.mcp.stacklet_auth import StackletCredentials

from .testing.http import mock_http_bearer, mock_http_cookie
from .testing.settings import default_settings, override_setting


# add imported fixtures to __all__ so they're considered in use in the module
__all__ = ["mock_http_cookie", "mock_http_bearer", "default_settings", "override_setting"]


@pytest.fixture
def mock_stacklet_credentials(monkeypatch):
    """Mock load_stacklet_auth to return fake test credentials."""
    fake_credentials = StackletCredentials(
        endpoint="https://api.example.com/",
        access_token="fake-access-token",
        identity_token="fake-identity-token",
    )

    monkeypatch.setattr("stacklet.mcp.stacklet_auth.load_stacklet_auth", lambda: fake_credentials)
    return fake_credentials


@pytest.fixture
async def mcp_client(override_setting, mock_stacklet_credentials):
    """A client for the MCP server."""

    # enable all tools
    override_setting("assetdb_allow_save", True)
    override_setting("assetdb_allow_archive", True)
    override_setting("platform_allow_mutations", True)

    async with Client(make_server()) as client:
        yield client


@pytest.fixture
def async_sleeps(monkeypatch):
    sleeps = []
    mock_time = MagicMock(return_value=12345)

    async def mock_sleep(duration):
        sleeps.append(duration)
        mock_time.return_value += duration

    monkeypatch.setattr("asyncio.sleep", mock_sleep)
    monkeypatch.setattr("time.monotonic", mock_time)
    return sleeps
