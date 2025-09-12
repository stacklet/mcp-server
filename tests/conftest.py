"""
Common test fixtures and configuration.
"""

import pytest

from stacklet.mcp.stacklet_auth import StackletCredentials


@pytest.fixture
def mock_stacklet_credentials(monkeypatch):
    """Mock load_stacklet_auth to return fake test credentials."""
    fake_credentials = StackletCredentials(
        endpoint="https://example.com/",
        access_token="fake-access-token",
        identity_token="fake-identity-token",
    )

    monkeypatch.setattr("stacklet.mcp.mcp.load_stacklet_auth", lambda: fake_credentials)
    return fake_credentials
