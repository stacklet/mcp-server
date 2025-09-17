"""
Common test fixtures and configuration.
"""

import pytest

from fastmcp import Client

from stacklet.mcp.mcp import make_server
from stacklet.mcp.stacklet_auth import StackletCredentials

from .testing.http import mock_http_request
from .testing.settings import default_settings, override_setting


# add imported fixtures to __all__ so they're considered in use in the module
__all__ = ["mock_http_request", "default_settings", "override_setting"]


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
    override_setting("assetdb_save", True)

    async with Client(make_server()) as client:
        yield client
