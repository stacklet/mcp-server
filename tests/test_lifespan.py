# LICENSE HEADER MANAGED BY add-license-header
#
# Copyright (c) 2025-2026 Stacklet, Inc.
#

"""
Tests for server lifespan, state management, and auth provider delegation.
"""

import json

from unittest.mock import AsyncMock, MagicMock

import pytest

from fastmcp import Client

from stacklet.mcp.lifespan import ServerState
from stacklet.mcp.server import make_server
from stacklet.mcp.stacklet_auth import StackletCredentials

from .testing.http import MockHTTPXResponse


class TestServerStateAclose:
    async def test_aclose_calls_aclose_on_cached_values(self):
        """ServerState.aclose() closes any cached objects that have aclose()."""
        state = ServerState(auth_provider=MagicMock())

        mock_transport = AsyncMock()
        state["HTTP_TRANSPORT"] = mock_transport
        state["PLAIN_VALUE"] = "no aclose here"

        await state.aclose()

        mock_transport.aclose.assert_awaited_once()

    async def test_aclose_ignores_values_without_aclose(self):
        """ServerState.aclose() is safe when cached values have no aclose()."""
        state = ServerState(auth_provider=MagicMock())
        state["STRING"] = "hello"
        state["NUMBER"] = 42

        await state.aclose()  # must not raise


class TestAuthProviderDelegation:
    async def test_credentials_routed_through_auth_provider(self, monkeypatch):
        """StackletCredentials.get() delegates to the server state's auth_provider."""
        fake_creds = StackletCredentials(
            endpoint="https://api.example.com/",
            access_token="stub-token",
            identity_token="stub-id-token",
        )

        calls: list[object] = []

        class StubAuthProvider:
            def get_credentials(self, ctx):
                calls.append(ctx)
                return fake_creds

        docs = [{"path": "foo.md", "title": "Foo"}]

        async def mock_request(self, method, url, **kwargs):
            return MockHTTPXResponse(json.dumps(docs))

        monkeypatch.setattr("httpx.AsyncClient.request", mock_request)

        server = make_server(auth_provider=StubAuthProvider())
        async with Client(server) as client:
            await client.call_tool_mcp("docs_list", {})

        assert len(calls) >= 1, "auth_provider.get_credentials was never called"

    async def test_stub_provider_credentials_reach_http_client(self, monkeypatch):
        """Credentials supplied by a custom auth provider are actually used in HTTP requests."""
        fake_creds = StackletCredentials(
            endpoint="https://api.example.com/",
            access_token="custom-token",
            identity_token="custom-id-token",
        )

        class StubAuthProvider:
            def get_credentials(self, ctx):
                return fake_creds

        seen_cookies: list[str] = []
        docs = [{"path": "foo.md", "title": "Foo"}]

        async def mock_request(self, method, url, **kwargs):
            seen_cookies.append(self.cookies.get("stacklet-auth", ""))
            return MockHTTPXResponse(json.dumps(docs))

        monkeypatch.setattr("httpx.AsyncClient.request", mock_request)

        server = make_server(auth_provider=StubAuthProvider())
        async with Client(server) as client:
            await client.call_tool_mcp("docs_list", {})

        assert seen_cookies, "no HTTP requests were made"
        assert all(c == "custom-id-token" for c in seen_cookies)
